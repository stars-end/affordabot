import pytest
from unittest.mock import AsyncMock, patch
import sys
from types import SimpleNamespace

class _AsyncOpenAIStub:
    def __init__(self, *args, **kwargs):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))


sys.modules.setdefault("instructor", SimpleNamespace(from_openai=lambda client: client))
sys.modules.setdefault("openai", SimpleNamespace(AsyncOpenAI=_AsyncOpenAIStub))

from services.discovery.service import ZAI_CODING_BASE_URL  # noqa: E402
from services.discovery import AutoDiscoveryService, DiscoveryResponse  # noqa: E402

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


@pytest.mark.asyncio
async def test_discover_url_malformed_output_falls_back_to_heuristics():
    with patch.dict("os.environ", {"ZAI_API_KEY": "fake_key"}):
        service = AutoDiscoveryService()
        service.client.chat.completions.create = AsyncMock(
            side_effect=Exception(
                "1 validation error for DiscoveryResponse: Invalid JSON <arg_key>is_scrapable"
            )
        )

        result = await service.discover_url(
            "https://www.sanjoseca.gov/your-government/appointees/city-clerk/council-agendas-minutes/council-agendas",
            "",
        )

        assert result.is_scrapable is True
        assert result.source_type == "minutes" or result.source_type == "agenda"
        assert result.confidence >= 0.75
        assert "Fallback heuristic applied" in result.reasoning


@pytest.mark.asyncio
async def test_discover_url_plural_validation_errors_falls_back_to_heuristics():
    with patch.dict("os.environ", {"ZAI_API_KEY": "fake_key"}):
        service = AutoDiscoveryService()
        service.client.chat.completions.create = AsyncMock(
            side_effect=Exception("6 validation errors for DiscoveryResponse")
        )

        result = await service.discover_url(
            "https://www.sanjoseca.gov/your-government/appointees/city-clerk/council-agendas-minutes/council-agendas",
            "",
        )

        assert result.is_scrapable is True
        assert result.confidence >= 0.75


@pytest.mark.asyncio
async def test_discover_url_non_malformed_error_returns_error_response():
    with patch.dict("os.environ", {"ZAI_API_KEY": "fake_key"}):
        service = AutoDiscoveryService()
        service.client.chat.completions.create = AsyncMock(
            side_effect=Exception("Rate limit reached for requests")
        )

        result = await service.discover_url("https://example.com", "")

        assert result.is_scrapable is False
        assert result.source_type == "error"
        assert result.confidence == 0.0


def test_discovery_response_cache_payload_roundtrip():
    response = DiscoveryResponse(
        is_scrapable=True,
        jurisdiction_name="San Jose",
        source_type="agenda",
        recommended_spider="generic",
        confidence=0.9,
        reasoning="test",
    )

    payload = AutoDiscoveryService.response_to_cache_payload(response)
    restored = AutoDiscoveryService.response_from_cache_payload(payload)

    assert restored is not None
    assert restored.is_scrapable is True
    assert restored.confidence == 0.9
