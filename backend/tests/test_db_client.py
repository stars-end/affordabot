import pytest
from unittest.mock import MagicMock
from db.supabase_client import SupabaseDB

@pytest.fixture
def mock_client():
    return MagicMock()

@pytest.mark.asyncio
async def test_get_or_create_jurisdiction_existing(mock_client):
    db = SupabaseDB(client=mock_client)
    # Mock existing
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"id": "jur-1"}]
    
    result = await db.get_or_create_jurisdiction("San Jose", "city")
    assert result == "jur-1"
    mock_client.table.assert_called_with("jurisdictions")
    mock_client.table.return_value.insert.assert_not_called()

@pytest.mark.asyncio
async def test_get_or_create_jurisdiction_new(mock_client):
    db = SupabaseDB(client=mock_client)
    # Mock not found
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    # Mock create response
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "jur-2"}]
    
    result = await db.get_or_create_jurisdiction("San Jose", "city")
    assert result == "jur-2"
    mock_client.table.return_value.insert.assert_called_once()

@pytest.mark.asyncio
async def test_store_legislation_new(mock_client):
    db = SupabaseDB(client=mock_client)
    bill_data = {
        "bill_number": "123",
        "title": "Test Bill",
        "text": "Content",
        "status": "introduced"
    }
    
    # Mock check (not found)
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    # Mock insert
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "leg-1"}]
    
    result = await db.store_legislation("jur-1", bill_data)
    assert result == "leg-1"
    mock_client.table.return_value.insert.assert_called_once()

@pytest.mark.asyncio
async def test_store_legislation_update(mock_client):
    db = SupabaseDB(client=mock_client)
    bill_data = {
        "bill_number": "123",
        "title": "Test Bill Updated",
        "text": "Content",
        "status": "passed"
    }
    
    # Mock check (found)
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"id": "leg-1"}]
    
    result = await db.store_legislation("jur-1", bill_data)
    assert result == "leg-1"
    mock_client.table.return_value.update.assert_called_once()
