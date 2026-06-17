"""
test_trend.py — Multi-snapshot trend analysis.

Includes regression tests for the v0.12.0 fix: to_html_trend()
interpolated column names and source file labels directly into HTML
and into an inline <script> block with no escaping. A column name or
filename containing "</script><script>..." could close the chart
script tag early and inject arbitrary script into the page.
"""

import pytest
from psiwatch.trend import analyze_trend, to_html_trend, print_trend


@pytest.fixture
def stable_snapshots():
    return [
        {"age": [22, 23, 21, 24, 25] * 4},
        {"age": [22, 23, 21, 24, 25] * 4},
        {"age": [22, 23, 21, 24, 25] * 4},
    ]


@pytest.fixture
def drifting_snapshots():
    return [
        {"age": [22, 23, 21, 24, 25] * 4},
        {"age": [22, 23, 21, 24, 25] * 4},
        {"age": [30, 31, 29, 32, 33] * 4},
    ]


def test_trend_returns_required_keys(stable_snapshots):
    tr = analyze_trend(stable_snapshots)
    required = {"files", "steps", "overall_health_history", "worsening_columns", "column_history"}
    assert required <= set(tr.keys())


def test_trend_stable_health_100_each_step(stable_snapshots):
    tr = analyze_trend(stable_snapshots)
    assert all(h == 100 for h in tr["overall_health_history"])
    assert tr["worsening_columns"] == []


def test_trend_n_inputs_gives_n_minus_1_steps_previous_mode(stable_snapshots):
    tr = analyze_trend(stable_snapshots)
    assert len(tr["steps"]) == 2
    assert "from" in tr["steps"][0] and "to" in tr["steps"][0]


def test_trend_drift_detected_in_later_step(drifting_snapshots):
    tr = analyze_trend(drifting_snapshots)
    assert tr["overall_health_history"][1] < 80
    assert "age" in tr["worsening_columns"]


def test_trend_baseline_first_mode(drifting_snapshots):
    tr = analyze_trend(drifting_snapshots, baseline="first")
    assert len(tr["steps"]) == 2
    assert tr["steps"][0]["from"] == tr["steps"][1]["from"]
    assert tr["baseline_mode"] == "first"


def test_trend_single_file_raises():
    with pytest.raises(ValueError):
        analyze_trend([{"age": [1, 2, 3]}])


def test_trend_bad_baseline_mode_raises(stable_snapshots):
    with pytest.raises(ValueError):
        analyze_trend(stable_snapshots, baseline="wrong")


def test_print_trend_runs_without_error(drifting_snapshots, capsys):
    tr = analyze_trend(drifting_snapshots)
    print_trend(tr)  # should not raise
    captured = capsys.readouterr()
    assert "age" in captured.out


def test_column_history_has_severity_and_psi(drifting_snapshots):
    tr = analyze_trend(drifting_snapshots)
    assert "severity_history" in tr["column_history"]["age"]
    assert "psi_history" in tr["column_history"]["age"]


# ─── Regression: HTML/JS injection via column names or filenames ──────────

def test_html_trend_escapes_malicious_column_name():
    payload_col = "</script><script>alert(1)</script>"
    snapshots = [
        {payload_col: [22, 23, 21, 24, 25] * 4},
        {payload_col: [22, 23, 21, 24, 25] * 4},
        {payload_col: [30, 31, 29, 32, 33] * 4},
    ]
    tr = analyze_trend(snapshots)
    out = to_html_trend(tr)

    assert "</script><script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_html_trend_neutralizes_script_breakout_in_json_payload():
    """
    Step labels are embedded inside an inline <script> block as a JSON
    array for Chart.js. Even with json.dumps() escaping quotes, a label
    containing a literal "</script" substring can still close the
    surrounding <script> tag early (the HTML parser doesn't know it's
    "inside a JS string" — it just sees the closing tag). This must be
    neutralized in the script payload, not just HTML-escaped elsewhere.
    """
    payload_col = "x</script><script>alert(1)</script>"
    snapshots = [
        {payload_col: [22, 23, 21, 24, 25] * 4},
        {payload_col: [22, 23, 21, 24, 25] * 4},
        {payload_col: [30, 31, 29, 32, 33] * 4},
    ]
    tr = analyze_trend(snapshots)
    out = to_html_trend(tr)

    script_block = out.split("<script>\nconst ctx")[-1]
    assert "</script><script>alert" not in script_block
