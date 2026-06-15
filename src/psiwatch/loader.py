"""
loader.py — Handles all input modes for psiwatch.
Supports: CSV file paths, Python dicts, Python lists, pandas DataFrames.

FIX: resolve_input now accepts lists directly via compare() without needing compare_columns().
FIX: detect_type is explicit about ambiguous columns.
"""

import csv
import os


def load_csv(filepath):
    """Load a CSV file and return a dict of column_name -> list of values."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise ValueError(f"Empty file: {filepath}")

    columns = {key: [] for key in rows[0]}
    for row in rows:
        for key, val in row.items():
            if val is not None:
                columns[key].append(val.strip())

    return columns


def load_dict(data):
    """Accept a plain Python dict of column_name -> list of values."""
    if not isinstance(data, dict):
        raise TypeError("Expected a dict of {column: [values]}")
    return {k: [str(v) for v in vals] for k, vals in data.items()}


def load_list(values, column_name="column"):
    """Accept a single Python list and wrap it as a single-column dict."""
    if not isinstance(values, list):
        raise TypeError("Expected a list of values")
    return {column_name: [str(v) for v in values]}


def load_dataframe(df):
    """
    Accept a pandas DataFrame and convert to dict of column_name -> list of values.
    pandas is optional — only imported when a DataFrame is passed.
    """
    result = {}
    for col in df.columns:
        result[col] = [str(v) for v in df[col].dropna().tolist()]
    return result


def detect_type(values):
    """
    Detect if a column is numeric or categorical.
    Threshold: >80% parseable as float → numeric.
    Returns: 'numeric' or 'categorical'
    """
    if not values:
        return 'categorical'
    numeric_count = sum(1 for v in values if _try_float(v))
    ratio = numeric_count / len(values)
    return 'numeric' if ratio > 0.8 else 'categorical'


def _try_float(v):
    try:
        float(v)
        return True
    except (ValueError, TypeError):
        return False


def cast_numeric(values):
    """Convert string list to floats, skipping blanks/invalid."""
    result = []
    for v in values:
        try:
            result.append(float(v))
        except (ValueError, TypeError):
            pass
    return result


def resolve_input(source, column_name="column"):
    """
    Smart resolver — accepts file path, dict, list, or pandas DataFrame.
    Always returns a dict of {column: [values]}.

    FIX: lists now work via compare() directly, not just compare_columns().
    """
    if isinstance(source, str):
        return load_csv(source)
    elif isinstance(source, dict):
        return load_dict(source)
    elif isinstance(source, list):
        # FIX: list of dicts → treat as tabular data (like records from json)
        if source and isinstance(source[0], dict):
            keys = source[0].keys()
            result = {k: [] for k in keys}
            for row in source:
                for k in keys:
                    result[k].append(str(row.get(k, '')))
            return result
        # plain list → single column
        return load_list(source, column_name)
    else:
        # Check for DataFrame without importing pandas at module level
        try:
            import pandas as pd
            if isinstance(source, pd.DataFrame):
                return load_dataframe(source)
        except ImportError:
            pass
        raise TypeError(
            f"Unsupported input type: {type(source).__name__}. "
            "Expected a file path (str), dict, list, or pandas DataFrame."
        )
