"""Centralized legislation search client construction for backend runtime."""

from __future__ import annotations

import html
import logging
import os
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

logger = logging.getLogger(__name__)

DEFAULT_ZAI_CHAT_COMPLETIONS_URL = "https://api.z.ai/api/coding/paas/v4/chat/completions"
DEFAULT_ZAI_SEARCH_MODEL = "glm-4.7"
DDG_HTML_SEARCH_URL = "https://html.duckduckgo.com/html/"
DEFAULT_USER_AGENT = "Mozilla/5.0"


class ZaiStructuredWebSearchClient:
    """Search client using Z.ai chat completions + web_search tool."""

    def __init__(
        self,
        api_key: str,
        endpoint: str = DEFAULT_ZAI_CHAT_COMPLETIONS_URL,
        model: str = DEFAULT_ZAI_SEARCH_MODEL,
    ) -> None:
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.client = httpx.AsyncClient(timeout=60.0)

    async def search(
        self,
        query: str,
        count: int = 5,
        domains: list[str] | None = None,
        recency: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        structured_results = await self._search_zai_structured(
            query=query,
            count=count,
            domains=domains,
            recency=recency,
            **kwargs,
        )
        if structured_results:
            return structured_results

        logger.warning(
            "Structured Z.ai search returned zero results for %r; falling back to DuckDuckGo HTML search",
            query,
        )
        return await self._search_duckduckgo_html(query=query, count=count)

    async def _search_zai_structured(
        self,
        query: str,
        count: int,
        domains: list[str] | None = None,
        recency: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": f"Search for: {query}"}],
            "tools": [
                {
                    "type": "web_search",
                    "web_search": {
                        "enable": "True",
                        "search_engine": "search-prime",
                        "search_result": "True",
                        "search_query": query,
                    },
                }
            ],
            "stream": False,
        }
        if domains:
            payload["tools"][0]["web_search"]["domains"] = domains
        if recency:
            payload["tools"][0]["web_search"]["recency"] = recency
        if kwargs:
            payload["tools"][0]["web_search"].update(kwargs)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = await self.client.post(self.endpoint, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        web_search_data = data.get("web_search", [])
        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for item in web_search_data:
            url = item.get("link") or item.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": url,
                    "link": url,
                    "snippet": item.get("content", ""),
                    "content": item.get("content", ""),
                }
            )

        return results[:count]

    async def _search_duckduckgo_html(self, query: str, count: int) -> list[dict[str, Any]]:
        response = await self.client.get(
            DDG_HTML_SEARCH_URL,
            params={"q": query},
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )
        response.raise_for_status()
        return self._parse_duckduckgo_html(response.text, count=count)

    @staticmethod
    def _parse_duckduckgo_html(html_body: str, count: int) -> list[dict[str, Any]]:
        snippet_pattern = re.compile(
            r'(?s)<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(.*?)</div>'
        )
        anchor_pattern = re.compile(
            r'(?s)<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
        )

        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for match in anchor_pattern.finditer(html_body):
            href, raw_title = match.groups()
            url = ZaiStructuredWebSearchClient._unwrap_duckduckgo_redirect(href)
            if not url or url in seen_urls:
                continue

            seen_urls.add(url)
            remainder = html_body[match.end() : match.end() + 1500]
            snippet_match = snippet_pattern.search(remainder)
            raw_snippet = ""
            if snippet_match:
                raw_snippet = snippet_match.group(1) or snippet_match.group(2) or ""

            title = ZaiStructuredWebSearchClient._clean_html_text(raw_title)
            snippet = ZaiStructuredWebSearchClient._clean_html_text(raw_snippet)
            results.append(
                {
                    "title": title,
                    "url": url,
                    "link": url,
                    "snippet": snippet,
                    "content": snippet,
                }
            )
            if len(results) >= count:
                break

        return results

    @staticmethod
    def _unwrap_duckduckgo_redirect(url: str) -> str:
        if not url:
            return ""

        if url.startswith("//"):
            url = f"https:{url}"

        parsed = urlparse(url)
        if "duckduckgo.com" not in parsed.netloc:
            return url

        uddg = parse_qs(parsed.query).get("uddg", [])
        if not uddg:
            return ""
        return unquote(uddg[0])

    @staticmethod
    def _clean_html_text(value: str) -> str:
        stripped = re.sub(r"<[^>]+>", " ", value)
        normalized = re.sub(r"\s+", " ", html.unescape(stripped)).strip()
        return normalized

    async def close(self) -> None:
        await self.client.aclose()


def create_web_search_client(api_key: str | None) -> ZaiStructuredWebSearchClient:
    """Create a web-search client using the validated Z.ai structured-search path."""
    endpoint = (
        os.getenv("ZAI_SEARCH_ENDPOINT", DEFAULT_ZAI_CHAT_COMPLETIONS_URL)
        .strip()
        .rstrip("/")
    )
    if not endpoint:
        endpoint = DEFAULT_ZAI_CHAT_COMPLETIONS_URL

    model = os.getenv("LLM_MODEL_RESEARCH", DEFAULT_ZAI_SEARCH_MODEL)
    logger.info("Using structured web search endpoint: %s", endpoint)

    return ZaiStructuredWebSearchClient(
        api_key=api_key or "",
        endpoint=endpoint,
        model=model,
    )
