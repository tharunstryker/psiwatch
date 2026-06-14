# psiwatch

**Python library for dataset drift detection in machine learning pipelines.**

Detect covariate drift, distribution shift, and data quality degradation between two datasets — using PSI, Chi-Square, Mean Shift, and Standard Deviation analysis. Zero dependencies. Pure Python.

![PyPI](https://img.shields.io/pypi/v/psiwatch)
![Downloads](https://img.shields.io/pypi/dm/psiwatch)
![License](https://img.shields.io/badge/license-MIT-7C3AED)
![Python](https://img.shields.io/badge/python-3.8+-blue)
![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-22c55e)

---

## What's New in v0.2.0

### pandas DataFrame support
Pass a DataFrame directly — no need to export to CSV first.

```python
import pandas as pd
import psiwatch

train = pd.read_csv("train.csv")
production = pd.read_csv("production.csv")

psiwatch.compare(train, production)
psiwatch.compare(train, production, output="report.html")
```

Works with `compare()`, `compare_data()`, `compare_columns()`, and `analyze()`. pandas remains optional — users who don't use it don't need to install it.

---

### Column summary stats
Every numeric column now shows min, max, and percentiles (P25, median, P75) alongside PSI and mean/std — so you can see exactly where the distribution shifted, not just that it shifted.

```
  [!!] credit_score  [numeric]  — HIGH DRIFT
     → Mean shifted by 2.20 std devs (752 → 624)
     → PSI = 11.12 (significant drift)
     ┌ Mean:    752.00 → 624.00
     ├ Std:     48.30 → 61.20
     ├ PSI:     11.1200
     ├ Min:     620.00 → 490.00
     ├ P25:     718.00 → 578.00
     ├ Median:  755.00 → 628.00
     ├ P75:     789.00 → 672.00
     └ Max:     850.00 → 799.00
```

These stats appear in all output formats — terminal, HTML, JSON, and TXT.

---

### Configurable drift thresholds
The default PSI thresholds (0.10 medium, 0.25 high) are industry standards for banking data. Your data may need different sensitivity. Now you can set your own.

**Quick shortcut — set the PSI high boundary:**
```python
# More sensitive — flag drift earlier
psiwatch.compare("old.csv", "new.csv", psi_threshold=0.10)

# More lenient — only flag large drifts
psiwatch.compare("old.csv", "new.csv", psi_threshold=0.40)
```
The medium threshold is auto-scaled to 40% of whatever you set, preserving the same ratio as the defaults.

**Full control — override any threshold individually:**
```python
psiwatch.compare("old.csv", "new.csv", thresholds={
    "psi_medium": 0.05,
    "psi_high": 0.15,
    "mean_shift_medium": 0.1,
    "mean_shift_high": 0.3,
})
```

**CLI flag:**
```bash
psiwatch compare old.csv new.csv --psi-threshold 0.15
```

---

## The Problem

You train a machine learning model on historical data. Weeks or months later, the model starts making wrong predictions — but nobody knows why.

The reason is **data drift**. Your production data no longer looks like your training data:

- Customer ages shifted
- New cities or categories appeared
- Salary distributions changed
- Credit scores dropped

Most teams discover this too late — after the model has already failed in production.

---

## The Solution

```bash
pip install psiwatch
psiwatch compare train.csv production.csv
```

```
════════════════════════════════════════════════════════
  PSIWATCH REPORT
════════════════════════════════════════════════════════

  [!!] credit_score  [numeric]  — HIGH DRIFT
     → Mean shifted by 2.20 std devs (752 → 624)
     → PSI = 11.12 (significant drift)
     ┌ Mean:    752.00 → 624.00
     ├ Std:     48.30 → 61.20
     ├ PSI:     11.1200
     ├ Min:     620.00 → 490.00
     ├ P25:     718.00 → 578.00
     ├ Median:  755.00 → 628.00
     ├ P75:     789.00 → 672.00
     └ Max:     850.00 → 799.00

  [!!] loan_type  [categorical]  — HIGH DRIFT
     → New categories found: ['BNPL', 'Crypto']
     → PSI = 4.19

  [OK] customer_id  [categorical]  — STABLE
     → No drift detected

────────────────────────────────────────────────────────
  HIGH: 2   MEDIUM: 0   PASS: 1

  Drift Health Score: 11/100  (Significant Drift)
════════════════════════════════════════════════════════
```

---

## Why psiwatch?

Most drift detection tools like `evidently`, `alibi-detect`, or `scipy` are heavy — they require numpy, pandas, scikit-learn, or scipy as dependencies and are designed for data scientists running Jupyter notebooks.

`psiwatch` is different:

| Feature | psiwatch | evidently | alibi-detect |
|---|---|---|---|
| Dependencies | Zero* | Heavy | Heavy |
| Install size | ~15KB | ~50MB+ | ~100MB+ |
| Works on Termux | Yes | No | No |
| CLI tool | Yes | No | No |
| Pure Python | Yes | No | No |
| HTML reports | Yes | Yes | No |
| DataFrame support | Yes | Yes | Yes |

*pandas is optional. If you pass a DataFrame, psiwatch uses it. If you don't, psiwatch never imports it.

---

## Install

```bash
pip install psiwatch
```

Works on Windows, Mac, Linux, VPS, Google Colab, Jupyter, and Termux on Android.

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

# Set a custom PSI threshold
psiwatch compare old.csv new.csv --psi-threshold 0.15
```

---

## Python Library

```python
import psiwatch

# Compare two CSV files
psiwatch.compare("old.csv", "new.csv")

# Compare pandas DataFrames directly
import pandas as pd
psiwatch.compare(pd.read_csv("old.csv"), pd.read_csv("new.csv"))

# Save HTML report
psiwatch.compare("old.csv", "new.csv", output="report.html")

# Compare specific columns
psiwatch.compare("old.csv", "new.csv", columns=["age", "score"])

# Custom PSI threshold
psiwatch.compare("old.csv", "new.csv", psi_threshold=0.15)

# Fine-grained threshold control
psiwatch.compare("old.csv", "new.csv", thresholds={
    "psi_medium": 0.05,
    "psi_high": 0.15,
    "mean_shift_high": 0.3,
})

# From Python dicts — no files needed
psiwatch.compare_data(
    old={"age": [22, 23, 21], "city": ["Chennai", "Delhi", "Mumbai"]},
    new={"age": [28, 30, 29], "city": ["Chennai", "Bangalore", "Hyderabad"]}
)

# From plain Python lists
psiwatch.compare_columns([22, 23, 21], [28, 30, 29], name="age")

# Get raw results programmatically
result = psiwatch.analyze("old.csv", "new.csv")
print(result["health_score"])         # 0-100
for col, data in result["columns"].items():
    print(col, data["severity"])      # HIGH / MEDIUM / PASS
    print(col, data["metrics"])       # PSI, mean, std, min, p25, median, p75, max
```

---

## Input Modes

| Mode | Example |
|---|---|
| CSV file path | `psiwatch.compare("old.csv", "new.csv")` |
| pandas DataFrame | `psiwatch.compare(old_df, new_df)` |
| Python dict | `psiwatch.compare_data(old_dict, new_dict)` |
| Python list | `psiwatch.compare_columns([1,2,3], [4,5,6])` |

Your files stay on your machine. pandas is never required — only used if you pass a DataFrame.

---

## Output Formats

| Format | Use case |
|---|---|
| Terminal (default) | Quick checks during development |
| HTML `--output report.html` | Sharing with team, presentations |
| JSON `--output report.json` | CI/CD pipelines, automation |
| TXT `--output report.txt` | Server logs, plain text reports |

---

## Detection Methods

### Numeric columns — age, score, salary, credit score...

| Method | What it detects |
|---|---|
| Mean Shift | Average moved significantly between datasets |
| Std Deviation Shift | Spread of values changed |
| PSI (Population Stability Index) | Overall distribution shape changed |
| Min / Max / Percentiles | Where exactly in the distribution the shift happened |

### Categorical columns — city, grade, status, loan type...

| Method | What it detects |
|---|---|
| New Category Detection | Values appeared that never existed in training data |
| Frequency Distribution Shift | Category proportions changed significantly |
| PSI | Overall distribution changed |
| Chi-Square Statistic | Frequency mismatch is statistically significant |

---

## PSI Reference

PSI (Population Stability Index) is the industry standard metric for production data drift monitoring.

| PSI | Status | Recommended Action |
|---|---|---|
| < 0.10 | Stable | Model is fine |
| 0.10 - 0.25 | Moderate Drift | Monitor closely, investigate |
| > 0.25 | Significant Drift | Retrain your model |

These are the defaults. Override them with `psi_threshold` or `thresholds` if your domain requires different sensitivity.

---

## Threshold Reference

All thresholds can be overridden via the `thresholds` dict:

| Key | Default | What it controls |
|---|---|---|
| `psi_medium` | `0.10` | PSI value that triggers MEDIUM severity |
| `psi_high` | `0.25` | PSI value that triggers HIGH severity |
| `mean_shift_medium` | `0.20` | Mean shift (in std devs) for MEDIUM |
| `mean_shift_high` | `0.50` | Mean shift (in std devs) for HIGH |
| `std_shift_medium` | `0.20` | Std dev shift ratio for MEDIUM |
| `std_shift_high` | `0.50` | Std dev shift ratio for HIGH |
| `category_share_shift` | `0.15` | Category frequency change for MEDIUM |
| `chi_square_medium` | `0.50` | Chi-square value for MEDIUM |

---

## Drift Health Score

Every report includes a single score — a quick read on how healthy your dataset is overall.

| Score | Status | What it means |
|---|---|---|
| 80 - 100 | Stable | Data is stable, model is likely fine |
| 50 - 79 | Moderate Drift | Some columns changed — investigate |
| 0 - 49 | Significant Drift | Major shifts — consider retraining |

---

## Real World Example — Banking Data

```bash
psiwatch compare bank_2023.csv bank_2026.csv
```

**What psiwatch caught:**

- Credit scores dropped from 752 to 624 — riskier customers
- Salaries dropped from 63k to 45k — lower income applicants
- Loan amounts jumped from 500k to 800k — borrowing more despite earning less
- New loan types appeared — BNPL and Crypto (never in training data)
- New statuses appeared — Defaulted and Frozen
- Branches completely changed — 5 old cities gone, 5 new cities added

**Health Score: 11/100** — a model trained on 2023 data would be completely blind to all of this in 2026.

---

## Project Structure

```
psiwatch/
├── src/psiwatch/
│   ├── __init__.py      ← public API (compare, compare_data, analyze)
│   ├── loader.py        ← CSV, dict, list, DataFrame input modes
│   ├── analyzer.py      ← PSI, mean/std, chi-square, percentiles, thresholds
│   ├── reporter.py      ← terminal, HTML, JSON, TXT output
│   └── cli.py           ← psiwatch compare command
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
python tests/test_analyzer.py
```

---

## Zero Dependencies

`psiwatch` uses only Python's standard library:
- `csv` — file reading
- `math` — statistical calculations
- `json` — JSON output
- `os` — file operations
- `argparse` — CLI interface

pandas is **optional**. It is only imported when you pass a DataFrame. No pip conflicts. No install failures. If Python runs, psiwatch runs.

---

## Changelog

### v0.2.0 — Phase 1 Upgrades
- **DataFrame support** — pass a `pd.DataFrame` directly to any input parameter
- **Column summary stats** — min, P25, median, P75, max shown for every numeric column in all output formats
- **Configurable thresholds** — `psi_threshold` shortcut and full `thresholds` dict available on all public functions and the CLI

### v0.1.0 — Initial Release
- CSV file comparison via CLI and Python API
- PSI, mean shift, std shift, chi-square, frequency analysis
- Terminal, HTML, JSON, TXT output formats
- Dict and list input modes
- Drift health score

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
