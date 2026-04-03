import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path
from fastapi.testclient import TestClient
import os
from main import app
from services.glass_box import GlassBoxService, AgentStep
from routers.admin import get_db

# Mock data
JURISDICTIONS_DATA = [
    {"id": "a6712c5b-4171-460b-832d-20606b53dfa3", "name": "State of California", "type": "STATE"},
    {"id": "b3d1b3e0-9a3e-4b2a-8c3d-3b3b3b3b3b3b", "name": "City of San Jose", "type": "CITY"},
]
PROMPTS_DATA = [
    {
        "id": "c6712c5b-4171-460b-832d-20606b53dfa3",
        "prompt_type": "test_prompt",
        "system_prompt": "You are a test prompt.",
        "description": "A prompt for testing.",
        "version": 1,
        "is_active": True,
    }
]

# Mock the GlassBoxService dependency
async def mock_get_traces(query_id: str):
    return [
        AgentStep(
            tool="test_tool",
            args={"foo": "bar"},
            result="success",
            task_id="task-1",
            query_id=query_id,
            timestamp=1234567890,
        )
    ]

async def mock_list_queries():
    return ["query-1", "query-2"]

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.connect = AsyncMock()
    db.close = AsyncMock()
    # Mock database methods used in admin router
    db._fetch = AsyncMock()
    db._fetchrow = AsyncMock()
    db.update_system_prompt = AsyncMock()
    return db

@pytest.fixture
def client(mock_db):
    # Setup
    from routers.admin import get_glass_box_service

    # Create a mock service
    mock_service = GlassBoxService(trace_dir="/tmp/test_traces")
    # Mock the async methods
    mock_service.get_traces_for_query = mock_get_traces
    mock_service.list_queries = mock_list_queries

    app.dependency_overrides[get_glass_box_service] = lambda: mock_service
    app.dependency_overrides[get_db] = lambda: mock_db

    # Secret for unit tests
    UNIT_TEST_SECRET = "unit-test-secret"

    with patch("main.db", mock_db):
        prev_env = os.environ.get("RAILWAY_ENVIRONMENT_NAME")
        prev_secret = os.environ.get("TEST_AUTH_BYPASS_SECRET")
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = "dev"
        os.environ["TEST_AUTH_BYPASS_SECRET"] = UNIT_TEST_SECRET
        try:
            # Ensure bypass middleware host allowlist passes (default TestClient host is "testserver")
            with TestClient(app, base_url="http://localhost") as c:
                # Helper to set signed cookie
                def set_auth(role="admin"):
                    import hmac
                    import hashlib
                    import base64
                    import json
                    import time
                    
                    payload = {
                        "sub": f"test_{role}",
                        "role": role,
                        "email": f"test_{role}@example.com",
                        "exp": int(time.time()) + 3600
                    }
                    payload_json = json.dumps(payload, separators=(',', ':'))
                    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")
                    
                    msg = f"v1.{payload_b64}"
                    sig = hmac.new(UNIT_TEST_SECRET.encode(), msg.encode(), hashlib.sha256).digest()
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

    # Teardown
    app.dependency_overrides = {}


def test_list_jurisdictions(client, mock_db):
    mock_db._fetch.return_value = JURISDICTIONS_DATA
    client.set_auth("admin")
    response = client.get("/api/admin/jurisdictions")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["name"] == "State of California"

def test_get_jurisdiction(client, mock_db):
    mock_db._fetchrow.side_effect = [
        {"id": JURISDICTIONS_DATA[0]["id"], "name": JURISDICTIONS_DATA[0]["name"], "type": JURISDICTIONS_DATA[0]["type"]}, # Jurisdiction fetch
        {"count": 10}, # Bill count
        {"count": 5} # Source count
    ]
    client.set_auth("admin")
    response = client.get(f"/api/admin/jurisdictions/{JURISDICTIONS_DATA[0]['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "State of California"
    assert data["bill_count"] == 10
    assert data["source_count"] == 5

def test_get_jurisdiction_dashboard(client, mock_db):
    mock_db._fetchrow.side_effect = [
        {"id": JURISDICTIONS_DATA[0]["id"], "name": JURISDICTIONS_DATA[0]["name"], "type": JURISDICTIONS_DATA[0]["type"]}, # Jurisdiction fetch
        {"count": 100}, # Raw scrapes
        {"count": 95}, # Processed scrapes
        {"last_scrape": "2023-10-27T10:00:00Z"} # Last scrape
    ]
    client.set_auth("admin")
    response = client.get(f"/api/admin/jurisdiction/{JURISDICTIONS_DATA[0]['id']}/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["jurisdiction"] == "State of California"
    assert data["total_raw_scrapes"] == 100
    assert data["processed_scrapes"] == 95
    assert data["pipeline_status"] == "healthy"

def test_list_prompts(client, mock_db):
    mock_db._fetch.return_value = PROMPTS_DATA
    client.set_auth("admin")
    response = client.get("/api/admin/prompts")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["prompt_type"] == "test_prompt"

def test_get_prompt(client, mock_db):
    mock_db._fetchrow.return_value = PROMPTS_DATA[0]
    client.set_auth("admin")
    response = client.get("/api/admin/prompts/test_prompt")
    assert response.status_code == 200
    assert response.json()["system_prompt"] == "You are a test prompt."

def test_update_prompt(client, mock_db):
    mock_db.update_system_prompt.return_value = 2 # New version
    client.set_auth("admin")
    response = client.post(
        "/api/admin/prompts",
        json={"type": "test_prompt", "system_prompt": "This is the new prompt."}
    )
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Prompt updated", "version": 2}
    mock_db.update_system_prompt.assert_called_once_with("test_prompt", "This is the new prompt.")

def test_list_scrapes(client, mock_db):
    mock_db._fetch.return_value = [
        {
            "id": "d6712c5b-4171-460b-832d-20606b53dfa3",
            "url": "http://example.com/scrape1",
            "created_at": "2023-10-27T10:00:00Z",
            "jurisdiction_id": JURISDICTIONS_DATA[0]['id'],
            "jurisdiction_name": "State of California",
            "metadata": {"status": "success"}
        }
    ]
    client.set_auth("admin")
    response = client.get("/api/admin/scrapes")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["url"] == "http://example.com/scrape1"

def test_get_dashboard_stats(client, mock_db):
    mock_db._fetchrow.side_effect = [
        {"count": 2}, # Jurisdictions
        {"count": 150}, # Scrapes
        {"count": 25}, # Sources
        {"count": 1000} # Chunks
    ]
    client.set_auth("admin")
    response = client.get("/api/admin/stats")
    assert response.status_code == 200
    assert response.json() == {
        "jurisdictions": 2,
        "scrapes": 150,
        "sources": 25,
        "chunks": 1000
    }

def test_list_sessions(client):
    client.set_auth("admin")
    response = client.get("/api/admin/traces")
    assert response.status_code == 200


def test_list_models_uses_openrouter_fallback_default(client, monkeypatch):
    client.set_auth("admin")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.delenv("LLM_MODEL_FALLBACK_OPENROUTER", raising=False)
    response = client.get("/api/admin/models")
    assert response.status_code == 200
    models = response.json()["models"]
    openrouter = next(model for model in models if model["provider"] == "openrouter")
    assert openrouter["id"] == "openrouter/auto"
    assert openrouter["name"] == "OpenRouter Fallback"

def test_get_traces(client):
    client.set_auth("admin")
    response = client.get("/api/admin/traces/query-1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["tool"] == "test_tool"
    assert data[0]["query_id"] == "query-1"


def test_bill_truth_includes_latest_run_heads(client, mock_db):
    mock_db._fetchrow.side_effect = [
        None,  # scrape lookup
        None,  # legislation lookup
    ]
    mock_db._fetch.return_value = [
        {
            "id": "run-new",
            "bill_id": "SB 277",
            "status": "interrupted",
            "started_at": "2026-03-22T14:00:00Z",
            "completed_at": None,
            "error": "cancelled",
            "result": '{"rag_chunks_retrieved": 0}',
            "trigger_source": "prefix:ingestion-through-mode",
        },
        {
            "id": "run-failed",
            "bill_id": "SB 277",
            "status": "failed",
            "started_at": "2026-03-22T13:00:00Z",
            "completed_at": "2026-03-22T13:01:00Z",
            "error": "timeout",
            "result": '{"rag_chunks_retrieved": 0}',
            "trigger_source": "manual",
        },
        {
            "id": "run-completed",
            "bill_id": "SB 277",
            "status": "completed",
            "started_at": "2026-03-22T12:00:00Z",
            "completed_at": "2026-03-22T12:05:00Z",
            "error": None,
            "result": '{"rag_chunks_retrieved": 3, "quantification_eligible": false}',
            "trigger_source": "manual",
        },
    ]

    client.set_auth("admin")
    with patch.object(
        GlassBoxService,
        "get_pipeline_run",
        new=AsyncMock(
            return_value={
                "prefix_boundary": "stopped_after_mode_selection",
                "mechanism_trace": {"executed_steps": ["ingestion_source", "chunk_index"]},
            }
        ),
    ):
        response = client.get("/api/admin/bill-truth/california/SB-277")
    assert response.status_code == 200
    body = response.json()

    assert body["pipeline_runs"]["latest_run"]["run_id"] == "run-new"
    assert body["pipeline_runs"]["latest_run"]["status"] == "interrupted"
    assert body["pipeline_runs"]["latest_run"]["is_prefix_run"] is True
    assert body["pipeline_runs"]["latest_run"]["run_label"] == "ingestion-through-mode"
    assert (
        body["pipeline_runs"]["latest_completed_run"]["run_id"] == "run-completed"
    )
    assert body["pipeline_runs"]["latest_failed_run"]["run_id"] == "run-failed"
    # Backward compatible alias remains the true latest run.
    assert body["pipeline_run"]["run_id"] == "run-new"
    assert body["pipeline_run"]["prefix_boundary"] == "stopped_after_mode_selection"
    assert "mechanism_trace" in body["pipeline_run"]


def test_bill_truth_scrape_query_uses_text_join_for_jurisdiction() -> None:
    admin_path = Path(__file__).resolve().parents[2] / "routers" / "admin.py"
    source = admin_path.read_text()
    bill_truth_section = source.split('@router.get("/bill-truth/{jurisdiction}/{bill_id}")', 1)[1]
    assert "s.jurisdiction_id::text = j.id::text" in bill_truth_section


def test_admin_scrape_queries_avoid_text_uuid_join_mismatch() -> None:
    admin_path = Path(__file__).resolve().parents[2] / "routers" / "admin.py"
    source = admin_path.read_text()
    assert source.count("s.jurisdiction_id::text = j.id::text") >= 3


def _substrate_row(
    *,
    row_id: str,
    run_id: str = "manual-substrate-test-run",
    promotion_state: str = "promoted_substrate",
    trust_tier: str = "official",
    content_class: str = "html_text",
    ingestion_stage: str = "retrievable",
    retrievable: bool = True,
    error_message: str | None = None,
):
    return {
        "id": row_id,
        "created_at": "2026-04-03T10:00:00Z",
        "url": "https://example.gov/doc-1",
        "data": {"content": "A" * 512},
        "error_message": error_message,
        "storage_uri": "substrate/doc-1.pdf",
        "document_id": "8eac5530-c3c7-4d3a-b49d-f2fb4b9eac15",
        "metadata": {
            "manual_run_id": run_id,
            "promotion_state": promotion_state,
            "promotion_reason_category": "ok",
            "trust_tier": trust_tier,
            "content_class": content_class,
            "document_type": "minutes",
            "ingestion_truth": {
                "stage": ingestion_stage,
                "retrievable": retrievable,
            },
        },
        "source_url": "https://example.gov/source",
        "source_type": "legistar_calendar",
        "source_name": "City Council",
        "jurisdiction_name": "City of Sample",
    }


def test_list_substrate_runs(client, mock_db):
    mock_db._fetch.return_value = [
        {
            "run_id": "manual-substrate-test-run",
            "first_created_at": "2026-04-03T09:50:00Z",
            "last_created_at": "2026-04-03T10:00:00Z",
            "raw_scrapes_total": 3,
            "promoted_substrate_count": 2,
            "durable_raw_count": 1,
            "captured_candidate_count": 0,
            "retrievable_count": 2,
            "raw_capture_error_count": 0,
        }
    ]

    client.set_auth("admin")
    response = client.get("/api/admin/substrate/runs?limit=10&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id_key"] == "manual_run_id"
    assert len(body["runs"]) == 1
    run = body["runs"][0]
    assert run["run_id"] == "manual-substrate-test-run"
    assert run["status"] == "healthy"
    assert run["raw_scrapes_total"] == 3
    assert run["promoted_substrate_count"] == 2


def test_get_substrate_run_detail(client, mock_db):
    mock_db._fetch.return_value = [
        _substrate_row(row_id="row-1"),
        _substrate_row(
            row_id="row-2",
            promotion_state="durable_raw",
            ingestion_stage="embedded",
            retrievable=False,
        ),
    ]
    client.set_auth("admin")
    response = client.get("/api/admin/substrate/runs/manual-substrate-test-run")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "manual-substrate-test-run"
    assert body["raw_scrapes_total"] == 2
    assert body["summary"]["raw_scrapes_total"] == 2
    assert "promotion_state_counts" in body["summary"]


def test_get_substrate_run_failure_buckets(client, mock_db):
    mock_db._fetch.return_value = [
        _substrate_row(
            row_id="row-1",
            promotion_state="captured_candidate",
            trust_tier="non_official",
            ingestion_stage="failed_fetch",
            retrievable=False,
        )
    ]
    client.set_auth("admin")
    response = client.get(
        "/api/admin/substrate/runs/manual-substrate-test-run/failure-buckets"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "manual-substrate-test-run"
    assert body["raw_scrapes_total"] == 1
    assert len(body["failure_buckets"]) >= 1


def test_list_substrate_run_raw_scrapes(client, mock_db):
    mock_db._fetch.return_value = [_substrate_row(row_id="row-1")]
    client.set_auth("admin")
    response = client.get(
        "/api/admin/substrate/runs/manual-substrate-test-run/raw-scrapes?limit=20&offset=0"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "manual-substrate-test-run"
    assert len(body["raw_scrapes"]) == 1
    row = body["raw_scrapes"][0]
    assert row["id"] == "row-1"
    assert row["promotion_state"] == "promoted_substrate"
    assert row["ingestion_truth_retrievable"] is True
    assert row["content_length"] == 512


def test_get_substrate_raw_scrape_detail(client, mock_db):
    mock_db._fetchrow.return_value = _substrate_row(row_id="row-1")
    client.set_auth("admin")
    response = client.get("/api/admin/substrate/raw-scrapes/row-1")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "row-1"
    assert body["metadata"]["manual_run_id"] == "manual-substrate-test-run"
    assert body["ingestion_truth"]["stage"] == "retrievable"
