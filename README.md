

```markdown
# psiwatch

**Dataset drift detection for ML pipelines.**

Know when your data changes. Before your model breaks.

[

![PyPI](https://img.shields.io/pypi/v/psiwatch?color=7C3AED)

](https://pypi.org/project/psiwatch)
[

![License](https://img.shields.io/badge/license-MIT-7C3AED)

](LICENSE)
[

![Python](https://img.shields.io/badge/python-3.8+-blue)

](https://python.org)
[

![Dependencies](https://img.shields.io/badge/dependencies-zero-22c55e)

](https://pypi.org/project/psiwatch)

---

## Install

```bash
pip install psiwatch
```

---

## What it does

You train a model on last year's data. Six months later it starts making wrong predictions. The reason? Your data changed. Scores dropped. New categories appeared. Distributions shifted.

`psiwatch` catches this. Point it at your old data and new data — it tells you exactly what drifted, how badly, and gives you a single health score.

```bash
psiwatch compare train.csv production.csv
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
```

After committing on GitHub, tell me and I'll give you the Termux commands to rebuild and upload.> Runs anywhere Python runs — including **Termux on Android.**

---

## ◈ Quickstart

```bash
git clone https://github.com/tharunstryker/psiwatch
cd psiwatch
pip install -e .
psiwatch compare samples/train.csv samples/new.csv
```

---

## ◈ Usage

<details>
<summary><b>CLI</b></summary>
<br/>

```bash
# Compare two CSV files
psiwatch compare old.csv new.csv

# Save as HTML report
psiwatch compare old.csv new.csv --output report.html

# Save as JSON
psiwatch compare old.csv new.csv --output report.json

# Save as plain text
psiwatch compare old.csv new.csv --output report.txt

# Compare specific columns only
psiwatch compare old.csv new.csv --columns age,score,city
```

</details>

<details>
<summary><b>Python Library</b></summary>
<br/>

**From your own CSV files:**

```python
import psiwatch

# Pass the path to any CSV file on your machine
psiwatch.compare("/your/path/old_data.csv", "/your/path/new_data.csv")

# Save report
psiwatch.compare("old.csv", "new.csv", output="report.html")

# Specific columns only
psiwatch.compare("old.csv", "new.csv", columns=["age", "score"])
```

**From Python dicts — no files needed:**

```python
psiwatch.compare_data(
    old={"age": [22, 23, 21, 24], "city": ["Chennai", "Delhi", "Mumbai", "Delhi"]},
    new={"age": [28, 30, 29, 31], "city": ["Chennai", "Bangalore", "Hyderabad", "Mumbai"]}
)
```

**From plain lists — single column:**

```python
psiwatch.compare_columns(
    old_list=[22, 23, 21, 24, 22],
    new_list=[28, 30, 29, 31, 27],
    name="age"
)
```

**Raw results — no printing:**

```python
result = psiwatch.analyze("old.csv", "new.csv")

print(result["health_score"])
# 25

for column, data in result["columns"].items():
    print(column, data["severity"], data["metrics"]["psi"])
# age    HIGH   0.87
# city   HIGH   1.34
# score  MEDIUM 0.14
# grade  PASS   0.02
```

</details>

---

## ◈ Detection Methods

<div align="center">

| Column Type | Method | What It Checks |
|---|---|---|
| Numeric | Mean Shift | Did the average move significantly? |
| Numeric | Std Deviation Shift | Did the spread of values change? |
| Numeric | PSI | Did the overall distribution shape change? |
| Numeric | Percentile Comparison | Did the median and quartiles shift? |
| Categorical | New Category Detection | Did values appear that never existed before? |
| Categorical | Frequency Shift | Did category proportions change? |
| Categorical | PSI | Did the overall distribution change? |
| Categorical | Chi-Square | Is the frequency mismatch statistically significant? |

</div>

---

## ◈ PSI Reference

<div align="center">

| PSI Value | Status | Action |
|---|---|---|
| `< 0.10` | Stable | Model is fine |
| `0.10 – 0.25` | Moderate Drift | Investigate |
| `> 0.25` | Significant Drift | Retrain your model |

</div>

PSI (Population Stability Index) is the industry standard metric for production data drift monitoring. `psiwatch` uses it as the primary signal for every column — numeric and categorical.

---

## ◈ Drift Health Score

<div align="center">

| Score | Status | Meaning |
|---|---|---|
| `80 – 100` | Healthy | Data is stable, model is likely fine |
| `50 – 79` | Moderate Drift | Some columns changed — investigate |
| `0 – 49` | Significant Drift | Major shifts — consider retraining |

</div>

---

## ◈ Output Formats

<div align="center">

| Format | Command | Best For |
|---|---|---|
| Terminal | default | Dev checks |
| HTML | `--output report.html` | Sharing, presentations |
| JSON | `--output report.json` | Pipelines, CI/CD |
| TXT | `--output report.txt` | Logs, servers |

</div>

---

## ◈ Project Structure

```
psiwatch/
├── src/psiwatch/
│   ├── __init__.py      ← public API
│   ├── loader.py        ← CSV · dict · list input modes
│   ├── analyzer.py      ← PSI · mean/std · chi-square · frequency
│   ├── reporter.py      ← terminal · HTML · JSON · TXT
│   └── cli.py           ← psiwatch compare command
├── samples/
│   ├── train.csv        ← baseline dataset example
│   └── new.csv          ← drifted dataset example
├── tests/
│   └── test_analyzer.py
├── pyproject.toml
└── README.md
```

---

## ◈ Tests

```bash
python tests/test_analyzer.py
```

```
Running psiwatch tests...

✓ numeric high drift detected
✓ numeric no drift — PASS
✓ categorical new category detected
✓ categorical no drift — PASS
✓ full analyze — health score: 0/100
✓ health score clean data: 100/100
✓ column filter works

All tests passed.
```

---

## ◈ Why Zero Dependencies?

Most drift tools require `scipy`, `pandas`, or `scikit-learn` — heavy installs, version conflicts, blocked on restricted systems.

`psiwatch` uses only `csv`, `math`, `json`, `os`, `argparse` — all built into Python. No install friction. No conflicts. Works on bare servers, CI runners, and Termux.

---

```yaml
built_by:   Tharun
entity:     Naeris · Aevra Studio
course:     B.Tech AI & Data Science
built_on:   Android · Termux
philosophy: "No framework. No build step. No shortcuts."
```

---

<p align="center">
  <a href="https://github.com/tharunstryker/psiwatch">
    <img src="https://img.shields.io/badge/Star_this_repo-7C3AED?style=for-the-badge&labelColor=0D0D1A" />
  </a>
</p>

<p align="center">
  <i>MIT © 2026 Tharun · <a href="https://naeris.vercel.app">Naeris</a></i>
</p>

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=7C3AED&height=100&section=footer&animation=fadeIn" width="100%" />
</p>

