"""
analyzer.py — Core drift detection engine for psiwatch.
Methods: Mean shift, Std shift, PSI, Chi-square, Frequency comparison.
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
    idx = int((p / 100) * (len(s) - 1))
    return s[idx]

def _frequencies(values):
    total = len(values)
    freq = {}
    for v in values:
        freq[v] = freq.get(v, 0) + 1
    return {k: v / total for k, v in freq.items()}


# ─── PSI ──────────────────────────────────────────────────────────────────────

def _psi_numeric(baseline, new, bins=10):
    """Population Stability Index for numeric columns."""
    all_vals = baseline + new
    min_val, max_val = min(all_vals), max(all_vals)

    if min_val == max_val:
        return 0.0

    bin_width = (max_val - min_val) / bins
    edges = [min_val + i * bin_width for i in range(bins + 1)]

    def bin_counts(vals):
        counts = [0] * bins
        for v in vals:
            idx = int((v - min_val) / bin_width)
            idx = min(idx, bins - 1)
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


def _psi_categorical(baseline_freq, new_freq):
    """Population Stability Index for categorical columns."""
    all_cats = set(baseline_freq) | set(new_freq)
    psi = 0.0
    for cat in all_cats:
        expected = max(baseline_freq.get(cat, 0), 1e-6)
        actual = max(new_freq.get(cat, 0), 1e-6)
        psi += (actual - expected) * math.log(actual / expected)
    return round(psi, 4)


# ─── Chi-Square ───────────────────────────────────────────────────────────────

def _chi_square(baseline, new):
    """Chi-square statistic for categorical columns."""
    all_cats = set(baseline) | set(new)
    base_total = len(baseline)
    new_total = len(new)

    chi2 = 0.0
    for cat in all_cats:
        expected = baseline.count(cat) / base_total if base_total else 1e-6
        observed = new.count(cat) / new_total if new_total else 0
        expected = max(expected, 1e-6)
        chi2 += ((observed - expected) ** 2) / expected

    return round(chi2, 4)


# ─── Severity Scoring ─────────────────────────────────────────────────────────

def _severity_from_psi(psi):
    if psi > 0.25:
        return 'HIGH'
    elif psi > 0.1:
        return 'MEDIUM'
    return 'PASS'

def _worst(a, b):
    order = ['PASS', 'MEDIUM', 'HIGH', 'UNKNOWN']
    return a if order.index(a) >= order.index(b) else b


# ─── Column Analyzers ─────────────────────────────────────────────────────────

def analyze_numeric(baseline_raw, new_raw):
    baseline = cast_numeric(baseline_raw)
    new = cast_numeric(new_raw)

    if len(baseline) < 2 or len(new) < 2:
        return {'severity': 'UNKNOWN', 'reasons': ['Insufficient numeric data'], 'metrics': {}}

    b_mean, b_std = _mean(baseline), _std(baseline)
    n_mean, n_std = _mean(new), _std(new)

    issues = []
    severity = 'PASS'
    metrics = {}

    # Mean shift
    mean_shift = abs(n_mean - b_mean) / b_std if b_std > 0 else 0
    metrics['mean_shift_std'] = round(mean_shift, 4)
    metrics['baseline_mean'] = round(b_mean, 4)
    metrics['new_mean'] = round(n_mean, 4)

    if mean_shift > 0.5:
        issues.append(f"Mean shifted by {mean_shift:.2f} std devs ({b_mean:.2f} → {n_mean:.2f})")
        severity = _worst(severity, 'HIGH')
    elif mean_shift > 0.2:
        issues.append(f"Mean shifted by {mean_shift:.2f} std devs ({b_mean:.2f} → {n_mean:.2f})")
        severity = _worst(severity, 'MEDIUM')

    # Std shift
    std_shift = abs(n_std - b_std) / b_std if b_std > 0 else 0
    metrics['std_shift'] = round(std_shift, 4)
    metrics['baseline_std'] = round(b_std, 4)
    metrics['new_std'] = round(n_std, 4)

    if std_shift > 0.5:
        issues.append(f"Std dev shifted by {std_shift*100:.1f}% ({b_std:.2f} → {n_std:.2f})")
        severity = _worst(severity, 'HIGH')
    elif std_shift > 0.2:
        issues.append(f"Std dev shifted by {std_shift*100:.1f}%")
        severity = _worst(severity, 'MEDIUM')

    # PSI
    psi = _psi_numeric(baseline, new)
    metrics['psi'] = psi
    psi_sev = _severity_from_psi(psi)
    if psi_sev != 'PASS':
        issues.append(f"PSI = {psi} ({'significant' if psi_sev == 'HIGH' else 'moderate'} drift)")
    severity = _worst(severity, psi_sev)

    # Percentiles
    metrics['baseline_median'] = round(_percentile(baseline, 50), 4)
    metrics['new_median'] = round(_percentile(new, 50), 4)

    return {'severity': severity, 'reasons': issues, 'metrics': metrics}


def analyze_categorical(baseline_raw, new_raw):
    baseline = [str(v) for v in baseline_raw]
    new = [str(v) for v in new_raw]

    issues = []
    severity = 'PASS'
    metrics = {}

    base_freq = _frequencies(baseline)
    new_freq = _frequencies(new)

    # New unseen categories
    unseen = set(new) - set(baseline)
    if unseen:
        issues.append(f"New categories found: {sorted(unseen)}")
        severity = _worst(severity, 'HIGH')
    metrics['new_categories'] = sorted(unseen)

    # Frequency distribution shift
    shifted = []
    for cat in set(baseline):
        base_share = base_freq.get(cat, 0)
        new_share = new_freq.get(cat, 0)
        shift = abs(new_share - base_share)
        if shift > 0.15:
            shifted.append(f"'{cat}' {base_share*100:.1f}% → {new_share*100:.1f}%")
            severity = _worst(severity, 'MEDIUM')
    if shifted:
        issues.append(f"Category share shifted: {', '.join(shifted)}")

    # PSI
    psi = _psi_categorical(base_freq, new_freq)
    metrics['psi'] = psi
    psi_sev = _severity_from_psi(psi)
    if psi_sev != 'PASS':
        issues.append(f"PSI = {psi}")
    severity = _worst(severity, psi_sev)

    # Chi-square
    chi2 = _chi_square(baseline, new)
    metrics['chi_square'] = chi2
    if chi2 > 0.5:
        issues.append(f"Chi-square = {chi2} (distribution mismatch)")
        severity = _worst(severity, 'MEDIUM')

    metrics['baseline_categories'] = len(set(baseline))
    metrics['new_categories_count'] = len(set(new))

    return {'severity': severity, 'reasons': issues, 'metrics': metrics}


# ─── Main Analyze Function ────────────────────────────────────────────────────

def analyze(baseline_cols, new_cols, columns=None):
    """
    Compare baseline and new column dicts.
    Optionally filter to specific columns.
    Returns per-column results + overall drift health score.
    """
    common = set(baseline_cols.keys()) & set(new_cols.keys())

    if columns:
        requested = set(columns)
        common = common & requested
        missing = requested - common
        if missing:
            raise ValueError(f"Columns not found in both datasets: {missing}")

    results = {}
    for col in sorted(common):
        col_type = detect_type(baseline_cols[col])
        if col_type == 'numeric':
            result = analyze_numeric(baseline_cols[col], new_cols[col])
        else:
            result = analyze_categorical(baseline_cols[col], new_cols[col])
        result['type'] = col_type
        results[col] = result

    # Overall drift health score (0 = no drift, 100 = max drift)
    score_map = {'PASS': 0, 'MEDIUM': 50, 'HIGH': 100, 'UNKNOWN': 0}
    if results:
        raw_score = sum(score_map[r['severity']] for r in results.values()) / len(results)
        health = round(100 - raw_score)
    else:
        health = 100

    return {'columns': results, 'health_score': health}
