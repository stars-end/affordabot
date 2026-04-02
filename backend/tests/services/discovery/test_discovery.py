import pytest
from unittest.mock import AsyncMock, patch
from services.discovery.service import ZAI_CODING_BASE_URL
from services.discovery import AutoDiscoveryService, DiscoveryResponse

@pytest.mark.asyncio
async def test_auto_discovery_initialization():
    with patch.dict("os.environ", {"ZAI_API_KEY": "fake_key"}):
        service = AutoDiscoveryService()
        assert service.client is not None
        assert service.model == "glm-4.7"

    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake_key"}, clear=True):
        service = AutoDiscoveryService()
        assert service.client is not None
        assert service.model == "x-ai/grok-4.1-fast:free"

    with patch.dict("os.environ", {}, clear=True):
        service = AutoDiscoveryService()
        assert service.client is None


def test_auto_discovery_uses_coding_endpoint_for_zai(monkeypatch):
    captured = {}

    class FakeAsyncOpenAI:
        def __init__(self, *, api_key, base_url):
            captured["api_key"] = api_key
            captured["base_url"] = base_url

    def fake_from_openai(client):
        return client

    monkeypatch.setattr("services.discovery.service.AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr("services.discovery.service.instructor.from_openai", fake_from_openai)

    with patch.dict("os.environ", {"ZAI_API_KEY": "fake_key"}, clear=True):
        service = AutoDiscoveryService()

    assert service.client is not None
    assert captured["base_url"] == ZAI_CODING_BASE_URL

@pytest.mark.asyncio
async def test_discover_url_success():
    mock_response = DiscoveryResponse(
        is_scrapable=True,
        jurisdiction_name="San Jose",
        source_type="agenda",
        recommended_spider="sanjose_prime",
        confidence=0.95,
        reasoning="Looks like an agenda page"
    )

    with patch.dict("os.environ", {"ZAI_API_KEY": "fake_key"}):
        service = AutoDiscoveryService()
        
        # Mock the instructor client create method
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await service.discover_url("http://sanjose.gov/agendas", "Agenda content")
        
        assert result.is_scrapable is True
        assert result.jurisdiction_name == "San Jose"
        assert service.client.chat.completions.create.called

@pytest.mark.asyncio
async def test_discover_url_no_client():
    with patch.dict("os.environ", {}, clear=True):
        service = AutoDiscoveryService()
        result = await service.discover_url("http://test.com")
        assert result.reasoning == "LLM Client not initialized"
        assert result.confidence == 0.0
