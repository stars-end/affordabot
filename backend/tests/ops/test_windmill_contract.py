from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import requests


ROOT = Path(__file__).resolve().parents[3]
WINDMILL_DIR = ROOT / "ops" / "windmill" / "f" / "affordabot"
TRIGGER_SCRIPT_PATH = WINDMILL_DIR / "trigger_cron_job.py"
WINDMILL_README_PATH = ROOT / "ops" / "windmill" / "README.md"
POLICY_EVIDENCE_SCRIPT_PATH = WINDMILL_DIR / "policy_evidence_package_orchestration.py"
BACKEND_MAIN_PATH = ROOT / "backend" / "main.py"


spec = spec_from_file_location("windmill_trigger_cron_job", TRIGGER_SCRIPT_PATH)
windmill_trigger = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(windmill_trigger)


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


@pytest.mark.parametrize(
    ("job_name", "endpoint", "schedule"),
    [
        ("discovery_run", "discovery", "schedule: 0 0 5 * * ?"),
        ("daily_scrape", "daily-scrape", "schedule: 0 0 6 * * ?"),
        ("rag_spiders", "rag-spiders", "schedule: 0 0 7 * * ?"),
        ("universal_harvester", "universal-harvester", "schedule: 0 0 8 * * ?"),
    ],
)
def test_shared_instance_windmill_assets_reference_trigger_contract(job_name, endpoint, schedule):
    flow_text = (WINDMILL_DIR / f"{job_name}__flow" / "flow.yaml").read_text()
    schedule_text = (WINDMILL_DIR / f"{job_name}.schedule.yaml").read_text()

    assert "path: f/affordabot/trigger_cron_job" in flow_text
    assert f"value: {endpoint}" in flow_text
    assert "value: $var:f/affordabot/BACKEND_PUBLIC_URL" in flow_text
    assert "value: $var:f/affordabot/CRON_SECRET" in flow_text
    assert "value: $var:f/affordabot/SLACK_WEBHOOK_URL" in flow_text
    assert "value: 7200" in flow_text
    assert "BACKEND_INTERNAL_URL" not in flow_text

    assert f"script_path: f/affordabot/{job_name}" in schedule_text
    assert "is_flow: true" in schedule_text
    assert "enabled: true" in schedule_text
    assert schedule in schedule_text


def test_trigger_script_schema_keeps_slack_webhook_input():
    schema_text = (WINDMILL_DIR / "trigger_cron_job.script.yaml").read_text()

    assert "slack_webhook_url:" in schema_text
    assert "Optional Slack webhook for Prime-style dev alert notifications." in schema_text
    assert "timeout_seconds:" in schema_text
    assert "backend_url:" in schema_text
    assert "cron_secret:" in schema_text
    assert "payload:" in schema_text


def test_manual_substrate_expansion_flow_references_trigger_contract():
    flow_text = (WINDMILL_DIR / "manual_substrate_expansion__flow" / "flow.yaml").read_text()

    assert "path: f/affordabot/trigger_cron_job" in flow_text
    assert "value: manual-substrate-expansion" in flow_text
    assert "value: $var:f/affordabot/BACKEND_PUBLIC_URL" in flow_text
    assert "value: $var:f/affordabot/CRON_SECRET" in flow_text
    assert "value: $var:f/affordabot/SLACK_WEBHOOK_URL" in flow_text
    assert "payload:" in flow_text
    assert "type: javascript" in flow_text
    assert "run_label: flow_input.run_label" in flow_text
    assert "jurisdictions: flow_input.jurisdictions" in flow_text
    assert "asset_classes: flow_input.asset_classes" in flow_text


def test_manual_substrate_expansion_readme_documents_cli_safe_operator_path():
    readme_text = WINDMILL_README_PATH.read_text()

    assert "wmill flow run f/affordabot/manual_substrate_expansion" in readme_text
    assert "Do not pass `-s` for this flow path." in readme_text
    assert "completed-job-not-found style response" in readme_text


def test_policy_evidence_backend_endpoint_route_mismatch_is_explicit():
    script_text = POLICY_EVIDENCE_SCRIPT_PATH.read_text()
    backend_main_text = BACKEND_MAIN_PATH.read_text()
    readme_text = WINDMILL_README_PATH.read_text()

    assert 'BACKEND_COMMAND_ENDPOINT_PATH = "/cron/pipeline/policy-evidence/command"' in script_text
    assert '@app.post("/cron/pipeline/domain/run-scope")' in backend_main_text
    assert '@app.post("/cron/pipeline/policy-evidence/command")' not in backend_main_text
    assert "Stub success here is not a full product pass." in readme_text
    assert "pipeline_daily_refresh_domain_boundary__flow" in readme_text
    assert "bd-3wefe.13-live-domain-backend-2026-04-15-r1" in readme_text
    assert "succeeded_with_alerts" in readme_text


def test_send_slack_alert_posts_webhook_payload(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse(status_code=200, payload={"ok": True})

    monkeypatch.setattr(windmill_trigger.requests, "post", fake_post)

    windmill_trigger.send_slack_alert(
        "https://hooks.slack.test/services/123",
        "INFO",
        "Affordabot discovery: SUCCESS",
        "Everything worked",
        "dev",
    )

    assert captured["url"] == "https://hooks.slack.test/services/123"
    assert captured["timeout"] == 10
    assert captured["json"]["text"].startswith("[INFO] ✅ Affordabot discovery: SUCCESS")
    assert captured["json"]["blocks"][1]["text"]["text"] == "Everything worked"
    assert "env=dev" in captured["json"]["blocks"][2]["elements"][0]["text"]


def test_send_slack_alert_normalizes_json_string_wrapped_webhook(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse(status_code=200, payload={"ok": True})

    monkeypatch.setattr(windmill_trigger.requests, "post", fake_post)

    windmill_trigger.send_slack_alert(
        '"https://hooks.slack.test/services/quoted"',
        "INFO",
        "Quoted URL",
        "Should still post",
        "dev",
    )

    assert captured["url"] == "https://hooks.slack.test/services/quoted"
    assert captured["timeout"] == 10


def test_send_slack_alert_skips_malformed_webhook(monkeypatch):
    called = {"post": False}

    def fake_post(url, json, timeout):
        called["post"] = True
        return DummyResponse(status_code=200, payload={"ok": True})

    monkeypatch.setattr(windmill_trigger.requests, "post", fake_post)

    windmill_trigger.send_slack_alert(
        '"not-a-valid-url"',
        "ERROR",
        "Bad URL",
        "Should not attempt post",
        "dev",
    )

    assert called["post"] is False


def test_main_success_posts_expected_headers_and_info_alert(monkeypatch):
    captured = {"alerts": []}

    def fake_post(url, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return DummyResponse(status_code=200, payload={"status": "succeeded", "job": "daily_scrape"})

    def fake_alert(webhook_url, severity, title, message, env):
        captured["alerts"].append((webhook_url, severity, title, message, env))

    monkeypatch.setattr(windmill_trigger.requests, "post", fake_post)
    monkeypatch.setattr(windmill_trigger, "send_slack_alert", fake_alert)

    result = windmill_trigger.main(
        endpoint="daily-scrape",
        backend_url="https://backend.example.com/",
        cron_secret="secret-123",
        env="dev",
        timeout_seconds=321,
        slack_webhook_url="https://hooks.slack.test/services/abc",
    )

    assert captured["url"] == "https://backend.example.com/cron/daily-scrape"
    assert captured["timeout"] == 321
    assert captured["headers"]["Authorization"] == "Bearer secret-123"
    assert captured["headers"]["X-PR-CRON-SECRET"] == "secret-123"
    assert captured["headers"]["X-PR-CRON-SOURCE"] == "windmill:f/affordabot/daily_scrape"
    assert captured["alerts"] == [
        (
            "https://hooks.slack.test/services/abc",
            "INFO",
            "Affordabot daily-scrape: SUCCESS",
            "Endpoint `daily-scrape` completed successfully.\n```{'status': 'succeeded', 'job': 'daily_scrape'}```",
            "dev",
        )
    ]
    assert result["status"] == "succeeded"
    assert result["response"]["job"] == "daily_scrape"
    assert result["slack_configured"] is True


def test_main_marks_slack_unconfigured_for_malformed_url(monkeypatch):
    def fake_post(url, headers, timeout):
        return DummyResponse(status_code=200, payload={"status": "succeeded", "job": "daily_scrape"})

    monkeypatch.setattr(windmill_trigger.requests, "post", fake_post)
    monkeypatch.setattr(windmill_trigger, "send_slack_alert", lambda *args, **kwargs: None)

    result = windmill_trigger.main(
        endpoint="daily-scrape",
        backend_url="https://backend.example.com/",
        cron_secret="secret-123",
        env="dev",
        timeout_seconds=321,
        slack_webhook_url='"not-a-url"',
    )

    assert result["status"] == "succeeded"
    assert result["slack_configured"] is False


def test_main_http_failure_sends_error_alert(monkeypatch):
    alerts = []

    def fake_post(url, headers, timeout):
        return DummyResponse(status_code=500, payload={"status": "failed", "detail": "boom"})

    def fake_alert(webhook_url, severity, title, message, env):
        alerts.append((severity, title, message, env))

    monkeypatch.setattr(windmill_trigger.requests, "post", fake_post)
    monkeypatch.setattr(windmill_trigger, "send_slack_alert", fake_alert)

    with pytest.raises(requests.HTTPError):
        windmill_trigger.main(
            endpoint="discovery",
            backend_url="https://backend.example.com",
            cron_secret="secret-123",
            slack_webhook_url="https://hooks.slack.test/services/abc",
        )

    assert alerts == [
        (
            "ERROR",
            "Affordabot discovery: HTTP_500",
            "Endpoint `https://backend.example.com/cron/discovery` returned `500`.\n```{'status': 'failed', 'detail': 'boom'}```",
            "dev",
        )
    ]


def test_main_request_exception_sends_error_alert(monkeypatch):
    alerts = []

    def fake_post(url, headers, timeout):
        raise requests.RequestException("network down")

    def fake_alert(webhook_url, severity, title, message, env):
        alerts.append((severity, title, message, env))

    monkeypatch.setattr(windmill_trigger.requests, "post", fake_post)
    monkeypatch.setattr(windmill_trigger, "send_slack_alert", fake_alert)

    with pytest.raises(requests.RequestException):
        windmill_trigger.main(
            endpoint="rag-spiders",
            backend_url="https://backend.example.com",
            cron_secret="secret-123",
            slack_webhook_url="https://hooks.slack.test/services/abc",
        )

    assert alerts == [
        (
            "ERROR",
            "Affordabot rag-spiders: REQUEST_FAILED",
            "Request to `https://backend.example.com/cron/rag-spiders` failed: `network down`",
            "dev",
        )
    ]


def test_main_posts_json_payload_when_present(monkeypatch):
    captured = {}

    def fake_post(url, headers, timeout, json):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        captured["json"] = json
        return DummyResponse(status_code=200, payload={"status": "succeeded", "job": "manual_substrate_expansion"})

    monkeypatch.setattr(windmill_trigger.requests, "post", fake_post)
    monkeypatch.setattr(windmill_trigger, "send_slack_alert", lambda *args, **kwargs: None)

    payload = {
        "run_label": "broad-test-2026-04-02",
        "jurisdictions": ["san-jose"],
        "asset_classes": ["agendas", "minutes"],
        "max_documents_per_source": 5,
        "run_mode": "capture_only",
        "ocr_mode": "off",
        "sample_size_per_bucket": 3,
    }
    windmill_trigger.main(
        endpoint="manual-substrate-expansion",
        backend_url="https://backend.example.com",
        cron_secret="secret-123",
        payload=payload,
    )

    assert captured["url"] == "https://backend.example.com/cron/manual-substrate-expansion"
    assert captured["headers"]["X-PR-CRON-SOURCE"] == "windmill:f/affordabot/manual_substrate_expansion"
    assert captured["json"] == payload
