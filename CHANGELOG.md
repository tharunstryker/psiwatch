# Changelog

All notable changes to psiwatch, newest first. Installed psiwatch shows the highlights of your version with `psiwatch version`.

## v0.15.1
- **Added:** `psiwatch version` now also prints the highlights of the installed release and a link to the full changelog. `psiwatch version --short` prints only the number, for scripts.
- **Docs:** README restructured — Install and Quickstart come first (`pip install psiwatch`), sections are grouped (Usage, Text Drift, Understanding the Report, Monitoring, Configuration, Development), and the hard-coded version line was removed. Release history now lives in this file.
- **Project:** GitHub Actions CI added to the repository (pytest on Python 3.8–3.13, package build, version-consistency and zero-dependency checks).
- Tests: 99 (+6 checks that every release has notes in `whatsnew.py` and `CHANGELOG.md`).

## v0.15.0
- **Added:** free-text column drift. Columns of sentences (chat messages, reviews, tickets, queries) are auto-detected and analysed for vocabulary drift (noise-corrected Jensen-Shannon divergence), rising/falling/brand-new words, unseen-word rate (Good-Turing corrected), script/language mix, length, and structure (empty, duplicate, URL, digit, upper-case, symbol rates). Pure Python, zero dependencies, no models. Works in `compare`, `analyze`, `summary`, `lock`/`check`, `trend`, `--plot` and `--embed-chart`.
  - `--text-columns a,b` / `text_columns=[...]` forces text analysis; `--no-text-detect` / `detect_text=False` restores pre-0.15 behaviour (text treated as categorical).
  - New thresholds: `text_jsd_medium/high`, `text_oov_medium/high`, `text_script_shift_medium/high`, `text_structure_shift`. New config keys: `text_columns`, `detect_text`.
  - Behaviour change: a free-text column that used to be reported as `[categorical]` is now reported as `[text]`.
  - Lock files gain a `text` column type (bounded: top-1,000 word counts + scalars). Locks containing text columns cannot be read by psiwatch < 0.15.
- **Fixed (README):** removed the non-existent `--config` flag; replaced the competitor comparison (unverified "No" claims and wrong sizes) with dependency counts and wheel sizes measured from PyPI metadata; corrected the package size (~74 KB wheel, not ~15 KB); replaced stale hand-rolled test output with the real pytest summary.
- Tests: 93 (53 existing + 40 new, including noise-calibration tests that require healthy data to stay PASS, and checks that every release has notes).

## v0.14.0
- **Added:** `psiwatch.viz.plot_drift()` — real baseline-vs-new histogram overlay charts (numeric columns) and category frequency comparisons (categorical columns), saved as a PNG/PDF/SVG. Built from the exact same binned histogram data PSI itself uses — not an approximation from summary stats.
  - `psiwatch compare old.csv new.csv --plot drift.png`
  - `psiwatch compare old.csv new.csv --plot drift.png --plot-style seaborn-v0_8-darkgrid`
  - Python: `from psiwatch.viz import plot_drift; plot_drift("old.csv", "new.csv", output="drift.png")`
  - Customization: `title=` and `dpi=` params (`plot_drift(..., title="Q3 Sales Drift", dpi=200)`) for presentation-ready output.
  - **Requires `matplotlib`** — install with `pip install psiwatch[charts]` or `pip install matplotlib`. This is the one deliberate exception to psiwatch's zero-dependency core: matplotlib is imported lazily *inside* `plot_drift()`/`plot_drift_bytes()` only, never at module load, so `import psiwatch` and every other feature remain fully dependency-free regardless of whether matplotlib is installed.
  - **No seaborn dependency, by design:** modern matplotlib ships several seaborn-derived style sheets built in (`seaborn-v0_8`, `seaborn-v0_8-darkgrid`, etc. — see `--plot-style`), so you get seaborn's visual look without psiwatch importing seaborn itself. If you want actual seaborn-specific plot types for your own custom analysis, install seaborn yourself and work with psiwatch's result data directly — psiwatch doesn't broker that.
- **Added:** `--embed-chart` — embeds the drift chart directly into an HTML report as an inline base64 image, instead of a separate chart file to keep track of alongside the report.
  - `psiwatch compare old.csv new.csv --output report.html --embed-chart`
  - Python: `psiwatch.compare(old, new, output="report.html", embed_chart=True)`
  - Silently ignored (no error) if `--output` isn't `.html`, or if no `--output` is given at all — only raises if you actually requested embedding and matplotlib is missing.
  - Uses a new `psiwatch.viz.plot_drift_bytes()` that returns PNG bytes in memory rather than writing a file, sharing the same chart-building logic as `plot_drift()` (no duplicated drawing code between the file and embedded paths).

## v0.13.0
- **Added:** `psiwatch learn-thresholds` — learns a per-column PSI threshold from a sequence of historical "normal" snapshots, instead of using one fixed global threshold for every column. Columns with naturally higher variance get a more lenient learned threshold; naturally stable columns keep a tight one. Uses `mean + sensitivity*std` over historical PSI (default sensitivity 3.0), clamped between 0.125 and 0.75 so it can never become dangerously lenient or impractically strict. Saves to a JSON file (default `psiwatch_thresholds.json`).
  - `psiwatch learn-thresholds day1.csv day2.csv ... --output thresholds.json`
  - `psiwatch learn-thresholds --dir history/ --output thresholds.json`
  - `psiwatch compare new_base.csv new_data.csv --thresholds-file thresholds.json`
  - **Scope note:** only the PSI threshold is learned/adapted. `mean_shift_high`/`std_shift_high` and other checks still use the global default — severity is the worst of all checks combined, so a column can still be flagged HIGH via a real mean/std shift even when its learned PSI threshold says PSI itself is within normal historical range.
  - **Data size note:** PSI is sensitive to sample size — snapshots under ~500 rows can produce learned thresholds that don't make intuitive sense (a tightly-distributed column can appear noisier than a widely-distributed one purely from bin-edge sensitivity at low N). `learn-thresholds` warns when any snapshot is under 500 rows.
- **Added:** runnable Java and JavaScript examples (`docs/examples/`) showing how to call the `psiwatch` CLI as a subprocess and parse its JSON report — no psiwatch code changes needed, since this already worked for any language capable of running a subprocess and parsing JSON. See `docs/java-interop.md`.

## v0.12.2
- **Added:** Parquet file support — `compare()`, `analyze()`, and the CLI `compare` command now accept `.parquet`/`.pq` file paths anywhere a CSV path is accepted, auto-detected by extension. Requires `pandas` + `pyarrow` to be installed (optional — psiwatch's core stays zero-dependency).
- **Added:** `load_sql(query, connection)` in `psiwatch.loader` — run a SQL query against any DB-API connection you already have open (`sqlite3`, `psycopg2`, `pymysql`, SQLAlchemy, etc.) and feed the result straight into `compare_data()`. psiwatch does not bundle or require any DB driver — bring your own connection.
- **Fixed:** values like `"NaN"`, `"inf"`, `"-Infinity"` were silently accepted by `float()` and could crash `compare()`/`analyze()` downstream during PSI binning. `cast_numeric()` now explicitly rejects NaN/infinity, treating them the same as any other unparseable value.
- **Fixed:** numeric columns with non-numeric/garbage values (including the NaN/inf case above) were silently dropped with no indication anywhere in the report — `new_count` would just be smaller than expected. A warning now reports exactly how many values (and what %) were excluded, on both the baseline and new side.

## v0.12.1
- **Fixed:** package metadata in `pyproject.toml` — corrected author name/email and switched `license` to the SPDX-string format expected by current packaging tooling. No code changes.

## v0.12.0 — security & bug-fix release (no new features)
- **Fixed:** `psiwatch lock` was storing the entire raw baseline dataset inside the lock file (under `values_sample`) instead of a statistical fingerprint — a 10,000-row baseline produced a multi-MB lock file containing your original training data. Lock files now store mean/std/percentiles plus a 10-bin histogram (numeric) or category frequencies (categorical) — bounded size regardless of dataset size, and no raw rows. Lock files created before this fix are detected and rejected with a message to re-run `psiwatch lock`.
- **Fixed:** HTML reports (`to_html()`, `to_html_trend()`) interpolated column names, category values, and source filenames directly into the page — and into an inline `<script>` block for the trend chart — with no escaping. A column name or category value containing `<script>...</script>` would execute when the report was opened in a browser. All interpolated content is now HTML-escaped, with an additional guard against `</script>` breakout in the chart's JSON payload.
- **Fixed:** `import psiwatch` made a network call to PyPI on every import (the update-check banner), even inside training pipelines, notebooks, or CI steps that never touch the CLI. The check now only runs from the `psiwatch` CLI itself; plain `import psiwatch` makes zero network calls. `compare()`'s `silent_update` parameter is now a documented no-op (kept so existing calls don't break) since the check it used to suppress no longer happens at that call site.
- Test suite converted from a standalone script with a hand-rolled pass/fail counter (no real `assert`s, never run by CI) into a real `pytest` suite across 6 files, including dedicated regression tests for all three fixes above. Added `.github/workflows/ci.yml` running the suite on Python 3.8–3.13 plus a package-build and version-consistency check on every push and pull request.

## v0.11.0
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

## v0.10.1
- `result["summary"]` in `analyze()` — `high_count`, `medium_count`, `pass_count`, `drifted_columns`, `stable_columns`, `total_columns`
- Sample size warning — fires when baseline and new data differ by more than 10x (PSI unreliable at extreme size ratios)
- `--ignore-columns / -x` flag — skip columns by name (IDs, timestamps, row numbers)
- `psiwatch summary` command — one-line health score for shell scripts without a full report
- `psiwatch lock` / `check` / `lock-info` — baseline locking: save a statistical fingerprint of training data, ship it with your model, check against it in CI without the original CSV

## v0.10.0
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

## v0.9.0 (previous)
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

## v0.2.0
- Custom threshold configuration (`psi_threshold`, `thresholds` dict)
- Column filtering (`columns` parameter)
- HTML report output
- `analyze()` function for programmatic access

## v0.1.0
- Initial release
- CSV comparison via CLI and Python API
- PSI, Mean Shift, Std Shift, Chi-Square, New Category detection
- Terminal, JSON, TXT output
- Zero dependencies
