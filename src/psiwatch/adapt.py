"""
adapt.py — Learns per-column drift thresholds from historical "stable" data.

psiwatch's default thresholds (psi_high=0.25, etc.) are fixed, global numbers
applied to every column equally. That's a reasonable default, but it has a
real blind spot: a column that's naturally noisy (e.g. daily transaction
counts) will trip false HIGH-drift alarms even when nothing's actually
wrong, while a column that's normally rock-stable (e.g. a user's signup
country) could drift meaningfully and still sit under the same generic
threshold.

learn_thresholds() fixes this by computing a threshold PER COLUMN, derived
from that column's own historical PSI variance — not a guess, not ML, just
mean + N standard deviations (a standard outlier-detection heuristic) over
a sequence of snapshots you provide that you know were "normal" (no real
incidents). Columns with more natural noise get a higher (more lenient)
threshold; stable columns keep a tight one.

Safety rule: a learned threshold is NEVER allowed to be weaker (higher) than
some absolute ceiling, and never lower than the existing global default
floor — see MIN_PSI_HIGH / MAX_PSI_HIGH below. This stops the tool from
ever learning its way into being blind to real drift on a column that
happened to be noisy in your training window.

This module does NOT change analyze()/analyze_numeric()'s core severity
logic — it builds learned, per-column psi_high values, then runs analyze()
once per column with that column's own override and merges the results.
Zero changes to the existing analyzer's signatures or behavior.

IMPORTANT SCOPE LIMITATION: only the PSI threshold (psi_high/psi_medium) is
learned and overridden per column. mean_shift_high, std_shift_high, and the
other independent checks in analyze_numeric() still use their global default
values. Severity is the WORST of all checks combined — so a column can still
be flagged HIGH via a large mean/std shift even when its learned PSI
threshold says the PSI itself is within that column's normal historical
range. This is intentional (a real mean shift is still worth knowing about
regardless of PSI calibration), but it means "adaptive" here specifically
means "adaptive PSI sensitivity," not "adaptive on every check."

Usage:
    CLI:
        psiwatch learn-thresholds day1.csv day2.csv day3.csv ... \\
            --output psiwatch_thresholds.json
        psiwatch learn-thresholds --dir history/ --output psiwatch_thresholds.json
        psiwatch compare new_base.csv new_data.csv \\
            --thresholds-file psiwatch_thresholds.json

    Python:
        from psiwatch.adapt import learn_thresholds, save_thresholds, \\
            load_thresholds, compare_with_learned_thresholds

        learned = learn_thresholds(["day1.csv", "day2.csv", "day3.csv"])
        save_thresholds(learned, "psiwatch_thresholds.json")

        result = compare_with_learned_thresholds(
            "new_base.csv", "new_data.csv", "psiwatch_thresholds.json"
        )
"""

import glob
import json
import os
from datetime import datetime

# A learned threshold is clamped into this range no matter what the data says.
# Floor: never tighter than half the global default (0.25 / 2 = 0.125) — keeps
# the tool from becoming hypersensitive on a column that happened to look
# extremely stable in a short training window.
# Ceiling: never more than 3x the global default — keeps the tool from
# learning its way into ignoring real drift on a column that was just noisy
# during the training period (e.g. a one-off promo spike).
MIN_PSI_HIGH = 0.125
MAX_PSI_HIGH = 0.75

DEFAULT_SENSITIVITY = 3.0  # "N" in mean + N*std — 3 is standard for outlier detection


def _resolve_file_list(files=None, directory=None, pattern="*.csv"):
    """Build the final ordered list of snapshot sources from files and/or a directory glob."""
    result = []
    if files:
        result.extend(files)
    if directory:
        matched = sorted(glob.glob(os.path.join(directory, pattern)))
        if not matched:
            raise ValueError(f"No files matching '{pattern}' found in directory: {directory}")
        result.extend(matched)
    if len(result) < 2:
        raise ValueError(
            "learn_thresholds requires at least 2 historical snapshots "
            "(via files=[...] and/or directory=...)"
        )
    return result


def learn_thresholds(files=None, directory=None, pattern="*.csv",
                      columns=None, ignore_columns=None,
                      sensitivity=DEFAULT_SENSITIVITY):
    """
    Learn a per-column psi_high threshold from a sequence of historical
    snapshots that represent normal, non-incident conditions.

    Args:
        files: list of CSV paths, dicts, lists of dicts, or DataFrames —
            at least 2 needed, in chronological order.
        directory: optional folder path — if given, all files matching
            `pattern` inside it are added (sorted by filename) after `files`.
        pattern: glob pattern used with `directory` (default "*.csv").
        columns: optional list — only learn thresholds for these columns.
        ignore_columns: optional list — skip these columns entirely.
        sensitivity: the "N" in mean + N*std. Higher = more lenient learned
            thresholds (fewer false alarms, slower to catch real drift).
            Lower = stricter. Default 3.0 (standard outlier-detection rule).

    Returns:
        dict: {
            "thresholds": {column_name: learned_psi_high, ...},
            "stats": {column_name: {"mean": ..., "std": ..., "samples": ...,
                                     "history": [psi, psi, ...]}, ...},
            "sensitivity": sensitivity,
            "source_files": [...],
            "generated_at": "YYYY-MM-DD HH:MM:SS",
        }

    Raises:
        ValueError: fewer than 2 total snapshots resolved.
    """
    from .trend import analyze_trend

    resolved_files = _resolve_file_list(files, directory, pattern)

    trend_result = analyze_trend(
        resolved_files,
        columns=columns,
        ignore_columns=ignore_columns,
        baseline="previous",
    )

    thresholds = {}
    stats = {}
    warnings = []

    for col, hist in trend_result["column_history"].items():
        psi_values = [v for v in hist["psi_history"] if v is not None]

        if len(psi_values) < 2:
            # Not enough signal to learn anything meaningful for this column —
            # leave it out entirely so it falls back to the global default.
            continue

        mean_psi = sum(psi_values) / len(psi_values)
        variance = sum((v - mean_psi) ** 2 for v in psi_values) / len(psi_values)
        std_psi = variance ** 0.5

        learned = mean_psi + sensitivity * std_psi
        clamped = max(MIN_PSI_HIGH, min(MAX_PSI_HIGH, learned))

        thresholds[col] = round(clamped, 4)
        stats[col] = {
            "mean": round(mean_psi, 4),
            "std": round(std_psi, 4),
            "samples": len(psi_values),
            "history": [round(v, 4) for v in psi_values],
            "raw_learned_value": round(learned, 4),
            "was_clamped": learned != clamped,
        }

    # PSI is sensitive to row count — with small snapshots (a few hundred rows
    # or fewer), normal sampling noise alone can produce PSI swings large
    # enough to make learning unreliable (counterintuitively, a tightly
    # distributed column can show *higher* apparent noise than a widely
    # distributed one purely from bin-edge sensitivity at small N). Warn
    # rather than silently learn from data too thin to trust.
    row_counts = []
    for f in resolved_files:
        try:
            from .loader import resolve_input
            cols = resolve_input(f)
            if cols:
                row_counts.append(len(next(iter(cols.values()))))
        except Exception:
            pass
    if row_counts and min(row_counts) < 500:
        warnings.append(
            f"Smallest snapshot has only {min(row_counts)} rows. Learned "
            f"thresholds from snapshots under ~500 rows can be unreliable — "
            f"PSI's bin-edge sensitivity at low sample sizes can make a "
            f"naturally stable column look noisier than a naturally volatile "
            f"one. Consider using larger snapshots if these thresholds look "
            f"surprising."
        )

    return {
        "thresholds": thresholds,
        "stats": stats,
        "warnings": warnings,
        "sensitivity": sensitivity,
        "source_files": trend_result["files"],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def save_thresholds(learned, filepath):
    """Write a learn_thresholds() result to a JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(learned, f, indent=2)


def load_thresholds(filepath):
    """
    Load a previously saved learn_thresholds() result.

    Raises:
        FileNotFoundError: if filepath doesn't exist.
        ValueError: if the file doesn't look like a valid thresholds file.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Thresholds file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "thresholds" not in data or not isinstance(data["thresholds"], dict):
        raise ValueError(
            f"'{filepath}' doesn't look like a psiwatch thresholds file "
            f"(missing or invalid 'thresholds' key)"
        )

    return data


def compare_with_learned_thresholds(old, new, thresholds_file,
                                     columns=None, ignore_columns=None,
                                     base_thresholds=None):
    """
    Run a normal compare() but use per-column learned psi_high values from
    a thresholds file wherever available, falling back to the global
    default (or base_thresholds, if given) for any column not covered.

    This does NOT modify analyze()/analyze_numeric() — it calls analyze()
    once per column with that column's own threshold override, then merges
    the per-column results back into one report shaped exactly like a
    normal compare() result, so existing report/print/HTML code works
    unmodified.

    Args:
        old: CSV path, dict, list of dicts, or pandas DataFrame — baseline
        new: CSV path, dict, list of dicts, or pandas DataFrame — new data
        thresholds_file: path to a JSON file produced by save_thresholds()
        columns: optional list — compare only these columns
        ignore_columns: optional list — skip these columns
        base_thresholds: optional dict — used as the fallback base for any
            column not present in the learned thresholds file (defaults to
            psiwatch's normal DEFAULT_THRESHOLDS)

    Returns:
        Same shape as psiwatch.compare()'s return value, with an added
        top-level "adaptive_columns" list naming which columns used a
        learned threshold instead of the default.
    """
    from .loader import resolve_input
    from .analyzer import analyze as _analyze, DEFAULT_THRESHOLDS

    learned = load_thresholds(thresholds_file)
    learned_map = learned["thresholds"]

    base = dict(DEFAULT_THRESHOLDS)
    if base_thresholds:
        base.update(base_thresholds)

    old_resolved = resolve_input(old)
    new_resolved = resolve_input(new)

    all_columns = columns or [c for c in old_resolved if c in new_resolved]
    if ignore_columns:
        all_columns = [c for c in all_columns if c not in ignore_columns]

    merged_columns = {}
    adaptive_columns = []
    high_count = medium_count = pass_count = 0

    for col in all_columns:
        col_thresholds = dict(base)
        if col in learned_map:
            col_thresholds["psi_high"] = learned_map[col]
            # keep psi_medium proportionate — 40% of the high threshold,
            # matching the relationship in the global DEFAULT_THRESHOLDS
            col_thresholds["psi_medium"] = round(learned_map[col] * 0.4, 4)
            adaptive_columns.append(col)

        single_result = _analyze(
            {col: old_resolved.get(col, [])},
            {col: new_resolved.get(col, [])},
            thresholds=col_thresholds,
        )

        col_result = single_result["columns"].get(col)
        if col_result is None:
            continue
        merged_columns[col] = col_result

        sev = col_result["severity"]
        if sev == "HIGH":
            high_count += 1
        elif sev == "MEDIUM":
            medium_count += 1
        elif sev == "PASS":
            pass_count += 1

    total = max(high_count + medium_count + pass_count, 1)
    health_score = round(100 * (pass_count + 0.5 * medium_count) / total)

    drifted = [c for c, r in merged_columns.items() if r["severity"] in ("HIGH", "MEDIUM")]
    stable = [c for c, r in merged_columns.items() if r["severity"] == "PASS"]

    return {
        "health_score": health_score,
        "warnings": [],
        "summary": {
            "high_count": high_count,
            "medium_count": medium_count,
            "pass_count": pass_count,
            "drifted_columns": drifted,
            "stable_columns": stable,
        },
        "columns": merged_columns,
        "adaptive_columns": sorted(adaptive_columns),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def print_learned_thresholds(learned):
    """Print a terminal summary of a learn_thresholds() result."""
    thresholds = learned["thresholds"]
    stats = learned["stats"]

    print("\n" + "═" * 62)
    print("  PSIWATCH — LEARNED THRESHOLDS")
    print(f"  Sources ({len(learned['source_files'])}): {' → '.join(learned['source_files'])}")
    print(f"  Sensitivity: {learned['sensitivity']} (mean + {learned['sensitivity']}×std)")
    print(f"  Generated: {learned.get('generated_at', '')}")
    print("═" * 62)

    for w in learned.get("warnings", []):
        print(f"\n  [!] {w}")

    if not thresholds:
        print("\n  No columns had enough historical data to learn a threshold.")
        print("  (Need at least 2 valid PSI comparisons per column.)")
        print("═" * 62 + "\n")
        return

    print(f"\n  {len(thresholds)} column(s) learned:\n")
    for col, value in sorted(thresholds.items()):
        s = stats[col]
        clamp_note = "  [clamped]" if s["was_clamped"] else ""
        print(f"    {col}")
        print(f"      learned psi_high: {value:.4f}{clamp_note}")
        print(f"      historical PSI:   mean={s['mean']:.4f}  std={s['std']:.4f}  "
              f"n={s['samples']}")
    print("\n═" * 1 + "═" * 61)
    print()
