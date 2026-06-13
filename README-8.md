# psiwatch

**Python library for dataset drift detection in machine learning pipelines.**

Detect covariate drift, distribution shift, and data quality degradation between two datasets — using PSI, Chi-Square, Mean Shift, and Standard Deviation analysis. Zero dependencies. Pure Python.

![PyPI](https://img.shields.io/pypi/v/psiwatch)
![Downloads](https://img.shields.io/pypi/dm/psiwatch)
![License](https://img.shields.io/badge/license-MIT-7C3AED)
![Python](https://img.shields.io/badge/python-3.8+-blue)
![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-22c55e)

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
| Dependencies | Zero | Heavy | Heavy |
| Install size | ~15KB | ~50MB+ | ~100MB+ |
| Works on Termux | Yes | No | No |
| CLI tool | Yes | No | No |
| Pure Python | Yes | No | No |
| HTML reports | Yes | Yes | No |

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
```

---

## Python Library

```python
import psiwatch

# Compare two CSV files on your machine
psiwatch.compare("/path/to/your/old.csv", "/path/to/your/new.csv")

# Save HTML report
psiwatch.compare("old.csv", "new.csv", output="report.html")

# Compare specific columns
psiwatch.compare("old.csv", "new.csv", columns=["age", "score"])

# From Python dicts — no files needed
psiwatch.compare_data(
    old={"age": [22, 23, 21], "city": ["Chennai", "Delhi", "Mumbai"]},
    new={"age": [28, 30, 29], "city": ["Chennai", "Bangalore", "Hyderabad"]}
)

# From plain Python lists
psiwatch.compare_columns([22, 23, 21], [28, 30, 29], name="age")

# Get raw results programmatically
result = psiwatch.analyze("old.csv", "new.csv")
print(result["health_score"])        # 0-100
for col, data in result["columns"].items():
    print(col, data["severity"])     # HIGH / MEDIUM / PASS
    print(col, data["metrics"])      # PSI, mean, std, chi-square
```

---

## Input Modes

| Mode | Example |
|---|---|
| CSV file path | `psiwatch.compare("old.csv", "new.csv")` |
| Python dict | `psiwatch.compare_data(old_dict, new_dict)` |
| Python list | `psiwatch.compare_columns([1,2,3], [4,5,6])` |

Your files stay on your machine. Pass any file path — `psiwatch` reads whatever path you give it.

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
| Percentile Comparison | Median and quartiles shifted |

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
│   ├── __init__.py      <- public API
│   ├── loader.py        <- CSV, dict, list input modes
│   ├── analyzer.py      <- PSI, mean/std, chi-square, frequency
│   ├── reporter.py      <- terminal, HTML, JSON, TXT output
│   └── cli.py           <- psiwatch compare command
├── samples/
│   ├── train.csv        <- example baseline dataset
│   └── new.csv          <- example drifted dataset
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

```
Running psiwatch tests...

PASS numeric high drift detected
PASS numeric no drift — PASS
PASS categorical new category detected
PASS categorical no drift — PASS
PASS full analyze — health score: 0/100
PASS health score clean data: 100/100
PASS column filter works

All tests passed.
```

---

## Zero Dependencies

Most drift detection libraries require heavy dependencies that cause version conflicts and can't run on minimal systems.

`psiwatch` uses only Python's standard library:
- `csv` — file reading
- `math` — statistical calculations
- `json` — JSON output
- `os` — file operations
- `argparse` — CLI interface

No pip conflicts. No install failures. If Python runs, psiwatch runs.

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
