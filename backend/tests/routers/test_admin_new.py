import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from main import app
import main
from services.glass_box import GlassBoxService, AgentStep

# Mock the GlassBoxService dependency
async def mock_get_traces(query_id: str):
    return [
        AgentStep(
            tool="test_tool",
            args={"foo": "bar"},
            result="success",
            task_id="task-1",
            query_id=query_id,
            timestamp=1234567890
        )
    ]

async def mock_list_queries():
    return ["query-1", "query-2"]

@pytest.fixture
def client():
    # Setup
    from routers.admin import get_glass_box_service
    
    # Create a mock service
    mock_service = GlassBoxService(trace_dir="/tmp/test_traces")
    # Mock the async methods
    mock_service.get_traces_for_query = mock_get_traces
    mock_service.list_queries = mock_list_queries
    
    # Mock DB connection to avoid startup errors
    main.db = AsyncMock()
    main.db.connect = AsyncMock()
    main.db.close = AsyncMock()
    
    app.dependency_overrides[get_glass_box_service] = lambda: mock_service
    
    with TestClient(app) as c:
        yield c
    
    # Teardown
    app.dependency_overrides = {}

def test_list_sessions(client):
    response = client.get("/admin/traces")
    assert response.status_code == 200
    assert response.json() == ["query-1", "query-2"]

def test_get_traces(client):
    response = client.get("/admin/traces/query-1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["tool"] == "test_tool"
    assert data[0]["query_id"] == "query-1"
