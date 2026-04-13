"""Centralized legislation search client construction for backend runtime."""

from __future__ import annotations

import asyncio
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
SEARXNG_PROVIDER_NAMES = {"oss_searxng", "searxng", "searx"}


class ZaiStructuredWebSearchClient:
    """Search client using Z.ai chat completions + web_search tool."""

    def __init__(
        self,
        api_key: str,
        endpoint: str = DEFAULT_ZAI_CHAT_COMPLETIONS_URL,
        model: str = DEFAULT_ZAI_SEARCH_MODEL,
        structured_timeout_s: float = 15.0,
        fallback_timeout_s: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.structured_timeout_s = max(0.1, structured_timeout_s)
        self.fallback_timeout_s = max(0.1, fallback_timeout_s)
        self.client = httpx.AsyncClient(timeout=60.0)

    async def search(
        self,
        query: str,
        count: int = 5,
        domains: list[str] | None = None,
        recency: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        try:
            async with asyncio.timeout(self.structured_timeout_s):
                structured_results = await self._search_zai_structured(
                    query=query,
                    count=count,
                    domains=domains,
                    recency=recency,
                    **kwargs,
                )
        except asyncio.TimeoutError:
            logger.warning(
                "Structured Z.ai search timed out for %r after %.2fs",
                query,
                self.structured_timeout_s,
            )
            structured_results = []
        except Exception as e:
            logger.warning("Structured Z.ai search failed for %r: %s", query, e)
            structured_results = []
        if structured_results:
            return structured_results

        logger.warning(
            "Structured Z.ai search returned zero results for %r; falling back to DuckDuckGo HTML search",
            query,
        )
        try:
            async with asyncio.timeout(self.fallback_timeout_s):
                return await self._search_duckduckgo_html(query=query, count=count)
        except asyncio.TimeoutError:
            logger.warning(
                "DuckDuckGo fallback timed out for %r after %.2fs",
                query,
                self.fallback_timeout_s,
            )
            return []
        except Exception as e:
            logger.warning("DuckDuckGo fallback failed for %r: %s", query, e)
            return []

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


class OssSearxngWebSearchClient:
    """Search client using a SearXNG JSON endpoint."""

    def __init__(
        self,
        endpoint: str,
        *,
        timeout_s: float = 20.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.endpoint = endpoint.strip()
        self.timeout_s = max(0.1, timeout_s)
        self.user_agent = user_agent
        self.client = httpx.AsyncClient(timeout=self.timeout_s)

    async def search(
        self,
        query: str,
        count: int = 5,
        domains: list[str] | None = None,
        recency: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        _ = recency
        if not self.endpoint:
            logger.warning("SearXNG search requested without SEARXNG endpoint")
            return []
        search_query = query
        if domains:
            search_query = f"{query} " + " ".join(f"site:{domain}" for domain in domains)
        try:
            response = await self.client.get(
                self.endpoint,
                params={"q": search_query, "format": "json", **kwargs},
                headers={"User-Agent": self.user_agent},
            )
            response.raise_for_status()
            return self._normalize_results(response.json(), count=count)
        except Exception as e:
            logger.warning("SearXNG search failed for %r: %s", query, e)
            return []

    @staticmethod
    def _normalize_results(payload: dict[str, Any], count: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for item in payload.get("results") or []:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("link")
            if not url or url in seen_urls:
                continue
            seen_urls.add(str(url))
            snippet = item.get("content") or item.get("snippet") or ""
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": str(url),
                    "link": str(url),
                    "snippet": snippet,
                    "content": snippet,
                    "engines": item.get("engines", []),
                }
            )
            if len(results) >= count:
                break
        return results

    async def close(self) -> None:
        await self.client.aclose()


def _configured_searxng_endpoint() -> str:
    return (
        os.getenv("SEARXNG_SEARCH_ENDPOINT")
        or os.getenv("WEB_SEARCH_SEARXNG_ENDPOINT")
        or os.getenv("SEARXNG_ENDPOINT")
        or ""
    ).strip()


def create_web_search_client(api_key: str | None) -> ZaiStructuredWebSearchClient | OssSearxngWebSearchClient:
    """Create the configured web-search client.

    Z.ai structured search is retained for backward compatibility, but the
    Windmill persisted-pipeline POC can opt into OSS SearXNG by setting
    WEB_SEARCH_PROVIDER=oss_searxng and SEARXNG_SEARCH_ENDPOINT. If a SearXNG
    endpoint is configured but WEB_SEARCH_PROVIDER is absent, prefer SearXNG so
    deployed POC environments do not silently fall back to the broken Z.ai
    search path.
    """
    searxng_endpoint = _configured_searxng_endpoint()
    provider = os.getenv("WEB_SEARCH_PROVIDER", "").strip().lower()
    if provider in SEARXNG_PROVIDER_NAMES or (not provider and searxng_endpoint):
        timeout_s = float(os.getenv("WEB_SEARCH_SEARXNG_TIMEOUT_S", "20"))
        logger.info("Using OSS SearXNG search endpoint: %s", searxng_endpoint)
        return OssSearxngWebSearchClient(
            endpoint=searxng_endpoint,
            timeout_s=timeout_s,
        )
    if provider and provider not in {"zai", "zai_structured", "zai_web_search"}:
        raise ValueError(f"unsupported WEB_SEARCH_PROVIDER: {provider}")

    endpoint = (
        os.getenv("ZAI_SEARCH_ENDPOINT", DEFAULT_ZAI_CHAT_COMPLETIONS_URL)
        .strip()
        .rstrip("/")
    )
    if not endpoint:
        endpoint = DEFAULT_ZAI_CHAT_COMPLETIONS_URL

    model = os.getenv("LLM_MODEL_RESEARCH", DEFAULT_ZAI_SEARCH_MODEL)
    structured_timeout_s = float(os.getenv("WEB_SEARCH_STRUCTURED_TIMEOUT_S", "15"))
    fallback_timeout_s = float(os.getenv("WEB_SEARCH_FALLBACK_TIMEOUT_S", "10"))
    logger.info("Using structured web search endpoint: %s", endpoint)

    return ZaiStructuredWebSearchClient(
        api_key=api_key or "",
        endpoint=endpoint,
        model=model,
        structured_timeout_s=structured_timeout_s,
        fallback_timeout_s=fallback_timeout_s,
    )
