"""
reporter.py — Handles all output formats for psiwatch.
Supports: terminal print, .json, .txt, .html
"""

import json
import os


ICONS = {'HIGH': '[!!]', 'MEDIUM': '[~]', 'PASS': '[OK]', 'UNKNOWN': '[?]'}
LABELS = {'HIGH': 'HIGH DRIFT', 'MEDIUM': 'MODERATE DRIFT', 'PASS': 'STABLE', 'UNKNOWN': 'UNKNOWN'}


def _health_label(score):
    if score >= 80:
        return ('[OK]', 'Healthy')
    elif score >= 50:
        return ('[~]', 'Moderate Drift')
    else:
        return ('[!!]', 'Significant Drift')


# ─── Terminal ─────────────────────────────────────────────────────────────────

def print_report(analysis):
    columns = analysis['columns']
    health = analysis['health_score']
    icon, label = _health_label(health)

    print("\n" + "═" * 56)
    print("  PSIWATCH REPORT")
    print("═" * 56)

    for col, result in columns.items():
        sev = result['severity']
        print(f"\n  {ICONS[sev]} {col}  [{result['type']}]  — {LABELS[sev]}")
        if result.get('reasons'):
            for reason in result['reasons']:
                print(f"     → {reason}")
        else:
            print(f"     → No drift detected")

        m = result.get('metrics', {})
        if result['type'] == 'numeric' and m:
            print(f"     ┌ Mean:   {m.get('baseline_mean','—')} → {m.get('new_mean','—')}")
            print(f"     ├ Std:    {m.get('baseline_std','—')} → {m.get('new_std','—')}")
            print(f"     └ PSI:    {m.get('psi','—')}")
        elif result['type'] == 'categorical' and m:
            print(f"     ┌ PSI:         {m.get('psi','—')}")
            print(f"     ├ Chi-square:  {m.get('chi_square','—')}")
            print(f"     └ New cats:    {m.get('new_categories') or 'None'}")

    counts = {s: 0 for s in ['HIGH', 'MEDIUM', 'PASS', 'UNKNOWN']}
    for r in columns.values():
        counts[r['severity']] += 1

    print("\n" + "─" * 56)
    print(f"  HIGH: {counts['HIGH']}   MEDIUM: {counts['MEDIUM']}   PASS: {counts['PASS']}")
    print(f"\n  {icon} Drift Health Score: {health}/100  ({label})")
    print("═" * 56 + "\n")


# ─── JSON ─────────────────────────────────────────────────────────────────────

def to_json(analysis, filepath=None):
    output = json.dumps(analysis, indent=2)
    if filepath:
        with open(filepath, 'w') as f:
            f.write(output)
        print(f"Report saved → {filepath}")
    else:
        print(output)
    return output


# ─── TXT ──────────────────────────────────────────────────────────────────────

def to_txt(analysis, filepath=None):
    columns = analysis['columns']
    health = analysis['health_score']
    icon, label = _health_label(health)

    lines = []
    lines.append("=" * 56)
    lines.append("PSIWATCH REPORT")
    lines.append("=" * 56)

    for col, result in columns.items():
        sev = result['severity']
        lines.append(f"\n[{sev}] {col} ({result['type']})")
        if result.get('reasons'):
            for reason in result['reasons']:
                lines.append(f"  -> {reason}")
        else:
            lines.append("  -> No drift detected")

        m = result.get('metrics', {})
        if result['type'] == 'numeric' and m:
            lines.append(f"  Mean: {m.get('baseline_mean')} -> {m.get('new_mean')}")
            lines.append(f"  PSI:  {m.get('psi')}")

    counts = {s: 0 for s in ['HIGH', 'MEDIUM', 'PASS']}
    for r in columns.values():
        if r['severity'] in counts:
            counts[r['severity']] += 1

    lines.append("\n" + "-" * 56)
    lines.append(f"HIGH: {counts['HIGH']}  MEDIUM: {counts['MEDIUM']}  PASS: {counts['PASS']}")
    lines.append(f"Drift Health Score: {health}/100 ({label})")
    lines.append("=" * 56)

    output = "\n".join(lines)

    if filepath:
        with open(filepath, 'w') as f:
            f.write(output)
        print(f"Report saved → {filepath}")
    else:
        print(output)

    return output


# ─── HTML ─────────────────────────────────────────────────────────────────────

def to_html(analysis, filepath=None):
    columns = analysis['columns']
    health = analysis['health_score']
    _, label = _health_label(health)

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

    rows_html = ""
    for col, result in columns.items():
        sev = result['severity']
        color = sev_colors[sev]
        reasons = "<br>".join(result.get('reasons', ['No drift detected'])) or "No drift detected"

        m = result.get('metrics', {})
        if result['type'] == 'numeric':
            metrics_html = f"""
            <div class="metrics">
              <span>Mean: <b>{m.get('baseline_mean','—')} → {m.get('new_mean','—')}</b></span>
              <span>Std: <b>{m.get('baseline_std','—')} → {m.get('new_std','—')}</b></span>
              <span>PSI: <b>{m.get('psi','—')}</b></span>
              <span>Median: <b>{m.get('baseline_median','—')} → {m.get('new_median','—')}</b></span>
            </div>"""
        else:
            metrics_html = f"""
            <div class="metrics">
              <span>PSI: <b>{m.get('psi','—')}</b></span>
              <span>Chi²: <b>{m.get('chi_square','—')}</b></span>
              <span>New categories: <b>{', '.join(m.get('new_categories', [])) or 'None'}</b></span>
            </div>"""

        rows_html += f"""
        <div class="col-card">
          <div class="col-header">
            <span class="col-name">{col}</span>
            <span class="col-type">{result['type']}</span>
            <span class="badge" style="background:{color}">{sev}</span>
          </div>
          <div class="reasons">{reasons}</div>
          {metrics_html}
        </div>"""

    counts = {s: 0 for s in ['HIGH', 'MEDIUM', 'PASS']}
    for r in columns.values():
        if r['severity'] in counts:
            counts[r['severity']] += 1

    html = f"""<!DOCTYPE html>
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
  .subtitle {{ color: #64748b; margin-top: 0.3rem; font-size: 0.9rem; }}
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
  .bar-fill {{ background: {bar_color}; height: 8px; border-radius: 99px; width: {health}%; transition: width 1s; }}
  .col-card {{
    background: #1e293b;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    border-left: 4px solid {health_color};
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
  .metrics {{ display: flex; flex-wrap: wrap; gap: 0.75rem; }}
  .metrics span {{ font-size: 0.78rem; background: #0f172a; padding: 0.3rem 0.7rem; border-radius: 6px; color: #94a3b8; }}
  .metrics b {{ color: #e2e8f0; }}
  footer {{ margin-top: 2rem; text-align: center; color: #334155; font-size: 0.75rem; }}
</style>
</head>
<body>
<header>
  <h1>DRIFT<span>WATCH</span> REPORT</h1>
  <p class="subtitle">Dataset drift analysis — generated by psiwatch</p>
</header>

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

{rows_html}

<footer>Generated by psiwatch · github.com/tharunstryker/psiwatch</footer>
</body>
</html>"""

    if filepath:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"Report saved → {filepath}")
    else:
        print(html)

    return html


# ─── Router ───────────────────────────────────────────────────────────────────

def output_report(analysis, output=None):
    """
    Route to the correct output format.
    output=None → terminal
    output='report.json' → JSON file
    output='report.txt' → TXT file
    output='report.html' → HTML file
    """
    if output is None:
        print_report(analysis)
        return

    ext = os.path.splitext(output)[1].lower()

    if ext == '.json':
        to_json(analysis, output)
    elif ext == '.txt':
        to_txt(analysis, output)
    elif ext == '.html':
        to_html(analysis, output)
    else:
        raise ValueError(f"Unsupported output format: {ext}. Use .json, .txt, or .html")
