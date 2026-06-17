"""
trend.py — Multi-snapshot trend analysis for psiwatch.

Tracks how columns drift across a sequence of datasets over time —
e.g. one CSV snapshot per day/week — instead of a single A/B compare.

v0.12.0 fix: HTML trend report now escapes column names and source
labels before interpolating them into the page (same XSS fix as
reporter.py's to_html()).

Usage:
    psiwatch trend day1.csv day2.csv day3.csv day4.csv
    psiwatch trend day1.csv day2.csv day3.csv --baseline first
    psiwatch trend day1.csv day2.csv day3.csv --output trend.html
    psiwatch trend day1.csv day2.csv day3.csv --output trend.json

    # Python
    from psiwatch.trend import analyze_trend, print_trend, to_html_trend, output_trend
    result = analyze_trend(["day1.csv", "day2.csv", "day3.csv"])
    print(result["overall_health_history"])
    print(result["worsening_columns"])
    to_html_trend(result, filepath="trend.html")
"""

import json
import os
import html
from datetime import datetime

_SEVERITY_ORDER = {"PASS": 0, "MEDIUM": 1, "HIGH": 2, "UNKNOWN": 0}


def _label(source, index):
    if isinstance(source, str):
        return os.path.basename(source)
    try:
        import pandas as pd
        if isinstance(source, pd.DataFrame):
            return f"DataFrame[{index}]({len(source)} rows)"
    except ImportError:
        pass
    if isinstance(source, dict):
        return f"dict[{index}]"
    if isinstance(source, list):
        return f"list[{index}]"
    return f"data[{index}]"


def _is_worsening(severity_history):
    """True if severity monotonically increased first → last and never improved back."""
    if len(severity_history) < 2:
        return False
    nums = [_SEVERITY_ORDER.get(s, 0) for s in severity_history]
    return nums[-1] > nums[0] and nums == sorted(nums)


def analyze_trend(files, columns=None, ignore_columns=None,
                  psi_threshold=None, thresholds=None, baseline="previous"):
    """
    Run drift analysis across a sequence of datasets.

    Args:
        files: list of CSV paths, dicts, lists of dicts, or DataFrames.
               Must contain at least 2 items.
        columns: optional list — compare only these columns
        ignore_columns: optional list — skip these columns
        psi_threshold: optional PSI HIGH boundary (medium auto-scales to 40%)
        thresholds: optional dict of fine-grained threshold overrides
        baseline: "previous" (default) — compare each file to the one before it
                  "first" — compare every file back to files[0]

    Returns:
        dict:
            'files'                  — list of source labels
            'baseline_mode'          — "previous" | "first"
            'steps'                  — list of per-comparison results:
                                         {from, to, health_score, summary, columns}
            'overall_health_history' — [health_score, ...] one per step
            'column_history'         — {col: {severity_history, psi_history}}
            'worsening_columns'      — columns that monotonically degraded
            'generated_at'           — timestamp string
    """
    from .loader import resolve_input
    from .analyzer import analyze as _analyze
    from . import _build_thresholds

    if baseline not in ("previous", "first"):
        raise ValueError("baseline must be 'previous' or 'first'")
    if not isinstance(files, (list, tuple)) or len(files) < 2:
        raise ValueError("trend requires a list of at least 2 datasets")

    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    labels = [_label(f, i) for i, f in enumerate(files)]
    resolved = [resolve_input(f) for f in files]

    steps = []
    column_history = {}

    for i in range(1, len(resolved)):
        base_idx = 0 if baseline == "first" else i - 1
        result = _analyze(
            resolved[base_idx], resolved[i],
            columns=columns, ignore_columns=ignore_columns, thresholds=t,
        )

        step_columns = {}
        for col, r in result["columns"].items():
            step_columns[col] = {
                "severity": r["severity"],
                "psi": r["metrics"].get("psi"),
                "trend_direction": r["metrics"].get("trend_direction"),
            }
            column_history.setdefault(col, {"severity_history": [], "psi_history": []})

        steps.append({
            "from": labels[base_idx],
            "to": labels[i],
            "health_score": result["health_score"],
            "summary": result["summary"],
            "columns": step_columns,
        })

    # Populate column_history from steps
    for step in steps:
        for col, hist in column_history.items():
            entry = step["columns"].get(col)
            if entry:
                hist["severity_history"].append(entry["severity"])
                hist["psi_history"].append(entry["psi"])
            else:
                hist["severity_history"].append("UNKNOWN")
                hist["psi_history"].append(None)

    worsening = [
        col for col, hist in column_history.items()
        if _is_worsening(hist["severity_history"])
    ]

    return {
        "files": labels,
        "baseline_mode": baseline,
        "steps": steps,
        "overall_health_history": [s["health_score"] for s in steps],
        "column_history": column_history,
        "worsening_columns": sorted(worsening),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def print_trend(result):
    """Print a terminal summary of a trend result."""
    files = result["files"]
    steps = result["steps"]

    print("\n" + "═" * 62)
    print("  PSIWATCH TREND REPORT")
    print(f"  Files ({len(files)}): {' → '.join(files)}")
    print(f"  Baseline mode: {result['baseline_mode']}")
    print(f"  Generated: {result.get('generated_at', '')}")
    print("═" * 62)

    print("\n  Health Score Over Time:")
    for step in steps:
        health = step["health_score"]
        icon = "[OK] " if health >= 80 else "[~]  " if health >= 50 else "[!!] "
        filled = health // 10
        bar = "█" * filled + "░" * (10 - filled)
        print(f"    {step['from']} → {step['to']}")
        print(f"      {icon} {health:3d}/100  {bar}")

    print("\n  Column Drift Over Time:")
    for col, hist in sorted(result["column_history"].items()):
        sev_str = " → ".join(hist["severity_history"])
        psi_str = ", ".join(
            f"{p:.3f}" if p is not None else "—" for p in hist["psi_history"]
        )
        flag = "  ⚠ WORSENING" if col in result["worsening_columns"] else ""
        print(f"    {col}: {sev_str}{flag}")
        print(f"      PSI: {psi_str}")

    if result["worsening_columns"]:
        print(f"\n  ⚠  Steadily worsening: {', '.join(result['worsening_columns'])}")
    else:
        print("\n  No columns show a steadily worsening trend.")

    valid = result["overall_health_history"]
    if len(valid) >= 2:
        first, last = valid[0], valid[-1]
        delta = last - first
        print("\n  " + "─" * 60)
        if delta < -20:
            print(f"  ↓  Deteriorating  ({first} → {last}, Δ{delta})")
        elif delta > 20:
            print(f"  ↑  Improving  ({first} → {last}, Δ+{delta})")
        else:
            print(f"  →  Stable  ({first} → {last}, Δ{delta:+d})")

    print("═" * 62 + "\n")


def to_html_trend(result, filepath=None):
    """Render trend analysis as HTML with a Chart.js health score line chart."""
    steps = result["steps"]
    column_history = result["column_history"]
    generated_at = result.get("generated_at", "")
    files_label = " → ".join(html.escape(str(f)) for f in result["files"])
    baseline_mode = result["baseline_mode"]

    health_over_time = [s["health_score"] for s in steps]
    # json.dumps (not str()) so step labels are JS-string-safe — a label
    # containing a quote can't break out of the JS string. The
    # "</script" guard additionally prevents a label from closing the
    # surrounding <script> tag early and injecting raw HTML/script after it.
    step_labels = [f"{s['from']} → {s['to']}" for s in steps]
    labels_js = json.dumps(step_labels).replace("</script", "<\\/script")
    health_js = json.dumps(health_over_time)

    sev_colors = {
        "HIGH": "#ef4444", "MEDIUM": "#eab308",
        "PASS": "#22c55e", "UNKNOWN": "#94a3b8",
    }

    col_rows = ""
    for col, hist in sorted(column_history.items()):
        col_escaped = html.escape(str(col))
        flag = " ⚠" if col in result["worsening_columns"] else ""
        cells = "".join(
            f'<td style="background:{sev_colors.get(s,"#334155")};color:white;'
            f'text-align:center;padding:0.3rem 0.6rem;font-size:0.72rem;'
            f'font-weight:700;border-radius:4px;min-width:80px">{html.escape(str(s))}</td>'
            for s in hist["severity_history"]
        )
        psi_cells = "".join(
            f'<td style="text-align:center;color:#64748b;font-size:0.72rem">'
            f'{f"{p:.3f}" if p is not None else "—"}</td>'
            for p in hist["psi_history"]
        )
        col_rows += (
            f"<tr>"
            f'<td style="padding:0.4rem 0.75rem;color:#94a3b8;white-space:nowrap">'
            f"{col_escaped}{flag}</td>{cells}</tr>"
            f"<tr><td style='padding:0 0.75rem 0.5rem;color:#475569;font-size:0.7rem'>"
            f"PSI</td>{psi_cells}</tr>"
        )

    step_headers = "".join(
        f"<th style='padding:0.3rem 0.6rem;color:#64748b;font-size:0.72rem;"
        f"white-space:nowrap'>{html.escape(str(s['from'])[:10])}→{html.escape(str(s['to'])[:10])}</th>"
        for s in steps
    )

    worsening_html = ""
    if result["worsening_columns"]:
        worsening_cols_escaped = ", ".join(html.escape(str(c)) for c in result["worsening_columns"])
        worsening_html = (
            f'<div class="warn-block">⚠ Steadily worsening: '
            f'<b>{worsening_cols_escaped}</b></div>'
        )

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Psiwatch Trend Report</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Segoe UI',system-ui,sans-serif; background:#0f172a; color:#e2e8f0; padding:2rem; }}
  h1 {{ font-size:1.8rem; font-weight:700; color:#f8fafc; letter-spacing:0.05em; }}
  h1 span {{ color:#6366f1; }}
  .meta {{ color:#475569; margin-top:0.4rem; font-size:0.8rem; display:flex; gap:1.5rem; flex-wrap:wrap; }}
  .card {{ background:#1e293b; border-radius:12px; padding:1.5rem; margin-top:1.5rem; }}
  .card-title {{ font-size:0.8rem; color:#64748b; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:1rem; }}
  canvas {{ max-height:280px; }}
  table {{ width:100%; border-collapse:separate; border-spacing:0 0.1rem; margin-top:0.5rem; }}
  th {{ text-align:left; padding:0.3rem 0.75rem; color:#64748b; font-size:0.72rem; border-bottom:1px solid #334155; }}
  .warn-block {{ background:#1c1009; border:1px solid #78350f; border-radius:8px;
                  padding:0.6rem 1rem; margin-top:1rem; font-size:0.82rem; color:#fbbf24; }}
  footer {{ margin-top:2rem; text-align:center; color:#334155; font-size:0.75rem; }}
</style>
</head>
<body>
<h1>PSI<span>WATCH</span> TREND</h1>
<div class="meta">
  <span>Files: {files_label}</span>
  <span>Baseline: {baseline_mode}</span>
  <span>Generated: {html.escape(str(generated_at))}</span>
</div>

{worsening_html}

<div class="card">
  <div class="card-title">Health Score Over Time</div>
  <canvas id="healthChart"></canvas>
</div>

<div class="card">
  <div class="card-title">Per-Column Severity &amp; PSI Over Time</div>
  <table>
    <thead><tr><th>Column</th>{step_headers}</tr></thead>
    <tbody>{col_rows}</tbody>
  </table>
</div>

<footer>Generated by psiwatch · github.com/tharunstryker/psiwatch</footer>

<script>
const ctx = document.getElementById('healthChart').getContext('2d');
new Chart(ctx, {{
  type: 'line',
  data: {{
    labels: {labels_js},
    datasets: [{{
      label: 'Health Score',
      data: {health_js},
      borderColor: '#6366f1',
      backgroundColor: 'rgba(99,102,241,0.08)',
      borderWidth: 2.5,
      pointBackgroundColor: {health_js}.map(h =>
        h >= 80 ? '#22c55e' : h >= 50 ? '#eab308' : '#ef4444'
      ),
      pointRadius: 7,
      tension: 0.35,
      fill: true,
    }}]
  }},
  options: {{
    responsive: true,
    scales: {{
      y: {{ min:0, max:100,
             grid:{{color:'#1e293b'}},
             ticks:{{color:'#64748b', callback: v => v+'/100'}} }},
      x: {{ grid:{{color:'#1e293b'}}, ticks:{{color:'#64748b'}} }}
    }},
    plugins: {{
      legend: {{labels:{{color:'#94a3b8'}}}},
      tooltip: {{callbacks:{{label: ctx => `Health: ${{ctx.raw}}/100`}}}}
    }}
  }}
}});
</script>
</body>
</html>"""

    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_out)
        print(f"  Trend report saved → {filepath}")
    else:
        print(html_out)
    return html_out


def output_trend(result, output=None):
    """Print to terminal. Optionally write JSON or HTML to file."""
    if output:
        if output.endswith(".html"):
            to_html_trend(result, filepath=output)
            return
        if output.endswith(".json"):
            with open(output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            print(f"  Trend report saved → {output}")
            return
    print_trend(result)
    if output:
        print("  (Use --output report.html or report.json for file output)")
