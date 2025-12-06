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
         patch("os.remove") as mock_remove, \
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
