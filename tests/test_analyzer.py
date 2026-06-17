"""
test_analyzer.py — Core analyze()/compare_columns() behavior.

Converted to pytest in v0.12.0. Previously this was a standalone script
with a hand-rolled pass/fail counter that never used `assert`, was never
run by CI, and exited 0 even when checks failed (you had to read the
printed PASS/FAIL lines yourself). Each `check(label, condition)` call
below is now a real test function with a real assert — a failure here
fails the test run and the CI build.
"""

import pytest
from psiwatch.analyzer import analyze
from psiwatch.loader import resolve_input


@pytest.fixture
def baseline():
    return resolve_input({"age": [22, 23, 21, 24, 25, 23, 22, 24, 21, 25],
                           "score": [78, 85, 70, 88, 91, 79, 77, 86, 71, 90]})


@pytest.fixture
def drifted():
    return resolve_input({"age": [35, 38, 40, 42, 44, 36, 39, 41, 43, 45],
                           "score": [30, 25, 20, 35, 28, 31, 26, 21, 34, 27]})


@pytest.fixture
def clean():
    return resolve_input({"age": [22, 23, 21, 24, 25, 23, 22, 24, 21, 25],
                           "score": [78, 85, 70, 88, 91, 79, 77, 86, 71, 90]})


# ─── Core numeric/categorical drift detection ──────────────────────────────

def test_numeric_high_drift_detected(baseline, drifted):
    r = analyze(baseline, drifted)
    assert r["columns"]["age"]["severity"] == "HIGH"


def test_numeric_no_drift_pass(baseline, clean):
    r = analyze(baseline, clean)
    assert r["columns"]["age"]["severity"] == "PASS"


def test_categorical_new_category_detected():
    b_cat = resolve_input({"city": ["Chennai", "Delhi", "Mumbai", "Chennai", "Delhi"]})
    n_cat = resolve_input({"city": ["Chennai", "Delhi", "Pune", "Kochi", "Pune"]})
    r = analyze(b_cat, n_cat)
    assert r["columns"]["city"]["severity"] in ("HIGH", "MEDIUM")


def test_categorical_no_drift_pass():
    b_cat = resolve_input({"city": ["Chennai", "Chennai", "Delhi", "Delhi", "Mumbai"]})
    n_cat = resolve_input({"city": ["Chennai", "Chennai", "Delhi", "Delhi", "Mumbai"]})
    r = analyze(b_cat, n_cat)
    assert r["columns"]["city"]["severity"] == "PASS"


# ─── Health score ───────────────────────────────────────────────────────────

def test_health_score_low_on_drift(baseline, drifted):
    r = analyze(baseline, drifted)
    assert r["health_score"] <= 50


def test_health_score_100_on_clean(baseline, clean):
    r = analyze(baseline, clean)
    assert r["health_score"] == 100


def test_health_score_hard_cap_on_high():
    big_b = resolve_input({"age": list(range(20)) + [35, 38, 40, 42, 44]})
    big_n = resolve_input({"age": [35, 38, 40, 42, 44, 36, 39, 41, 43, 45,
                                    36, 38, 40, 42, 44, 37, 39, 41, 43, 45]})
    r = analyze(big_b, big_n)
    assert r["health_score"] <= 50


# ─── Column filtering ───────────────────────────────────────────────────────

def test_column_filter_works(baseline, drifted):
    r = analyze(baseline, drifted, columns=["age"])
    assert "score" not in r["columns"]
    assert "age" in r["columns"]


def test_ignore_columns_removes_and_keeps():
    b_ig = resolve_input({"age": [22, 23, 21], "id": [1, 2, 3], "score": [78, 85, 70]})
    n_ig = resolve_input({"age": [35, 38, 40], "id": [4, 5, 6], "score": [30, 25, 20]})
    r = analyze(b_ig, n_ig, ignore_columns=["id"])
    assert "id" not in r["columns"]
    assert "age" in r["columns"]
    assert any("id" in w for w in r["warnings"])


# ─── Input loading ───────────────────────────────────────────────────────────

def test_list_of_dicts_input_works():
    list_input = resolve_input([{"age": 22, "city": "Chennai"}, {"age": 23, "city": "Delhi"}])
    assert "age" in list_input and "city" in list_input


def test_missing_column_warning_fires():
    b_miss = resolve_input({"age": [22, 23], "score": [78, 85], "city": ["Chennai", "Delhi"]})
    n_miss = resolve_input({"age": [22, 23], "score": [78, 85]})
    r = analyze(b_miss, n_miss)
    assert any("city" in w for w in r["warnings"])


# ─── summary dict ────────────────────────────────────────────────────────────

def test_summary_on_drifted(baseline, drifted):
    r = analyze(baseline, drifted)
    s = r.get("summary", {})
    assert "summary" in r
    assert s.get("high_count", 0) >= 1
    assert isinstance(s.get("drifted_columns"), list)
    assert s.get("total_columns") == 2
    assert isinstance(s.get("stable_columns"), list)


def test_summary_on_clean(baseline, clean):
    r = analyze(baseline, clean)
    s = r.get("summary", {})
    assert s.get("pass_count") == 2
    assert s.get("drifted_columns") == []


# ─── Sample size warning ─────────────────────────────────────────────────────

def test_sample_size_warning_fires_on_mismatch():
    b_big = resolve_input({"score": list(range(100))})
    n_small = resolve_input({"score": [1, 2, 3, 4, 5]})
    r = analyze(b_big, n_small)
    assert any("mismatch" in w.lower() for w in r["columns"]["score"].get("warnings", []))


def test_no_sample_size_warning_on_equal_sizes():
    b_eq = resolve_input({"score": list(range(10))})
    n_eq = resolve_input({"score": list(range(10, 20))})
    r = analyze(b_eq, n_eq)
    assert not any("mismatch" in w.lower() for w in r["columns"]["score"].get("warnings", []))


# ─── Metrics extras ──────────────────────────────────────────────────────────

def test_metrics_extras_present(baseline, drifted):
    r = analyze(baseline, drifted)
    m = r["columns"]["age"]["metrics"]
    assert "baseline_count" in m
    assert "new_count" in m
    assert "trend_direction" in m
