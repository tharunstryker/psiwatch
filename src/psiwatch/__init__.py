"""
psiwatch — Dataset drift detection library.

Usage as a library:
    import psiwatch

    # Compare two CSV files
    psiwatch.compare("old.csv", "new.csv")

    # Compare with custom PSI threshold
    psiwatch.compare("old.csv", "new.csv", psi_threshold=0.15)

    # Compare a pandas DataFrame directly
    import pandas as pd
    old_df = pd.read_csv("train.csv")
    new_df = pd.read_csv("production.csv")
    psiwatch.compare(old_df, new_df, output="report.html")

    # Compare Python dicts directly
    psiwatch.compare_data(
        {"age": [22, 23, 21], "score": [78, 85, 70]},
        {"age": [28, 30, 29], "score": [45, 40, 38]}
    )

    # Compare a single list (single column)
    psiwatch.compare_columns([22, 23, 21, 24], [28, 30, 29, 31])

    # Get raw analysis result as a dict (no print)
    result = psiwatch.analyze("old.csv", "new.csv")
    print(result["health_score"])

    # CI/CD — raise exception if drift detected
    psiwatch.compare("train.csv", "new.csv", fail_on_drift=True)
"""

from .loader import resolve_input
from .analyzer import analyze as _analyze
from .reporter import output_report
from .updater import check_for_update

__version__ = "0.10.0"
__all__ = ["compare", "compare_data", "compare_columns", "analyze"]

# Version check runs once on import — silent, cached 24h, never blocks
try:
    check_for_update(__version__)
except Exception:
    pass


def _build_thresholds(psi_threshold=None, thresholds=None):
    merged = {}
    if psi_threshold is not None:
        if not isinstance(psi_threshold, (int, float)) or psi_threshold <= 0:
            raise ValueError("psi_threshold must be a positive number")
        merged['psi_medium'] = round(psi_threshold * 0.4, 6)
        merged['psi_high'] = float(psi_threshold)
    if thresholds:
        if not isinstance(thresholds, dict):
            raise TypeError("thresholds must be a dict")
        merged.update(thresholds)
    return merged if merged else None


def _source_label(old, new):
    """Build a human-readable source label for reports."""
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
            return f"dict({len(s)} cols)"
        if isinstance(s, list):
            return f"list({len(s)} items)"
        return type(s).__name__
    import os
    return f"baseline: {name(old)}  →  new: {name(new)}"


def compare(old, new, output=None, columns=None, psi_threshold=None, thresholds=None, fail_on_drift=False):
    """
    Compare two datasets and print or save a drift report.

    Args:
        old: file path (str), dict, list, or pandas DataFrame — baseline/old data
        new: file path (str), dict, list, or pandas DataFrame — new/current data
        output: optional output file path (.json, .txt, .html)
        columns: optional list of column names to compare
        psi_threshold: convenience param — sets the HIGH drift PSI boundary.
        thresholds: dict of fine-grained threshold overrides.
        fail_on_drift: if True, raises DriftDetected exception when health_score < 80.
                       Use this in CI/CD pipelines: psiwatch compare --fail-on-drift

    Returns:
        dict with 'columns', 'health_score', 'warnings'

    Raises:
        DriftDetected: if fail_on_drift=True and drift is detected
    """
    baseline = resolve_input(old)
    current = resolve_input(new)
    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    result = _analyze(baseline, current, columns=columns, thresholds=t)
    source_info = _source_label(old, new)
    output_report(result, output=output, source_info=source_info)

    if fail_on_drift and result['health_score'] < 80:
        raise DriftDetected(
            f"Drift detected — health score: {result['health_score']}/100. "
            f"HIGH columns: {[c for c, r in result['columns'].items() if r['severity'] == 'HIGH']}"
        )

    return result


def compare_data(old_data, new_data, output=None, columns=None, psi_threshold=None, thresholds=None, fail_on_drift=False):
    """
    Compare two datasets — accepts dicts, lists, or pandas DataFrames.
    Alias for compare() with the same signature.
    """
    return compare(old_data, new_data, output=output, columns=columns,
                   psi_threshold=psi_threshold, thresholds=thresholds,
                   fail_on_drift=fail_on_drift)


def compare_columns(old_list, new_list, name="column", output=None, psi_threshold=None, thresholds=None, fail_on_drift=False):
    """
    Compare two plain Python lists (single column).

    Args:
        old_list: list — baseline values
        new_list: list — new values
        name: column name label (default: "column")
        output: optional output file path
        psi_threshold: convenience PSI threshold override
        thresholds: dict of fine-grained threshold overrides
        fail_on_drift: raise DriftDetected if drift found
    """
    baseline = resolve_input(old_list, column_name=name)
    current = resolve_input(new_list, column_name=name)
    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    result = _analyze(baseline, current, thresholds=t)
    output_report(result, output=output)

    if fail_on_drift and result['health_score'] < 80:
        raise DriftDetected(
            f"Drift detected in column '{name}' — health score: {result['health_score']}/100"
        )

    return result


def analyze(old, new, columns=None, psi_threshold=None, thresholds=None):
    """
    Run drift analysis and return raw result dict (no output).
    Useful for programmatic access.

    Returns:
        dict with keys:
            'columns': per-column analysis
            'health_score': 0-100 (100 = no drift)
            'warnings': list of dataset-level warnings
    """
    baseline = resolve_input(old)
    current = resolve_input(new)
    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    return _analyze(baseline, current, columns=columns, thresholds=t)


class DriftDetected(Exception):
    """
    Raised when fail_on_drift=True and drift is detected.
    Use in CI/CD pipelines to fail the build on data drift.

    Example GitHub Actions usage:
        - name: Check data drift
          run: psiwatch compare train.csv new.csv --fail-on-drift
    """
    pass
