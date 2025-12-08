import pytest
from unittest.mock import MagicMock, AsyncMock
from services.source_service import SourceService, SourceCreate, SourceUpdate

@pytest.fixture
def mock_supabase():
    mock = MagicMock()
    return mock

@pytest.mark.asyncio
async def test_get_sources(mock_supabase):
    service = SourceService(mock_supabase)
    mock_data = [{"id": "1", "url": "http://example.com"}]
    
    # Mock chain: table().select().execute().data
    mock_supabase.table.return_value.select.return_value.execute.return_value.data = mock_data
    
    sources = await service.get_sources()
    
    assert len(sources) == 1
    assert sources[0]["url"] == "http://example.com"
    mock_supabase.table.assert_called_with("sources")

@pytest.mark.asyncio
async def test_get_sources_filtered(mock_supabase):
    service = SourceService(mock_supabase)
    
    # Mock chain: table().select().eq().execute()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    
    await service.get_sources(jurisdiction_id="sanjose")
    
    mock_supabase.table.return_value.select.return_value.eq.assert_called_with("jurisdiction_id", "sanjose")

@pytest.mark.asyncio
async def test_create_source(mock_supabase):
    service = SourceService(mock_supabase)
    new_source = SourceCreate(jurisdiction_id="sanjose", url="http://example.com", type="general")
    mock_resp = {"id": "1", **new_source.dict()}
    
    # Mock chain: table().insert().execute().data
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [mock_resp]
    
    created = await service.create_source(new_source)
    
    assert created["id"] == "1"
    mock_supabase.table.return_value.insert.assert_called()
    # Verify insert call args
    call_args = mock_supabase.table.return_value.insert.call_args[0][0]
    assert call_args["url"] == "http://example.com"

@pytest.mark.asyncio
async def test_update_source(mock_supabase):
    service = SourceService(mock_supabase)
    update = SourceUpdate(status="inactive")
    mock_resp = {"id": "1", "url": "http://example.com", "status": "inactive"}
    
    # Mock chain: table().update().eq().execute().data
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [mock_resp]
    
    updated = await service.update_source("1", update)
    
    assert updated["status"] == "inactive"
    mock_supabase.table.return_value.update.assert_called_with({"status": "inactive"})
    mock_supabase.table.return_value.update.return_value.eq.assert_called_with("id", "1")

@pytest.mark.asyncio
async def test_delete_source(mock_supabase):
    service = SourceService(mock_supabase)
    
    # Mock chain: table().delete().eq().execute()
    await service.delete_source("1")
    
    mock_supabase.table.return_value.delete.assert_called()
    mock_supabase.table.return_value.delete.return_value.eq.assert_called_with("id", "1")
