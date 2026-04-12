import json
import os
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Optional
from urllib.parse import urlparse

import requests

STEP_ENDPOINT_BY_NAME = {
    "start_run": "/internal/pipeline/poc/start-run",
    "search_materialize": "/internal/pipeline/poc/search-materialize",
    "read_extract": "/internal/pipeline/poc/read-extract",
    "analyze": "/internal/pipeline/poc/analyze",
    "finalize_report": "/internal/pipeline/poc/finalize-report",
    "zai_search_canary": "/internal/pipeline/poc/zai-search-canary",
}

SOURCE_BY_STEP = {
    "start_run": "windmill:f/affordabot/pipeline_sanjose_searxng_zai_poc/start_run",
    "search_materialize": "windmill:f/affordabot/pipeline_sanjose_searxng_zai_poc/search_materialize",
    "read_extract": "windmill:f/affordabot/pipeline_sanjose_searxng_zai_poc/read_extract",
    "analyze": "windmill:f/affordabot/pipeline_sanjose_searxng_zai_poc/analyze",
    "finalize_report": "windmill:f/affordabot/pipeline_sanjose_searxng_zai_poc/finalize_report",
    "zai_search_canary": "windmill:f/affordabot/zai_web_search_weekly_canary/zai_search_canary",
}


def normalize_slack_webhook_url(webhook_url: Optional[str]) -> Optional[str]:
    if webhook_url is None:
        return None

    candidate = str(webhook_url).strip()
    if not candidate:
        return None

    for _ in range(2):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            break
        if isinstance(parsed, str):
            candidate = parsed.strip()
            continue
        break

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
        response = requests.post(normalized_webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        print(f"Slack alert sent: [{severity}] {title}")
    except Exception as exc:
        print(f"Failed to send Slack alert: {exc}")


def _merge_payload(base_payload: dict[str, Any], extra_payload: Optional[dict[str, Any]]) -> dict[str, Any]:
    if extra_payload is None:
        return base_payload
    merged = dict(base_payload)
    merged.update(extra_payload)
    return merged


def main(
    step: str,
    backend_url: str,
    cron_secret: str,
    env: str = "dev",
    timeout_seconds: int = 180,
    slack_webhook_url: Optional[str] = None,
    run_id: Optional[str] = None,
    windmill_flow_run_id: Optional[str] = None,
    windmill_job_id: Optional[str] = None,
    jurisdiction: str = "San Jose, CA",
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if step not in STEP_ENDPOINT_BY_NAME:
        raise ValueError(f"Unsupported step: {step}")

    endpoint = STEP_ENDPOINT_BY_NAME[step]
    url = f"{backend_url.rstrip('/')}{endpoint}"
    normalized_slack_webhook_url = normalize_slack_webhook_url(slack_webhook_url)

    source = SOURCE_BY_STEP.get(step, f"windmill:f/affordabot/pipeline_step/{step}")
    headers = {
        "Authorization": f"Bearer {cron_secret}",
        "X-PR-CRON-SECRET": cron_secret,
        "X-PR-CRON-SOURCE": source,
        "X-PR-PIPELINE-STEP": step,
        "Content-Type": "application/json",
    }

    request_payload = {
        "contract_version": "persisted-pipeline.v1",
        "step": step,
        "run_id": run_id,
        "windmill_flow_run_id": windmill_flow_run_id,
        "windmill_job_id": windmill_job_id,
        "jurisdiction": jurisdiction,
    }
    request_payload = _merge_payload(request_payload, payload)

    try:
        response = requests.post(
            url,
            headers=headers,
            json=request_payload,
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        send_slack_alert(
            normalized_slack_webhook_url,
            "ERROR",
            f"Affordabot pipeline step {step}: REQUEST_FAILED",
            f"Request to `{url}` failed: `{exc}`",
            env,
        )
        raise

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = {"raw_text": response.text}

    if response.status_code >= 400:
        send_slack_alert(
            normalized_slack_webhook_url,
            "ERROR",
            f"Affordabot pipeline step {step}: HTTP_{response.status_code}",
            f"Endpoint `{url}` returned `{response.status_code}`.\n```{response_payload}```",
            env,
        )
        response.raise_for_status()

    status = response_payload.get("status", "unknown") if isinstance(response_payload, dict) else "unknown"
    decision = response_payload.get("decision") if isinstance(response_payload, dict) else None
    severity = "INFO"
    if status in {"failed", "blocked"}:
        severity = "ERROR"
    elif decision == "stale_backed":
        severity = "WARNING"

    send_slack_alert(
        normalized_slack_webhook_url,
        severity,
        f"Affordabot pipeline step {step}: {status.upper()}",
        f"Decision: `{decision}`\n```{response_payload}```",
        env,
    )

    result = {
        "step": step,
        "status": status,
        "decision": decision,
        "http_status": response.status_code,
        "response": response_payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "env": env,
        "slack_configured": bool(normalized_slack_webhook_url),
    }
    print(result)
    return result
