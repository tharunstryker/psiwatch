"""
analyzer.py — Core drift detection engine for psiwatch.
Methods: Mean shift, Std shift, PSI, Chi-square, Frequency comparison.

v0.11.0 additions:
- result["summary"] — high_count, medium_count, pass_count, drifted_columns list
- Sample size warning — warns when baseline/new differ by more than 10x
- ignore_columns support — passed through from public API

v0.12.0 fixes:
- analyze_numeric/analyze_categorical now accept a pre-summarized baseline
  (mean/std/percentiles + fixed-bin histogram or category frequencies)
  instead of requiring raw baseline values. This lets locker.py store a
  bounded fingerprint instead of the entire raw dataset. See
  build_numeric_summary() / build_categorical_summary().
- PSI for numeric columns is now computed from a histogram (10 fixed bins
  over the baseline's own min/max) rather than re-binning raw baseline
  values against the combined baseline+new range on every call. This is
  the standard industry PSI definition and is what locked baselines need
  to be reproducible from a summary alone.
"""

import math
from .loader import detect_type, cast_numeric


# ─── Math Utilities ───────────────────────────────────────────────────────────

def _mean(values):
    return sum(values) / len(values) if values else 0.0

def _variance(values):
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return sum((x - m) ** 2 for x in values) / len(values)

def _std(values):
    return math.sqrt(_variance(values))

def _percentile(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    idx = p / 100 * (len(s) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)

def _frequencies(values):
    total = len(values)
    freq = {}
    for v in values:
        freq[v] = freq.get(v, 0) + 1
    return {k: v / total for k, v in freq.items()}


# ─── PSI ──────────────────────────────────────────────────────────────────────

def _psi_numeric(baseline, new, bins=10):
    all_vals = baseline + new
    min_val, max_val = min(all_vals), max(all_vals)
    if min_val == max_val:
        return 0.0
    bin_width = (max_val - min_val) / bins

    def bin_counts(vals):
        counts = [0] * bins
        for v in vals:
            idx = min(int((v - min_val) / bin_width), bins - 1)
            counts[idx] += 1
        return counts

    base_counts = bin_counts(baseline)
    new_counts = bin_counts(new)
    base_total = len(baseline)
    new_total = len(new)

    psi = 0.0
    for i in range(bins):
        expected = max(base_counts[i] / base_total, 1e-6)
        actual = max(new_counts[i] / new_total, 1e-6)
        psi += (actual - expected) * math.log(actual / expected)
    return round(psi, 4)


def build_numeric_histogram(values, min_val, max_val, bins=10):
    """
    Bin `values` into `bins` fixed-width buckets over [min_val, max_val].
    Used both to compute PSI live and to persist a baseline fingerprint
    (locker.py) that doesn't require storing raw values.
    """
    counts = [0] * bins
    if min_val == max_val:
        # Degenerate range — everything falls in bin 0.
        counts[0] = len(values)
        return counts
    bin_width = (max_val - min_val) / bins
    for v in values:
        idx = min(max(int((v - min_val) / bin_width), 0), bins - 1)
        counts[idx] += 1
    return counts


def _psi_from_histograms(base_counts, base_total, new_counts, new_total):
    """PSI computed from two pre-built histograms of equal bin count."""
    bins = len(base_counts)
    psi = 0.0
    for i in range(bins):
        expected = max(base_counts[i] / base_total, 1e-6) if base_total else 1e-6
        actual = max(new_counts[i] / new_total, 1e-6) if new_total else 1e-6
        psi += (actual - expected) * math.log(actual / expected)
    return round(psi, 4)


def build_numeric_summary(values, bins=10):
    """
    Build a bounded statistical fingerprint of a numeric column for
    locking — O(bins) storage instead of O(n) raw values.

    Returns dict with mean/std/percentiles/min/max/count plus a fixed-bin
    histogram (counts over [min, max]) used to reproduce PSI later.
    """
    nums = values
    if not nums:
        return None
    mn, mx = min(nums), max(nums)
    return {
        "count": len(nums),
        "mean": round(_mean(nums), 6),
        "std": round(_std(nums), 6),
        "min": round(mn, 6),
        "p25": round(_percentile(nums, 25), 6),
        "median": round(_percentile(nums, 50), 6),
        "p75": round(_percentile(nums, 75), 6),
        "max": round(mx, 6),
        "hist_bins": bins,
        "hist_min": round(mn, 6),
        "hist_max": round(mx, 6),
        "hist_counts": build_numeric_histogram(nums, mn, mx, bins=bins),
    }


def build_categorical_summary(values):
    """
    Build a bounded statistical fingerprint of a categorical column for
    locking — O(unique categories) storage instead of O(n) raw values.
    """
    strs = [str(v) for v in values]
    if not strs:
        return None
    freq = _frequencies(strs)
    return {
        "count": len(strs),
        "categories": sorted(set(strs)),
        "frequencies": freq,
    }


def _psi_categorical(baseline_freq, new_freq):
    all_cats = set(baseline_freq) | set(new_freq)
    psi = 0.0
    for cat in all_cats:
        expected = max(baseline_freq.get(cat, 0), 1e-6)
        actual = max(new_freq.get(cat, 0), 1e-6)
        psi += (actual - expected) * math.log(actual / expected)
    return round(psi, 4)


# ─── Chi-Square (O(n)) ────────────────────────────────────────────────────────

def _chi_square(baseline, new):
    base_total = len(baseline)
    new_total = len(new)
    all_cats = set(baseline) | set(new)

    base_counts = {}
    for v in baseline:
        base_counts[v] = base_counts.get(v, 0) + 1

    new_counts = {}
    for v in new:
        new_counts[v] = new_counts.get(v, 0) + 1

    chi2 = 0.0
    for cat in all_cats:
        expected = base_counts.get(cat, 0) / base_total if base_total else 1e-6
        observed = new_counts.get(cat, 0) / new_total if new_total else 0
        expected = max(expected, 1e-6)
        chi2 += ((observed - expected) ** 2) / expected
    return round(chi2, 4)


def _chi_square_from_freq(base_freq, new_freq):
    """Chi-square computed from two frequency (share) dicts directly,
    rather than from raw values. Equivalent to _chi_square() since that
    function only ever uses count/total (i.e. frequency share) per
    category — never row order or raw identity."""
    all_cats = set(base_freq) | set(new_freq)
    chi2 = 0.0
    for cat in all_cats:
        expected = max(base_freq.get(cat, 0), 1e-6)
        observed = new_freq.get(cat, 0)
        chi2 += ((observed - expected) ** 2) / expected
    return round(chi2, 4)


# ─── Thresholds ───────────────────────────────────────────────────────────────

DEFAULT_THRESHOLDS = {
    "psi_medium": 0.1,
    "psi_high": 0.25,
    "mean_shift_medium": 0.2,
    "mean_shift_high": 0.5,
    "std_shift_medium": 0.2,
    "std_shift_high": 0.5,
    "category_share_shift": 0.15,
    "chi_square_medium": 0.5,
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _severity_from_psi(psi, thresholds):
    if psi > thresholds["psi_high"]:
        return "HIGH"
    elif psi > thresholds["psi_medium"]:
        return "MEDIUM"
    return "PASS"

def _worst(a, b):
    order = ["PASS", "MEDIUM", "HIGH", "UNKNOWN"]
    return a if order.index(a) >= order.index(b) else b

def _is_numeric(v):
    try:
        float(v)
        return True
    except (ValueError, TypeError):
        return False


# ─── Column Analyzers ─────────────────────────────────────────────────────────

def analyze_numeric(baseline_raw, new_raw, thresholds=None, baseline_summary=None):
    """
    Compare baseline vs new for a numeric column.

    Args:
        baseline_raw: list of raw baseline values. Ignored if baseline_summary
            is provided (pass None or [] in that case).
        new_raw: list of raw new values — always required, always raw.
        thresholds: optional threshold overrides.
        baseline_summary: optional pre-built summary from build_numeric_summary().
            When given, baseline stats/PSI are computed from this fingerprint
            instead of from baseline_raw. Used by locker.py so a locked
            baseline doesn't need to carry the original raw dataset around.
    """
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    new = cast_numeric(new_raw)

    if baseline_summary is not None:
        b_count = baseline_summary["count"]
        if b_count < 2 or len(new) < 2:
            return {"severity": "UNKNOWN", "reasons": ["Insufficient numeric data"], "metrics": {}, "warnings": []}
        b_mean, b_std = baseline_summary["mean"], baseline_summary["std"]
        b_min, b_p25, b_median, b_p75, b_max = (
            baseline_summary["min"], baseline_summary["p25"],
            baseline_summary["median"], baseline_summary["p75"], baseline_summary["max"],
        )
    else:
        baseline = cast_numeric(baseline_raw)
        b_count = len(baseline)
        if b_count < 2 or len(new) < 2:
            return {"severity": "UNKNOWN", "reasons": ["Insufficient numeric data"], "metrics": {}, "warnings": []}
        b_mean, b_std = _mean(baseline), _std(baseline)
        b_min = min(baseline)
        b_p25 = _percentile(baseline, 25)
        b_median = _percentile(baseline, 50)
        b_p75 = _percentile(baseline, 75)
        b_max = max(baseline)

    n_mean, n_std = _mean(new), _std(new)

    issues = []
    severity = "PASS"
    metrics = {}
    warnings = []

    # Sample size warning
    ratio = max(b_count, len(new)) / max(min(b_count, len(new)), 1)
    if ratio > 10:
        warnings.append(
            f"Sample size mismatch: baseline={b_count}, new={len(new)} "
            f"({ratio:.0f}x difference) — PSI may be unreliable"
        )

    # Mean shift
    mean_shift = abs(n_mean - b_mean) / b_std if b_std > 0 else 0
    metrics["mean_shift_std"] = round(mean_shift, 4)
    metrics["baseline_mean"] = round(b_mean, 4)
    metrics["new_mean"] = round(n_mean, 4)

    if mean_shift > t["mean_shift_high"]:
        issues.append(f"Mean shifted by {mean_shift:.2f} std devs ({b_mean:.2f} → {n_mean:.2f})")
        severity = _worst(severity, "HIGH")
    elif mean_shift > t["mean_shift_medium"]:
        issues.append(f"Mean shifted by {mean_shift:.2f} std devs ({b_mean:.2f} → {n_mean:.2f})")
        severity = _worst(severity, "MEDIUM")

    # Std shift
    std_shift = abs(n_std - b_std) / b_std if b_std > 0 else 0
    metrics["std_shift"] = round(std_shift, 4)
    metrics["baseline_std"] = round(b_std, 4)
    metrics["new_std"] = round(n_std, 4)

    if std_shift > t["std_shift_high"]:
        issues.append(f"Std dev shifted by {std_shift*100:.1f}% ({b_std:.2f} → {n_std:.2f})")
        severity = _worst(severity, "HIGH")
    elif std_shift > t["std_shift_medium"]:
        issues.append(f"Std dev shifted by {std_shift*100:.1f}%")
        severity = _worst(severity, "MEDIUM")

    # PSI
    if baseline_summary is not None:
        bins = baseline_summary["hist_bins"]
        new_counts = build_numeric_histogram(
            new, baseline_summary["hist_min"], baseline_summary["hist_max"], bins=bins
        )
        psi = _psi_from_histograms(
            baseline_summary["hist_counts"], b_count, new_counts, len(new)
        )
    else:
        psi = _psi_numeric(baseline, new)
    metrics["psi"] = psi
    psi_sev = _severity_from_psi(psi, t)
    if psi_sev != "PASS":
        issues.append(f"PSI = {psi} ({'significant' if psi_sev == 'HIGH' else 'moderate'} drift)")
    severity = _worst(severity, psi_sev)

    # Trend direction
    if n_mean > b_mean:
        metrics["trend_direction"] = "up"
    elif n_mean < b_mean:
        metrics["trend_direction"] = "down"
    else:
        metrics["trend_direction"] = "stable"

    # Percentiles — baseline
    metrics["baseline_min"] = round(b_min, 4)
    metrics["baseline_p25"] = round(b_p25, 4)
    metrics["baseline_median"] = round(b_median, 4)
    metrics["baseline_p75"] = round(b_p75, 4)
    metrics["baseline_max"] = round(b_max, 4)

    # Percentiles — new
    metrics["new_min"] = round(min(new), 4)
    metrics["new_p25"] = round(_percentile(new, 25), 4)
    metrics["new_median"] = round(_percentile(new, 50), 4)
    metrics["new_p75"] = round(_percentile(new, 75), 4)
    metrics["new_max"] = round(max(new), 4)

    # Row counts
    metrics["baseline_count"] = b_count
    metrics["new_count"] = len(new)

    return {"severity": severity, "reasons": issues, "metrics": metrics, "warnings": warnings}


def analyze_categorical(baseline_raw, new_raw, thresholds=None, baseline_summary=None):
    """
    Compare baseline vs new for a categorical column.

    Args:
        baseline_raw: list of raw baseline values. Ignored if baseline_summary
            is provided (pass None or [] in that case).
        new_raw: list of raw new values — always required, always raw.
        thresholds: optional threshold overrides.
        baseline_summary: optional pre-built summary from
            build_categorical_summary(). When given, baseline category set
            and frequencies come from this fingerprint instead of from
            baseline_raw. Used by locker.py.
    """
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    new = [str(v) for v in new_raw]

    if baseline_summary is not None:
        b_count = baseline_summary["count"]
        base_categories = set(baseline_summary["categories"])
        base_freq = baseline_summary["frequencies"]
    else:
        baseline = [str(v) for v in baseline_raw]
        b_count = len(baseline)
        base_categories = set(baseline)
        base_freq = _frequencies(baseline)

    issues = []
    severity = "PASS"
    metrics = {}
    warnings = []

    # Sample size warning
    ratio = max(b_count, len(new)) / max(min(b_count, len(new)), 1)
    if ratio > 10:
        warnings.append(
            f"Sample size mismatch: baseline={b_count}, new={len(new)} "
            f"({ratio:.0f}x difference) — PSI may be unreliable"
        )

    new_freq = _frequencies(new)
    new_categories = set(new)

    # New unseen categories
    unseen = new_categories - base_categories
    if unseen:
        issues.append(f"New categories found: {sorted(unseen)}")
        severity = _worst(severity, "HIGH")
    metrics["new_categories"] = sorted(unseen)

    # Vanished categories
    vanished = base_categories - new_categories
    if vanished:
        issues.append(f"Categories vanished from new data: {sorted(vanished)}")
        severity = _worst(severity, "MEDIUM")
    metrics["vanished_categories"] = sorted(vanished)

    # Frequency distribution shift
    shifted = []
    for cat in base_categories:
        base_share = base_freq.get(cat, 0)
        new_share = new_freq.get(cat, 0)
        if abs(new_share - base_share) > t["category_share_shift"]:
            shifted.append(f"'{cat}' {base_share*100:.1f}% → {new_share*100:.1f}%")
            severity = _worst(severity, "MEDIUM")
    if shifted:
        issues.append(f"Category share shifted: {', '.join(shifted)}")

    # PSI
    psi = _psi_categorical(base_freq, new_freq)
    metrics["psi"] = psi
    psi_sev = _severity_from_psi(psi, t)
    if psi_sev != "PASS":
        issues.append(f"PSI = {psi}")
    severity = _worst(severity, psi_sev)

    # Chi-square
    chi2 = _chi_square_from_freq(base_freq, new_freq)
    metrics["chi_square"] = chi2
    if chi2 > t["chi_square_medium"]:
        issues.append(f"Chi-square = {chi2} (distribution mismatch)")
        severity = _worst(severity, "MEDIUM")

    metrics["baseline_categories"] = len(base_categories)
    metrics["new_categories_count"] = len(new_categories)
    metrics["baseline_count"] = b_count
    metrics["new_count"] = len(new)

    return {"severity": severity, "reasons": issues, "metrics": metrics, "warnings": warnings}


# ─── Main Analyze ─────────────────────────────────────────────────────────────

def analyze(baseline_cols, new_cols, columns=None, ignore_columns=None,
            thresholds=None, baseline_summaries=None):
    """
    Compare baseline and new column dicts.

    Args:
        baseline_cols: dict of column_name -> list of values. If a column
            has an entry in baseline_summaries, its raw values here are
            ignored (pass {} or partial data) — used by locker.py so a
            locked baseline never needs raw values reconstructed.
        new_cols: dict of column_name -> list of values
        columns: optional list — compare only these columns
        ignore_columns: optional list — skip these columns
        thresholds: optional dict of threshold overrides
        baseline_summaries: optional dict of column_name -> {"type": ...,
            "summary": build_numeric_summary()/build_categorical_summary() result}.
            When a column is present here, it's compared using the summary
            instead of raw baseline values.

    Returns dict with:
        'columns': per-column analysis
        'health_score': 0-100, hard-capped ≤50 if any HIGH column
        'warnings': dataset-level schema warnings
        'summary': high_count, medium_count, pass_count, unknown_count,
                   drifted_columns, stable_columns, total_columns
    """
    baseline_summaries = baseline_summaries or {}
    baseline_keys = set(baseline_summaries.keys()) if baseline_summaries else set(baseline_cols.keys())
    new_keys = set(new_cols.keys())
    common = baseline_keys & new_keys

    # Schema mismatch warnings
    only_in_baseline = baseline_keys - new_keys
    only_in_new = new_keys - baseline_keys
    warnings = []
    if only_in_baseline:
        warnings.append(f"Columns only in baseline (skipped): {sorted(only_in_baseline)}")
    if only_in_new:
        warnings.append(f"Columns only in new data (skipped): {sorted(only_in_new)}")

    # Column filtering
    if columns:
        requested = set(columns)
        missing = requested - common
        if missing:
            raise ValueError(f"Columns not found in both datasets: {sorted(missing)}")
        common = common & requested

    # ignore_columns
    if ignore_columns:
        ignored = set(ignore_columns)
        common = common - ignored
        if ignored:
            warnings.append(f"Columns ignored by request: {sorted(ignored & (baseline_keys | new_keys))}")

    results = {}
    for col in sorted(common):
        col_summary_entry = baseline_summaries.get(col)

        if col_summary_entry is not None:
            col_type = col_summary_entry["type"]
            if col_type == "numeric":
                result = analyze_numeric(
                    None, new_cols[col], thresholds=thresholds,
                    baseline_summary=col_summary_entry["summary"],
                )
            else:
                result = analyze_categorical(
                    None, new_cols[col], thresholds=thresholds,
                    baseline_summary=col_summary_entry["summary"],
                )
        else:
            col_type = detect_type(baseline_cols[col])

            # Mixed-type warning: 50-80% numeric
            numeric_ratio = sum(1 for v in baseline_cols[col] if _is_numeric(v)) / max(len(baseline_cols[col]), 1)
            type_warning = None
            if 0.5 < numeric_ratio < 0.8:
                type_warning = (
                    f"Column '{col}' is {numeric_ratio*100:.0f}% numeric — "
                    f"treated as categorical. Cast to float if intended as numeric."
                )

            if col_type == "numeric":
                result = analyze_numeric(baseline_cols[col], new_cols[col], thresholds=thresholds)
            else:
                result = analyze_categorical(baseline_cols[col], new_cols[col], thresholds=thresholds)

            if type_warning:
                result.setdefault("warnings", []).append(type_warning)

        result["type"] = col_type
        results[col] = result

    # Health score — any HIGH hard-caps at ≤50
    score_map = {"PASS": 0, "MEDIUM": 50, "HIGH": 100, "UNKNOWN": 0}
    if results:
        raw_score = sum(score_map[r["severity"]] for r in results.values()) / len(results)
        health = round(100 - raw_score)
        if any(r["severity"] == "HIGH" for r in results.values()):
            health = min(health, 50)
    else:
        health = 100

    # Summary
    counts = {"HIGH": 0, "MEDIUM": 0, "PASS": 0, "UNKNOWN": 0}
    for r in results.values():
        counts[r["severity"]] += 1

    drifted = [c for c, r in results.items() if r["severity"] in ("HIGH", "MEDIUM")]
    stable = [c for c, r in results.items() if r["severity"] == "PASS"]

    summary = {
        "high_count": counts["HIGH"],
        "medium_count": counts["MEDIUM"],
        "pass_count": counts["PASS"],
        "unknown_count": counts["UNKNOWN"],
        "total_columns": len(results),
        "drifted_columns": sorted(drifted),
        "stable_columns": sorted(stable),
    }

    return {
        "columns": results,
        "health_score": health,
        "warnings": warnings,
        "summary": summary,
    }
