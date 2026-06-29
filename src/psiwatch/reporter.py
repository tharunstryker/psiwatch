"""
reporter.py — Handles all output formats for psiwatch.
Supports: terminal print, .json, .txt, .html

FIX: HTML report now includes timestamp + source file names.
FIX: Warnings (dropped columns, mixed-type columns) shown in all output formats.

v0.12.0 fix: all user-derived strings (column names, category values,
reasons, warnings, source labels) are now HTML-escaped before being
interpolated into the HTML report. Previously a column name or category
value like "<script>...</script>" in the source CSV would execute when
the generated report was opened in a browser.
"""

import json
import os
import html
from datetime import datetime


ICONS = {'HIGH': '[!!]', 'MEDIUM': '[~]', 'PASS': '[OK]', 'UNKNOWN': '[?]'}
LABELS = {'HIGH': 'HIGH DRIFT', 'MEDIUM': 'MODERATE DRIFT', 'PASS': 'STABLE', 'UNKNOWN': 'UNKNOWN'}


def _health_label(score):
    if score >= 80:
        return ('[OK]', 'Healthy')
    elif score >= 50:
        return ('[~]', 'Moderate Drift')
    else:
        return ('[!!]', 'Significant Drift')


def _fmt(v, decimals=4):
    if v is None or v == '':
        return '—'
    try:
        return f"{float(v):.{decimals}f}"
    except (TypeError, ValueError):
        return str(v)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─── Terminal ─────────────────────────────────────────────────────────────────

def print_report(analysis, source_info=None):
    columns = analysis['columns']
    health = analysis['health_score']
    icon, label = _health_label(health)
    warnings = analysis.get('warnings', [])

    print("\n" + "═" * 62)
    print("  PSIWATCH REPORT")
    if source_info:
        print(f"  {source_info}")
    print(f"  Generated: {_now()}")
    print("═" * 62)

    # Warnings block
    if warnings:
        print("\n  [WARN]")
        for w in warnings:
            print(f"     ⚠  {w}")

    for col, result in columns.items():
        sev = result['severity']
        print(f"\n  {ICONS[sev]} {col}  [{result['type']}]  — {LABELS[sev]}")

        # Column-level warnings
        for w in result.get('warnings', []):
            print(f"     ⚠  {w}")

        if result.get('reasons'):
            for reason in result['reasons']:
                print(f"     → {reason}")
        else:
            print(f"     → No drift detected")

        m = result.get('metrics', {})
        if result['type'] == 'numeric' and m:
            print(f"     ┌ Mean:    {_fmt(m.get('baseline_mean'),2)} → {_fmt(m.get('new_mean'),2)}")
            print(f"     ├ Std:     {_fmt(m.get('baseline_std'),2)} → {_fmt(m.get('new_std'),2)}")
            print(f"     ├ PSI:     {_fmt(m.get('psi'),4)}")
            print(f"     ├ Min:     {_fmt(m.get('baseline_min'),2)} → {_fmt(m.get('new_min'),2)}")
            print(f"     ├ P25:     {_fmt(m.get('baseline_p25'),2)} → {_fmt(m.get('new_p25'),2)}")
            print(f"     ├ Median:  {_fmt(m.get('baseline_median'),2)} → {_fmt(m.get('new_median'),2)}")
            print(f"     ├ P75:     {_fmt(m.get('baseline_p75'),2)} → {_fmt(m.get('new_p75'),2)}")
            print(f"     └ Max:     {_fmt(m.get('baseline_max'),2)} → {_fmt(m.get('new_max'),2)}")
        elif result['type'] == 'categorical' and m:
            print(f"     ┌ PSI:         {_fmt(m.get('psi'),4)}")
            print(f"     ├ Chi-square:  {_fmt(m.get('chi_square'),4)}")
            print(f"     └ New cats:    {m.get('new_categories') or 'None'}")

    counts = {s: 0 for s in ['HIGH', 'MEDIUM', 'PASS', 'UNKNOWN']}
    for r in columns.values():
        counts[r['severity']] += 1

    print("\n" + "─" * 62)
    print(f"  HIGH: {counts['HIGH']}   MEDIUM: {counts['MEDIUM']}   PASS: {counts['PASS']}")
    print(f"\n  {icon} Drift Health Score: {health}/100  ({label})")
    print("═" * 62 + "\n")


# ─── JSON ─────────────────────────────────────────────────────────────────────

def to_json(analysis, filepath=None, silent=False):
    enriched = {**analysis, 'generated_at': _now()}
    output = json.dumps(enriched, indent=2)
    if filepath:
        with open(filepath, 'w') as f:
            f.write(output)
        if not silent:
            print(f"Report saved → {filepath}")
    else:
        print(output)
    return output


# ─── TXT ──────────────────────────────────────────────────────────────────────

def to_txt(analysis, filepath=None, source_info=None, silent=False):
    columns = analysis['columns']
    health = analysis['health_score']
    icon, label = _health_label(health)
    warnings = analysis.get('warnings', [])

    lines = []
    lines.append("=" * 62)
    lines.append("PSIWATCH REPORT")
    if source_info:
        lines.append(source_info)
    lines.append(f"Generated: {_now()}")
    lines.append("=" * 62)

    if warnings:
        lines.append("\nWARNINGS:")
        for w in warnings:
            lines.append(f"  ! {w}")

    for col, result in columns.items():
        sev = result['severity']
        lines.append(f"\n[{sev}] {col} ({result['type']})")
        for w in result.get('warnings', []):
            lines.append(f"  ! {w}")
        if result.get('reasons'):
            for reason in result['reasons']:
                lines.append(f"  -> {reason}")
        else:
            lines.append("  -> No drift detected")

        m = result.get('metrics', {})
        if result['type'] == 'numeric' and m:
            lines.append(f"  Mean:    {_fmt(m.get('baseline_mean'),2)} -> {_fmt(m.get('new_mean'),2)}")
            lines.append(f"  Std:     {_fmt(m.get('baseline_std'),2)} -> {_fmt(m.get('new_std'),2)}")
            lines.append(f"  PSI:     {_fmt(m.get('psi'),4)}")
            lines.append(f"  Min:     {_fmt(m.get('baseline_min'),2)} -> {_fmt(m.get('new_min'),2)}")
            lines.append(f"  P25:     {_fmt(m.get('baseline_p25'),2)} -> {_fmt(m.get('new_p25'),2)}")
            lines.append(f"  Median:  {_fmt(m.get('baseline_median'),2)} -> {_fmt(m.get('new_median'),2)}")
            lines.append(f"  P75:     {_fmt(m.get('baseline_p75'),2)} -> {_fmt(m.get('new_p75'),2)}")
            lines.append(f"  Max:     {_fmt(m.get('baseline_max'),2)} -> {_fmt(m.get('new_max'),2)}")

    counts = {s: 0 for s in ['HIGH', 'MEDIUM', 'PASS']}
    for r in columns.values():
        if r['severity'] in counts:
            counts[r['severity']] += 1

    lines.append("\n" + "-" * 62)
    lines.append(f"HIGH: {counts['HIGH']}  MEDIUM: {counts['MEDIUM']}  PASS: {counts['PASS']}")
    lines.append(f"Drift Health Score: {health}/100 ({label})")
    lines.append("=" * 62)

    output = "\n".join(lines)
    if filepath:
        with open(filepath, 'w') as f:
            f.write(output)
        if not silent:
            print(f"Report saved → {filepath}")
    else:
        print(output)
    return output


# ─── HTML ─────────────────────────────────────────────────────────────────────

def to_html(analysis, filepath=None, source_info=None, silent=False, embed_chart=None):
    columns = analysis['columns']
    health = analysis['health_score']
    _, label = _health_label(health)
    warnings = analysis.get('warnings', [])
    timestamp = _now()

    if health >= 80:
        health_color = "#22c55e"
        bar_color = "#22c55e"
    elif health >= 50:
        health_color = "#eab308"
        bar_color = "#eab308"
    else:
        health_color = "#ef4444"
        bar_color = "#ef4444"

    sev_colors = {
        'HIGH': '#ef4444',
        'MEDIUM': '#eab308',
        'PASS': '#22c55e',
        'UNKNOWN': '#94a3b8'
    }

    # Warnings block HTML
    warnings_html = ""
    all_warnings = list(warnings)
    for r in columns.values():
        all_warnings.extend(r.get('warnings', []))
    if all_warnings:
        warn_items = "".join(f"<li>⚠ {html.escape(str(w))}</li>" for w in all_warnings)
        warnings_html = f'<div class="warn-block"><ul>{warn_items}</ul></div>'

    # Optional embedded chart (base64 PNG — no separate file to track)
    chart_html = ""
    if embed_chart:
        import base64
        b64 = base64.b64encode(embed_chart).decode("ascii")
        chart_html = (
            '<div class="chart-block">'
            f'<img src="data:image/png;base64,{b64}" alt="Baseline vs new distribution chart" '
            'style="max-width:100%;border-radius:10px;background:#fff;padding:0.5rem;"/>'
            '</div>'
        )

    rows_html = ""
    for col, result in columns.items():
        sev = result['severity']
        color = sev_colors[sev]
        reason_list = result.get('reasons', ['No drift detected'])
        reasons = "<br>".join(html.escape(str(r)) for r in reason_list) or "No drift detected"

        m = result.get('metrics', {})
        if result['type'] == 'numeric':
            stats_rows = [
                ("Mean",   m.get('baseline_mean'), m.get('new_mean')),
                ("Std",    m.get('baseline_std'),  m.get('new_std')),
                ("Min",    m.get('baseline_min'),  m.get('new_min')),
                ("P25",    m.get('baseline_p25'),  m.get('new_p25')),
                ("Median", m.get('baseline_median'), m.get('new_median')),
                ("P75",    m.get('baseline_p75'),  m.get('new_p75')),
                ("Max",    m.get('baseline_max'),  m.get('new_max')),
            ]
            table_rows = "".join(
                f"<tr><td>{lbl}</td><td>{_fmt(b,2)}</td><td>{_fmt(n,2)}</td></tr>"
                for lbl, b, n in stats_rows
            )
            metrics_html = f"""
            <div class="stats-wrap">
              <div class="psi-chip">PSI <b>{_fmt(m.get('psi'),4)}</b></div>
              <table class="stats-table">
                <thead><tr><th>Stat</th><th>Baseline</th><th>New</th></tr></thead>
                <tbody>{table_rows}</tbody>
              </table>
            </div>"""
        else:
            new_cats_escaped = ', '.join(html.escape(str(c)) for c in m.get('new_categories', [])) or 'None'
            metrics_html = f"""
            <div class="metrics">
              <span>PSI: <b>{_fmt(m.get('psi'),4)}</b></span>
              <span>Chi²: <b>{_fmt(m.get('chi_square'),4)}</b></span>
              <span>New categories: <b>{new_cats_escaped}</b></span>
            </div>"""

        rows_html += f"""
        <div class="col-card" style="border-left-color:{color}">
          <div class="col-header">
            <span class="col-name">{html.escape(str(col))}</span>
            <span class="col-type">{html.escape(str(result['type']))}</span>
            <span class="badge" style="background:{color}">{sev}</span>
          </div>
          <div class="reasons">{reasons}</div>
          {metrics_html}
        </div>"""

    counts = {s: 0 for s in ['HIGH', 'MEDIUM', 'PASS']}
    for r in columns.values():
        if r['severity'] in counts:
            counts[r['severity']] += 1

    # FIX: timestamp + source in HTML
    meta_line = f'<span class="meta-item">Generated: {html.escape(timestamp)}</span>'
    if source_info:
        meta_line += f'<span class="meta-item">{html.escape(str(source_info))}</span>'

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Psiwatch Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    padding: 2rem;
    min-height: 100vh;
  }}
  header {{
    border-bottom: 1px solid #1e293b;
    padding-bottom: 1.5rem;
    margin-bottom: 2rem;
  }}
  h1 {{
    font-size: 1.8rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: #f8fafc;
  }}
  h1 span {{ color: {health_color}; }}
  .meta {{ color: #475569; margin-top: 0.4rem; font-size: 0.8rem; display: flex; gap: 1.5rem; flex-wrap: wrap; }}
  .meta-item::before {{ content: '◆ '; font-size: 0.6rem; vertical-align: middle; }}
  .warn-block {{
    background: #292219;
    border: 1px solid #78350f;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 1.5rem;
    font-size: 0.82rem;
    color: #fbbf24;
  }}
  .warn-block ul {{ list-style: none; display: flex; flex-direction: column; gap: 0.25rem; }}
  .summary {{
    display: flex;
    gap: 1.5rem;
    margin-bottom: 2rem;
    flex-wrap: wrap;
  }}
  .stat {{
    background: #1e293b;
    border-radius: 10px;
    padding: 1rem 1.5rem;
    min-width: 120px;
    text-align: center;
  }}
  .stat .num {{ font-size: 2rem; font-weight: 700; }}
  .stat .lbl {{ font-size: 0.75rem; color: #64748b; margin-top: 0.2rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .health-bar-wrap {{
    background: #1e293b;
    border-radius: 10px;
    padding: 1.2rem 1.5rem;
    flex: 1;
    min-width: 200px;
  }}
  .health-label {{ font-size: 0.8rem; color: #64748b; margin-bottom: 0.5rem; }}
  .health-score {{ font-size: 1.5rem; font-weight: 700; color: {health_color}; }}
  .bar-bg {{ background: #0f172a; border-radius: 99px; height: 8px; margin-top: 0.5rem; }}
  .bar-fill {{ background: {bar_color}; height: 8px; border-radius: 99px; width: {health}%; }}
  .col-card {{
    background: #1e293b;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    border-left: 4px solid #334155;
  }}
  .col-header {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.6rem;
  }}
  .col-name {{ font-weight: 700; font-size: 1rem; }}
  .col-type {{ font-size: 0.75rem; color: #64748b; background: #0f172a; padding: 0.2rem 0.5rem; border-radius: 4px; }}
  .badge {{ font-size: 0.7rem; font-weight: 700; padding: 0.25rem 0.6rem; border-radius: 99px; color: white; margin-left: auto; }}
  .reasons {{ font-size: 0.85rem; color: #94a3b8; line-height: 1.6; margin-bottom: 0.75rem; }}
  .stats-wrap {{ display: flex; align-items: flex-start; gap: 1rem; flex-wrap: wrap; }}
  .psi-chip {{
    background: #0f172a;
    border-radius: 8px;
    padding: 0.5rem 0.9rem;
    font-size: 0.78rem;
    color: #94a3b8;
    white-space: nowrap;
    align-self: center;
  }}
  .psi-chip b {{ color: #e2e8f0; }}
  .stats-table {{
    font-size: 0.78rem;
    border-collapse: collapse;
  }}
  .stats-table th, .stats-table td {{
    padding: 0.2rem 0.75rem;
    text-align: right;
    color: #94a3b8;
  }}
  .stats-table th {{ color: #64748b; font-weight: 600; border-bottom: 1px solid #334155; }}
  .stats-table td:first-child {{ text-align: left; color: #64748b; }}
  .metrics {{ display: flex; flex-wrap: wrap; gap: 0.75rem; }}
  .metrics span {{ font-size: 0.78rem; background: #0f172a; padding: 0.3rem 0.7rem; border-radius: 6px; color: #94a3b8; }}
  .metrics b {{ color: #e2e8f0; }}
  footer {{ margin-top: 2rem; text-align: center; color: #334155; font-size: 0.75rem; }}
</style>
</head>
<body>
<header>
  <h1>DRIFT<span>WATCH</span> REPORT</h1>
  <div class="meta">{meta_line}</div>
</header>

{warnings_html}

<div class="summary">
  <div class="stat"><div class="num" style="color:#ef4444">{counts['HIGH']}</div><div class="lbl">High Drift</div></div>
  <div class="stat"><div class="num" style="color:#eab308">{counts['MEDIUM']}</div><div class="lbl">Moderate</div></div>
  <div class="stat"><div class="num" style="color:#22c55e">{counts['PASS']}</div><div class="lbl">Stable</div></div>
  <div class="health-bar-wrap">
    <div class="health-label">DRIFT HEALTH SCORE</div>
    <div class="health-score">{health}/100 — {label}</div>
    <div class="bar-bg"><div class="bar-fill"></div></div>
  </div>
</div>

{chart_html}

{rows_html}

<footer>Generated by psiwatch · github.com/tharunstryker/psiwatch</footer>
</body>
</html>"""

    if filepath:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_out)
        print(f"Report saved → {filepath}")
    else:
        print(html_out)
    return html_out


# ─── Router ───────────────────────────────────────────────────────────────────

def output_report(analysis, output=None, source_info=None, silent=False, embed_chart=None):
    if output is None:
        print_report(analysis, source_info=source_info)
        return

    ext = os.path.splitext(output)[1].lower()

    if ext == '.json':
        to_json(analysis, output, silent=silent)
    elif ext == '.txt':
        to_txt(analysis, output, source_info=source_info, silent=silent)
    elif ext == '.html':
        to_html(analysis, output, source_info=source_info, silent=silent, embed_chart=embed_chart)
    else:
        raise ValueError(f"Unsupported output format: {ext}. Use .json, .txt, or .html")
