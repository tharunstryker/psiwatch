"""
loader.py — Handles all input modes for psiwatch.
Supports: CSV file paths, Parquet file paths, Python dicts, Python lists,
pandas DataFrames, and SQL query results (via a user-supplied DB-API connection).

FIX: resolve_input now accepts lists directly via compare() without needing compare_columns().
FIX: detect_type is explicit about ambiguous columns.
"""

import csv
import math
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


def load_parquet(filepath):
    """
    Load a Parquet file and return a dict of column_name -> list of values.

    Requires pandas + pyarrow (or fastparquet) to be installed — these are
    optional extras, not core dependencies. psiwatch itself stays
    zero-dependency for anyone who doesn't need Parquet support.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "Reading Parquet files requires pandas and a parquet engine. "
            "Install with: pip install pandas pyarrow"
        )

    try:
        df = pd.read_parquet(filepath)
    except ImportError:
        raise ImportError(
            "Reading Parquet files requires a parquet engine. "
            "Install with: pip install pyarrow"
        )

    if df.empty:
        raise ValueError(f"Empty file: {filepath}")

    return load_dataframe(df)


def load_sql(query, connection):
    """
    Run a SQL query against a user-supplied DB-API connection and return a
    dict of column_name -> list of values.

    psiwatch does NOT manage database drivers or credentials — bring your own
    connection (sqlite3, psycopg2, pymysql, mysql-connector, etc., or a
    SQLAlchemy connection/engine.connect() result). Any object exposing a
    standard DB-API .cursor() works.

    Example:
        import sqlite3
        conn = sqlite3.connect("mydb.sqlite")
        baseline = load_sql("SELECT * FROM users WHERE month = 'jan'", conn)
        new = load_sql("SELECT * FROM users WHERE month = 'feb'", conn)
    """
    if not query or not isinstance(query, str):
        raise TypeError("Expected a SQL query string")

    cursor = connection.cursor()
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        if cursor.description is None:
            raise ValueError("Query returned no column metadata (not a SELECT?)")
        col_names = [d[0] for d in cursor.description]
    finally:
        cursor.close()

    if not rows:
        raise ValueError("Query returned no rows")

    columns = {name: [] for name in col_names}
    for row in rows:
        for name, val in zip(col_names, row):
            if val is not None:
                columns[name].append(str(val))

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
    """
    Convert string list to floats, skipping blanks/invalid.

    FIX: float() happily parses the strings "nan", "NaN", "inf", "-Infinity",
    etc. into real NaN/inf values — these used to silently pass through and
    later crash PSI binning (int(nan) raises ValueError) or poison
    mean/std/percentile calculations. They're now treated the same as any
    other unparseable value and excluded.
    """
    result = []
    for v in values:
        try:
            f = float(v)
        except (ValueError, TypeError):
            continue
        if math.isnan(f) or math.isinf(f):
            continue
        result.append(f)
    return result


def resolve_input(source, column_name="column"):
    """
    Smart resolver — accepts file path, dict, list, or pandas DataFrame.
    Always returns a dict of {column: [values]}.

    FIX: lists now work via compare() directly, not just compare_columns().
    """
    if isinstance(source, str):
        if source.lower().endswith(('.parquet', '.pq')):
            return load_parquet(source)
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
