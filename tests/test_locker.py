"""
test_locker.py — Baseline locking.

Includes regression tests for the v0.12.0 fix: lock files previously
stored the entire raw baseline dataset under "values_sample" instead of
a bounded statistical fingerprint, defeating the purpose of a "lock" file
(committable, portable, small) and leaking raw training data into JSON.
"""

import os
import json
import tempfile
import pytest
from psiwatch.locker import save_lock, load_lock, lock_info
from psiwatch.analyzer import analyze


@pytest.fixture
def lock_path():
    with tempfile.NamedTemporaryFile(suffix=".lock.json", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


def test_save_lock_creates_file(lock_path):
    src = {"age": [22, 23, 21, 24, 25] * 4,
           "city": ["Chennai", "Delhi", "Mumbai", "Chennai", "Delhi"] * 4}
    lock = save_lock(src, lock_path=lock_path)
    assert os.path.exists(lock_path)
    assert lock.get("psiwatch_lock") is True
    assert "age" in lock["columns"] and "city" in lock["columns"]


def test_load_lock_stable_data_health_100(lock_path):
    src = {"age": [22, 23, 21, 24, 25] * 4, "city": ["Chennai", "Delhi", "Mumbai", "Chennai", "Delhi"] * 4}
    save_lock(src, lock_path=lock_path)
    stable_new = {"age": [22, 23, 21, 24, 25] * 4, "city": ["Chennai", "Delhi", "Mumbai", "Chennai", "Delhi"] * 4}
    r = load_lock(stable_new, lock_path=lock_path)
    assert r["health_score"] == 100


def test_load_lock_drifted_data_health_low(lock_path):
    src = {"age": [22, 23, 21, 24, 25] * 4, "city": ["Chennai", "Delhi", "Mumbai", "Chennai", "Delhi"] * 4}
    save_lock(src, lock_path=lock_path)
    drifted_new = {"age": [40, 42, 44, 46, 48] * 4, "city": ["Pune", "Kochi", "Gurugram", "Noida", "Surat"] * 4}
    r = load_lock(drifted_new, lock_path=lock_path)
    assert r["health_score"] <= 50


def test_lock_info_runs_without_error(lock_path, capsys):
    src = {"age": [22, 23, 21, 24, 25] * 4}
    save_lock(src, lock_path=lock_path)
    result = lock_info(lock_path=lock_path)
    assert result is not None


def test_load_lock_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        load_lock({"age": [1, 2, 3]}, lock_path="/tmp/definitely_does_not_exist.lock.json")


# ─── Regression: lock file must NOT contain raw row values ─────────────────

def test_lock_file_does_not_store_raw_values(lock_path):
    """
    v0.12.0 regression test. The old format stored every raw value under
    "values_sample" — a 10,000-row baseline produced a 10,000-element
    JSON array, leaking training data and defeating the point of a lock
    file. This must never come back.
    """
    src = {"age": list(range(2000))}
    save_lock(src, lock_path=lock_path)
    with open(lock_path) as f:
        raw_text = f.read()
    data = json.loads(raw_text)

    assert "values_sample" not in data["columns"]["age"]
    # The fingerprint must be bounded — not proportional to row count.
    # 2000 raw floats would be tens of KB; a histogram-based summary
    # should be under 2KB regardless of how many rows were locked.
    assert len(raw_text) < 2000


def test_lock_file_size_bounded_for_large_dataset(lock_path):
    """A 50,000-row baseline must still produce a small lock file."""
    src = {"age": list(range(50_000))}
    save_lock(src, lock_path=lock_path)
    size = os.path.getsize(lock_path)
    assert size < 5_000, (
        f"Lock file is {size} bytes for 50,000 rows — looks like raw "
        f"values are being stored again instead of a fingerprint."
    )


def test_lock_then_check_matches_direct_compare_severity():
    """
    The severity classification (not the exact PSI float — binning basis
    differs between direct-compare and lock-based-compare by design)
    must agree between analyze() on raw data and load_lock() on a
    locked fingerprint of the same baseline.
    """
    import random
    random.seed(7)
    baseline = {"age": [random.randint(20, 30) for _ in range(2000)]}
    drifted_new = {"age": [random.randint(40, 50) for _ in range(2000)]}
    stable_new = {"age": [random.randint(20, 30) for _ in range(2000)]}

    direct_drift = analyze(baseline, drifted_new)
    direct_stable = analyze(baseline, stable_new)

    with tempfile.NamedTemporaryFile(suffix=".lock.json", delete=False) as f:
        path = f.name
    try:
        save_lock(baseline, lock_path=path)
        lock_drift = load_lock(drifted_new, lock_path=path)
        lock_stable = load_lock(stable_new, lock_path=path)

        assert direct_drift["columns"]["age"]["severity"] == lock_drift["columns"]["age"]["severity"] == "HIGH"
        assert direct_stable["columns"]["age"]["severity"] == lock_stable["columns"]["age"]["severity"] == "PASS"
    finally:
        os.unlink(path)


def test_legacy_v1_lock_file_rejected_with_clear_message(lock_path):
    """
    Lock files written by psiwatch <= 0.11.0 used the raw values_sample
    format. Silently "supporting" them would mean silently reading raw
    training data back out of an old lock — instead they must fail
    loudly and tell the user to regenerate the lock.
    """
    legacy_lock = {
        "psiwatch_lock": True,
        "version": "1",
        "created_at": "2026-01-01 00:00:00",
        "source": "old.csv",
        "columns": {"age": {"type": "numeric", "count": 3, "values_sample": [1.0, 2.0, 3.0]}},
    }
    with open(lock_path, "w") as f:
        json.dump(legacy_lock, f)

    with pytest.raises(ValueError, match="older psiwatch version"):
        load_lock({"age": [1, 2, 3]}, lock_path=lock_path)


def test_categorical_lock_preserves_category_set(lock_path):
    src = {"grade": ["A", "B", "C", "A", "B"] * 10}
    save_lock(src, lock_path=lock_path)
    with open(lock_path) as f:
        data = json.load(f)
    assert set(data["columns"]["grade"]["summary"]["categories"]) == {"A", "B", "C"}


def test_categorical_lock_detects_new_categories(lock_path):
    src = {"grade": ["A", "B", "C", "A", "B"] * 10}
    save_lock(src, lock_path=lock_path)
    new_data = {"grade": ["D", "E", "F", "D", "E"] * 10}
    r = load_lock(new_data, lock_path=lock_path)
    assert r["columns"]["grade"]["severity"] == "HIGH"
    assert set(r["columns"]["grade"]["metrics"]["new_categories"]) == {"D", "E", "F"}
