import asyncio
import pytest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

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


@pytest.mark.asyncio
async def test_search_falls_back_to_duckduckgo_when_structured_search_is_empty():
    client = ZaiStructuredWebSearchClient(api_key="test-key")

    async def fake_structured(*args, **kwargs):
        return []

    async def fake_duckduckgo(*args, **kwargs):
        return [{"url": "https://example.com/fallback", "title": "Fallback"}]

    client._search_zai_structured = fake_structured  # type: ignore[method-assign]
    client._search_duckduckgo_html = fake_duckduckgo  # type: ignore[method-assign]

    results = await client.search("SB 277 fiscal impact", count=3)

    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/fallback"
    await client.close()


@pytest.mark.asyncio
async def test_search_uses_fallback_when_structured_times_out():
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

    results = await client.search("SB 277 fiscal impact", count=3)

    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/fallback-timeout"
    await client.close()


@pytest.mark.asyncio
async def test_search_returns_empty_when_fallback_times_out():
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

    results = await client.search("SB 277 fiscal impact", count=3)

    assert results == []
    await client.close()


@pytest.mark.asyncio
async def test_oss_searxng_client_normalizes_results():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = json.dumps(
                {
                    "results": [
                        {
                            "title": "Official fiscal analysis",
                            "url": "https://lao.ca.gov/analysis",
                            "content": "Contains cost estimates.",
                        },
                        {
                            "title": "Duplicate",
                            "url": "https://lao.ca.gov/analysis",
                            "content": "Duplicate row",
                        },
                    ]
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # noqa: D401
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        client = OssSearxngWebSearchClient(endpoint=f"http://127.0.0.1:{port}/search")
        results = await client.search("AB 123 fiscal impact", count=5)
        await client.close()
    finally:
        server.shutdown()
        server.server_close()

    assert len(results) == 1
    assert results[0]["url"] == "https://lao.ca.gov/analysis"
    assert "cost estimates" in results[0]["snippet"]


def test_create_web_search_client_uses_oss_provider(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "oss-searxng")
    monkeypatch.setenv("OSS_WEB_SEARCH_ENDPOINT", "http://127.0.0.1:9999/search")

    client = create_web_search_client(api_key=None)

    assert isinstance(client, OssSearxngWebSearchClient)
