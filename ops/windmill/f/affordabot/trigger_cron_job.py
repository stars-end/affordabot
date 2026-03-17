from datetime import datetime, timezone
from typing import Optional

import requests

SOURCE_BY_ENDPOINT = {
    "discovery": "windmill:f/affordabot/discovery_run",
    "daily-scrape": "windmill:f/affordabot/daily_scrape",
    "rag-spiders": "windmill:f/affordabot/rag_spiders",
    "universal-harvester": "windmill:f/affordabot/universal_harvester",
}


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
        response.raise_for_status()

    result = {
        "endpoint": endpoint,
        "status": "succeeded",
        "http_status": response.status_code,
        "response": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "env": env,
        "slack_configured": bool(slack_webhook_url),
    }
    print(result)
    return result
