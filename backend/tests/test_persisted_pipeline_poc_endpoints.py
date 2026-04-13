from fastapi.testclient import TestClient

import sqlite3

import main
from services.persisted_pipeline import FailingSearchProvider


client = TestClient(main.app)


def _auth_headers(**extra):
    headers = {"Authorization": "Bearer test-secret"}
    headers.update(extra)
    return headers


def test_poc_start_run_requires_auth(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    response = client.post(
        "/internal/pipeline/poc/start-run",
        json={
            "run_label": "unauth",
            "query": "q",
            "family": "fam",
        },
    )
    assert response.status_code == 401


def test_poc_start_run_stores_windmill_linkage(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    response = client.post(
        "/internal/pipeline/poc/start-run",
        headers=_auth_headers(
            **{
                "X-PR-WINDMILL-FLOW-RUN-ID": "flow-123",
                "X-PR-WINDMILL-JOB-ID": "job-456",
                "X-PR-PIPELINE-STEP": "windmill:poc/start-run",
            }
        ),
        json={
            "run_label": "linkage",
            "query": "query-one",
            "family": "family-one",
        },
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    ctx = main._POC_PIPELINE_RUNS[run_id]
    assert ctx["windmill_flow_run_id"] == "flow-123"
    assert ctx["windmill_job_id"] == "job-456"
    conn = sqlite3.connect(str(ctx["store"].db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT windmill_flow_run_id, windmill_job_id FROM pipeline_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    conn.close()
    assert row["windmill_flow_run_id"] == "flow-123"
    assert row["windmill_job_id"] == "job-456"


def test_search_materialize_domain_failure_is_2xx(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    start = client.post(
        "/internal/pipeline/poc/start-run",
        headers=_auth_headers(),
        json={
            "run_label": "domain-failure",
            "query": "query-one",
            "family": "family-one",
        },
    )
    assert start.status_code == 200
    run_id = start.json()["run_id"]
    main._POC_PIPELINE_RUNS[run_id]["pipeline"].search_provider = FailingSearchProvider(
        "forced failure"
    )

    response = client.post(
        "/internal/pipeline/poc/search-materialize",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["decision"] == "provider_failed_no_fallback"


def test_search_materialize_runtime_failure_is_5xx(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    start = client.post(
        "/internal/pipeline/poc/start-run",
        headers=_auth_headers(),
        json={
            "run_label": "runtime-failure",
            "query": "query-one",
            "family": "family-one",
        },
    )
    assert start.status_code == 200
    run_id = start.json()["run_id"]

    def _raise_runtime(*args, **kwargs):
        raise RuntimeError("retryable boom")

    main._POC_PIPELINE_RUNS[run_id][
        "pipeline"
    ]._step_search_materialize = _raise_runtime

    response = client.post(
        "/internal/pipeline/poc/search-materialize",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert response.status_code == 503


def test_pr420_endpoint_names_are_callable(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    start = client.post(
        "/internal/pipeline/poc/start-run",
        headers=_auth_headers(),
        json={
            "run_label": "full-path",
            "query": "query-one",
            "family": "family-one",
        },
    )
    assert start.status_code == 200
    run_id = start.json()["run_id"]

    search = client.post(
        "/internal/pipeline/poc/search-materialize",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert search.status_code == 200

    read = client.post(
        "/internal/pipeline/poc/read-extract",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert read.status_code == 200

    analyze = client.post(
        "/internal/pipeline/poc/analyze",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert analyze.status_code == 200

    finalize = client.post(
        "/internal/pipeline/poc/finalize-report",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert finalize.status_code == 200
    assert finalize.json()["step"] == "finalize"

    canary = client.post(
        "/internal/pipeline/poc/zai-search-canary",
        headers=_auth_headers(),
    )
    assert canary.status_code == 200
    assert canary.json()["ZAI_DIRECT_SEARCH_DEPRECATED"] is True


def test_finalize_report_propagates_failed_read_status(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    start = client.post(
        "/internal/pipeline/poc/start-run",
        headers=_auth_headers(),
        json={
            "run_label": "failed-read",
            "query": "query-one",
            "family": "family-one",
            "skip_analysis": True,
        },
    )
    assert start.status_code == 200
    run_id = start.json()["run_id"]

    search = client.post(
        "/internal/pipeline/poc/search-materialize",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert search.status_code == 200

    def _failed_read(**kwargs):
        return {
            "contract_version": "persisted-pipeline.v1",
            "run_id": kwargs["run_id"],
            "step": "read_extract",
            "status": "failed",
            "decision": "reader_failed",
            "decision_reason": "forced test failure",
            "evidence": {"forced": True},
            "alerts": [],
        }

    main._POC_PIPELINE_RUNS[run_id]["pipeline"]._step_read_extract = _failed_read
    read = client.post(
        "/internal/pipeline/poc/read-extract",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert read.status_code == 200
    assert read.json()["status"] == "failed"

    analyze = client.post(
        "/internal/pipeline/poc/analyze",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert analyze.status_code == 200
    assert analyze.json()["status"] == "succeeded"

    finalize = client.post(
        "/internal/pipeline/poc/finalize-report",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert finalize.status_code == 200
    body = finalize.json()
    assert body["status"] == "failed"
    assert body["decision"] == "downstream_failed"
    assert body["evidence"]["read_status"] == "failed"
    assert body["evidence"]["failing_steps"] == ["read"]


def test_finalize_report_propagates_failed_analyze_status(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    start = client.post(
        "/internal/pipeline/poc/start-run",
        headers=_auth_headers(),
        json={
            "run_label": "failed-analyze",
            "query": "query-one",
            "family": "family-one",
        },
    )
    assert start.status_code == 200
    run_id = start.json()["run_id"]

    search = client.post(
        "/internal/pipeline/poc/search-materialize",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert search.status_code == 200

    read = client.post(
        "/internal/pipeline/poc/read-extract",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert read.status_code == 200
    assert read.json()["status"] == "succeeded"

    def _failed_analyze(**kwargs):
        return {
            "contract_version": "persisted-pipeline.v1",
            "run_id": kwargs["run_id"],
            "step": "analyze",
            "status": "failed",
            "decision": "analysis_failed",
            "decision_reason": "forced analyze failure",
            "evidence": {"forced": True},
            "alerts": [],
        }

    main._POC_PIPELINE_RUNS[run_id]["pipeline"]._step_analyze = _failed_analyze
    analyze = client.post(
        "/internal/pipeline/poc/analyze",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert analyze.status_code == 200
    assert analyze.json()["status"] == "failed"

    finalize = client.post(
        "/internal/pipeline/poc/finalize-report",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert finalize.status_code == 200
    body = finalize.json()
    assert body["status"] == "failed"
    assert body["decision"] == "downstream_failed"
    assert body["evidence"]["analyze_status"] == "failed"
    assert body["evidence"]["failing_steps"] == ["analyze"]


def test_finalize_report_happy_path_still_succeeds(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    start = client.post(
        "/internal/pipeline/poc/start-run",
        headers=_auth_headers(),
        json={
            "run_label": "happy-finalize",
            "query": "query-one",
            "family": "family-one",
        },
    )
    assert start.status_code == 200
    run_id = start.json()["run_id"]

    for endpoint in (
        "/internal/pipeline/poc/search-materialize",
        "/internal/pipeline/poc/read-extract",
        "/internal/pipeline/poc/analyze",
    ):
        resp = client.post(endpoint, headers=_auth_headers(), json={"run_id": run_id})
        assert resp.status_code == 200

    finalize = client.post(
        "/internal/pipeline/poc/finalize-report",
        headers=_auth_headers(),
        json={"run_id": run_id},
    )
    assert finalize.status_code == 200
    body = finalize.json()
    assert body["status"] == "succeeded"
    assert body["decision"] in {"fresh_snapshot", "stale_backed"}
    assert body["evidence"]["failing_steps"] == []
