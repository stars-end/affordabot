from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from llm_common.web_search import WebSearchClient, SearchResult

@pytest.fixture
def mock_supabase():
    client = MagicMock()
    # Mock table().select().eq().execute()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    return client

@pytest.fixture
def search_client(mock_supabase):
    return WebSearchClient(api_key="test-key", supabase_client=mock_supabase)

@pytest.mark.asyncio
async def test_search_cache_miss(search_client):
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"title": "Test", "url": "http://test.com", "snippet": "Snippet"}
            ]
        }
        mock_post.return_value = mock_response
        
        results = await search_client.search("query")
        
        assert len(results) == 1
        assert results[0].title == "Test"
        # Verify Supabase upsert called
        search_client.supabase.table.return_value.upsert.assert_called_once()

@pytest.mark.asyncio
async def test_search_memory_cache_hit(search_client):
    # Pre-populate memory cache
    cache_key = search_client._generate_cache_key("query", 10, None, None)
    cached_result = [SearchResult(title="Cached", url="url", snippet="snippet")]
    search_client.memory_cache[cache_key] = (cached_result, datetime.now())
    
    with patch("httpx.AsyncClient.post") as mock_post:
        results = await search_client.search("query")
        
        assert len(results) == 1
        assert results[0].title == "Cached"
        mock_post.assert_not_called()
