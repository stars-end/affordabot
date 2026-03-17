from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


async def _successful_job(script_path: str, job_name: str):
    return {
        "job": job_name,
        "script_path": script_path,
        "exit_code": 0,
        "status": "succeeded",
        "stdout_tail": "ok",
        "stderr_tail": "",
    }


async def _failed_job(script_path: str, job_name: str):
    return {
        "job": job_name,
        "script_path": script_path,
        "exit_code": 1,
        "status": "failed",
        "stdout_tail": "",
        "stderr_tail": "boom",
    }


def test_cron_endpoint_rejects_missing_auth(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    response = client.post("/cron/discovery")
    assert response.status_code == 401


def test_cron_endpoint_runs_synchronously_with_valid_auth(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(main, "_run_script_job", _successful_job)

    response = client.post(
        "/cron/discovery",
        headers={"Authorization": "Bearer test-secret"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["job"] == "discovery"


def test_cron_endpoint_accepts_prime_style_shared_instance_header(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(main, "_run_script_job", _successful_job)

    response = client.post(
        "/cron/rag-spiders",
        headers={"X-PR-CRON-SECRET": "test-secret"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["job"] == "rag_spiders"


def test_cron_endpoint_returns_500_on_job_failure(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(main, "_run_script_job", _failed_job)

    response = client.post(
        "/cron/daily-scrape",
        headers={"Authorization": "Bearer test-secret"},
    )

    assert response.status_code == 500
    assert response.json()["detail"]["status"] == "failed"
