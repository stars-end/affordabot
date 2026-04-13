import os
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest

from main import app
from routers.admin import get_db
from services.pipeline.domain.constants import CONTRACT_VERSION


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.connect = AsyncMock()
    db.close = AsyncMock()
    db._fetch = AsyncMock()
    db._fetchrow = AsyncMock()
    return db


@pytest.fixture
def client(mock_db):
    UNIT_TEST_SECRET = "unit-test-secret"

    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("main.db", mock_db):
        prev_env = os.environ.get("RAILWAY_ENVIRONMENT_NAME")
        prev_secret = os.environ.get("TEST_AUTH_BYPASS_SECRET")
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = "dev"
        os.environ["TEST_AUTH_BYPASS_SECRET"] = UNIT_TEST_SECRET
        try:
            with TestClient(app, base_url="http://localhost") as c:
                def set_auth(role: str = "admin"):
                    import base64
                    import hashlib
                    import hmac
                    import json
                    import time

                    payload = {
                        "sub": f"test_{role}",
                        "role": role,
                        "email": f"test_{role}@example.com",
                        "exp": int(time.time()) + 3600,
                    }
                    payload_json = json.dumps(payload, separators=(",", ":"))
                    payload_b64 = (
                        base64.urlsafe_b64encode(payload_json.encode())
                        .decode()
                        .rstrip("=")
                    )
                    msg = f"v1.{payload_b64}"
                    sig = hmac.new(
                        UNIT_TEST_SECRET.encode(), msg.encode(), hashlib.sha256
                    ).digest()
                    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
                    token = f"{msg}.{sig_b64}"
                    c.cookies.set("x-test-user", token)

                c.set_auth = set_auth
                yield c
        finally:
            if prev_env is None:
                os.environ.pop("RAILWAY_ENVIRONMENT_NAME", None)
            else:
                os.environ["RAILWAY_ENVIRONMENT_NAME"] = prev_env
            if prev_secret is None:
                os.environ.pop("TEST_AUTH_BYPASS_SECRET", None)
            else:
                os.environ["TEST_AUTH_BYPASS_SECRET"] = prev_secret

    app.dependency_overrides = {}


def test_get_pipeline_jurisdiction_status_shape(client, mock_db):
    mock_db._fetchrow.side_effect = [
        {"id": "jur-1", "name": "San Jose CA", "type": "CITY"},
        {
            "id": "run-1",
            "jurisdiction": "San Jose CA",
            "status": "completed",
            "started_at": "2026-04-13T01:00:00Z",
            "completed_at": "2026-04-13T01:05:00Z",
            "error": None,
            "windmill_run_id": "wm-run-1",
            "result": {
                "freshness": {
                    "status": "stale_but_usable",
                    "alerts": ["source_search_failed_using_last_success"],
                },
                "search_results_count": 2,
                "raw_scrapes_count": 1,
                "artifact_count": 1,
                "rag_chunks_retrieved": 4,
                "analysis": {"summary": "ok"},
                "validated_evidence_count": 4,
                "sufficiency_state": "qualitative_only",
                "alerts": ["source_search_failed_using_last_success"],
            },
        },
        {"completed_at": "2026-04-13T01:05:00Z"},
    ]
    client.set_auth("admin")
    response = client.get("/api/admin/pipeline/jurisdictions/jur-1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["jurisdiction_id"] == "jur-1"
    assert data["source_family"] == "meeting_minutes"
    assert data["pipeline_status"] == "stale_but_usable"
    assert data["freshness"]["stale_usable_ceiling_hours"] == 72
    assert data["counts"]["chunks"] == 4
    assert data["latest_analysis"]["status"] == "ready"


def test_get_pipeline_run_detail_shape(client, mock_db):
    mock_db._fetchrow.return_value = {
        "id": "run-2",
        "bill_id": "SB-1",
        "jurisdiction": "San Jose CA",
        "status": "completed",
        "started_at": "2026-04-13T02:00:00Z",
        "completed_at": "2026-04-13T02:01:00Z",
        "error": None,
        "trigger_source": "windmill",
        "windmill_workspace": "affordabot",
        "windmill_run_id": "wm-run-2",
        "source_family": "meeting_minutes",
        "result": {
            "search_results_count": 3,
            "raw_scrapes_count": 2,
            "artifact_count": 2,
            "rag_chunks_retrieved": 5,
            "analysis": {"summary": "ready"},
            "validated_evidence_count": 5,
        },
    }
    client.set_auth("admin")
    response = client.get("/api/admin/pipeline/runs/run-2")
    assert response.status_code == 200
    data = response.json()
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["run_id"] == "run-2"
    assert data["counts"]["search_results"] == 3
    assert data["latest_analysis"]["evidence_count"] == 5
    assert data["operator_links"]["windmill_run_url"].endswith("/wm-run-2")


def test_get_pipeline_run_steps_shape(client, mock_db):
    mock_db._fetch.return_value = [
        {
            "id": "step-1",
            "run_id": "run-2",
            "step_name": "search_materialize",
            "command": "search_materialize",
            "status": "succeeded",
            "duration_ms": 42,
            "input_context": {"q": "san jose meeting minutes"},
            "output_result": {
                "decision_reason": "fresh_snapshot_materialized",
                "retry_class": "none",
                "counts": {"search_results": 2},
            },
            "decision_reason": "fresh_snapshot_materialized",
            "retry_class": "none",
            "alerts": [],
            "refs": {"search_snapshot_id": "snap-1"},
            "created_at": "2026-04-13T02:00:10Z",
        }
    ]
    client.set_auth("admin")
    response = client.get("/api/admin/pipeline/runs/run-2/steps")
    assert response.status_code == 200
    data = response.json()
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["run_id"] == "run-2"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["command"] == "search_materialize"
    assert data["steps"][0]["refs"]["search_snapshot_id"] == "snap-1"


def test_get_pipeline_run_evidence_shape(client, mock_db):
    mock_db._fetchrow.return_value = {
        "id": "run-3",
        "result": {
            "analysis": {
                "citations": [
                    {"type": "chunk", "label": "City Agenda Packet", "source_ref": "raw-1"}
                ]
            }
        },
    }
    client.set_auth("admin")
    response = client.get("/api/admin/pipeline/runs/run-3/evidence")
    assert response.status_code == 200
    data = response.json()
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["evidence_count"] == 1
    assert data["items"][0]["label"] == "City Agenda Packet"


def test_post_pipeline_jurisdiction_refresh_shape(client, mock_db):
    mock_db._fetchrow.return_value = {
        "id": "jur-7",
        "name": "San Jose CA",
        "type": "CITY",
    }
    client.set_auth("admin")
    response = client.post("/api/admin/pipeline/jurisdictions/jur-7/refresh")
    assert response.status_code == 200
    data = response.json()
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["status"] == "accepted"
    assert data["decision_reason"] == "manual_refresh_queued"
    assert data["jurisdiction_id"] == "jur-7"
