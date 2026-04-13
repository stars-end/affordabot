from fastapi.testclient import TestClient

import main
from services.pipeline.domain.bridge import PipelineDomainBridge


client = TestClient(main.app)


def _payload(**overrides):
    base = {
        "contract_version": "2026-04-13.windmill-domain.v1",
        "idempotency_key": "wm:run-scope:2026-04-13",
        "jurisdiction": "san-jose-ca",
        "source_family": "meeting_minutes",
        "stale_status": "fresh",
        "windmill_workspace": "affordabot",
        "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
        "windmill_run_id": "wm-run-123",
        "windmill_job_id": "wm-job-123",
        "search_query": "San Jose housing meeting minutes",
        "analysis_question": "Summarize housing policy changes from latest minutes.",
    }
    base.update(overrides)
    return base


def _authorized_post(payload):
    return client.post(
        "/cron/pipeline/domain/run-scope",
        headers={"Authorization": "Bearer test-secret"},
        json=payload,
    )


def test_pipeline_domain_bridge_requires_cron_auth(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    response = client.post("/cron/pipeline/domain/run-scope", json=_payload())
    assert response.status_code == 401


def test_pipeline_domain_bridge_rejects_contract_mismatch(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(main, "_get_pipeline_domain_bridge", lambda: PipelineDomainBridge())
    response = _authorized_post(_payload(contract_version="2026-01-01.invalid.v1"))
    assert response.status_code == 400
    assert "contract_version mismatch" in response.json()["detail"]


def test_pipeline_domain_bridge_happy_path(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(main, "_get_pipeline_domain_bridge", lambda: PipelineDomainBridge())
    response = _authorized_post(_payload())
    assert response.status_code == 200

    body = response.json()
    assert body["command"] == "run_scope_pipeline"
    assert body["status"] == "succeeded"
    assert body["stale_status"] == "fresh"
    assert body["windmill_workspace"] == "affordabot"
    assert body["windmill_flow_path"] == "f/affordabot/pipeline_daily_refresh_domain_boundary__flow"
    assert body["steps"]["search_materialize"]["envelope"]["search_query"]
    assert body["steps"]["analyze"]["envelope"]["analysis_question"]
    assert "postgres_pipeline_state_store_adapter" in body["missing_runtime_adapters"]


def test_pipeline_domain_bridge_stale_but_usable(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(main, "_get_pipeline_domain_bridge", lambda: PipelineDomainBridge())
    response = _authorized_post(_payload(idempotency_key="wm:stale-usable", stale_status="stale_but_usable"))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded_with_alerts"
    assert body["stale_status"] == "stale_but_usable"
    assert "source_search_failed_using_last_success" in body["alerts"]


def test_pipeline_domain_bridge_stale_blocked(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(main, "_get_pipeline_domain_bridge", lambda: PipelineDomainBridge())
    response = _authorized_post(_payload(idempotency_key="wm:stale-blocked", stale_status="stale_blocked"))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["stale_status"] == "stale_blocked"
    assert "read_fetch" not in body["steps"]


def test_pipeline_domain_bridge_rerun_reuses_idempotent_results(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    bridge = PipelineDomainBridge()
    monkeypatch.setattr(main, "_get_pipeline_domain_bridge", lambda: bridge)
    payload = _payload(idempotency_key="wm:rerun")

    first = _authorized_post(payload)
    second = _authorized_post(payload)
    assert first.status_code == 200
    assert second.status_code == 200

    second_body = second.json()
    assert second_body["steps"]["search_materialize"]["details"]["idempotent_reuse"] is True
    assert second_body["steps"]["summarize_run"]["details"]["idempotent_reuse"] is True
