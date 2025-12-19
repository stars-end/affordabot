import pytest
from unittest.mock import AsyncMock, MagicMock
from services.source_service import SourceService, SourceCreate, SourceUpdate

@pytest.fixture
def mock_db():
    mock = MagicMock()
    mock.get_sources = AsyncMock()
    mock.get_source = AsyncMock()
    mock.create_source = AsyncMock()
    mock.update_source = AsyncMock()
    mock.delete_source = AsyncMock()
    return mock

@pytest.mark.asyncio
async def test_get_sources(mock_db):
    service = SourceService(mock_db)
    mock_data = [{"id": "1", "url": "http://example.com"}]
    mock_db.get_sources.return_value = mock_data
    
    sources = await service.get_sources()
    
    assert len(sources) == 1
    assert sources[0]["url"] == "http://example.com"
    mock_db.get_sources.assert_called_once_with(None)

@pytest.mark.asyncio
async def test_get_sources_filtered(mock_db):
    service = SourceService(mock_db)
    mock_db.get_sources.return_value = []
    
    await service.get_sources(jurisdiction_id="sanjose")
    
    mock_db.get_sources.assert_called_with("sanjose")

@pytest.mark.asyncio
async def test_create_source(mock_db):
    service = SourceService(mock_db)
    new_source = SourceCreate(jurisdiction_id="sanjose", url="http://example.com", type="general")
    mock_resp = {"id": "1", **new_source.model_dump()}
    mock_db.create_source.return_value = mock_resp
    
    created = await service.create_source(new_source)
    
    assert created["id"] == "1"
    mock_db.create_source.assert_called_once()
    call_args = mock_db.create_source.call_args[0][0]
    assert call_args["url"] == "http://example.com"

@pytest.mark.asyncio
async def test_update_source(mock_db):
    service = SourceService(mock_db)
    update = SourceUpdate(status="inactive")
    mock_resp = {"id": "1", "url": "http://example.com", "status": "inactive"}
    mock_db.update_source.return_value = mock_resp
    
    updated = await service.update_source("1", update)
    
    assert updated["status"] == "inactive"
    mock_db.update_source.assert_called_once_with("1", {"status": "inactive"})

@pytest.mark.asyncio
async def test_delete_source(mock_db):
    service = SourceService(mock_db)
    mock_db.delete_source.return_value = None
    
    await service.delete_source("1")
    
    mock_db.delete_source.assert_called_once_with("1")
