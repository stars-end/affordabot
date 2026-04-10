"""Centralized legislation search client construction for backend runtime."""

from __future__ import annotations

import asyncio
import html
import logging
import os
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
import urllib.parse
import urllib.request
import urllib.error

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - compatibility path for lean runtimes
    class _CompatResponse:
        def __init__(self, status_code: int, body: bytes):
            self.status_code = status_code
            self._body = body
            self.text = body.decode("utf-8", errors="replace")

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP error: {self.status_code}")

        def json(self) -> Any:
            import json

            return json.loads(self.text)

    class _CompatAsyncClient:
        def __init__(self, timeout: float = 60.0):
            self.timeout = timeout

        async def get(self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None):
            def _do_get() -> _CompatResponse:
                full_url = url
                if params:
                    sep = "&" if "?" in url else "?"
                    full_url = f"{url}{sep}{urllib.parse.urlencode(params, doseq=True)}"
                req = urllib.request.Request(full_url, headers=headers or {}, method="GET")
                try:
                    with urllib.request.urlopen(req, timeout=self.timeout) as response:
                        return _CompatResponse(response.status, response.read())
                except urllib.error.HTTPError as e:
                    return _CompatResponse(e.code, e.read())

            return await asyncio.to_thread(_do_get)

        async def post(self, url: str, json: Any | None = None, headers: dict[str, str] | None = None):
            def _do_post() -> _CompatResponse:
                import json as jsonlib

                payload = jsonlib.dumps(json or {}).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers=headers or {}, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=self.timeout) as response:
                        return _CompatResponse(response.status, response.read())
                except urllib.error.HTTPError as e:
                    return _CompatResponse(e.code, e.read())

            return await asyncio.to_thread(_do_post)

        async def aclose(self) -> None:
            return None

    class httpx:  # type: ignore[no-redef]
        AsyncClient = _CompatAsyncClient

logger = logging.getLogger(__name__)

DEFAULT_ZAI_CHAT_COMPLETIONS_URL = "https://api.z.ai/api/coding/paas/v4/chat/completions"
DEFAULT_ZAI_SEARCH_MODEL = "glm-4.7"
DDG_HTML_SEARCH_URL = "https://html.duckduckgo.com/html/"
DEFAULT_SEARXNG_SEARCH_URL = "http://127.0.0.1:8080/search"
DEFAULT_USER_AGENT = "Mozilla/5.0"


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
    """Search client backed by an OSS-hosted SearXNG endpoint."""

    def __init__(
        self,
        endpoint: str = DEFAULT_SEARXNG_SEARCH_URL,
        timeout_s: float = 20.0,
        max_retries: int = 2,
        backoff_base_s: float = 0.5,
        backoff_max_s: float = 5.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout_s = max(0.1, timeout_s)
        self.max_retries = max(0, max_retries)
        self.backoff_base_s = max(0.0, backoff_base_s)
        self.backoff_max_s = max(self.backoff_base_s, backoff_max_s)
        self.client = httpx.AsyncClient(timeout=self.timeout_s)

    async def search(
        self,
        query: str,
        count: int = 5,
        domains: list[str] | None = None,
        recency: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "q": query,
            "format": "json",
            "language": "en-US",
        }
        if domains:
            params["engines"] = ",".join(domains)
        if recency:
            params["time_range"] = recency
        if kwargs:
            params.update(kwargs)

        last_error: Exception | None = None
        payload: dict[str, Any] = {}
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.get(self.endpoint, params=params)
                status_code = getattr(response, "status_code", 200)
                if status_code in {429, 503} and attempt < self.max_retries:
                    await self._sleep_backoff(attempt)
                    continue
                response.raise_for_status()
                payload = response.json()
                break
            except Exception as e:
                last_error = e
                if attempt >= self.max_retries:
                    raise
                await self._sleep_backoff(attempt)

        if not payload and last_error:
            raise last_error

        normalized: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for item in payload.get("results", []):
            url = item.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            normalized.append(
                {
                    "title": item.get("title", ""),
                    "url": url,
                    "link": url,
                    "snippet": item.get("content", ""),
                    "content": item.get("content", ""),
                }
            )
            if len(normalized) >= count:
                break
        return normalized

    async def _sleep_backoff(self, attempt: int) -> None:
        if self.backoff_base_s <= 0:
            return
        delay = min(
            self.backoff_max_s,
            self.backoff_base_s * (2**attempt),
        )
        # light jitter avoids synchronized retries across workers.
        jitter = delay * 0.2
        await asyncio.sleep(max(0.0, delay + ((jitter * 2 * os.urandom(1)[0] / 255.0) - jitter)))

    async def close(self) -> None:
        await self.client.aclose()


def create_web_search_client(
    api_key: str | None,
) -> ZaiStructuredWebSearchClient | OssSearxngWebSearchClient:
    """Create a web-search client for either Z.ai structured search or OSS SearXNG."""
    provider = os.getenv("WEB_SEARCH_PROVIDER", "zai").strip().lower()
    if provider in {"oss", "oss-searxng", "searxng"}:
        endpoint = (
            os.getenv("OSS_WEB_SEARCH_ENDPOINT", DEFAULT_SEARXNG_SEARCH_URL)
            .strip()
            .rstrip("/")
        )
        if not endpoint:
            endpoint = DEFAULT_SEARXNG_SEARCH_URL
        timeout_s = float(os.getenv("OSS_WEB_SEARCH_TIMEOUT_S", "20"))
        max_retries = int(os.getenv("OSS_WEB_SEARCH_MAX_RETRIES", "2"))
        backoff_base_s = float(os.getenv("OSS_WEB_SEARCH_BACKOFF_BASE_S", "0.5"))
        backoff_max_s = float(os.getenv("OSS_WEB_SEARCH_BACKOFF_MAX_S", "5"))
        logger.info("Using OSS web search endpoint: %s", endpoint)
        return OssSearxngWebSearchClient(
            endpoint=endpoint,
            timeout_s=timeout_s,
            max_retries=max_retries,
            backoff_base_s=backoff_base_s,
            backoff_max_s=backoff_max_s,
        )

    # Default to existing Z.ai behavior.
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
