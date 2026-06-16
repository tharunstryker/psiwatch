# psiwatch

**Zero-dependency Python library for dataset drift detection in ML pipelines.**

Detect covariate drift, distribution shift, and data quality degradation between two datasets — using PSI, Chi-Square, Mean Shift, and Standard Deviation analysis. Pure Python. No numpy. No scipy. No pandas required.

![PyPI](https://img.shields.io/pypi/v/psiwatch)
![Downloads](https://img.shields.io/pypi/dm/psiwatch)
![License](https://img.shields.io/badge/license-MIT-7C3AED)
![Python](https://img.shields.io/badge/python-3.8+-blue)
![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-22c55e)

---

## The Problem

You train a model on historical data. Weeks later, predictions go wrong — silently. No errors. No alerts.

The cause is **data drift**. Production data no longer looks like training data:

- Customer ages shifted
- New cities or categories appeared
- Salary distributions changed
- Credit scores dropped

Most teams discover this *after* the model has already failed.

---

## The Solution

```bash
pip install psiwatch
psiwatch compare train.csv production.csv
```

```
══════════════════════════════════════════════════════════════
  PSIWATCH REPORT
  baseline: train.csv  →  new: production.csv
  Generated: 2026-06-14 09:00:00
══════════════════════════════════════════════════════════════

  [!!] credit_score  [numeric]  — HIGH DRIFT
     → Mean shifted by 2.20 std devs (752.00 → 624.00)  ↓
     → PSI = 11.1200 (significant drift)
     ┌ Mean:    752.00 → 624.00  ↓
     ├ Std:     48.00 → 71.00
     ├ PSI:     11.1200
     ├ Min:     600.00 → 420.00
     ├ P25:     720.00 → 560.00
     ├ Median:  750.00 → 620.00
     ├ P75:     790.00 → 690.00
     └ Max:     850.00 → 800.00

  [!!] loan_type  [categorical]  — HIGH DRIFT
     → New categories found: ['BNPL', 'Crypto']
     → Categories vanished from new data: ['Personal']
     → PSI = 4.1900
     ┌ PSI:          4.1900
     ├ Chi-square:   3.8200
     ├ New cats:     ['BNPL', 'Crypto']
     └ Vanished:     ['Personal']

  [OK] customer_id  [categorical]  — STABLE
     → No drift detected

──────────────────────────────────────────────────────────────
  HIGH: 2   MEDIUM: 0   PASS: 1

  [!!] Drift Health Score: 11/100  (Significant Drift)
══════════════════════════════════════════════════════════════
```

---

## Why psiwatch?

Most drift detection tools require heavy dependencies and are built for Jupyter notebooks — not pipelines or minimal environments.

| Feature | psiwatch | evidently | alibi-detect |
|---|---|---|---|
| Dependencies | **Zero** | Heavy | Heavy |
| Install size | **~15KB** | ~50MB+ | ~100MB+ |
| Works on Termux/Android | **Yes** | No | No |
| CLI tool | **Yes** | No | No |
| CI/CD `--fail-on-drift` flag | **Yes** | No | No |
| Self-upgrade via CLI | **Yes** | No | No |
| pandas DataFrame support | **Yes** | Yes | Yes |
| Pure Python | **Yes** | No | No |
| Auto update check | **Yes** | No | No |
| HTML reports | **Yes** | Yes | No |
| Trend direction (↑↓→) | **Yes** | No | No |
| Vanished category detection | **Yes** | No | No |

---

## Install

```bash
pip install psiwatch
```

Works on Windows, Mac, Linux, VPS, Google Colab, Jupyter, and Termux on Android.

### Upgrade

```bash
# via CLI (easiest)
psiwatch update

# or standard pip
pip install --upgrade psiwatch
```

---

## Quickstart

```bash
git clone https://github.com/tharunstryker/psiwatch
cd psiwatch
pip install -e .
psiwatch compare samples/train.csv samples/new.csv
```

---

## CLI

```bash
# Compare two CSV files
psiwatch compare old.csv new.csv

# Save as HTML report
psiwatch compare old.csv new.csv --output report.html

# Save as JSON for pipelines
psiwatch compare old.csv new.csv --output report.json

# Save as plain text
psiwatch compare old.csv new.csv --output report.txt

# Compare specific columns only
psiwatch compare old.csv new.csv --columns age,score,city

# Skip columns (IDs, timestamps, row numbers)
psiwatch compare old.csv new.csv --ignore-columns id,timestamp,row_num

# Set custom PSI threshold
psiwatch compare old.csv new.csv --psi-threshold 0.15

# Fail with exit code 1 if drift detected (for CI/CD)
psiwatch compare old.csv new.csv --fail-on-drift

# Suppress update banner (useful in scripts)
psiwatch compare old.csv new.csv --silent

# Send a Slack/Discord/webhook alert on drift
psiwatch compare old.csv new.csv --webhook https://hooks.slack.com/services/XXX/YYY/ZZZ

# Use a config file instead of passing flags every time
psiwatch compare old.csv new.csv --config myconfig.toml

# One-line health summary (no full report — ideal for shell scripts)
psiwatch summary train.csv new.csv

# Lock training data as a statistical baseline
psiwatch lock train.csv                          # creates psiwatch.lock.json
psiwatch lock train.csv --output model.lock.json

# Check new data against the lock
psiwatch check new.csv
psiwatch check new.csv --lock model.lock.json --fail-on-drift

# Show what's stored in a lock file
psiwatch lock-info

# Track drift across a sequence of datasets over time
psiwatch trend day1.csv day2.csv day3.csv day4.csv
psiwatch trend day1.csv day2.csv day3.csv --baseline first
psiwatch trend day1.csv day2.csv day3.csv --output trend.json

# Watch a directory and check new CSV files as they arrive
psiwatch watch data/
psiwatch watch data/ --once               # one pass, exit — good for cron and CI
psiwatch watch data/ --webhook https://hooks.slack.com/services/XXX --fail-on-drift

# Upgrade to latest version
psiwatch update

# Show installed version
psiwatch version
```

---

## Python Library

### CSV files

```python
import psiwatch

psiwatch.compare("old.csv", "new.csv")
psiwatch.compare("old.csv", "new.csv", output="report.html")
psiwatch.compare("old.csv", "new.csv", columns=["age", "score"])
```

### pandas DataFrames

```python
import pandas as pd
import psiwatch

old_df = pd.read_csv("train.csv")
new_df = pd.read_csv("production.csv")

psiwatch.compare(old_df, new_df)
psiwatch.compare(old_df, new_df, output="report.html")
```

pandas is **optional** — psiwatch works without it. Only imported when a DataFrame is passed.

### Python dicts

```python
psiwatch.compare_data(
    old={"age": [22, 23, 21], "city": ["Chennai", "Delhi", "Mumbai"]},
    new={"age": [28, 30, 29], "city": ["Chennai", "Bangalore", "Hyderabad"]}
)
```

### List of dicts (JSON records)

```python
old_records = [{"age": 22, "city": "Chennai"}, {"age": 23, "city": "Delhi"}]
new_records = [{"age": 28, "city": "Mumbai"}, {"age": 30, "city": "Pune"}]

psiwatch.compare(old_records, new_records)
```

### Single list (one column)

```python
psiwatch.compare_columns([22, 23, 21], [28, 30, 29], name="age")
```

### Raw results (no print)

```python
result = psiwatch.analyze("old.csv", "new.csv")

print(result["health_score"])         # 0-100

for col, data in result["columns"].items():
    print(col, data["severity"])      # HIGH / MEDIUM / PASS
    print(col, data["metrics"])       # PSI, mean, std, chi-square, percentiles, trend_direction
    print(col, data.get("warnings"))  # mixed-type or schema warnings
```

---

## CI/CD — Fail on Drift

Block deployments when data drifts. psiwatch exits with code 1 if `health_score < 80`.

### GitHub Actions

```yaml
- name: Check data drift
  run: psiwatch compare train.csv production.csv --fail-on-drift
```

### Python

```python
import psiwatch
from psiwatch import DriftDetected

try:
    psiwatch.compare("train.csv", "new.csv", fail_on_drift=True)
except DriftDetected as e:
    print(f"Drift detected: {e}")
    # send alert, stop deploy, log to monitoring
```

---

## Self-Upgrade

```bash
psiwatch update
```

Runs `pip install --upgrade psiwatch` under the hood — same Python environment, no extra steps. Works on Termux too.

---

## Custom Thresholds

```python
# Shortcut — set HIGH boundary, medium auto-scales to 40%
psiwatch.compare("old.csv", "new.csv", psi_threshold=0.15)

# Full control
psiwatch.compare("old.csv", "new.csv", thresholds={
    "psi_medium": 0.05,
    "psi_high": 0.15,
    "mean_shift_medium": 0.2,
    "mean_shift_high": 0.5,
    "std_shift_medium": 0.2,
    "std_shift_high": 0.5,
    "category_share_shift": 0.10,
    "chi_square_medium": 0.5,
})
```

---

## Auto Update Check

psiwatch checks PyPI for newer versions on every run. Check is cached for 24 hours — won't spam on every import. Automatically silent in CI environments (`CI=true`, `GITHUB_ACTIONS=true`, `PSIWATCH_SILENT=1`).

```
  ╔════════════════════════════════════════════════════╗
  ║  psiwatch update available: 0.9.0 → 0.10.0        ║
  ║  Run: pip install --upgrade psiwatch               ║
  ╚════════════════════════════════════════════════════╝
```

To suppress manually:

```python
import psiwatch
psiwatch.compare("old.csv", "new.csv", silent_update=True)
```

---

## Dataset Warnings

psiwatch warns instead of failing silently when your datasets have schema mismatches.

```
  [WARN]
     ⚠  Columns only in baseline (skipped): ['old_feature', 'legacy_col']
     ⚠  Columns only in new data (skipped): ['new_feature']
     ⚠  Column 'income' is 72% numeric — treated as categorical. Cast to float if intended as numeric.
```

---

## Trend Direction

Numeric columns include a trend direction — which way the mean moved:

| Symbol | Meaning |
|---|---|
| ↑ | Mean increased in new data |
| ↓ | Mean decreased in new data |
| → | Mean stable |

Available in terminal output, HTML report, and in `result["metrics"]["trend_direction"]`.

---

## Vanished Category Detection

Categorical columns now detect categories that existed in the baseline but are completely absent from new data — not just new categories appearing.

```
  → Categories vanished from new data: ['Personal', 'Auto']
```

---

## Trend Analysis

Track how your data drifts across a sequence of files over time.

```bash
psiwatch trend monday.csv tuesday.csv wednesday.csv thursday.csv
psiwatch trend day1.csv day2.csv day3.csv --baseline first --output trend.json
```

`--baseline previous` (default) compares each file to the one before it. `--baseline first` compares every file back to the first (cumulative drift from training). The report shows health score per step, per-column severity and PSI over time, and flags any column that steadily worsened across the sequence.

```python
from psiwatch import analyze_trend

result = analyze_trend(["day1.csv", "day2.csv", "day3.csv"])
print(result["overall_health_history"])   # [97, 68, 21]
print(result["worsening_columns"])        # ["age"]
```

---

## Watch Mode

Poll a directory for new CSV files and check each one against a baseline lock as it arrives.

```bash
psiwatch lock train.csv
psiwatch watch data/ --webhook https://hooks.slack.com/services/XXX
```

`--once` is designed for cron jobs and CI. Checks current directory contents and exits. psiwatch persists which files it has already checked (mtime-based, stored in `<lock>.seen.json`), so repeated runs only process new or modified files.

```bash
# In a cron job or CI step:
psiwatch watch data/ --once --fail-on-drift
```

```python
from psiwatch import watch_directory

result = watch_directory("data/", once=True)
print(result["drifted_files"])
```

---

## Webhook Alerts

Send a drift notification to Slack, Discord, or any JSON endpoint when drift is detected. The alert is skipped automatically when health score >= 80.

```bash
psiwatch compare train.csv new.csv --webhook https://hooks.slack.com/services/T/B/xxx
psiwatch check new.csv --webhook https://discord.com/api/webhooks/123/abc
psiwatch watch data/ --once --webhook https://example.com/psiwatch-alert
```

Format auto-detected from URL host: Slack → `{"text": "..."}`, Discord → `{"content": "..."}`, anything else → full JSON payload with `health_score`, `summary`, `message`.

```python
from psiwatch import compare, send_webhook

result = compare("train.csv", "new.csv")
send_webhook("https://hooks.slack.com/services/XXX/YYY/ZZZ", result)
```

---

## Config File

Store default settings in `psiwatch.toml` or `.psiwatchrc` (JSON) in your project directory. CLI flags always win over the config file.

**`psiwatch.toml`:**
```toml
psi_threshold = 0.2
ignore_columns = ["id", "timestamp"]
fail_on_drift = true
webhook = "https://hooks.slack.com/services/XXX/YYY/ZZZ"

[thresholds]
mean_shift_high = 0.6
```

**`.psiwatchrc` (JSON):**
```json
{
  "psi_threshold": 0.2,
  "ignore_columns": ["id", "timestamp"],
  "fail_on_drift": true
}
```

psiwatch auto-detects these files in the current directory. Use `--config path/to/config.toml` for a different path.

---

## Output Formats

| Format | Command | Use case |
|---|---|---|
| Terminal | default | Quick checks during development |
| HTML | `--output report.html` | Sharing with team, presentations |
| JSON | `--output report.json` | CI/CD pipelines, automation, dashboards |
| TXT | `--output report.txt` | Server logs, plain text reports |

All outputs include: timestamp, source file names, per-column metrics, health score.

---

## Input Modes

| Input | Works with |
|---|---|
| CSV file path `"old.csv"` | `compare()` |
| pandas DataFrame | `compare()`, `compare_data()` |
| Python dict `{"col": [values]}` | `compare()`, `compare_data()` |
| List of dicts `[{"col": val}, ...]` | `compare()` |
| Plain Python list | `compare_columns()` |

---

## Detection Methods

### Numeric columns — age, score, salary, credit score

| Method | What it detects |
|---|---|
| Mean Shift | Average moved significantly |
| Std Deviation Shift | Spread of values changed |
| PSI | Overall distribution shape changed |
| Percentiles | Min, P25, Median, P75, Max compared |
| Trend Direction | Which way the mean moved (↑ ↓ →) |

### Categorical columns — city, grade, status, loan type

| Method | What it detects |
|---|---|
| New Category Detection | Values that never existed in training data |
| Vanished Category Detection | Values gone from new data |
| Frequency Distribution Shift | Category proportions changed |
| PSI | Overall distribution changed |
| Chi-Square | Frequency mismatch is statistically significant |

---

## PSI Reference

PSI (Population Stability Index) is the industry standard metric for monitoring production data drift.

| PSI | Status | Action |
|---|---|---|
| < 0.10 | Stable | Model is fine |
| 0.10 – 0.25 | Moderate Drift | Monitor closely, investigate |
| > 0.25 | Significant Drift | Retrain your model |

---

## Drift Health Score

Every report includes a single 0–100 score.

| Score | Status | Meaning |
|---|---|---|
| 80–100 | Stable | Data is stable, model likely fine |
| 50–79 | Moderate Drift | Some columns changed — investigate |
| 0–49 | Significant Drift | Major shifts — retrain |

**Important:** if *any* column is HIGH severity, the score is hard-capped at ≤50 — one bad column in a 20-column dataset does not average away into "Healthy".

---

## Real World Example — Banking Data

```bash
psiwatch compare bank_2023.csv bank_2026.csv
```

What psiwatch caught:

- Credit scores dropped from 752 → 624 — riskier customers ↓
- Salaries dropped from 63k → 45k — lower income applicants ↓
- Loan amounts jumped from 500k → 800k — borrowing more, earning less ↑
- New loan types appeared — `BNPL`, `Crypto` (never in training data)
- Categories vanished — `Personal`, `Auto` no longer in new data
- New statuses appeared — `Defaulted`, `Frozen`
- Branches completely changed — 5 old cities gone, 5 new cities added

**Health Score: 11/100** — a model trained on 2023 data would be completely blind to all of this.

---

## Project Structure

```
psiwatch/
├── src/psiwatch/
│   ├── __init__.py      ← public API + DriftDetected exception
│   ├── loader.py        ← CSV, dict, list, DataFrame input
│   ├── analyzer.py      ← PSI, mean/std, chi-square, percentiles, trend
│   ├── reporter.py      ← terminal, HTML, JSON, TXT output
│   ├── updater.py       ← PyPI version check (24h cached) + self-upgrade
│   ├── locker.py        ← baseline locking (lock / check / lock-info)
│   ├── trend.py         ← multi-file drift trend analysis
│   ├── watcher.py       ← directory polling with mtime-based state
│   ├── webhook.py       ← Slack/Discord/generic webhook alerts
│   ├── config.py        ← psiwatch.toml / .psiwatchrc config loader
│   └── cli.py           ← psiwatch CLI
├── samples/
│   ├── train.csv        ← example baseline dataset
│   └── new.csv          ← example drifted dataset
├── tests/
│   └── test_analyzer.py
├── pyproject.toml
└── README.md
```

---

## Run Tests

```bash
PYTHONPATH=src python3 tests/test_analyzer.py
```

```
Running psiwatch tests...

PASS numeric high drift detected
PASS numeric no drift — PASS
PASS categorical new category detected
PASS categorical no drift — PASS
PASS full analyze — health score: 0/100
PASS health score clean data: 100/100
PASS column filter works
PASS list of dicts input works
PASS missing column warning fires
PASS health score hard cap: HIGH column in large dataset → 50/100

All tests passed.
```

---

## Zero Dependencies

psiwatch uses only Python's standard library:

| Module | Used for |
|---|---|
| `csv` | File reading |
| `math` | Statistical calculations |
| `json` | JSON output + version cache |
| `os` | File operations |
| `argparse` | CLI interface |
| `urllib` | PyPI version check |
| `subprocess` | Self-upgrade (`psiwatch update`) |
| `datetime` | Report timestamps |

No pip conflicts. No install failures. If Python runs, psiwatch runs.

---

## Changelog

### v0.12.0
- `psiwatch trend` — track drift across a sequence of datasets over time; detect worsening columns
- `psiwatch watch` — poll a directory for new CSV files and check each against a lock baseline; persists seen-file state across `--once` runs (cron/CI-safe)
- `--webhook URL` — send Slack, Discord, or generic JSON alert on any drift detection (`compare`, `check`, `summary`, `watch`)
- Config file support — drop a `psiwatch.toml` or `.psiwatchrc` (JSON) in your project directory to set default thresholds, columns, webhook, etc.; CLI flags always override
- `analyze_trend()` Python API — full programmatic access to trend result dict including `worsening_columns` and `column_history`
- `watch_directory()` Python API — embed directory watching in your own scripts
- `send_webhook()` Python API — post drift alerts to any endpoint from Python
- `load_config()` Python API — load and apply config files programmatically
- Webhook skips automatically when health score ≥ 80 (drift-only alerting by default)
- `--once` flag on `watch` — single-pass mode for cron jobs and CI pipelines

### v0.11.0
- `result["summary"]` in `analyze()` — `high_count`, `medium_count`, `pass_count`, `drifted_columns`, `stable_columns`, `total_columns`
- Sample size warning — fires when baseline and new data differ by more than 10x (PSI unreliable at extreme size ratios)
- `--ignore-columns / -x` flag — skip columns by name (IDs, timestamps, row numbers)
- `psiwatch summary` command — one-line health score for shell scripts without a full report
- `psiwatch lock` / `check` / `lock-info` — baseline locking: save a statistical fingerprint of training data, ship it with your model, check against it in CI without the original CSV

### v0.10.0
- `psiwatch update` CLI command — self-upgrade without leaving the terminal
- Trend direction (↑ ↓ →) — numeric columns now show which way the mean moved
- Vanished category detection — categories missing from new data flagged explicitly
- Version banner fixed — fixed-width box, never misaligns on any version string length
- CI detection — banner auto-suppressed when `CI=true` or `GITHUB_ACTIONS=true`
- `--silent` CLI flag — suppress update banner in scripts
- `silent_update` param in `compare()` — same for programmatic use
- JSON output now includes `source_info` field
- `pyproject.toml` classifiers expanded — Python 3.8–3.13, better discoverability
- `vanished_categories` in all output formats (terminal, HTML, TXT, JSON)

### v0.9.0 (previous)
- pandas DataFrame support — pass DataFrames directly to `compare()`
- List of dicts input — `[{"age": 22, "city": "Chennai"}, ...]` supported
- `--fail-on-drift` CLI flag — exit code 1 when drift detected, for CI/CD pipelines
- `DriftDetected` exception — catch in Python for custom alerting logic
- Auto version check against PyPI, 24h cached
- Health score hard-cap — any HIGH column caps score at ≤50
- Missing column warnings — schema mismatches shown explicitly
- Mixed-type column warnings — columns 50-80% numeric now warn
- Timestamp + source in all reports
- Chi-square O(n²) → O(n)

### v0.2.0
- Custom threshold configuration (`psi_threshold`, `thresholds` dict)
- Column filtering (`columns` parameter)
- HTML report output
- `analyze()` function for programmatic access

### v0.1.0
- Initial release
- CSV comparison via CLI and Python API
- PSI, Mean Shift, Std Shift, Chi-Square, New Category detection
- Terminal, JSON, TXT output
- Zero dependencies

---

## Related Tools

If you need heavier drift detection with statistical testing frameworks:

- [evidently](https://github.com/evidentlyai/evidently) — full ML monitoring platform
- [alibi-detect](https://github.com/SeldonIO/alibi-detect) — advanced drift detection with deep learning support
- [scipy.stats](https://docs.scipy.org/doc/scipy/reference/stats.html) — statistical tests

Use `psiwatch` when you need something lightweight, fast, and dependency-free.

---

## License

MIT © 2026 Tharun · [Naeris](https://naeris.vercel.app)

Built entirely on Android using Termux. No laptop. No PC. No IDE.
