"""
locker.py — Baseline locking for psiwatch.

Saves a statistical fingerprint of a CSV to a .lock.json file.
Future runs compare against the lock instead of the original CSV.

v0.12.0 fix: the lock file now stores a bounded statistical fingerprint
(mean/std/percentiles + a 10-bin histogram for numeric columns, category
frequencies for categorical columns) instead of every raw row value. A
lock for a 1,000,000-row baseline is now a few KB, not a copy of the
dataset. Old lock files saved before this fix used the legacy
"values_sample" format and will raise a clear error — re-run
`psiwatch lock` to regenerate them in the new format.

Usage:
    # CLI
    psiwatch lock train.csv                      # creates psiwatch.lock.json
    psiwatch lock train.csv --output model.lock.json
    psiwatch check new.csv                       # compares against psiwatch.lock.json
    psiwatch check new.csv --lock model.lock.json
    psiwatch lock-info                           # show what's in the current lock

    # Python
    from psiwatch.locker import save_lock, load_lock, lock_info
    save_lock("train.csv")
    result = load_lock("new.csv")
    print(result["health_score"])
"""

import json
import os
from datetime import datetime

DEFAULT_LOCK_FILE = "psiwatch.lock.json"
LOCK_FORMAT_VERSION = "2"


def _summarize(col_data):
    """
    Build a bounded statistical fingerprint of a column dict — O(bins) for
    numeric columns, O(unique categories) for categorical columns. Never
    stores raw row-level values.
    """
    from .analyzer import build_numeric_summary, build_categorical_summary
    from .loader import detect_type, cast_numeric

    snapshot = {}
    for col, values in col_data.items():
        col_type = detect_type(values)
        entry = {"type": col_type, "count": len(values)}

        if col_type == "numeric":
            nums = cast_numeric(values)
            summary = build_numeric_summary(nums)
            if summary:
                entry["summary"] = summary
        else:
            summary = build_categorical_summary(values)
            if summary:
                entry["summary"] = summary

        snapshot[col] = entry
    return snapshot


def save_lock(source, lock_path=DEFAULT_LOCK_FILE, columns=None):
    """
    Save a statistical fingerprint of source to a lock file.

    Args:
        source: CSV path, dict, list of dicts, or DataFrame
        lock_path: where to write the lock file (default: psiwatch.lock.json)
        columns: optional list of columns to lock (default: all)

    Returns:
        dict — the lock data that was saved
    """
    from .loader import resolve_input

    col_data = resolve_input(source)
    if columns:
        col_data = {k: v for k, v in col_data.items() if k in columns}

    # Build source label
    if isinstance(source, str):
        source_label = os.path.basename(source)
    else:
        source_label = type(source).__name__

    lock = {
        "psiwatch_lock": True,
        "version": LOCK_FORMAT_VERSION,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source_label,
        "columns": _summarize(col_data),
    }

    with open(lock_path, "w", encoding="utf-8") as f:
        json.dump(lock, f, indent=2)

    print(f"  Lock saved → {lock_path}")
    print(f"  Locked {len(lock['columns'])} columns from {source_label}")
    return lock


def _lock_to_summaries(lock):
    """
    Build the baseline_summaries dict that analyzer.analyze() expects,
    from a v2 lock file's per-column fingerprints.
    """
    summaries = {}
    for col, entry in lock["columns"].items():
        if "summary" not in entry:
            continue
        summaries[col] = {"type": entry["type"], "summary": entry["summary"]}
    return summaries


def load_lock(new_source, lock_path=DEFAULT_LOCK_FILE, output=None,
              columns=None, ignore_columns=None, psi_threshold=None,
              thresholds=None, fail_on_drift=False):
    """
    Compare new_source against an existing lock file.

    Args:
        new_source: CSV path, dict, list of dicts, or DataFrame
        lock_path: path to lock file (default: psiwatch.lock.json)
        output: optional report path (.json, .txt, .html)
        columns: optional list to compare
        ignore_columns: optional list to skip
        psi_threshold: PSI threshold override
        thresholds: dict of threshold overrides
        fail_on_drift: raise DriftDetected if health_score < 80

    Returns:
        dict — same shape as analyze() result
    """
    from .loader import resolve_input
    from .analyzer import analyze as _analyze
    from .reporter import output_report
    from . import DriftDetected, _build_thresholds

    if not os.path.exists(lock_path):
        raise FileNotFoundError(
            f"Lock file not found: {lock_path}\n"
            f"Run `psiwatch lock <baseline.csv>` first."
        )

    with open(lock_path, "r", encoding="utf-8") as f:
        lock = json.load(f)

    if not lock.get("psiwatch_lock"):
        raise ValueError(f"{lock_path} is not a valid psiwatch lock file.")

    if lock.get("version") == "1" or any(
        "values_sample" in entry for entry in lock.get("columns", {}).values()
    ):
        raise ValueError(
            f"{lock_path} was created by an older psiwatch version (lock format v1) "
            f"that stored raw row data instead of a fingerprint. Re-run "
            f"`psiwatch lock <baseline.csv> --output {os.path.basename(lock_path)}` "
            f"to regenerate it in the current format."
        )

    baseline_summaries = _lock_to_summaries(lock)
    new_cols = resolve_input(new_source)

    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    result = _analyze({}, new_cols, columns=columns,
                      ignore_columns=ignore_columns, thresholds=t,
                      baseline_summaries=baseline_summaries)

    locked_at = lock.get("created_at", "unknown")
    source_info = f"lock: {os.path.basename(lock_path)} (created {locked_at})"
    output_report(result, output=output, source_info=source_info)

    if fail_on_drift and result["health_score"] < 80:
        high_cols = [c for c, r in result["columns"].items() if r["severity"] == "HIGH"]
        raise DriftDetected(
            f"Drift detected vs lock — health score: {result['health_score']}/100. "
            f"HIGH columns: {high_cols}"
        )

    return result


def lock_info(lock_path=DEFAULT_LOCK_FILE):
    """
    Print a summary of what's stored in a lock file.
    """
    if not os.path.exists(lock_path):
        print(f"  No lock file found at: {lock_path}")
        return None

    with open(lock_path, "r", encoding="utf-8") as f:
        lock = json.load(f)

    print(f"\n  Lock file: {lock_path}")
    print(f"  Created:   {lock.get('created_at', 'unknown')}")
    print(f"  Source:    {lock.get('source', 'unknown')}")
    print(f"  Columns:   {len(lock['columns'])}")
    print()

    for col, entry in lock["columns"].items():
        col_type = entry.get("type", "?")
        count = entry.get("count", "?")
        summary = entry.get("summary", {})
        if col_type == "numeric":
            print(f"  {col} [numeric, n={count}]")
            print(f"    mean={summary.get('mean')}  std={summary.get('std')}")
            print(f"    min={summary.get('min')}  p25={summary.get('p25')}  "
                  f"median={summary.get('median')}  p75={summary.get('p75')}  max={summary.get('max')}")
        else:
            cats = summary.get("categories", [])
            print(f"  {col} [categorical, n={count}, {len(cats)} categories]")
            print(f"    {cats[:8]}{'...' if len(cats) > 8 else ''}")
    print()
    return lock
