# psiwatch

**Zero-dependency Python library and CLI for dataset drift detection in ML pipelines.**

Compare your training data with production data and find out what changed — numeric, categorical and free-text columns — before your model fails silently. Pure Python: no numpy, no scipy, no pandas, no models to download.

[![PyPI](https://img.shields.io/pypi/v/psiwatch)](https://pypi.org/project/psiwatch/)
[![Downloads](https://img.shields.io/pypi/dm/psiwatch)](https://pypi.org/project/psiwatch/)
[![CI](https://github.com/tharunstryker/psiwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/tharunstryker/psiwatch/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.8+-blue)
![License](https://img.shields.io/badge/license-MIT-7C3AED)
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

## Install

```bash
pip install psiwatch
```

Works on Windows, Mac, Linux, VPS, Google Colab, Jupyter, and Termux on Android.

### Upgrade

```bash
# via CLI (easiest) — works on Termux too
psiwatch update

# or standard pip
pip install --upgrade psiwatch
```

## Quickstart

```bash
pip install psiwatch
psiwatch compare train.csv production.csv
```

```python
import psiwatch

result = psiwatch.compare("train.csv", "production.csv")   # prints the report
print(result["health_score"])                               # 0-100, 100 = no drift
```

Want to try it without your own data? Clone the repo and run the bundled samples:

```bash
git clone https://github.com/tharunstryker/psiwatch
cd psiwatch
pip install -e .
psiwatch compare samples/train.csv samples/new.csv
```

---

## What's New in 0.15.0

**Free-text column drift.** Columns of chat messages, reviews or tickets are now auto-detected and analysed as text: vocabulary drift, rising / falling / brand-new words, unseen-word rate, language and script mix, length and structure — pure Python, no models. See [Text Drift](#text-drift--messages-reviews-tickets).

- `psiwatch version` now shows what's new in your installed version (`--short` prints only the number).
- New options: `--text-columns a,b` to force text analysis, `--no-text-detect` to turn auto-detection off.
- **Behaviour change:** a free-text column that used to be reported as `[categorical]` is now reported as `[text]`.

**Past versions →** [CHANGELOG.md](https://github.com/tharunstryker/psiwatch/blob/main/CHANGELOG.md)

---

## Features

| Feature | How |
|---|---|
| Numeric and categorical drift (PSI, chi-square, mean / std shift, new and vanished categories) | `psiwatch compare old.csv new.csv` |
| **Free-text drift** (vocabulary, new words, language mix, length) | automatic — see [Text Drift](#text-drift--messages-reviews-tickets) |
| 0–100 health score per comparison | in every report |
| Lock a training set as a small baseline file | `psiwatch lock` / `psiwatch check` |
| Drift over a sequence of datasets | `psiwatch trend` |
| Check new files as they arrive | `psiwatch watch` |
| Slack / Discord / webhook alerts | `--webhook URL` |
| Fail a CI build on drift | `--fail-on-drift` |
| Charts (optional, needs matplotlib) | `--plot drift.png` |
| Per-column thresholds learned from history | `psiwatch learn-thresholds` |
| Inputs: CSV, Parquet, SQL, pandas, dicts, lists | see [Input modes](#input-modes) |
| Outputs: terminal, HTML, JSON, TXT | `--output report.html` |

---

## Usage

Everything below works from the command line and from Python.

### Command line

```bash
# Compare two CSV files
psiwatch compare old.csv new.csv

# Save as HTML report
psiwatch compare old.csv new.csv --output report.html

# Save as JSON for pipelines
psiwatch compare old.csv new.csv --output report.json

# Save as plain text
psiwatch compare old.csv new.csv --output report.txt

# Force a column to be analysed as free text / turn text auto-detection off
psiwatch compare old.csv new.csv --text-columns message
psiwatch compare old.csv new.csv --no-text-detect

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

# Config files (psiwatch.toml / .psiwatchrc) in the project directory are picked up automatically
psiwatch compare old.csv new.csv

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

# Show installed version + what's new in it (add --short for just the number)
psiwatch version
```

### Python API

#### CSV files

```python
import psiwatch

psiwatch.compare("old.csv", "new.csv")
psiwatch.compare("old.csv", "new.csv", output="report.html")
psiwatch.compare("old.csv", "new.csv", columns=["age", "score"])
```

#### pandas DataFrames

```python
import pandas as pd
import psiwatch

old_df = pd.read_csv("train.csv")
new_df = pd.read_csv("production.csv")

psiwatch.compare(old_df, new_df)
psiwatch.compare(old_df, new_df, output="report.html")
```

pandas is **optional** — psiwatch works without it. Only imported when a DataFrame is passed.

#### Python dicts

```python
psiwatch.compare_data(
    old={"age": [22, 23, 21], "city": ["Chennai", "Delhi", "Mumbai"]},
    new={"age": [28, 30, 29], "city": ["Chennai", "Bangalore", "Hyderabad"]}
)
```

#### List of dicts (JSON records)

```python
old_records = [{"age": 22, "city": "Chennai"}, {"age": 23, "city": "Delhi"}]
new_records = [{"age": 28, "city": "Mumbai"}, {"age": 30, "city": "Pune"}]

psiwatch.compare(old_records, new_records)
```

#### Single list (one column)

```python
psiwatch.compare_columns([22, 23, 21], [28, 30, 29], name="age")
```

#### Raw results (no print)

```python
result = psiwatch.analyze("old.csv", "new.csv")

print(result["health_score"])         # 0-100

for col, data in result["columns"].items():
    print(col, data["severity"])      # HIGH / MEDIUM / PASS
    print(col, data["metrics"])       # PSI, mean, std, chi-square, percentiles, trend_direction
    print(col, data.get("warnings"))  # mixed-type or schema warnings
```

### Input modes

| Input | Works with |
|---|---|
| CSV file path `"old.csv"` | `compare()` |
| Parquet file path `"old.parquet"` | `compare()` (requires `pandas` + `pyarrow`) |
| pandas DataFrame | `compare()`, `compare_data()` |
| Python dict `{"col": [values]}` | `compare()`, `compare_data()` |
| List of dicts `[{"col": val}, ...]` | `compare()` |
| Plain Python list | `compare_columns()` |
| SQL query + DB-API connection | `psiwatch.loader.load_sql()` → `compare_data()` |

### Output formats

| Format | Command | Use case |
|---|---|---|
| Terminal | default | Quick checks during development |
| HTML | `--output report.html` | Sharing with team, presentations |
| JSON | `--output report.json` | CI/CD pipelines, automation, dashboards |
| TXT | `--output report.txt` | Server logs, plain text reports |

All outputs include: timestamp, source file names, per-column metrics, health score.

### CI/CD — fail on drift

Block deployments when data drifts. psiwatch exits with code 1 if `health_score < 80`.

#### GitHub Actions

```yaml
- name: Check data drift
  run: psiwatch compare train.csv production.csv --fail-on-drift
```

#### Python

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

## Text Drift — messages, reviews, tickets

A column of sentences used to be treated as a categorical column where every unique sentence is its own "category" — meaningless results and no explanation. psiwatch now detects free-text columns automatically and analyses them as text, with **no embeddings, no models and no extra dependencies**.

```bash
psiwatch compare chats_jan.csv chats_feb.csv
```

```
  [!!] message  [text]  — HIGH DRIFT
     → Vocabulary drift score 0.518 (significant; noise floor 0.007) — rising: order, help, pls; falling: delivery, blue, package
     → New words not in baseline: refund, திரும்ப, பணம், give, எனக்கு
     → 55.2% of words are unseen in the baseline (expected ~0.0%)
     ┌ Vocab drift:  0.5176  (noise floor 0.0071)
     ├ Words/value:  6.7 → 6.3
     ├ Unseen words: 0.0% expected → 55.2%
     ├ Scripts:      Latin 100%  →  Latin 87.5%, Tamil 12.5%
     ├ Rising:       order (6.5% → 13.8%), help (9.5% → 12.8%), pls (9.5% → 12.8%)
     ├ Falling:      delivery (20.5% → 0%), blue (12% → 0%), package (11.7% → 0%), price (11.7% → 0%)
     └ New words:    refund (19.2%), திரும்ப (14.7%), பணம் (14.7%), give (14.3%), scam (14%), chargeback (13.8%)
```

(Percentages after a word = share of messages containing it, baseline → new.)

| What is checked | What it catches |
|---|---|
| **Vocabulary drift** — Jensen-Shannon divergence (bits, 0–1) between word distributions, **corrected for small-sample noise** | The topics people talk about changed |
| **Rising / falling / brand-new words** | *What* changed — not just that something did |
| **Unseen-word rate** (Good-Turing corrected) | New slang, new products, prompt injection, a new campaign |
| **Script / language mix** (Latin, Tamil, Devanagari, Arabic, CJK …) | A wave of Tamil-script or Hindi traffic arriving at an English-only model |
| **Length** (words per value) | Users switch from short queries to long pasted prompts |
| **Structure** — empty, duplicate, URL, digit, upper-case and symbol/emoji rates (MEDIUM at most) | Bots, spam floods, templated or injected input |

**Unicode-aware:** Tamil, Hindi, Bengali etc. are tokenised correctly (combining vowel signs stay attached to their word); CJK is tokenised per character.

**Detection and control:**

```python
psiwatch.compare("old.csv", "new.csv")                          # text columns auto-detected
psiwatch.compare("old.csv", "new.csv", text_columns=["message"])  # force a column to text
psiwatch.compare("old.csv", "new.csv", detect_text=False)       # pre-0.15 behaviour
```
```bash
psiwatch compare old.csv new.csv --text-columns message
psiwatch compare old.csv new.csv --no-text-detect
```

A column is treated as text when it isn't numeric, has several words per value, and its values are mostly unique. Repeated multi-word categories ("New York", "Order shipped") stay categorical. Locks (`psiwatch lock`) store a bounded fingerprint for text columns too: word counts for the top 1,000 words plus a few scalars, not the messages.

**Honest limits — read these:**
- **Bag-of-words, not meaning.** "refund" and "money back" are unrelated words to psiwatch. For semantic drift you need embedding-based tools (see [How psiwatch Compares](#how-psiwatch-compares)).
- **Small samples have low power.** Under ~100 values per side, psiwatch warns and the noise-aware thresholds make it slower to flag. Fewer than 5 non-empty values → `UNKNOWN`.
- **Thresholds are heuristics.** They were calibrated on simulated chatbot traffic (healthy samples stay PASS from ~100 values; a topic takeover reaches HIGH). Tune them on your own data with `[thresholds] text_jsd_medium / text_jsd_high` (default 0.005 / 0.04 bits).
- **Word lists reveal vocabulary.** A lock file holds no messages, but its top-word list reflects your data's vocabulary — don't commit locks built from sensitive text to a public repo.
- **Charts can't draw Indic scripts.** matplotlib (used only by `--plot` / `--embed-chart`) has no native Tamil shaping, so Tamil/Devanagari words appear as boxes in the PNG chart. Terminal, TXT, HTML and JSON reports render them correctly.
- **Speed:** pure Python, roughly 6.5 s for 100k + 100k messages on a desktop CPU; expect slower on a phone.

---

## Understanding the Report

How to read what psiwatch tells you.


### Detection methods

#### Numeric columns — age, score, salary, credit score

| Method | What it detects |
|---|---|
| Mean Shift | Average moved significantly |
| Std Deviation Shift | Spread of values changed |
| PSI | Overall distribution shape changed |
| Percentiles | Min, P25, Median, P75, Max compared |
| Trend Direction | Which way the mean moved (↑ ↓ →) |

#### Categorical columns — city, grade, status, loan type

| Method | What it detects |
|---|---|
| New Category Detection | Values that never existed in training data |
| Vanished Category Detection | Values gone from new data |
| Frequency Distribution Shift | Category proportions changed |
| PSI | Overall distribution changed |
| Chi-Square | Frequency mismatch is statistically significant |

#### Text columns — messages, reviews, tickets, search queries

| Method | What it detects |
|---|---|
| Vocabulary drift (noise-corrected JSD) | Word distribution changed |
| Rising / falling / new words | Which words drove the change |
| Unseen-word rate (Good-Turing corrected) | Words never seen in the baseline |
| Script / language mix | Writing system shifted (e.g. Latin → Tamil) |
| Length shift | Words per value changed |
| Structure rates | Empty, duplicate, URL, digit, upper-case, symbol/emoji rates |

See **Text Drift** above for details and limits.

### PSI reference

PSI (Population Stability Index) is the industry standard metric for monitoring production data drift.

| PSI | Status | Action |
|---|---|---|
| < 0.10 | Stable | Model is fine |
| 0.10 – 0.25 | Moderate Drift | Monitor closely, investigate |
| > 0.25 | Significant Drift | Retrain your model |

### Drift health score

Every report includes a single 0–100 score.

| Score | Status | Meaning |
|---|---|---|
| 80–100 | Stable | Data is stable, model likely fine |
| 50–79 | Moderate Drift | Some columns changed — investigate |
| 0–49 | Significant Drift | Major shifts — retrain |

**Important:** if *any* column is HIGH severity, the score is hard-capped at ≤50 — one bad column in a 20-column dataset does not average away into "Healthy".

### Trend direction

Numeric columns include a trend direction — which way the mean moved:

| Symbol | Meaning |
|---|---|
| ↑ | Mean increased in new data |
| ↓ | Mean decreased in new data |
| → | Mean stable |

Available in terminal output, HTML report, and in `result["metrics"]["trend_direction"]`.

### Vanished category detection

Categorical columns now detect categories that existed in the baseline but are completely absent from new data — not just new categories appearing.

```
  → Categories vanished from new data: ['Personal', 'Auto']
```

### Dataset warnings

psiwatch warns instead of failing silently when your datasets have schema mismatches.

```
  [WARN]
     ⚠  Columns only in baseline (skipped): ['old_feature', 'legacy_col']
     ⚠  Columns only in new data (skipped): ['new_feature']
     ⚠  Column 'income' is 72% numeric — treated as categorical. Cast to float if intended as numeric.
```

### Real-world example — banking data

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

## Monitoring Over Time

Track drift across many datasets instead of one comparison.


### Trend analysis

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

### Watch mode

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

### Webhook alerts

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

## Configuration

Defaults you can set once.


### Custom thresholds

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
    # free-text columns (defaults shown)
    "text_jsd_medium": 0.005,        # vocabulary drift score, bits
    "text_jsd_high": 0.04,
    "text_oov_medium": 0.10,         # excess share of unseen words
    "text_oov_high": 0.25,
    "text_script_shift_medium": 0.15,  # share of values changing writing system
    "text_script_shift_high": 0.30,
    "text_structure_shift": 0.10,    # empty/duplicate/URL/digit/upper/symbol rates
})
```

### Config file

Store default settings in `psiwatch.toml` or `.psiwatchrc` (JSON) in your project directory. CLI flags always win over the config file.

**`psiwatch.toml`:**
```toml
psi_threshold = 0.2
ignore_columns = ["id", "timestamp"]
text_columns = ["message"]      # force free-text analysis (optional)
# detect_text = false           # turn text auto-detection off
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

psiwatch auto-detects these files in the current directory (and walks up through parent directories). There is no `--config` flag; keep the file in your project root.

### Update notifications

The `psiwatch` CLI checks PyPI for newer versions when you run a command — never on `import psiwatch`. The check is cached for 24 hours (so it's not a PyPI request on every run, just every CLI invocation within the cache window) and is automatically silent in CI environments (`CI=true`, `GITHUB_ACTIONS=true`, `PSIWATCH_SILENT=1`).

```
  ╔════════════════════════════════════════════════════╗
  ║  psiwatch update available: 0.15.1 → 0.16.0        ║
  ║  Run: pip install --upgrade psiwatch               ║
  ╚════════════════════════════════════════════════════╝
```

To suppress from the CLI:

```bash
psiwatch compare old.csv new.csv --silent
```

`import psiwatch` and library calls like `psiwatch.compare(...)` never trigger this check or make any network call — it's CLI-only. If you want the check inside your own script, opt in explicitly:

```python
from psiwatch.updater import check_for_update
import psiwatch
check_for_update(psiwatch.__version__)
```

---

## How psiwatch Compares

psiwatch is for pipelines and minimal environments where you want a drift check with nothing to install but psiwatch itself.

| | psiwatch | evidently | alibi-detect |
|---|---|---|---|
| Required dependencies | **0** | 26 | 17 |
| Wheel size (package only) | ~75 KB | 11.7 MB | 0.4 MB |
| Python versions | 3.8+ | 3.10+ | 3.9+ |

*Measured October 2026 from each package's PyPI metadata (psiwatch 0.15.1, evidently 0.7.23, alibi-detect 0.13.0; core requirements, excluding extras). Wheel size excludes dependencies — installing the others pulls in numpy, pandas, scikit-learn and more; psiwatch pulls in nothing.*

**What psiwatch does not do** (use the tools listed below when you need these): model-based or embedding-based drift detection, multivariate drift (columns are analysed one at a time), a monitoring dashboard/UI, or target/prediction drift and model-quality metrics.

**When to use something else:**

- [evidently](https://github.com/evidentlyai/evidently) — full ML monitoring platform
- [alibi-detect](https://github.com/SeldonIO/alibi-detect) — advanced drift detection with deep learning support
- [scipy.stats](https://docs.scipy.org/doc/scipy/reference/stats.html) — statistical tests

Use psiwatch when you want something lightweight, fast and dependency-free; use these when you need the capabilities above.

---

## Development


### Contributing

Issues and pull requests are welcome.

```bash
git clone https://github.com/tharunstryker/psiwatch
cd psiwatch
pip install pytest matplotlib
PYTHONPATH=src python -m pytest -q
```

The test suite must pass on Python 3.8–3.13 (CI runs all of them), and psiwatch's core must stay dependency-free. For a release, bump the version in `pyproject.toml` and `src/psiwatch/__init__.py`, then add an entry to `CHANGELOG.md` and `src/psiwatch/whatsnew.py` — a test fails if you forget.

### Run tests

```bash
pip install -e ".[dev]"
pytest
```

```
============================== 99 passed ==============================
```

### Project structure

```
psiwatch/
├── .github/workflows/
│   └── ci.yml            ← pytest on Python 3.8–3.13 + build/version check
├── src/psiwatch/
│   ├── __init__.py      ← public API + DriftDetected exception
│   ├── loader.py        ← CSV, Parquet, SQL, dict, list, DataFrame input
│   ├── adapt.py          ← learn-thresholds: per-column learned PSI thresholds
│   ├── viz.py            ← optional matplotlib chart export (psiwatch[charts])
│   ├── whatsnew.py      ← release highlights shown by `psiwatch version`
│   ├── analyzer.py      ← PSI, mean/std, chi-square, percentiles, trend, baseline summaries
│   ├── text.py          ← free-text drift: vocabulary JSD, new words, scripts, length, structure
│   ├── reporter.py      ← terminal, HTML, JSON, TXT output (HTML-escaped)
│   ├── updater.py       ← PyPI version check (24h cached) + self-upgrade — CLI-triggered only
│   ├── locker.py        ← baseline locking (lock / check / lock-info) — stores fingerprints, not raw data
│   ├── trend.py         ← multi-file drift trend analysis (HTML-escaped)
│   ├── watcher.py       ← directory polling with mtime-based state
│   ├── webhook.py       ← Slack/Discord/generic webhook alerts
│   ├── config.py        ← psiwatch.toml / .psiwatchrc config loader
│   └── cli.py           ← psiwatch CLI
├── samples/
│   ├── train.csv        ← example baseline dataset
│   └── new.csv          ← example drifted dataset
├── tests/
│   ├── test_analyzer.py
│   ├── test_locker.py
│   ├── test_changelog.py
│   ├── test_reporter.py
│   ├── test_text.py
│   ├── test_trend.py
│   ├── test_updater.py
│   ├── test_webhook.py
│   └── test_config.py
├── CHANGELOG.md          ← full release history
├── pyproject.toml
└── README.md
```

### Zero dependencies

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
| `re`, `unicodedata`, `collections`, `bisect` | Text tokenisation and word counts (0.15+) |

No pip conflicts. No install failures. If Python runs, psiwatch runs.

---

## License

MIT © 2026 Tharun · [Naeris](https://naeris.vercel.app)

Built entirely on Android using Termux. No laptop. No PC. No IDE.
