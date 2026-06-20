# psiwatch — Developer Log & Troubleshooting Guide

How I built and published a Python package entirely from Android using Termux — with every error I hit and how I fixed it.

**Author:** Tharun (TharunStryker)
**Course:** B.Tech AI & Data Science
**Built on:** Android phone, Termux
**Published:** https://pypi.org/project/psiwatch
**GitHub:** https://github.com/tharunstryker/psiwatch

---

## The Story

This entire library was built on an Android phone using Termux. No laptop. No PC. No IDE. Just Python, a terminal, and a lot of problem solving.

The idea came from a real problem in AI/Data Science — models fail silently in production because data changes over time and nobody catches it early enough. Most drift detection tools are too heavy for lightweight use. So I built one from scratch with zero dependencies.

From first line of code to published PyPI package — all on Android.

---

## What psiwatch does

Detects dataset drift between two CSV files (or Python dicts/lists/DataFrames) using:

- **PSI** (Population Stability Index) — industry standard drift metric
- **Mean shift** — did the average move significantly?
- **Std deviation shift** — did the spread change?
- **Chi-square** — is the category frequency mismatch statistically significant?
- **New category detection** — did values appear that never existed in training data?
- **Vanished category detection** — did training categories disappear from new data?
- **Trend direction** — which way did numeric means move? (↑ ↓ →)

Outputs to terminal, HTML, JSON, or TXT with a 0-100 Drift Health Score.

---

## Project structure

```
psiwatch/
├── .github/workflows/
│   └── ci.yml            ← pytest on Python 3.8–3.13 + build/version check, runs on every push/PR
├── src/psiwatch/
│   ├── __init__.py      ← public API + DriftDetected exception
│   ├── loader.py        ← CSV, dict, list, DataFrame input
│   ├── analyzer.py      ← PSI, mean/std, chi-square, percentiles, trend, baseline summaries
│   ├── reporter.py      ← terminal, HTML, JSON, TXT output (HTML-escaped)
│   ├── updater.py       ← PyPI version check + psiwatch update command (CLI-only trigger)
│   ├── locker.py        ← baseline locking (lock / check / lock-info) — stores fingerprints, not raw data
│   ├── trend.py         ← multi-file drift trend analysis (HTML-escaped)
│   ├── watcher.py       ← directory polling with mtime-based state
│   ├── webhook.py       ← Slack/Discord/generic webhook alerts
│   ├── config.py        ← psiwatch.toml / .psiwatchrc config loader
│   └── cli.py           ← CLI entry point
├── samples/
│   ├── train.csv
│   └── new.csv
├── tests/
│   ├── test_analyzer.py ← core analyze()/compare_columns() behavior
│   ├── test_locker.py   ← lock/check + fingerprint-size regression tests
│   ├── test_reporter.py ← HTML report + XSS-escaping regression tests
│   ├── test_trend.py    ← trend analysis + HTML/script-injection regression tests
│   ├── test_updater.py  ← import-time network-call regression test
│   ├── test_webhook.py  ← webhook formatting/dispatch
│   └── test_config.py   ← TOML config loading
├── pyproject.toml        ← includes [tool.pytest.ini_options] + dev extras
└── README.md
```

---

## Version history

```
v0.1.0  → Initial release — CSV, PSI, mean/std, chi-square, terminal/JSON/TXT output
v0.2.0  → Custom thresholds, column filtering, HTML report, analyze() API
v0.9.0  → pandas DataFrame support, list of dicts input, --fail-on-drift, DriftDetected
           exception, health score hard-cap, missing column warnings, mixed-type warnings,
           timestamp in all reports, chi-square O(n²) → O(n) fix, updater.py
v0.10.0 → psiwatch update command, trend direction (↑↓→), vanished category detection,
           banner alignment fix, CI auto-silence, --silent flag, JSON source_info field
v0.11.0 → result["summary"] in analyze(), sample size warnings, --ignore-columns,
           psiwatch summary command, psiwatch lock / check / lock-info (baseline locking),
           psiwatch trend (multi-file drift timeline + worsening detection),
           psiwatch watch (directory polling, mtime state persistence, --once for cron/CI),
           --webhook flag (Slack/Discord/generic JSON alerts on all commands),
           config file support (psiwatch.toml / .psiwatchrc, auto-detected),
           analyze_trend() / watch_directory() / send_webhook() / load_config() Python APIs
           57 tests
v0.12.0 → SECURITY/BUG-FIX RELEASE (no new features):
           • locker.py: lock files were storing the entire raw baseline dataset under
             "values_sample" instead of a fingerprint — a 10,000-row baseline produced a
             ~multi-MB lock file containing the original training data. Now stores a
             bounded statistical fingerprint (mean/std/percentiles + 10-bin histogram for
             numeric, category frequencies for categorical) — O(bins)/O(unique categories)
             instead of O(rows). A 50,000-row baseline now locks to under 5KB. Old-format
             lock files are detected and rejected with a message to re-run `psiwatch lock`.
           • reporter.py / trend.py: to_html() and to_html_trend() interpolated column
             names, category values, reasons, and file labels directly into HTML (and into
             an inline <script> block for the trend chart) with zero escaping. A column
             name or category value like "<script>...</script>" in the source CSV would
             execute when the generated report was opened in a browser. All interpolated
             strings are now html.escape()'d; the script-block payload additionally guards
             against "</script>" breakout.
           • __init__.py: `import psiwatch` made an unconditional network call to PyPI on
             every import (the update-check banner), including inside training pipelines,
             notebooks, or CI steps that never touch the CLI. The check now only fires from
             the `psiwatch` CLI entry point; plain `import psiwatch` makes zero network calls.
           • Test suite converted from a hand-rolled script with a pass/fail counter (no
             real asserts, never run by CI, exited 0 on failure) to a real pytest suite
             across 6 files. CI added (.github/workflows/ci.yml) running pytest on Python
             3.8–3.13 plus a build + version-consistency check on every push/PR.
           53 tests, all real pytest asserts (vs. 65 script-counted checks before)
v0.12.1 → Metadata-only fix — corrected author name/email and switched `license` to the
           SPDX-string format expected by current packaging tooling. No code changes.
v0.12.2 → loader.py: added Parquet file support — compare()/analyze()/CLI `compare` now
           accept .parquet/.pq paths anywhere a CSV path works, auto-detected by extension
           (requires pandas + pyarrow, optional — core stays zero-dependency). Added
           load_sql(query, connection) — run a query against any DB-API connection you
           already opened (sqlite3, psycopg2, pymysql, SQLAlchemy, etc.) and feed the result
           straight into compare_data(). No bundled DB driver, no credential handling —
           bring your own connection.

           Bug fixes found during issue hunt, same release:
           - cast_numeric() used bare float(), which accepts the strings "NaN"/"inf"/
             "-Infinity" as valid floats. These crashed analyze_numeric()'s PSI binning
             downstream (int(nan) raises ValueError) — a single "NaN" string in a numeric
             column could kill the whole compare() call. Now explicitly rejected like any
             other unparseable value.
           - Non-numeric values dropped by cast_numeric (garbage, blanks, the NaN/inf case
             above) were silently excluded with zero indication in the report — new_count
             would just be smaller than the row count with no explanation. Added a warning
             that fires when >5% of either baseline or new values get dropped, stating
             exactly how many/what % were excluded.
```

---

## Build order (first version)

```
Week 1 → loader.py    — read CSVs, detect column types
Week 2 → analyzer.py  — PSI, mean/std shift, chi-square
Week 3 → reporter.py  — terminal, HTML, JSON, TXT output
Week 4 → __init__.py  — public library API
         cli.py       — CLI entry point
         pyproject.toml — pip packaging
         README.md    — documentation
         Published to PyPI
```

---

## How to use psiwatch

### Install

```bash
pip install psiwatch
```

### Upgrade

```bash
psiwatch update
# or
pip install --upgrade psiwatch
```

### CLI

```bash
psiwatch compare old.csv new.csv
psiwatch compare old.csv new.csv --output report.html
psiwatch compare old.csv new.csv --output report.json
psiwatch compare old.csv new.csv --columns age,score,city
psiwatch compare old.csv new.csv --ignore-columns id,timestamp
psiwatch compare old.csv new.csv --psi-threshold 0.15
psiwatch compare old.csv new.csv --fail-on-drift
psiwatch compare old.csv new.csv --webhook https://hooks.slack.com/services/XXX/YYY/ZZZ
psiwatch summary train.csv new.csv
psiwatch lock train.csv
psiwatch check new.csv --fail-on-drift
psiwatch trend day1.csv day2.csv day3.csv
psiwatch trend day1.csv day2.csv day3.csv --baseline first --output trend.json
psiwatch watch data/ --once --webhook https://hooks.slack.com/services/XXX
psiwatch update
psiwatch version
```

### Library

```python
import psiwatch

psiwatch.compare("old.csv", "new.csv")
psiwatch.compare_data({"age": [22,23]}, {"age": [28,30]})
psiwatch.compare_columns([22,23,21], [28,30,29], name="age")

result = psiwatch.analyze("old.csv", "new.csv")
print(result["health_score"])
print(result["summary"]["drifted_columns"])
print(result["columns"]["age"]["metrics"]["trend_direction"])  # "up" / "down" / "stable"

# Trend across multiple files
trend = psiwatch.analyze_trend(["day1.csv", "day2.csv", "day3.csv"])
print(trend["overall_health_history"])
print(trend["worsening_columns"])

# Watch a directory (cron-safe)
psiwatch.watch_directory("data/", once=True, webhook="https://hooks.slack.com/services/XXX")

# Send webhook manually
psiwatch.send_webhook("https://hooks.slack.com/services/XXX/YYY/ZZZ", result)
```

### Generate test data in Termux

```bash
mkdir ~/testdata && cd ~/testdata
python3 -c "
import random, csv
random.seed(42)
cities_old = ['Chennai','Delhi','Mumbai','Hyderabad','Bangalore']
grades_old = ['A','B','C']
with open('old_data.csv','w',newline='') as f:
    w = csv.writer(f)
    w.writerow(['age','score','city','grade'])
    for i in range(200):
        w.writerow([random.randint(18,24),round(random.gauss(75,8),1),random.choice(cities_old),random.choice(grades_old)])
cities_new = ['Chennai','Pune','Noida','Gurugram','Kochi']
grades_new = ['A','B','C','D','F']
with open('new_data.csv','w',newline='') as f:
    w = csv.writer(f)
    w.writerow(['age','score','city','grade'])
    for i in range(200):
        w.writerow([random.randint(17,22),round(random.gauss(55,12),1),random.choice(cities_new),random.choice(grades_new)])
print('Done')
"
psiwatch compare old_data.csv new_data.csv
```

---

## Publishing to PyPI from Termux

> Standard tools like twine are broken on Termux/Android. Here is what actually works.

### Step 1 — Create PyPI account

Go to https://pypi.org/account/register, create account, verify email.

### Step 2 — Create API token

Go to https://pypi.org/manage/account/token, create token, copy it. Starts with `pypi-`.

### Step 3 — Save token to file

```bash
nano ~/token.txt
# paste your token
# Ctrl+X → Y → Enter
```

### Step 4 — Install build tools

```bash
pip install build --no-build-isolation --break-system-packages
pip install requests --break-system-packages
```

### Step 5 — Build the package

```bash
cd ~/psiwatch
python -m build
```

### Step 6 — Create upload script

Standard `twine` is broken on Termux. Use this custom upload script instead:

```bash
cat > ~/upload.py << 'UPLOADEOF'
import requests, os, hashlib

token = open(os.path.expanduser('~/token.txt')).read().strip()
readme = open(os.path.expanduser('~/psiwatch/README.md')).read()
VERSION = '0.10.0'  # bump this every upload

for fname in os.listdir('/data/data/com.termux/files/home/psiwatch/dist/'):
    if not fname.endswith(('.whl', '.tar.gz')):
        continue
    fpath = f'/data/data/com.termux/files/home/psiwatch/dist/{fname}'
    with open(fpath, 'rb') as f:
        data = f.read()
    md5 = hashlib.md5(data).hexdigest()
    r = requests.post(
        'https://upload.pypi.org/legacy/',
        auth=('__token__', token),
        files={'content': (fname, data, 'application/octet-stream')},
        data={
            ':action': 'file_upload',
            'protocol_version': '1',
            'name': 'psiwatch',
            'version': VERSION,
            'metadata_version': '2.1',
            'filetype': 'sdist' if fname.endswith('.tar.gz') else 'bdist_wheel',
            'pyversion': 'source' if fname.endswith('.tar.gz') else 'py3',
            'md5_digest': md5,
            'description': readme,
            'description_content_type': 'text/markdown',
            'summary': 'Dataset drift detection for ML pipelines.',
        }
    )
    print(fname, r.status_code, r.text[:200])
UPLOADEOF
```

### Step 7 — Upload

```bash
python3 ~/upload.py
```

### Step 8 — Verify

```bash
pip install psiwatch
psiwatch compare samples/train.csv samples/new.csv
```

---

## Updating the package

PyPI never allows the same version twice. Always bump version before uploading.

```bash
# 1. Bump version in pyproject.toml
sed -i 's/version = "OLD"/version = "NEW"/' ~/psiwatch/pyproject.toml

# 2. Bump version in __init__.py
sed -i 's/__version__ = "OLD"/__version__ = "NEW"/' ~/psiwatch/src/psiwatch/__init__.py

# 3. Bump version in upload.py
sed -i "s/VERSION = 'OLD'/VERSION = 'NEW'/" ~/upload.py

# 4. Clean old build files
rm -rf ~/psiwatch/dist

# 5. Rebuild
cd ~/psiwatch && python -m build

# 6. Upload
python3 ~/upload.py
```

---

## Run Tests

```bash
cd ~/psiwatch
pip install -e ".[dev]" --break-system-packages
pytest
```

CI runs this automatically on every push/PR across Python 3.8–3.13.

---

## Errors Faced & Solutions

### Error 1 — nh3 build failure (Rust not found)

```
ERROR: Failed to build 'nh3' when installing build dependencies
Rust not found, installing into a temporary directory
Target triple not supported by rustup: aarch64-unknown-linux-android
```

**Cause:** Latest twine requires `nh3` which needs Rust. Termux on Android doesn't support Rust.

**Fix:**
```bash
pip install build --no-build-isolation --break-system-packages
# skip twine entirely, use custom upload.py script above
```

---

### Error 2 — twine broken on Python 3.13

```
KeyError: 'license'
importlib_metadata.PackageNotFoundError: No package metadata was found for readme-renderer
ModuleNotFoundError: No module named 'colorama'
ModuleNotFoundError: No module named 'rich'
ModuleNotFoundError: No module named 'id'
```

**Cause:** twine 3.x and 4.x both broken on Python 3.13 in Termux.

**Fix:** Skip twine entirely. Use the custom `upload.py` script that uses only `requests`.

---

### Error 3 — Storage permission denied

```
bash: cd: /sdcard/Download: Permission denied
ls: cannot access '/data/data/com.termux/files/home/storage/': No such file or directory
```

**Fix:**
```bash
termux-setup-storage
# tap Allow when prompted
ls ~/storage/shared/
```

If permission dialog doesn't appear:
- Go to phone Settings → Apps → Termux → Permissions → Storage → Allow
- Then run `termux-setup-storage` again

---

### Error 4 — File already exists on PyPI

```
400 File already exists ('psiwatch-0.1.0.tar.gz')
```

**Cause:** PyPI never allows uploading the same version twice.

**Fix:** Bump all three version locations (pyproject.toml, `__init__.py`, upload.py), clean dist/, rebuild.

---

### Error 5 — Only one sdist may be uploaded per release

```
400 Only one sdist may be uploaded per release
400 Version in filename should be '0.1.0' not '0.2.0'
```

**Cause:** Old and new build files mixed in dist/ folder.

**Fix:**
```bash
rm -rf ~/psiwatch/dist
python -m build
python3 ~/upload.py
```

---

### Error 6 — No description showing on PyPI

**Cause 1:** README uses HTML tags — PyPI doesn't render `<p>`, `<img>`, `<div>` tags.

**Fix:** Use plain markdown only in README. No HTML tags.

**Cause 2:** Upload script not sending description field to PyPI API.

**Fix:** Use the upload script from Step 6 above — it explicitly sends `description` and `description_content_type` fields.

---

### Error 7 — Mirror error during pkg update

```
E: Failed to fetch https://termux.niranjan.co/termux-main
File has unexpected size (549095 != 549815)
```

**Fix:**
```bash
termux-change-repo
# select Single mirror → Grimler or A-Lex
pkg update && pkg upgrade
```

---

### Error 8 — No such file or directory for project

```
bash: cd: ~/psiwatch: No such file or directory
Source does not appear to be a Python project: no pyproject.toml
```

**Fix:**
```bash
pkg install git -y
git clone https://github.com/tharunstryker/psiwatch
cd psiwatch
```

---

### Error 9 — Can't paste token in Termux

**Fix:** Save token to a file instead of pasting interactively.

```bash
nano ~/token.txt
# type or paste token
# Ctrl+X → Y → Enter to save

cat ~/token.txt  # verify
```

---

### Error 10 — ModuleNotFoundError during upload

```
ModuleNotFoundError: No module named 'requests'
```

**Fix:**
```bash
pip install requests --break-system-packages
```

---

## Quick Reference

### First time publish

```bash
cd ~/psiwatch
pip install build --no-build-isolation --break-system-packages
pip install requests --break-system-packages
python -m build
python3 ~/upload.py
```

### Every update

```bash
# Bump version in all 3 places
sed -i 's/version = "X.X.X"/version = "Y.Y.Y"/' ~/psiwatch/pyproject.toml
sed -i 's/__version__ = "X.X.X"/__version__ = "Y.Y.Y"/' ~/psiwatch/src/psiwatch/__init__.py
sed -i "s/VERSION = 'X.X.X'/VERSION = 'Y.Y.Y'/" ~/upload.py

rm -rf ~/psiwatch/dist
cd ~/psiwatch && python -m build
python3 ~/upload.py
```

### Run tests

```bash
cd ~/psiwatch
pip install -e ".[dev]" --break-system-packages
pytest
```

### Locate files in Termux

```bash
ls ~/
find / -name "yourfile.csv" 2>/dev/null
ls ~/storage/shared/Download/   # after termux-setup-storage
```

---

## Key Lessons

1. **twine doesn't work on Termux** — use a custom requests-based upload script
2. **PyPI needs plain markdown** — no HTML tags in README
3. **Bump version in 3 places** — pyproject.toml, `__init__.py`, upload.py
4. **Always clean dist/ before rebuilding** — old files cause version conflicts
5. **Storage permission in Termux is separate** — run `termux-setup-storage` and allow in settings
6. **Build everything in Termux home** (`~/`) — no storage permission issues
7. **`psiwatch update` works on Termux** — uses `sys.executable` so it upgrades the right Python env

---

## Built entirely on Android

This project was built on an Android phone using Termux with no laptop, no PC, and no IDE.

- Language: Python 3.13
- Terminal: Termux
- Version control: Git
- Published: PyPI
- Pair programming: Claude AI

---

*MIT © 2026 Tharun · Naeris · Aevra Studio*
