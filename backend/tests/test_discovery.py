import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from main import app 
from services.auto_discovery_service import AutoDiscoveryService

# Mock AutoDiscoveryService
mock_auto_discovery_service = AsyncMock(spec=AutoDiscoveryService)

def override_get_discovery_service() -> AutoDiscoveryService:
    return mock_auto_discovery_service

# Apply the dependency override to the app
from routers.discovery import get_discovery_service

# Apply the dependency override to the app
app.dependency_overrides[get_discovery_service] = override_get_discovery_service

client = TestClient(app, raise_server_exceptions=False)

@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset mocks before each test."""
    mock_auto_discovery_service.reset_mock()
    mock_auto_discovery_service.discover_sources.reset_mock()

def test_run_discovery_success():
    """Test the /discovery/run endpoint for a successful discovery."""
    # Arrange
    expected_results = [
        {"url": "http://example.com/meetings", "title": "City Council Meetings"}
    ]
    mock_auto_discovery_service.discover_sources.return_value = expected_results
    
    # Act
    response = client.post(
        "/discovery/run",
        json={"jurisdiction_name": "Test City", "jurisdiction_type": "city"},
    )
    
    # Assert
    assert response.status_code == 200
    assert response.json() == expected_results
    mock_auto_discovery_service.discover_sources.assert_called_once_with(
        "Test City", "city"
    )

def test_run_discovery_no_results():
    """Test the /discovery/run endpoint when no sources are found."""
    # Arrange
    mock_auto_discovery_service.discover_sources.return_value = []
    
    # Act
    response = client.post(
        "/discovery/run",
        json={"jurisdiction_name": "No Results City", "jurisdiction_type": "city"},
    )
    
    # Assert
    assert response.status_code == 200
    assert response.json() == []
    mock_auto_discovery_service.discover_sources.assert_called_once_with(
        "No Results City", "city"
    )

def test_run_discovery_service_error():
    """Test the /discovery/run endpoint when the service raises an exception."""
    # Arrange
    mock_auto_discovery_service.discover_sources.side_effect = Exception(
        "Service failure"
    )
    
    # Act
    response = client.post(
        "/discovery/run",
        json={"jurisdiction_name": "Error City", "jurisdiction_type": "city"},
    )
    
    # Assert
    assert response.status_code == 500  # Assuming a generic 500 for unhandled exceptions
    # FastAPI returns detailed error in debug mode or if not handled
    assert "Service failure" in response.text
    mock_auto_discovery_service.discover_sources.assert_called_once_with(
        "Error City", "city"
    )
