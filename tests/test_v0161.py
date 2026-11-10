"""
test_v0161.py — regression tests for the 0.16.1 fixes.

  * constant-baseline columns (std == 0) in compare(), locks and the Guard
  * compare_with_learned_thresholds(): HIGH health cap, text args, CLI output
  * rising/falling words ignore tiny moves
  * psiwatch.assert_no_drift()
"""

import json
import os
import random
import sys
import time

import pytest

import psiwatch
from psiwatch import Guard, assert_no_drift, save_baseline
from psiwatch.adapt import compare_with_learned_thresholds


# ─── Constant baseline (std == 0) ─────────────────────────────────────────────

def _sev(result, col="x"):
    return result["columns"][col]["severity"]


def test_constant_baseline_same_value_passes():
    r = psiwatch.analyze({"x": [0.0] * 300}, {"x": [0.0] * 300})
    assert _sev(r) == "PASS"


def test_constant_baseline_jump_is_high_in_compare():
    r = psiwatch.analyze({"x": [0.0] * 300}, {"x": [1_000_000.0] * 300})
    assert _sev(r) == "HIGH"
    assert r["columns"]["x"]["metrics"]["baseline_constant"] is True


def test_constant_baseline_small_change_is_noise_in_compare():
    base = {"x": [0.0] * 400}
    one_percent = {"x": [0.0] * 396 + [5.0] * 4}
    assert _sev(psiwatch.analyze(base, one_percent)) == "PASS"


def test_constant_baseline_caught_through_a_lock(tmp_path):
    lock = str(tmp_path / "c.lock.json")
    psiwatch.save_lock({"x": [0.0] * 400}, lock_path=lock)
    levels = {"x": ([0.0] * 396 + [5.0] * 4, "PASS"),        # 1% differ  -> noise
              "y": ([0.0] * 360 + [5.0] * 40, "MEDIUM"),     # 10% differ
              "z": ([0.0] * 200 + [5.0] * 200, "HIGH"),      # 50% differ
              "w": ([1_000_000.0] * 400, "HIGH")}            # everything moved
    for name, (new, expected) in levels.items():
        r = psiwatch.load_lock({"x": new}, lock_path=lock)
        assert r["columns"]["x"]["severity"] == expected, name


def test_constant_baseline_caught_by_guard(tmp_path):
    model = tmp_path / "m.joblib"
    model.write_bytes(b"model")
    save_baseline({"x": [0.0] * 300, "y": [float(i % 7) for i in range(300)]}, str(model))
    guard = Guard.from_model(str(model), window=200, min_samples=100,
                             check_every=50, background=False)
    for i in range(200):
        guard.observe({"x": 1_000_000.0, "y": float(i % 7)})
    st = guard.status()
    assert st["drifting"] is True
    assert "x" in st["drifted_columns"]


def test_constant_baseline_guard_stays_quiet_when_unchanged(tmp_path):
    model = tmp_path / "m.joblib"
    model.write_bytes(b"model")
    save_baseline({"x": [0.0] * 300, "y": [float(i % 7) for i in range(300)]}, str(model))
    guard = Guard.from_model(str(model), window=200, min_samples=100,
                             check_every=50, background=False)
    for i in range(300):
        guard.observe({"x": 0.0, "y": float(i % 7)})
    assert guard.status()["drifting"] is False


# ─── compare_with_learned_thresholds ─────────────────────────────────────────

def _thresholds_file(tmp_path, thresholds=None):
    p = tmp_path / "thr.json"
    p.write_text(json.dumps({"thresholds": thresholds or {}, "stats": {},
                             "source_files": [], "sensitivity": 3.0}))
    return str(p)


def _twenty_columns(shift_first):
    rng = random.Random(7)
    old = {f"c{i}": [rng.gauss(0, 1) for _ in range(400)] for i in range(20)}
    new = {f"c{i}": [rng.gauss(0, 1) for _ in range(400)] for i in range(20)}
    if shift_first:
        new["c0"] = [rng.gauss(8, 1) for _ in range(400)]
    return old, new


def test_learned_thresholds_health_matches_compare_and_caps_at_50(tmp_path):
    old, new = _twenty_columns(True)
    plain = psiwatch.analyze(old, new)
    learned = compare_with_learned_thresholds(old, new, _thresholds_file(tmp_path))
    assert plain["health_score"] <= 50
    assert learned["health_score"] == plain["health_score"]
    assert learned["summary"]["high_count"] == plain["summary"]["high_count"]


def test_learned_thresholds_forwards_text_columns(tmp_path):
    old = {"msg": [f"order number {i} please ship it" for i in range(80)]}
    new = {"msg": [f"order number {i} please ship it" for i in range(80)]}
    r = compare_with_learned_thresholds(old, new, _thresholds_file(tmp_path),
                                        text_columns=["msg"])
    assert r["columns"]["msg"]["type"] == "text"
    r = compare_with_learned_thresholds(old, new, _thresholds_file(tmp_path),
                                        detect_text=False)
    assert r["columns"]["msg"]["type"] == "categorical"


def test_cli_thresholds_file_writes_real_html(tmp_path, monkeypatch, capsys):
    from psiwatch import cli
    old, new = _twenty_columns(True)
    out = tmp_path / "r.html"
    # the CLI reads CSV files
    def write(path, cols):
        keys = list(cols)
        rows = ["{}".format(",".join(keys))]
        for i in range(len(cols[keys[0]])):
            rows.append(",".join(str(cols[k][i]) for k in keys))
        path.write_text("\n".join(rows))
    old_csv, new_csv = tmp_path / "old.csv", tmp_path / "new.csv"
    write(old_csv, old)
    write(new_csv, new)
    monkeypatch.setattr(sys, "argv", [
        "psiwatch", "compare", str(old_csv), str(new_csv),
        "--thresholds-file", _thresholds_file(tmp_path),
        "--output", str(out), "--silent",
    ])
    cli.main()
    page = out.read_text(encoding="utf-8")
    assert page.lstrip().lower().startswith("<!doctype html")
    assert "PSI<span>WATCH</span> REPORT" in page      # was "DRIFT<span>WATCH</span>"
    assert "DRIFT<span>" not in page


# ─── Rising / falling words ──────────────────────────────────────────────────

def test_tiny_word_moves_are_not_listed_as_rising():
    # "refund": 20% -> 20.4% of documents (noise). "outage": 2% -> 40% (real).
    base = [f"ticket {i} about billing" + (" refund" if i % 5 == 0 else "")
            + (" outage" if i % 50 == 1 else "") for i in range(500)]
    new = [f"ticket {i} about billing" + (" refund" if i % 5 == 0 or i == 2 else "")
           + (" outage" if i % 5 in (1, 2) else "") for i in range(500)]
    r = psiwatch.analyze({"t": base}, {"t": new}, text_columns=["t"])
    rising = [e["term"] for e in r["columns"]["t"]["metrics"].get("rising_terms", [])]
    assert "outage" in rising
    assert "refund" not in rising


# ─── assert_no_drift ─────────────────────────────────────────────────────────

def test_assert_no_drift_passes_on_same_distribution():
    rng = random.Random(1)
    a = {"v": [rng.gauss(0, 1) for _ in range(500)]}
    b = {"v": [rng.gauss(0, 1) for _ in range(500)]}
    result = assert_no_drift(a, b)
    assert result["health_score"] >= 80


def test_assert_no_drift_raises_and_names_the_column():
    rng = random.Random(1)
    a = {"v": [rng.gauss(0, 1) for _ in range(500)], "ok": [rng.gauss(0, 1) for _ in range(500)]}
    b = {"v": [rng.gauss(5, 1) for _ in range(500)], "ok": [rng.gauss(0, 1) for _ in range(500)]}
    with pytest.raises(AssertionError, match="v"):
        assert_no_drift(a, b)
    try:
        assert_no_drift(a, b)
    except AssertionError as e:
        assert "- v [HIGH]" in str(e)
        assert "- ok" not in str(e)


def test_assert_no_drift_max_severity_and_min_health():
    rng = random.Random(5)
    a = {"v": [rng.gauss(0, 1) for _ in range(800)]}
    b = {"v": [rng.gauss(0.3, 1) for _ in range(800)]}     # MEDIUM drift
    assert psiwatch.analyze(a, b)["columns"]["v"]["severity"] == "MEDIUM"
    with pytest.raises(AssertionError):
        assert_no_drift(a, b, min_health=0)                # default: any drift fails
    assert_no_drift(a, b, min_health=0, max_severity="MEDIUM")   # only HIGH fails
    with pytest.raises(AssertionError):
        assert_no_drift(a, b, min_health=90, max_severity="HIGH")  # score too low


def test_assert_no_drift_rejects_bad_max_severity():
    with pytest.raises(ValueError):
        assert_no_drift({"x": [1.0, 2.0]}, {"x": [1.0, 2.0]}, max_severity="LOW")


# ─── Chi-square with a new category ──────────────────────────────────────────

def test_new_category_does_not_blow_up_chi_square():
    base = {"plan": ["Home"] * 50 + ["Auto"] * 50}
    new = {"plan": ["Home"] * 40 + ["Auto"] * 40 + ["Crypto"] * 20}
    m = psiwatch.analyze(base, new)["columns"]["plan"]
    assert m["severity"] == "HIGH"                    # the new category is still flagged
    assert any("Crypto" in r for r in m["reasons"])
    assert m["metrics"]["chi_square"] < 5             # was ~40,000
