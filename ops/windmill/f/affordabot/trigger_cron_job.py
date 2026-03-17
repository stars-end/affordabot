import os
from datetime import datetime, timezone
from typing import Optional

import requests

SOURCE_BY_ENDPOINT = {
    "discovery": "windmill:f/affordabot/discovery_run",
    "daily-scrape": "windmill:f/affordabot/daily_scrape",
    "rag-spiders": "windmill:f/affordabot/rag_spiders",
    "universal-harvester": "windmill:f/affordabot/universal_harvester",
}


def send_slack_alert(
    webhook_url: Optional[str],
    severity: str,
    title: str,
    message: str,
    env: str = "dev",
) -> None:
    """Send Windmill cron alerts using the same webhook-driven pattern as Prime."""
    if not webhook_url:
        return

    emoji_map = {"INFO": "✅", "WARNING": "⚠️", "ERROR": "🔴", "CRITICAL": "🚨"}
    emoji = emoji_map.get(severity, "📢")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hostname = os.uname().nodename.split(".")[0]

    payload = {
        "text": f"[{severity}] {emoji} {title}",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*[{severity}]* {emoji} *{title}*"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": message}},
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"env={env} | host={hostname} | time={timestamp}"}],
            },
        ],
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"Slack alert sent: [{severity}] {title}")
    except Exception as exc:
        print(f"Failed to send Slack alert: {exc}")


def main(
    endpoint: str,
    backend_url: str,
    cron_secret: str,
    env: str = "dev",
    timeout_seconds: int = 7200,
    slack_webhook_url: Optional[str] = None,
) -> dict:
    """
    Trigger an affordabot cron job over HTTP from Windmill.

    Windmill owns scheduling and observability. The backend owns execution.
    """
    base_url = backend_url.rstrip("/")
    url = f"{base_url}/cron/{endpoint}"
    source = SOURCE_BY_ENDPOINT.get(endpoint, f"windmill:f/affordabot/{endpoint}")

    headers = {
        "Authorization": f"Bearer {cron_secret}",
        "X-PR-CRON-SECRET": cron_secret,
        "X-PR-CRON-SOURCE": source,
        "Content-Type": "application/json",
    }

    print(f"Triggering {endpoint} against {url}")

    try:
        response = requests.post(url, headers=headers, timeout=timeout_seconds)
    except requests.RequestException as exc:
        error = {
            "endpoint": endpoint,
            "status": "failed",
            "error": f"request_error: {exc}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "env": env,
        }
        print(error)
        send_slack_alert(
            slack_webhook_url,
            "ERROR",
            f"Affordabot {endpoint}: REQUEST_FAILED",
            f"Request to `{url}` failed: `{exc}`",
            env,
        )
        raise

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw_text": response.text}

    if response.status_code >= 400:
        error = {
            "endpoint": endpoint,
            "status": "failed",
            "http_status": response.status_code,
            "response": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "env": env,
        }
        print(error)
        send_slack_alert(
            slack_webhook_url,
            "ERROR",
            f"Affordabot {endpoint}: HTTP_{response.status_code}",
            f"Endpoint `{url}` returned `{response.status_code}`.\n```{payload}```",
            env,
        )
        response.raise_for_status()

    result_status = payload.get("status", "unknown") if isinstance(payload, dict) else "unknown"
    result = {
        "endpoint": endpoint,
        "status": "succeeded",
        "http_status": response.status_code,
        "response": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "env": env,
        "slack_configured": bool(slack_webhook_url),
    }
    if result_status == "succeeded":
        send_slack_alert(
            slack_webhook_url,
            "INFO",
            f"Affordabot {endpoint}: SUCCESS",
            f"Endpoint `{endpoint}` completed successfully.\n```{payload}```",
            env,
        )
    else:
        send_slack_alert(
            slack_webhook_url,
            "ERROR",
            f"Affordabot {endpoint}: FAILED",
            f"Endpoint `{endpoint}` returned a non-success payload.\n```{payload}```",
            env,
        )
    print(result)
    return result
