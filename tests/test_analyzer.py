"""
test_analyzer.py — psiwatch v0.11.0 full test suite
"""

import sys
import os
import tempfile
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from psiwatch.analyzer import analyze
from psiwatch.loader import resolve_input
from psiwatch import compare_columns, DriftDetected
from psiwatch.locker import save_lock, load_lock, lock_info
from psiwatch.trend import analyze_trend, print_trend
from psiwatch.webhook import build_payload, format_message, send_webhook

PASS_COUNT = 0
FAIL_COUNT = 0

def check(label, condition):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        print(f"PASS {label}")
        PASS_COUNT += 1
    else:
        print(f"FAIL {label}")
        FAIL_COUNT += 1

print("\nRunning psiwatch tests...\n")

# ─── Fixtures ─────────────────────────────────────────────────────────────────

baseline = resolve_input({"age": [22,23,21,24,25,23,22,24,21,25],
                          "score": [78,85,70,88,91,79,77,86,71,90]})
drifted  = resolve_input({"age": [35,38,40,42,44,36,39,41,43,45],
                          "score": [30,25,20,35,28,31,26,21,34,27]})
clean    = resolve_input({"age": [22,23,21,24,25,23,22,24,21,25],
                          "score": [78,85,70,88,91,79,77,86,71,90]})

# ─── Core analyzer ────────────────────────────────────────────────────────────

r = analyze(baseline, drifted)
check("numeric high drift detected", r["columns"]["age"]["severity"] == "HIGH")

r2 = analyze(baseline, clean)
check("numeric no drift — PASS", r2["columns"]["age"]["severity"] == "PASS")

b_cat = resolve_input({"city": ["Chennai","Delhi","Mumbai","Chennai","Delhi"]})
n_cat = resolve_input({"city": ["Chennai","Delhi","Pune","Kochi","Pune"]})
r3 = analyze(b_cat, n_cat)
check("categorical new category detected", r3["columns"]["city"]["severity"] in ("HIGH","MEDIUM"))

b_cat2 = resolve_input({"city": ["Chennai","Chennai","Delhi","Delhi","Mumbai"]})
n_cat2 = resolve_input({"city": ["Chennai","Chennai","Delhi","Delhi","Mumbai"]})
r4 = analyze(b_cat2, n_cat2)
check("categorical no drift — PASS", r4["columns"]["city"]["severity"] == "PASS")

r5 = analyze(baseline, drifted)
check("health score low on drift", r5["health_score"] <= 50)

r6 = analyze(baseline, clean)
check("health score 100 on clean data", r6["health_score"] == 100)

r7 = analyze(baseline, drifted, columns=["age"])
check("column filter works", "score" not in r7["columns"] and "age" in r7["columns"])

list_input = resolve_input([{"age": 22, "city": "Chennai"}, {"age": 23, "city": "Delhi"}])
check("list of dicts input works", "age" in list_input and "city" in list_input)

b_miss = resolve_input({"age": [22,23], "score": [78,85], "city": ["Chennai","Delhi"]})
n_miss = resolve_input({"age": [22,23], "score": [78,85]})
r8 = analyze(b_miss, n_miss)
check("missing column warning fires", any("city" in w for w in r8["warnings"]))

big_b = resolve_input({"age": list(range(20)) + [35,38,40,42,44]})
big_n = resolve_input({"age": [35,38,40,42,44,36,39,41,43,45,
                                36,38,40,42,44,37,39,41,43,45]})
r9 = analyze(big_b, big_n)
check("health score hard cap ≤50 on HIGH", r9["health_score"] <= 50)

# ─── summary dict ─────────────────────────────────────────────────────────────

r10 = analyze(baseline, drifted)
s = r10.get("summary", {})
check("summary key exists", "summary" in r10)
check("summary.high_count >= 1", s.get("high_count", 0) >= 1)
check("summary.drifted_columns is list", isinstance(s.get("drifted_columns"), list))
check("summary.total_columns == 2", s.get("total_columns") == 2)
check("summary.stable_columns is list", isinstance(s.get("stable_columns"), list))

r14 = analyze(baseline, clean)
s14 = r14.get("summary", {})
check("summary.pass_count == 2 on clean", s14.get("pass_count") == 2)
check("summary.drifted_columns empty on clean", s14.get("drifted_columns") == [])

# ─── sample size warning ──────────────────────────────────────────────────────

b_big = resolve_input({"score": list(range(100))})
n_small = resolve_input({"score": [1, 2, 3, 4, 5]})
r11 = analyze(b_big, n_small)
check("sample size warning fires on 20x mismatch",
      any("mismatch" in w.lower() for w in r11["columns"]["score"].get("warnings", [])))

b_eq = resolve_input({"score": list(range(10))})
n_eq = resolve_input({"score": list(range(10, 20))})
r12 = analyze(b_eq, n_eq)
check("no sample size warning on equal sizes",
      not any("mismatch" in w.lower() for w in r12["columns"]["score"].get("warnings", [])))

# ─── ignore_columns ───────────────────────────────────────────────────────────

b_ig = resolve_input({"age": [22,23,21], "id": [1,2,3], "score": [78,85,70]})
n_ig = resolve_input({"age": [35,38,40], "id": [4,5,6], "score": [30,25,20]})
r13 = analyze(b_ig, n_ig, ignore_columns=["id"])
check("ignore_columns removes column", "id" not in r13["columns"])
check("ignore_columns keeps others", "age" in r13["columns"])
check("ignore_columns warning present", any("id" in w for w in r13["warnings"]))

# ─── metrics extras ───────────────────────────────────────────────────────────

r15 = analyze(baseline, drifted)
m = r15["columns"]["age"]["metrics"]
check("metrics.baseline_count present", "baseline_count" in m)
check("metrics.new_count present", "new_count" in m)
check("metrics.trend_direction present", "trend_direction" in m)

# ─── lock system ──────────────────────────────────────────────────────────────

b_lock_src = {"age": [22,23,21,24,25]*4, "city": ["Chennai","Delhi","Mumbai","Chennai","Delhi"]*4}

with tempfile.NamedTemporaryFile(suffix=".lock.json", delete=False) as f:
    lock_path = f.name

try:
    lock = save_lock(b_lock_src, lock_path=lock_path)
    check("save_lock creates file", os.path.exists(lock_path))
    check("save_lock has psiwatch_lock key", lock.get("psiwatch_lock") is True)
    check("save_lock stores columns", "age" in lock["columns"] and "city" in lock["columns"])

    stable_new = {"age": [22,23,21,24,25]*4, "city": ["Chennai","Delhi","Mumbai","Chennai","Delhi"]*4}
    r_stable = load_lock(stable_new, lock_path=lock_path)
    check("load_lock stable — health 100", r_stable["health_score"] == 100)

    drifted_new = {"age": [40,42,44,46,48]*4, "city": ["Pune","Kochi","Gurugram","Noida","Surat"]*4}
    r_drift = load_lock(drifted_new, lock_path=lock_path)
    check("load_lock drifted — health ≤50", r_drift["health_score"] <= 50)

    try:
        lock_info(lock_path=lock_path)
        check("lock_info runs without error", True)
    except Exception:
        check("lock_info runs without error", False)

    try:
        load_lock(stable_new, lock_path="/tmp/nonexistent.lock.json")
        check("load_lock raises on missing lock", False)
    except FileNotFoundError:
        check("load_lock raises on missing lock", True)
finally:
    if os.path.exists(lock_path):
        os.unlink(lock_path)

# ─── trend — previous baseline ────────────────────────────────────────────────

_stable = [
    {"age": [22,23,21,24,25]*4},
    {"age": [22,23,21,24,25]*4},
    {"age": [22,23,21,24,25]*4},
]
tr1 = analyze_trend(_stable)
check("trend: returns required keys",
      {"files","steps","overall_health_history","worsening_columns","column_history"} <= set(tr1.keys()))
check("trend: stable → health 100 each step",
      all(h == 100 for h in tr1["overall_health_history"]))
check("trend: stable → no worsening columns", tr1["worsening_columns"] == [])
check("trend: 3 inputs → 2 steps (previous)", len(tr1["steps"]) == 2)
check("trend: step has from/to keys",
      "from" in tr1["steps"][0] and "to" in tr1["steps"][0])

_drifting = [
    {"age": [22,23,21,24,25]*4},
    {"age": [22,23,21,24,25]*4},
    {"age": [30,31,29,32,33]*4},
]
tr2 = analyze_trend(_drifting)
check("trend: drift detected in step 2", tr2["overall_health_history"][1] < 80)
check("trend: worsening column detected", "age" in tr2["worsening_columns"])

# ─── trend — first baseline ───────────────────────────────────────────────────

tr3 = analyze_trend(_drifting, baseline="first")
check("trend: baseline=first → 2 steps", len(tr3["steps"]) == 2)
check("trend: baseline=first → same 'from' label",
      tr3["steps"][0]["from"] == tr3["steps"][1]["from"])
check("trend: baseline_mode stored", tr3["baseline_mode"] == "first")

try:
    analyze_trend([{"age": [1,2,3]}])
    check("trend: single file raises ValueError", False)
except ValueError:
    check("trend: single file raises ValueError", True)

try:
    analyze_trend(_stable, baseline="wrong")
    check("trend: bad baseline raises ValueError", False)
except ValueError:
    check("trend: bad baseline raises ValueError", True)

# ─── trend — print_trend doesn't crash ────────────────────────────────────────

import io
from contextlib import redirect_stdout
buf = io.StringIO()
try:
    with redirect_stdout(buf):
        print_trend(tr2)
    check("print_trend runs without error", True)
except Exception:
    check("print_trend runs without error", False)

# ─── trend — column_history ───────────────────────────────────────────────────

check("column_history has severity_history",
      "severity_history" in tr2["column_history"]["age"])
check("column_history has psi_history",
      "psi_history" in tr2["column_history"]["age"])

# ─── webhook ──────────────────────────────────────────────────────────────────

_drift_result = analyze(baseline, drifted)
_clean_result = analyze(baseline, clean)

msg = format_message(_drift_result, source_info="old.csv → new.csv")
check("webhook: message contains health score", "/100" in msg)
check("webhook: drifted columns in message", "Drifted" in msg)
check("webhook: source_info in message", "old.csv" in msg)

slack_p = build_payload("https://hooks.slack.com/services/X", _drift_result, "test")
check("webhook: slack payload has 'text'", "text" in slack_p)

discord_p = build_payload("https://discord.com/api/webhooks/X/Y", _drift_result, "test")
check("webhook: discord payload has 'content'", "content" in discord_p)

generic_p = build_payload("https://example.com/hook", _drift_result, "test")
check("webhook: generic payload has 'event'", "event" in generic_p)
check("webhook: generic payload has 'health_score'", "health_score" in generic_p)
check("webhook: generic payload has 'summary'", "summary" in generic_p)

check("webhook: skipped when health >= 80 (no drift)",
      send_webhook("https://example.com", _clean_result) is False)
check("webhook: skipped when url=None",
      send_webhook(None, _drift_result) is False)

# healthy result with always=True should NOT be skipped (but will fail network — returns False)
result_always = send_webhook("https://example.invalid", _clean_result, always=True)
check("webhook: always=True attempts even on no drift (returns bool)",
      isinstance(result_always, bool))

# ─── config ───────────────────────────────────────────────────────────────────

from psiwatch.config import load_config, apply_config, write_example_config
import argparse

with tempfile.NamedTemporaryFile(suffix=".toml", delete=False, mode="w") as f:
    f.write("[psiwatch]\npsi_threshold = 0.15\nfail_on_drift = true\ncolumns = [\"age\", \"score\"]\n")
    cfg_path = f.name

try:
    cfg = load_config(explicit_path=cfg_path, silent=True)
    check("config: loads psi_threshold", cfg.get("psi_threshold") == 0.15)
    check("config: loads fail_on_drift", cfg.get("fail_on_drift") is True)
    check("config: loads columns as list", isinstance(cfg.get("columns"), list))

    ns = argparse.Namespace(psi_threshold=None, fail_on_drift=False, columns=None,
                            ignore_columns=None, format=None, output=None,
                            silent=False, webhook=None)
    apply_config(ns, cfg)
    check("apply_config: fills psi_threshold", ns.psi_threshold == 0.15)
    check("apply_config: fills fail_on_drift", ns.fail_on_drift is True)
    check("apply_config: CLI None filled from config", ns.columns is not None)

    # CLI value wins over config
    ns2 = argparse.Namespace(psi_threshold=0.30, fail_on_drift=False, columns=None,
                              ignore_columns=None, format=None, output=None,
                              silent=False, webhook=None)
    apply_config(ns2, cfg)
    check("apply_config: CLI value wins over config", ns2.psi_threshold == 0.30)
finally:
    os.unlink(cfg_path)

# ─── Final ────────────────────────────────────────────────────────────────────

print(f"\n{PASS_COUNT + FAIL_COUNT} tests — {PASS_COUNT} passed, {FAIL_COUNT} failed.")
if FAIL_COUNT:
    print("SOME TESTS FAILED.")
    sys.exit(1)
else:
    print("\nAll tests passed.\n")
