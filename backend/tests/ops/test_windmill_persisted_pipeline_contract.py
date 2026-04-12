from importlib.util import module_from_spec
from importlib.util import spec_from_file_location
from pathlib import Path

import pytest
import requests


ROOT = Path(__file__).resolve().parents[3]
WINDMILL_DIR = ROOT / "ops" / "windmill" / "f" / "affordabot"
STEP_TRIGGER_SCRIPT_PATH = WINDMILL_DIR / "trigger_pipeline_step.py"
STEP_TRIGGER_SCHEMA_PATH = WINDMILL_DIR / "trigger_pipeline_step.script.yaml"
POC_FLOW_PATH = WINDMILL_DIR / "pipeline_sanjose_searxng_zai_poc__flow" / "flow.yaml"
POC_SCHEDULE_PATH = WINDMILL_DIR / "pipeline_sanjose_searxng_zai_poc.schedule.yaml"
ZAI_CANARY_FLOW_PATH = WINDMILL_DIR / "zai_web_search_weekly_canary__flow" / "flow.yaml"
ZAI_CANARY_SCHEDULE_PATH = WINDMILL_DIR / "zai_web_search_weekly_canary.schedule.yaml"
README_PATH = ROOT / "ops" / "windmill" / "README.md"

spec = spec_from_file_location("windmill_trigger_pipeline_step", STEP_TRIGGER_SCRIPT_PATH)
trigger_pipeline_step = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(trigger_pipeline_step)


class DummyResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_poc_flow_contract_has_step_order_retry_timeout_and_branches():
    flow_text = POC_FLOW_PATH.read_text()
    schedule_text = POC_SCHEDULE_PATH.read_text()

    assert "id: start_run" in flow_text
    assert "id: search_materialize" in flow_text
    assert "id: decision_branch" in flow_text
    assert "id: read_extract_fresh" in flow_text
    assert "id: analyze_fresh" in flow_text
    assert "id: finalize_report_fresh" in flow_text

    assert "path: f/affordabot/trigger_pipeline_step" in flow_text
    assert "value: search_materialize" in flow_text
    assert "value: 180" in flow_text
    assert "retry:" in flow_text
    assert "attempts: 3" in flow_text
    assert "type: branchone" in flow_text
    assert "expr: results.search_materialize.response.decision" in flow_text
    assert "fresh_snapshot:" in flow_text
    assert "stale_backed:" in flow_text
    assert "zero_results:" in flow_text
    assert "provider_failed_no_fallback:" in flow_text
    assert "fail_zero_results" in flow_text
    assert "fail_provider_no_fallback" in flow_text
    assert "zai_search_canary" not in flow_text
    assert "web_search" not in flow_text.lower()

    assert "script_path: f/affordabot/pipeline_sanjose_searxng_zai_poc" in schedule_text
    assert "is_flow: true" in schedule_text
    assert "enabled: false" in schedule_text


def test_deprecated_zai_web_search_is_canary_only():
    canary_flow_text = ZAI_CANARY_FLOW_PATH.read_text()
    canary_schedule_text = ZAI_CANARY_SCHEDULE_PATH.read_text()
    readme_text = README_PATH.read_text()

    assert "value: zai_search_canary" in canary_flow_text
    assert "product_path_enabled: false" in canary_flow_text
    assert "script_path: f/affordabot/zai_web_search_weekly_canary" in canary_schedule_text
    assert "enabled: false" in canary_schedule_text

    assert "Z.ai direct Web Search: deprecated, canary only, disabled by default" in readme_text
    assert "zai_web_search_weekly_canary" in readme_text


def test_step_trigger_schema_and_script_contract():
    schema_text = STEP_TRIGGER_SCHEMA_PATH.read_text()
    script_text = STEP_TRIGGER_SCRIPT_PATH.read_text()
    script_text_lower = script_text.lower()

    assert "step:" in schema_text
    assert "timeout_seconds:" in schema_text
    assert "windmill_flow_run_id:" in schema_text
    assert "windmill_job_id:" in schema_text
    assert "payload:" in schema_text

    assert "STEP_ENDPOINT_BY_NAME" in script_text
    assert '"/internal/pipeline/poc/start-run"' in script_text
    assert '"/internal/pipeline/poc/search-materialize"' in script_text
    assert '"/internal/pipeline/poc/read-extract"' in script_text
    assert '"/internal/pipeline/poc/analyze"' in script_text
    assert '"/internal/pipeline/poc/finalize-report"' in script_text
    assert "X-PR-CRON-SECRET" in script_text
    assert "X-PR-CRON-SOURCE" in script_text
    assert "X-PR-PIPELINE-STEP" in script_text

    # Windmill orchestration only: no direct DB/object-store writes in trigger scripts.
    assert "psycopg" not in script_text_lower
    assert "sqlalchemy" not in script_text_lower
    assert "insert into" not in script_text_lower
    assert "update " not in script_text_lower
    assert "minio" not in script_text_lower


def test_main_posts_expected_step_headers_and_payload(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse(
            status_code=200,
            payload={
                "status": "succeeded",
                "decision": "fresh_snapshot",
                "run_id": "run-123",
            },
        )

    monkeypatch.setattr(trigger_pipeline_step.requests, "post", fake_post)
    monkeypatch.setattr(trigger_pipeline_step, "send_slack_alert", lambda *args, **kwargs: None)

    result = trigger_pipeline_step.main(
        step="search_materialize",
        backend_url="https://backend.example.com/",
        cron_secret="secret-123",
        timeout_seconds=180,
        run_id="run-123",
        windmill_flow_run_id="flow-1",
        windmill_job_id="job-1",
        jurisdiction="San Jose, CA",
        payload={"query_family": "city_council_minutes"},
    )

    assert captured["url"] == "https://backend.example.com/internal/pipeline/poc/search-materialize"
    assert captured["headers"]["Authorization"] == "Bearer secret-123"
    assert captured["headers"]["X-PR-CRON-SECRET"] == "secret-123"
    assert captured["headers"]["X-PR-PIPELINE-STEP"] == "search_materialize"
    assert captured["timeout"] == 180
    assert captured["json"]["contract_version"] == "persisted-pipeline.v1"
    assert captured["json"]["run_id"] == "run-123"
    assert captured["json"]["windmill_flow_run_id"] == "flow-1"
    assert captured["json"]["windmill_job_id"] == "job-1"
    assert captured["json"]["jurisdiction"] == "San Jose, CA"
    assert captured["json"]["query_family"] == "city_council_minutes"
    assert result["status"] == "succeeded"
    assert result["decision"] == "fresh_snapshot"


def test_main_raises_on_http_error_and_sends_error_alert(monkeypatch):
    alerts = []

    def fake_post(url, headers, json, timeout):
        return DummyResponse(status_code=503, payload={"status": "failed", "decision": "provider_failed_no_fallback"})

    def fake_alert(webhook_url, severity, title, message, env):
        alerts.append((severity, title, message, env))

    monkeypatch.setattr(trigger_pipeline_step.requests, "post", fake_post)
    monkeypatch.setattr(trigger_pipeline_step, "send_slack_alert", fake_alert)

    with pytest.raises(requests.HTTPError):
        trigger_pipeline_step.main(
            step="search_materialize",
            backend_url="https://backend.example.com",
            cron_secret="secret-123",
            slack_webhook_url="https://hooks.slack.test/services/abc",
        )

    assert alerts
    assert alerts[0][0] == "ERROR"
    assert "HTTP_503" in alerts[0][1]
