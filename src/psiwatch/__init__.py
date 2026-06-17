"""
psiwatch — Dataset drift detection library.

    import psiwatch

    # Compare files, dicts, DataFrames
    psiwatch.compare("old.csv", "new.csv")
    psiwatch.compare("old.csv", "new.csv", output="report.html")
    psiwatch.compare(old_df, new_df)
    psiwatch.compare_data({"age": [22,23]}, {"age": [28,30]})
    psiwatch.compare_columns([22,23,21], [28,30,29], name="age")

    # Raw result — no output
    result = psiwatch.analyze("old.csv", "new.csv")
    print(result["health_score"])
    print(result["summary"]["drifted_columns"])
    print(result["summary"]["high_count"])

    # CI/CD — fail on drift
    psiwatch.compare("train.csv", "new.csv", fail_on_drift=True)

    # Baseline locking
    psiwatch.save_lock("train.csv")
    psiwatch.load_lock("new.csv", fail_on_drift=True)
    psiwatch.lock_info()

    # Trend
    from psiwatch.trend import analyze_trend, print_trend, to_html_trend
    result = analyze_trend(["week1.csv", "week2.csv", "week3.csv"])
    result = analyze_trend(["w1.csv", "w2.csv", "w3.csv"], baseline="first")
    print(result["worsening_columns"])

    # Watch mode
    from psiwatch.watcher import watch_directory
    watch_directory("data/", once=True)
    watch_directory("data/", lock_path="train.lock.json", webhook="https://...")

    # Webhook
    from psiwatch.webhook import send_webhook
    send_webhook("https://hooks.slack.com/...", result)
"""

import os
from .loader import resolve_input
from .analyzer import analyze as _analyze
from .reporter import output_report
from .updater import check_for_update

__version__ = "0.12.0"
__all__ = [
    "compare", "compare_data", "compare_columns", "analyze",
    "DriftDetected", "save_lock", "load_lock", "lock_info",
    "analyze_trend", "watch_directory", "write_example_config",
]

# v0.12.0 fix: `import psiwatch` no longer makes a network call to PyPI.
# Previously this ran unconditionally on every import — including when
# psiwatch is imported inside a training pipeline, notebook, or CI step
# that never calls the CLI — adding a silent ~3s network dependency to
# code that just wanted the library. The update-check banner is now only
# triggered by the `psiwatch` CLI entry point (see cli.py main()), which
# is the only context where a human is actually watching the terminal
# output. Library users who *do* want the check can opt in explicitly:
#
#     from psiwatch.updater import check_for_update
#     check_for_update(psiwatch.__version__)


# ─── Threshold builder (used by locker, watcher, trend) ──────────────────────

def _build_thresholds(psi_threshold=None, thresholds=None):
    merged = {}
    if psi_threshold is not None:
        if not isinstance(psi_threshold, (int, float)) or psi_threshold <= 0:
            raise ValueError("psi_threshold must be a positive number")
        merged["psi_medium"] = round(psi_threshold * 0.4, 6)
        merged["psi_high"] = float(psi_threshold)
    if thresholds:
        if not isinstance(thresholds, dict):
            raise TypeError("thresholds must be a dict")
        merged.update(thresholds)
    return merged if merged else None


# ─── Source label ─────────────────────────────────────────────────────────────

def _source_label(old, new):
    def name(s):
        if isinstance(s, str):
            return os.path.basename(s)
        try:
            import pandas as pd
            if isinstance(s, pd.DataFrame):
                return f"DataFrame({len(s)} rows)"
        except ImportError:
            pass
        if isinstance(s, dict):
            return f"dict({len(next(iter(s.values())))} rows)"
        if isinstance(s, list):
            return f"list({len(s)} items)"
        return type(s).__name__
    return f"baseline: {name(old)}  →  new: {name(new)}"


# ─── Public API ───────────────────────────────────────────────────────────────

def compare(old, new, output=None, columns=None, ignore_columns=None,
            psi_threshold=None, thresholds=None, fail_on_drift=False,
            silent_update=False, silent_save=False):
    """
    Compare two datasets and print or save a drift report.

    Args:
        old: CSV path, dict, list of dicts, or pandas DataFrame — baseline
        new: CSV path, dict, list of dicts, or pandas DataFrame — new data
        output: optional file path (.json, .txt, .html)
        columns: optional list — compare only these columns
        ignore_columns: optional list — skip these columns
        psi_threshold: sets the HIGH drift PSI boundary (medium auto-scales to 40%)
        thresholds: dict of fine-grained threshold overrides
        fail_on_drift: raises DriftDetected if health_score < 80
        silent_update: deprecated, no-op as of v0.12.0. The PyPI update-check
            banner no longer runs from library code (compare/analyze/etc) —
            it only fires from the `psiwatch` CLI, gated by --silent there.
            Kept here only so existing calls with silent_update=... don't break.

    Returns:
        dict — keys: 'columns', 'health_score', 'warnings', 'summary'
    """
    baseline = resolve_input(old)
    current = resolve_input(new)
    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    result = _analyze(baseline, current, columns=columns,
                      ignore_columns=ignore_columns, thresholds=t)
    source_info = _source_label(old, new)
    output_report(result, output=output, source_info=source_info, silent=silent_save)

    if fail_on_drift and result["health_score"] < 80:
        high_cols = [c for c, r in result["columns"].items() if r["severity"] == "HIGH"]
        raise DriftDetected(
            f"Drift detected — health score: {result['health_score']}/100. "
            f"HIGH columns: {high_cols}"
        )
    return result


def compare_data(old_data, new_data, output=None, columns=None,
                 ignore_columns=None, psi_threshold=None, thresholds=None,
                 fail_on_drift=False):
    """Compare dicts, lists of dicts, or DataFrames. Alias for compare()."""
    return compare(old_data, new_data, output=output, columns=columns,
                   ignore_columns=ignore_columns, psi_threshold=psi_threshold,
                   thresholds=thresholds, fail_on_drift=fail_on_drift)


def compare_columns(old_list, new_list, name="column", output=None,
                    psi_threshold=None, thresholds=None, fail_on_drift=False):
    """Compare two plain Python lists (single column)."""
    baseline = resolve_input(old_list, column_name=name)
    current = resolve_input(new_list, column_name=name)
    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    result = _analyze(baseline, current, thresholds=t)
    output_report(result, output=output)
    if fail_on_drift and result["health_score"] < 80:
        raise DriftDetected(
            f"Drift detected in column '{name}' — health score: {result['health_score']}/100"
        )
    return result


def analyze(old, new, columns=None, ignore_columns=None,
            psi_threshold=None, thresholds=None):
    """
    Run drift analysis — returns raw result dict, no output, no side effects.

    Returns dict with:
        'columns'      — per-column analysis
        'health_score' — 0-100 (100 = no drift)
        'warnings'     — dataset-level schema / size warnings
        'summary'      — {high_count, medium_count, pass_count, unknown_count,
                          total_columns, drifted_columns, stable_columns}
    """
    baseline = resolve_input(old)
    current = resolve_input(new)
    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    return _analyze(baseline, current, columns=columns,
                    ignore_columns=ignore_columns, thresholds=t)


# ─── Lock API ─────────────────────────────────────────────────────────────────

from .locker import save_lock, load_lock, lock_info

# ─── Trend API ────────────────────────────────────────────────────────────────

from .trend import analyze_trend, print_trend, to_html_trend, output_trend

# ─── Watch API ────────────────────────────────────────────────────────────────

from .watcher import watch_directory

# ─── Config API ───────────────────────────────────────────────────────────────

from .config import load_config, write_example_config

# ─── Webhook API ──────────────────────────────────────────────────────────────

from .webhook import send_webhook, build_payload, format_message


# ─── Exception ────────────────────────────────────────────────────────────────

class DriftDetected(Exception):
    """
    Raised when fail_on_drift=True and health_score < 80.

        from psiwatch import DriftDetected
        try:
            psiwatch.compare("train.csv", "new.csv", fail_on_drift=True)
        except DriftDetected as e:
            print(f"Blocked: {e}")
    """
    pass
