# psiwatch

**Dataset drift detection for ML pipelines.**

Know when your data changes. Before your model breaks.

![PyPI](https://img.shields.io/pypi/v/psiwatch)
![License](https://img.shields.io/badge/license-MIT-7C3AED)
![Python](https://img.shields.io/badge/python-3.8+-blue)
![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-22c55e)

---

## What it does

You train a model on last year's data. Six months later it starts making wrong predictions. The reason? Your data changed. Scores dropped. New categories appeared. Distributions shifted.

`psiwatch` catches this. Point it at your old data and new data — it tells you exactly what drifted, how badly, and gives you a single health score.

```bash
psiwatch compare train.csv production.csv
```

---

## Install

```bash
pip install psiwatch
```

---

## CLI Usage

```bash
psiwatch compare old.csv new.csv
psiwatch compare old.csv new.csv --output report.html
psiwatch compare old.csv new.csv --output report.json
psiwatch compare old.csv new.csv --columns age,score,city
```

---

## Library Usage

```python
import psiwatch

# From CSV files
psiwatch.compare("old.csv", "new.csv")

# Save as HTML
psiwatch.compare("old.csv", "new.csv", output="report.html")

# From Python dicts
psiwatch.compare_data(
    old={"age": [22, 23, 21], "city": ["Chennai", "Delhi", "Mumbai"]},
    new={"age": [28, 30, 29], "city": ["Chennai", "Bangalore", "Hyderabad"]}
)

# From plain lists
psiwatch.compare_columns([22, 23, 21], [28, 30, 29], name="age")

# Raw results
result = psiwatch.analyze("old.csv", "new.csv")
print(result["health_score"])  # 0-100
```

---

## Detection Methods

| Column Type | Methods |
|---|---|
| Numeric | Mean shift, Std shift, PSI, Percentile comparison |
| Categorical | New category detection, Frequency shift, PSI, Chi-square |

---

## Drift Health Score

| Score | Status |
|---|---|
| 80 - 100 | Stable |
| 50 - 79 | Moderate Drift |
| 0 - 49 | Significant Drift |

---

## Zero Dependencies

Pure Python only. No numpy, pandas, or scipy. Runs anywhere Python runs including Termux on Android.

---

## License

MIT © 2026 Tharun · [Naeris](https://naeris.vercel.app)
