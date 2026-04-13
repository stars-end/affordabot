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
