import asyncio

from services.llm.web_search_factory import (
    OssSearxngWebSearchClient,
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
