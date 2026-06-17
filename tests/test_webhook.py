"""
test_webhook.py — Webhook notification formatting and dispatch.
"""

from psiwatch.analyzer import analyze
from psiwatch.loader import resolve_input
from psiwatch.webhook import build_payload, format_message, send_webhook


def _results():
    baseline = resolve_input({"age": [22, 23, 21, 24, 25, 23, 22, 24, 21, 25],
                               "score": [78, 85, 70, 88, 91, 79, 77, 86, 71, 90]})
    drifted = resolve_input({"age": [35, 38, 40, 42, 44, 36, 39, 41, 43, 45],
                              "score": [30, 25, 20, 35, 28, 31, 26, 21, 34, 27]})
    clean = resolve_input({"age": [22, 23, 21, 24, 25, 23, 22, 24, 21, 25],
                            "score": [78, 85, 70, 88, 91, 79, 77, 86, 71, 90]})
    return analyze(baseline, drifted), analyze(baseline, clean)


def test_format_message_contains_health_score_and_drifted_columns():
    drift_result, _ = _results()
    msg = format_message(drift_result, source_info="old.csv → new.csv")
    assert "/100" in msg
    assert "Drifted" in msg
    assert "old.csv" in msg


def test_build_payload_slack():
    drift_result, _ = _results()
    payload = build_payload("https://hooks.slack.com/services/X", drift_result, "test")
    assert "text" in payload


def test_build_payload_discord():
    drift_result, _ = _results()
    payload = build_payload("https://discord.com/api/webhooks/X/Y", drift_result, "test")
    assert "content" in payload


def test_build_payload_generic():
    drift_result, _ = _results()
    payload = build_payload("https://example.com/hook", drift_result, "test")
    assert "event" in payload
    assert "health_score" in payload
    assert "summary" in payload


def test_send_webhook_skipped_when_health_ok():
    _, clean_result = _results()
    assert send_webhook("https://example.com", clean_result) is False


def test_send_webhook_skipped_when_url_none():
    drift_result, _ = _results()
    assert send_webhook(None, drift_result) is False


def test_send_webhook_always_true_still_returns_bool():
    _, clean_result = _results()
    result = send_webhook("https://example.invalid", clean_result, always=True)
    assert isinstance(result, bool)
