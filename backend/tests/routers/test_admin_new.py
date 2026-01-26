import pytest
from unittest.mock import AsyncMock, patch
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
    assert response.json() == ["query-1", "query-2"]

def test_get_traces(client):
    client.set_auth("admin")
    response = client.get("/api/admin/traces/query-1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["tool"] == "test_tool"
    assert data[0]["query_id"] == "query-1"
