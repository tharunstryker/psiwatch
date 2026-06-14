"""
psiwatch — Dataset drift detection library.

Usage as a library:
    import psiwatch

    # Compare two CSV files
    psiwatch.compare("old.csv", "new.csv")

    # Compare with custom PSI threshold
    psiwatch.compare("old.csv", "new.csv", psi_threshold=0.15)

    # Full threshold control
    psiwatch.compare("old.csv", "new.csv", thresholds={
        "psi_medium": 0.05,
        "psi_high": 0.15,
    })

    # Compare a pandas DataFrame directly
    import pandas as pd
    old_df = pd.read_csv("train.csv")
    new_df = pd.read_csv("production.csv")
    psiwatch.compare(old_df, new_df, output="report.html")

    # compare_data also accepts DataFrames
    psiwatch.compare_data(old_df, new_df)

    # Compare specific columns only
    psiwatch.compare("old.csv", "new.csv", columns=["age", "score"])

    # Compare Python dicts directly (no files needed)
    psiwatch.compare_data(
        {"age": [22, 23, 21], "score": [78, 85, 70]},
        {"age": [28, 30, 29], "score": [45, 40, 38]}
    )

    # Compare a single list (single column)
    psiwatch.compare_columns([22, 23, 21, 24], [28, 30, 29, 31])

    # Get raw analysis result as a dict (no print)
    result = psiwatch.analyze("old.csv", "new.csv")
    print(result["health_score"])
"""

from .loader import resolve_input
from .analyzer import analyze as _analyze
from .reporter import output_report


def _build_thresholds(psi_threshold=None, thresholds=None):
    """
    Merge user-supplied threshold overrides.
    psi_threshold is a convenience shortcut that sets both psi_medium
    and psi_high proportionally (medium = threshold * 0.4, high = threshold).
    A full `thresholds` dict takes precedence over psi_threshold for any
    keys it explicitly provides.
    """
    merged = {}
    if psi_threshold is not None:
        if not isinstance(psi_threshold, (int, float)) or psi_threshold <= 0:
            raise ValueError("psi_threshold must be a positive number")
        # Scale medium threshold proportionally: ~40% of the high threshold,
        # matching the default 0.10 / 0.25 ≈ 0.4 ratio.
        merged['psi_medium'] = round(psi_threshold * 0.4, 6)
        merged['psi_high'] = float(psi_threshold)
    if thresholds:
        if not isinstance(thresholds, dict):
            raise TypeError("thresholds must be a dict")
        merged.update(thresholds)
    return merged if merged else None


def compare(old, new, output=None, columns=None, psi_threshold=None, thresholds=None):
    """
    Compare two datasets and print or save a drift report.

    Args:
        old: file path (str), dict, list, or pandas DataFrame — baseline/old data
        new: file path (str), dict, list, or pandas DataFrame — new/current data
        output: optional output file path (.json, .txt, .html)
        columns: optional list of column names to compare
        psi_threshold: convenience param — sets the HIGH drift PSI boundary.
            Medium is scaled to ~40% of this value automatically.
            Example: psi_threshold=0.15 → medium=0.06, high=0.15
        thresholds: dict of fine-grained threshold overrides. Supported keys:
            psi_medium (default 0.10), psi_high (default 0.25),
            mean_shift_medium (0.2), mean_shift_high (0.5),
            std_shift_medium (0.2), std_shift_high (0.5),
            category_share_shift (0.15), chi_square_medium (0.5)

    Example:
        psiwatch.compare("train.csv", "production.csv")
        psiwatch.compare("train.csv", "production.csv", output="report.html")
        psiwatch.compare("train.csv", "production.csv", psi_threshold=0.15)
    """
    baseline = resolve_input(old)
    current = resolve_input(new)
    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    result = _analyze(baseline, current, columns=columns, thresholds=t)
    output_report(result, output=output)
    return result


def compare_data(old_data, new_data, output=None, columns=None, psi_threshold=None, thresholds=None):
    """
    Compare two datasets — accepts dicts, lists, or pandas DataFrames.

    Args:
        old_data: dict, list, or pandas DataFrame — baseline data
        new_data: dict, list, or pandas DataFrame — new data
        output: optional output file path
        columns: optional list of column names to compare
        psi_threshold: convenience PSI threshold override (see compare())
        thresholds: dict of fine-grained threshold overrides (see compare())

    Example:
        import pandas as pd
        psiwatch.compare_data(
            pd.read_csv("train.csv"),
            pd.read_csv("production.csv"),
            psi_threshold=0.15
        )
        psiwatch.compare_data(
            {"age": [22, 23, 21], "city": ["Chennai", "Delhi"]},
            {"age": [28, 30, 29], "city": ["Mumbai", "Bangalore"]}
        )
    """
    baseline = resolve_input(old_data)
    current = resolve_input(new_data)
    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    result = _analyze(baseline, current, columns=columns, thresholds=t)
    output_report(result, output=output)
    return result


def compare_columns(old_list, new_list, name="column", output=None, psi_threshold=None, thresholds=None):
    """
    Compare two plain Python lists (single column).

    Args:
        old_list: list — baseline values
        new_list: list — new values
        name: column name label (default: "column")
        output: optional output file path
        psi_threshold: convenience PSI threshold override (see compare())
        thresholds: dict of fine-grained threshold overrides (see compare())

    Example:
        psiwatch.compare_columns([22, 23, 21], [28, 30, 29], name="age")
    """
    baseline = resolve_input(old_list, column_name=name)
    current = resolve_input(new_list, column_name=name)
    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    result = _analyze(baseline, current, thresholds=t)
    output_report(result, output=output)
    return result


def analyze(old, new, columns=None, psi_threshold=None, thresholds=None):
    """
    Run drift analysis and return raw result dict (no output).
    Useful for programmatic access.

    Args:
        old: file path (str), dict, list, or pandas DataFrame
        new: file path (str), dict, list, or pandas DataFrame
        columns: optional list of column names to compare
        psi_threshold: convenience PSI threshold override (see compare())
        thresholds: dict of fine-grained threshold overrides (see compare())

    Returns:
        dict with keys:
            'columns': per-column analysis
            'health_score': 0-100 (100 = no drift)

    Example:
        result = psiwatch.analyze("train.csv", "new.csv")
        print(result["health_score"])
        for col, data in result["columns"].items():
            print(col, data["severity"])
    """
    baseline = resolve_input(old)
    current = resolve_input(new)
    t = _build_thresholds(psi_threshold=psi_threshold, thresholds=thresholds)
    return _analyze(baseline, current, columns=columns, thresholds=t)


__version__ = "0.2.0"
__all__ = ["compare", "compare_data", "compare_columns", "analyze"]

