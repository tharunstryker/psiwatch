"""
webhook.py — Webhook alerts for psiwatch.

Sends a drift notification to Slack, Discord, or any generic JSON
endpoint when drift is detected.

Usage:
    psiwatch compare old.csv new.csv --webhook https://hooks.slack.com/services/XXX
    psiwatch check new.csv --webhook https://discord.com/api/webhooks/XXX/YYY
    psiwatch watch data/ --webhook https://example.com/psiwatch-alerts

Target format is auto-detected from the URL host:
    hooks.slack.com / slack.com   → Slack message format  {"text": ...}
    discord.com / discordapp.com  → Discord message format {"content": ...}
    anything else                 → generic JSON payload

By default, alerts are only sent when health_score < 80 (i.e. drift
was actually detected). Pass always=True to send on every run.

This module never raises — webhook failures (network errors, bad
URLs, non-2xx responses) are reported via the return value only, so
a broken webhook never breaks a compare/check/watch run.
"""

import json
import urllib.request
import urllib.error


def _icon(health):
    if health >= 80:
        return "🟢"
    if health >= 50:
        return "🟡"
    return "🔴"


def _status_label(health):
    if health >= 80:
        return "Healthy"
    if health >= 50:
        return "Moderate Drift"
    return "Significant Drift"


def format_message(result, source_info=None):
    """Build a short human-readable summary of a drift result."""
    health = result["health_score"]
    summary = result["summary"]

    lines = [f"{_icon(health)} psiwatch — {health}/100 ({_status_label(health)})"]
    if source_info:
        lines.append(source_info)

    lines.append(
        f"HIGH: {summary['high_count']}  "
        f"MEDIUM: {summary['medium_count']}  "
        f"PASS: {summary['pass_count']}"
    )

    if summary["drifted_columns"]:
        lines.append(f"Drifted columns: {', '.join(summary['drifted_columns'])}")
    else:
        lines.append("All columns stable.")

    return "\n".join(lines)


def build_payload(url, result, source_info=None):
    """Build the JSON payload appropriate for the target webhook URL."""
    text = format_message(result, source_info=source_info)
    host = url.lower()

    if "hooks.slack.com" in host or "slack.com" in host:
        return {"text": text}

    if "discord.com" in host or "discordapp.com" in host:
        return {"content": text}

    return {
        "event": "psiwatch_drift_report",
        "health_score": result["health_score"],
        "summary": result["summary"],
        "source": source_info,
        "message": text,
    }


def send_webhook(url, result, source_info=None, always=False, timeout=5):
    """
    POST a drift notification to a webhook URL.

    Args:
        url: webhook URL (Slack, Discord, or generic JSON endpoint)
        result: a psiwatch analyze()/compare() result dict
        source_info: optional label describing the dataset/source
        always: if False (default), only sends when health_score < 80
        timeout: request timeout in seconds

    Returns:
        True if the webhook was sent and returned a 2xx status,
        False if skipped (no drift, no URL) or if sending failed.
        Never raises.
    """
    if not url:
        return False

    if not always and result.get("health_score", 100) >= 80:
        return False

    payload = build_payload(url, result, source_info=source_info)
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "psiwatch-webhook"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", resp.getcode())
            return 200 <= status < 300
    except Exception:
        return False
