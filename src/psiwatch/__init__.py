"""
psiwatch — Dataset drift detection library.

Usage as a library:
    import psiwatch

    # Compare two CSV files
    psiwatch.compare("old.csv", "new.csv")

    # Compare two CSV files, save HTML report
    psiwatch.compare("old.csv", "new.csv", output="report.html")

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


def compare(old, new, output=None, columns=None):
    """
    Compare two datasets and print or save a drift report.

    Args:
        old: file path (str), dict, or list — baseline/old data
        new: file path (str), dict, or list — new/current data
        output: optional output file path (.json, .txt, .html)
        columns: optional list of column names to compare

    Example:
        psiwatch.compare("train.csv", "production.csv")
        psiwatch.compare("train.csv", "production.csv", output="report.html")
    """
    baseline = resolve_input(old)
    current = resolve_input(new)
    result = _analyze(baseline, current, columns=columns)
    output_report(result, output=output)
    return result


def compare_data(old_dict, new_dict, output=None, columns=None):
    """
    Compare two Python dicts of {column: [values]}.

    Args:
        old_dict: dict — baseline data
        new_dict: dict — new data
        output: optional output file path
        columns: optional list of column names to compare

    Example:
        psiwatch.compare_data(
            {"age": [22, 23, 21], "city": ["Chennai", "Delhi"]},
            {"age": [28, 30, 29], "city": ["Mumbai", "Bangalore"]}
        )
    """
    baseline = resolve_input(old_dict)
    current = resolve_input(new_dict)
    result = _analyze(baseline, current, columns=columns)
    output_report(result, output=output)
    return result


def compare_columns(old_list, new_list, name="column", output=None):
    """
    Compare two plain Python lists (single column).

    Args:
        old_list: list — baseline values
        new_list: list — new values
        name: column name label (default: "column")
        output: optional output file path

    Example:
        psiwatch.compare_columns([22, 23, 21], [28, 30, 29], name="age")
    """
    baseline = resolve_input(old_list, column_name=name)
    current = resolve_input(new_list, column_name=name)
    result = _analyze(baseline, current)
    output_report(result, output=output)
    return result


def analyze(old, new, columns=None):
    """
    Run drift analysis and return raw result dict (no output).
    Useful for programmatic access.

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
    return _analyze(baseline, current, columns=columns)


__version__ = "0.1.0"
__all__ = ["compare", "compare_data", "compare_columns", "analyze"]
