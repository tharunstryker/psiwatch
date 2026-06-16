"""
locker.py — Baseline locking for psiwatch.

Saves a statistical fingerprint of a CSV to a .lock.json file.
Future runs compare against the lock instead of the original CSV.

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


def _summarize(col_data):
    """Build a compact statistical fingerprint of a column dict."""
    from .analyzer import (
        _mean, _std, _percentile, _frequencies,
        _is_numeric, DEFAULT_THRESHOLDS
    )
    from .loader import detect_type, cast_numeric

    snapshot = {}
    for col, values in col_data.items():
        col_type = detect_type(values)
        entry = {"type": col_type, "count": len(values)}

        if col_type == "numeric":
            nums = cast_numeric(values)
            if nums:
                entry["mean"] = round(_mean(nums), 6)
                entry["std"] = round(_std(nums), 6)
                entry["min"] = round(min(nums), 6)
                entry["p25"] = round(_percentile(nums, 25), 6)
                entry["median"] = round(_percentile(nums, 50), 6)
                entry["p75"] = round(_percentile(nums, 75), 6)
                entry["max"] = round(max(nums), 6)
                entry["values_sample"] = nums  # kept for PSI binning
        else:
            strs = [str(v) for v in values]
            freq = _frequencies(strs)
            entry["categories"] = sorted(set(strs))
            entry["frequencies"] = freq
            entry["values_sample"] = strs

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
        "version": "1",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source_label,
        "columns": _summarize(col_data),
    }

    with open(lock_path, "w", encoding="utf-8") as f:
        json.dump(lock, f, indent=2)

    print(f"  Lock saved → {lock_path}")
    print(f"  Locked {len(lock['columns'])} columns from {source_label}")
    return lock


def _lock_to_col_data(lock):
    """Reconstruct column data dict from a lock snapshot for analyze()."""
    col_data = {}
    for col, entry in lock["columns"].items():
        col_data[col] = entry.get("values_sample", [])
    return col_data


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

    baseline_cols = _lock_to_col_data(lock)
    new_cols = resolve_input(new_source)

    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    result = _analyze(baseline_cols, new_cols, columns=columns,
                      ignore_columns=ignore_columns, thresholds=t)

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
        if col_type == "numeric":
            print(f"  {col} [numeric, n={count}]")
            print(f"    mean={entry.get('mean')}  std={entry.get('std')}")
            print(f"    min={entry.get('min')}  p25={entry.get('p25')}  "
                  f"median={entry.get('median')}  p75={entry.get('p75')}  max={entry.get('max')}")
        else:
            cats = entry.get("categories", [])
            print(f"  {col} [categorical, n={count}, {len(cats)} categories]")
            print(f"    {cats[:8]}{'...' if len(cats) > 8 else ''}")
    print()
    return lock
