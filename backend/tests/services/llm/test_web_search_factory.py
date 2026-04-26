import asyncio
import json

import httpx
import pytest

from services.llm.web_search_factory import (
    ExaWebSearchClient,
    OssSearxngWebSearchClient,
    TavilyWebSearchClient,
    ZaiStructuredWebSearchClient,
    create_web_search_client,
)


def test_parse_duckduckgo_html_extracts_redirected_urls_and_snippets():
    html_body = """
    <div class="result results_links_deep web-result">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Freport">Example Report</a>
      <a class="result__snippet">Estimated cost is <b>$50M</b> over five years.</a>
    </div>
    """

    results = ZaiStructuredWebSearchClient._parse_duckduckgo_html(html_body, count=5)

    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/report"
    assert results[0]["title"] == "Example Report"
    assert "$50M" in results[0]["snippet"]


def test_search_falls_back_to_duckduckgo_when_structured_search_is_empty():
    client = ZaiStructuredWebSearchClient(api_key="test-key")

    async def fake_structured(*args, **kwargs):
        return []

    async def fake_duckduckgo(*args, **kwargs):
        return [{"url": "https://example.com/fallback", "title": "Fallback"}]

    client._search_zai_structured = fake_structured  # type: ignore[method-assign]
    client._search_duckduckgo_html = fake_duckduckgo  # type: ignore[method-assign]

    async def _run():
        results = await client.search("SB 277 fiscal impact", count=3)
        await client.close()
        return results

    results = asyncio.run(_run())

    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/fallback"


def test_search_uses_fallback_when_structured_times_out():
    client = ZaiStructuredWebSearchClient(
        api_key="test-key",
        structured_timeout_s=0.01,
    )

    async def slow_structured(*args, **kwargs):
        await asyncio.sleep(0.1)
        return [{"url": "https://example.com/structured"}]

    async def fake_duckduckgo(*args, **kwargs):
        return [{"url": "https://example.com/fallback-timeout", "title": "Fallback"}]

    client._search_zai_structured = slow_structured  # type: ignore[method-assign]
    client._search_duckduckgo_html = fake_duckduckgo  # type: ignore[method-assign]

    async def _run():
        results = await client.search("SB 277 fiscal impact", count=3)
        await client.close()
        return results

    results = asyncio.run(_run())

    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/fallback-timeout"


def test_search_returns_empty_when_fallback_times_out():
    client = ZaiStructuredWebSearchClient(
        api_key="test-key",
        fallback_timeout_s=0.01,
    )

    async def fake_structured(*args, **kwargs):
        return []

    async def slow_duckduckgo(*args, **kwargs):
        await asyncio.sleep(0.1)
        return [{"url": "https://example.com/never"}]

    client._search_zai_structured = fake_structured  # type: ignore[method-assign]
    client._search_duckduckgo_html = slow_duckduckgo  # type: ignore[method-assign]

    async def _run():
        results = await client.search("SB 277 fiscal impact", count=3)
        await client.close()
        return results

    results = asyncio.run(_run())

    assert results == []


def test_searxng_normalizes_json_results():
    payload = {
        "results": [
            {
                "url": "https://www.sanjoseca.gov/agenda/1",
                "title": "Agenda",
                "content": "Housing permit timelines",
                "engines": ["mock-searxng"],
            },
            {
                "url": "https://www.sanjoseca.gov/agenda/1",
                "title": "Duplicate",
                "content": "Duplicate should be removed",
            },
        ]
    }

    results = OssSearxngWebSearchClient._normalize_results(payload, count=5)

    assert results == [
        {
            "title": "Agenda",
            "url": "https://www.sanjoseca.gov/agenda/1",
            "link": "https://www.sanjoseca.gov/agenda/1",
            "snippet": "Housing permit timelines",
            "content": "Housing permit timelines",
            "engines": ["mock-searxng"],
        }
    ]


def test_factory_selects_searxng_when_provider_configured(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "oss_searxng")
    monkeypatch.setenv("SEARXNG_SEARCH_ENDPOINT", "https://search.example/search")

    client = create_web_search_client(api_key=None)

    assert isinstance(client, OssSearxngWebSearchClient)
    assert client.endpoint == "https://search.example/search"
    asyncio.run(client.close())


def test_factory_prefers_configured_searxng_endpoint_over_zai_default(monkeypatch):
    monkeypatch.delenv("WEB_SEARCH_PROVIDER", raising=False)
    monkeypatch.setenv("SEARXNG_SEARCH_ENDPOINT", "https://search.example/search")

    client = create_web_search_client(api_key="zai-key")

    assert isinstance(client, OssSearxngWebSearchClient)
    asyncio.run(client.close())


def test_factory_selects_tavily_with_env_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")

    client = create_web_search_client(api_key=None)

    assert isinstance(client, TavilyWebSearchClient)
    asyncio.run(client.close())


def test_factory_selects_tavily_with_explicit_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    client = create_web_search_client(api_key="explicit-key")

    assert isinstance(client, TavilyWebSearchClient)
    assert client.api_key == "explicit-key"
    asyncio.run(client.close())


def test_factory_tavily_prefers_provider_specific_env_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-env-key")

    client = create_web_search_client(api_key="zai-key-that-should-not-be-used")

    assert isinstance(client, TavilyWebSearchClient)
    assert client.api_key == "tavily-env-key"
    asyncio.run(client.close())


def test_factory_tavily_requires_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with pytest.raises(
        ValueError, match="missing TAVILY_API_KEY for WEB_SEARCH_PROVIDER=tavily"
    ):
        create_web_search_client(api_key=None)


def test_factory_selects_exa_with_env_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "exa")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-key")

    client = create_web_search_client(api_key=None)

    assert isinstance(client, ExaWebSearchClient)
    asyncio.run(client.close())


def test_factory_selects_exa_with_explicit_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "exa")
    monkeypatch.delenv("EXA_API_KEY", raising=False)

    client = create_web_search_client(api_key="explicit-exa-key")

    assert isinstance(client, ExaWebSearchClient)
    assert client.api_key == "explicit-exa-key"
    asyncio.run(client.close())


def test_factory_exa_prefers_provider_specific_env_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "exa")
    monkeypatch.setenv("EXA_API_KEY", "exa-env-key")

    client = create_web_search_client(api_key="zai-key-that-should-not-be-used")

    assert isinstance(client, ExaWebSearchClient)
    assert client.api_key == "exa-env-key"
    asyncio.run(client.close())


def test_factory_exa_requires_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "exa")
    monkeypatch.delenv("EXA_API_KEY", raising=False)

    with pytest.raises(ValueError, match="missing EXA_API_KEY for WEB_SEARCH_PROVIDER=exa"):
        create_web_search_client(api_key=None)


def test_tavily_search_posts_expected_payload_and_headers():
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["auth"] = request.headers.get("Authorization")
        observed["content_type"] = request.headers.get("Content-Type")
        observed["payload"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "City Council Minutes",
                        "url": "https://www.sanjoseca.gov/minutes",
                        "content": "Council considered housing policy updates.",
                        "raw_content": "Full minutes body content",
                        "score": 0.92,
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = TavilyWebSearchClient(api_key="tavily-key", endpoint="https://api.tavily.com/search")
    client.client = httpx.AsyncClient(transport=transport, timeout=20.0)

    async def _run():
        results = await client.search("san jose city council meeting minutes", count=3)
        await client.close()
        return results

    results = asyncio.run(_run())

    assert observed["url"] == "https://api.tavily.com/search"
    assert observed["auth"] == "Bearer tavily-key"
    assert observed["content_type"] == "application/json"
    payload = json.loads(str(observed["payload"]))
    assert payload["query"] == "san jose city council meeting minutes"
    assert payload["search_depth"] == "basic"
    assert payload["include_raw_content"] is False
    assert payload["max_results"] == 3
    assert results == [
        {
            "title": "City Council Minutes",
            "url": "https://www.sanjoseca.gov/minutes",
            "link": "https://www.sanjoseca.gov/minutes",
            "snippet": "Council considered housing policy updates.",
            "content": "Full minutes body content",
            "score": 0.92,
        }
    ]


def test_tavily_normalizes_and_deduplicates_results():
    payload = {
        "results": [
            {
                "title": "A",
                "url": "https://example.com/a",
                "content": "snippet-a",
                "raw_content": "raw-a",
                "score": 0.7,
            },
            {
                "title": "Duplicate A",
                "url": "https://example.com/a",
                "content": "dup",
            },
            {
                "title": "B",
                "url": "https://example.com/b",
                "snippet": "snippet-b",
            },
        ]
    }

    results = TavilyWebSearchClient._normalize_results(payload, count=5)

    assert results == [
        {
            "title": "A",
            "url": "https://example.com/a",
            "link": "https://example.com/a",
            "snippet": "snippet-a",
            "content": "raw-a",
            "score": 0.7,
        },
        {
            "title": "B",
            "url": "https://example.com/b",
            "link": "https://example.com/b",
            "snippet": "snippet-b",
            "content": "snippet-b",
            "score": None,
        },
    ]


def test_exa_search_posts_expected_payload_and_headers():
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["api_key"] = request.headers.get("x-api-key")
        observed["content_type"] = request.headers.get("Content-Type")
        observed["user_agent"] = request.headers.get("User-Agent")
        observed["payload"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "San Jose Legistar Minutes",
                        "url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=123",
                        "highlights": ["Minutes include housing item updates."],
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = ExaWebSearchClient(
        api_key="exa-key",
        endpoint="https://api.exa.ai/search",
        user_agent="affordabot-test/1.0",
    )
    client.client = httpx.AsyncClient(transport=transport, timeout=20.0)

    async def _run():
        results = await client.search("san jose city council meeting minutes", count=3)
        await client.close()
        return results

    results = asyncio.run(_run())

    assert observed["url"] == "https://api.exa.ai/search"
    assert observed["api_key"] == "exa-key"
    assert observed["content_type"] == "application/json"
    assert observed["user_agent"] == "affordabot-test/1.0"
    payload = json.loads(str(observed["payload"]))
    assert payload["query"] == "san jose city council meeting minutes"
    assert payload["numResults"] == 3
    assert payload["type"] == "auto"
    assert payload["contents"] == {"highlights": {"maxCharacters": 400}}
    assert results == [
        {
            "title": "San Jose Legistar Minutes",
            "url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=123",
            "link": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=123",
            "snippet": "Minutes include housing item updates.",
            "content": "Minutes include housing item updates.",
            "provider": "exa",
            "position": 1,
        }
    ]


def test_exa_normalizes_and_deduplicates_results():
    payload = {
        "results": [
            {
                "title": "A",
                "url": "https://example.com/a",
                "highlights": ["snippet-a"],
            },
            {
                "title": "Duplicate A",
                "url": "https://example.com/a",
                "highlights": ["dup"],
            },
            {
                "title": "B",
                "url": "https://example.com/b",
                "highlights": [],
            },
        ]
    }

    results = ExaWebSearchClient._normalize_results(payload, count=5)

    assert results == [
        {
            "title": "A",
            "url": "https://example.com/a",
            "link": "https://example.com/a",
            "snippet": "snippet-a",
            "content": "snippet-a",
            "provider": "exa",
            "position": 1,
        },
        {
            "title": "B",
            "url": "https://example.com/b",
            "link": "https://example.com/b",
            "snippet": "",
            "content": "",
            "provider": "exa",
            "position": 2,
        },
    ]
