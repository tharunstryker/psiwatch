"""
test_reporter.py — Report output formats.

Includes regression tests for the v0.12.0 fix: to_html() interpolated
column names, category values, and reason strings directly into the
HTML report with no escaping. A baseline or new CSV with a column name
or category value like "<script>alert(1)</script>" would execute that
script the moment the generated report was opened in a browser.
"""

from psiwatch.reporter import to_html
from psiwatch.analyzer import analyze


def test_html_report_basic_structure():
    baseline = {"age": [22, 23, 21, 24, 25] * 4}
    new = {"age": [22, 23, 21, 24, 25] * 4}
    result = analyze(baseline, new)
    out = to_html(result)
    assert "<html" in out
    assert "age" in out


# ─── Regression: column names / category values must be HTML-escaped ─────

def test_html_report_escapes_malicious_column_name():
    payload_col = "<script>alert(1)</script>"
    baseline = {payload_col: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}
    new = {payload_col: [50, 60, 70, 80, 90, 55, 65, 75, 85, 95]}
    result = analyze(baseline, new)
    out = to_html(result)

    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_html_report_escapes_malicious_category_value():
    baseline = {"city": ["Chennai", "Delhi", "Mumbai", "Chennai", "Delhi"]}
    new = {"city": ["Chennai", "<img src=x onerror=alert(2)>", "Pune", "Kochi", "Pune"]}
    result = analyze(baseline, new)
    out = to_html(result)

    assert "<img src=x onerror=alert(2)>" not in out
    assert "&lt;img" in out


def test_html_report_escapes_malicious_reason_text():
    # Category names also surface inside "reasons" strings (e.g. category
    # share shift, new/vanished categories) — those must be escaped too,
    # not just the raw metrics fields.
    baseline = {"grade": ["A"] * 10}
    new = {"grade": ["<b>X</b>"] * 10}
    result = analyze(baseline, new)
    out = to_html(result)

    body = out.split("<body>")[1]
    assert "<b>X</b>" not in body
    assert "&lt;b&gt;" in out
