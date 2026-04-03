import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests

SOURCE_BY_ENDPOINT = {
    "discovery": "windmill:f/affordabot/discovery_run",
    "daily-scrape": "windmill:f/affordabot/daily_scrape",
    "rag-spiders": "windmill:f/affordabot/rag_spiders",
    "universal-harvester": "windmill:f/affordabot/universal_harvester",
    "manual-substrate-expansion": "windmill:f/affordabot/manual_substrate_expansion",
}


def normalize_slack_webhook_url(webhook_url: Optional[str]) -> Optional[str]:
    """Normalize and validate Slack webhook URL values from Windmill vars."""
    if webhook_url is None:
        return None

    candidate = str(webhook_url).strip()
    if not candidate:
        return None

    # Handle accidental JSON string wrapping, e.g. "\"https://hooks.slack...\""
    for _ in range(2):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            break
        if isinstance(parsed, str):
            candidate = parsed.strip()
            continue
        break

    # Handle simple quote wrapping, e.g. '"https://hooks.slack..."'
    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in {"'", '"'}:
        candidate = candidate[1:-1].strip()

    parsed_url = urlparse(candidate)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return None
    return candidate


def send_slack_alert(
    webhook_url: Optional[str],
    severity: str,
    title: str,
    message: str,
    env: str = "dev",
) -> None:
    """Send Windmill cron alerts using the same webhook-driven pattern as Prime."""
    normalized_webhook_url = normalize_slack_webhook_url(webhook_url)
    if not normalized_webhook_url:
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
        resp = requests.post(normalized_webhook_url, json=payload, timeout=10)
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
    payload: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Trigger an affordabot cron job over HTTP from Windmill.

    Windmill owns scheduling and observability. The backend owns execution.
    """
    base_url = backend_url.rstrip("/")
    url = f"{base_url}/cron/{endpoint}"
    source = SOURCE_BY_ENDPOINT.get(endpoint, f"windmill:f/affordabot/{endpoint}")
    normalized_slack_webhook_url = normalize_slack_webhook_url(slack_webhook_url)

    headers = {
        "Authorization": f"Bearer {cron_secret}",
        "X-PR-CRON-SECRET": cron_secret,
        "X-PR-CRON-SOURCE": source,
        "Content-Type": "application/json",
    }

    print(f"Triggering {endpoint} against {url}")

    request_kwargs: Dict[str, Any] = {
        "headers": headers,
        "timeout": timeout_seconds,
    }
    if payload is not None:
        request_kwargs["json"] = payload

    try:
        response = requests.post(url, **request_kwargs)
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
        "slack_configured": bool(normalized_slack_webhook_url),
    }
    if result_status == "succeeded":
        send_slack_alert(
            normalized_slack_webhook_url,
            "INFO",
            f"Affordabot {endpoint}: SUCCESS",
            f"Endpoint `{endpoint}` completed successfully.\n```{payload}```",
            env,
        )
    else:
        send_slack_alert(
            normalized_slack_webhook_url,
            "ERROR",
            f"Affordabot {endpoint}: FAILED",
            f"Endpoint `{endpoint}` returned a non-success payload.\n```{payload}```",
            env,
        )
    print(result)
    return result
