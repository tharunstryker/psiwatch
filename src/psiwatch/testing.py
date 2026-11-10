"""
testing.py — drift assertions for pytest / unittest.

    from psiwatch import assert_no_drift

    def test_training_data_has_not_drifted():
        assert_no_drift("train.csv", "latest.csv")

Raises AssertionError (so pytest shows a normal test failure) listing every
drifted column and why. Standard library only.
"""

from .analyzer import analyze as _analyze, DEFAULT_THRESHOLDS  # noqa: F401
from .loader import resolve_input


def assert_no_drift(old, new, min_health=80, max_severity="PASS", columns=None,
                    ignore_columns=None, thresholds=None, text_columns=None,
                    detect_text=True):
    """
    Fail (AssertionError) if `new` has drifted from `old`.

    Args:
        old, new: CSV/Parquet path, dict, list of dicts, or DataFrame.
        min_health: fail if the health score is below this (default 80,
            the same line as --fail-on-drift).
        max_severity: worst per-column severity allowed — "PASS" (default,
            any drifted column fails), "MEDIUM" (only HIGH columns fail), or
            "HIGH" (only the health score is checked).
        columns, ignore_columns, thresholds, text_columns, detect_text:
            same as psiwatch.compare().

    Returns the analysis result when it passes, so you can inspect it.
    """
    order = {"PASS": 0, "MEDIUM": 1, "HIGH": 2}
    if max_severity not in order:
        raise ValueError("max_severity must be 'PASS', 'MEDIUM' or 'HIGH'")

    result = _analyze(resolve_input(old), resolve_input(new), columns=columns,
                      ignore_columns=ignore_columns,
                      thresholds={**DEFAULT_THRESHOLDS, **(thresholds or {})},
                      text_columns=text_columns, detect_text=detect_text)

    bad = []
    for col, r in result["columns"].items():
        if r["severity"] in order and order[r["severity"]] > order[max_severity]:
            why = "; ".join(r.get("reasons") or ["drift detected"])
            bad.append(f"  - {col} [{r['severity']}]: {why}")

    health = result["health_score"]
    if health < min_health or bad:
        lines = [f"Data drift detected — health score {health}/100 (minimum {min_health})"]
        lines += bad or ["  (no single column crossed the limit; the combined score is low)"]
        raise AssertionError("\n".join(lines))
    return result
