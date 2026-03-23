import pytest

from services.llm.web_search_factory import ZaiStructuredWebSearchClient


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
