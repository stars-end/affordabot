import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json
from services.discovery.city_scrapers_discovery import CityScrapersDiscoveryService
from services.discovery.municode_discovery import MunicodeDiscoveryService
from llm_common.core.models import WebSearchResult

class MockProcess:
    def __init__(self, returncode: int, stdout: bytes, stderr: bytes):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        
    def communicate(self):
        return self.stdout, self.stderr

@pytest.mark.asyncio
async def test_city_scrapers_find_meeting_content_success():
    service = CityScrapersDiscoveryService()
    
    # Mock data from Scrapy
    mock_data = [
        {
            "Name": {"label": "City Council"},
            "Meeting Date": "2023-10-27",
            "Meeting Time": "1:30 PM",
            "Agenda": {"url": "http://example.com/agenda.pdf"},
            "Minutes": {"url": "http://example.com/minutes.pdf"}
        }
    ]
    
    with patch("subprocess.Popen") as mock_popen, \
         patch("os.path.exists", return_value=True), \
         patch("os.remove"), \
         patch("builtins.open", new_callable=MagicMock) as mock_open:
             
        # Mock Subprocess
        mock_process = MockProcess(0, b"", b"")
        mock_popen.return_value = mock_process
        
        # Mock File Read
        mock_file = MagicMock()
        mock_file.__enter__.return_value = mock_file
        mock_file.read.return_value = json.dumps(mock_data)
        mock_open.return_value = mock_file
        
        # Mock json.load
        with patch("json.load", return_value=mock_data):
            results = await service.find_meeting_content("sanjose")
            
    assert len(results) == 2
    assert isinstance(results[0], WebSearchResult)
    assert results[0].url == "http://example.com/agenda.pdf"
    assert "Agenda" in results[0].title
    assert results[1].url == "http://example.com/minutes.pdf"
    assert "Minutes" in results[1].title

@pytest.mark.asyncio
async def test_city_scrapers_failure():
    service = CityScrapersDiscoveryService()
    
    with patch("subprocess.Popen") as mock_popen:
        # Mock Failure
        mock_process = MockProcess(1, b"", b"Error")
        mock_popen.return_value = mock_process
        
        results = await service.find_meeting_content("sanjose")
        
    assert len(results) == 0

@pytest.mark.asyncio
async def test_municode_discovery_success():
    # Mock PlaywrightExtractor inside the service
    with patch("services.discovery.municode_discovery.PlaywrightExtractor") as MockExtractor:
        mock_instance = MockExtractor.return_value
        # Mock fetch_raw_content to return HTML
        mock_instance.fetch_raw_content = AsyncMock()
        mock_instance.fetch_raw_content.return_value = """
        <html>
            <body>
                <a href="/nodeId=123" class="toc-item">Title 1</a>
                <a href="/other">Ignore</a>
            </body>
        </html>
        """
        
        service = MunicodeDiscoveryService()
        results = await service.find_laws()
        
        
        assert len(results) == 1
        assert results[0].title == "Title 1"
        assert "nodeId=123" in results[0].url

@pytest.mark.asyncio
async def test_search_discovery_zai_success():
    """Test Z.ai Structured Search success path."""
    from services.discovery.search_discovery import SearchDiscoveryService
    
    # Mock Response Data
    mock_zai_response = {
        "web_search": [
            {
                "refer": "ref_1",
                "title": "Z.ai Result 1",
                "link": "http://example.com/1",
                "content": "Snippet 1"
            },
            {
                "refer": "ref_2",
                "title": "Z.ai Result 2",
                "link": "http://example.com/2",
                "content": "Snippet 2"
            }
        ]
    }
    
    # Mock HTTP Client
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_zai_response
        mock_client.post.return_value = mock_resp
        
        service = SearchDiscoveryService(api_key="test-key")
        results = await service.find_urls("test query")
        
        assert len(results) == 2
        assert results[0].url == "http://example.com/1"
        assert results[0].title == "Z.ai Result 1"
        assert results[0].domain == "example.com"

@pytest.mark.asyncio
async def test_search_discovery_fallback_logic():
    """Test fallback to Playwright (mocked) when Z.ai fails."""
    from services.discovery.search_discovery import SearchDiscoveryService
    
    # Mock Z.ai Failure (Empty results or API error)
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        # Scenario: API Error
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client.post.return_value = mock_resp
        
        service = SearchDiscoveryService(api_key="test-key")
        
        # Mock _fallback_search_duckduckgo using patch.object
        # We need to patch it BEFORE calling find_urls
        with patch.object(service, '_fallback_search_duckduckgo', new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = [WebSearchResult(url="http://fallback.com", title="Fallback", snippet="Desc", domain="fallback.com")]
            
            results = await service.find_urls("test query")
            
            # Verify Z.ai called
            mock_client.post.assert_called_once()
            
            # Verify Fallback called
            mock_fallback.assert_called_once_with("test query", 5)
            
            assert len(results) == 1
            assert results[0].url == "http://fallback.com"

def test_search_discovery_query_optimization():
    """Test site: operator optimization."""
    from services.discovery.search_discovery import SearchDiscoveryService
    service = SearchDiscoveryService(api_key="test")
    
    # Case 1: Standard query
    assert service._optimize_query("hello world") == "hello world"
    
    # Case 2: site: operator
    assert service._optimize_query("site:example.com housing") == "housing from example.com"

