"""Round 1 benchmark helpers for baseline-vs-SearXNG discovery search lanes."""

from __future__ import annotations

import time
from dataclasses import dataclass
from statistics import median
from typing import Any, Iterable, Protocol
from urllib.parse import urlparse

DEFAULT_RESULT_COUNT = 10

INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "agenda": ("agenda", "meeting agenda", "meeting materials"),
    "minutes": ("minutes", "meeting minutes", "approved minutes"),
    "ordinance": ("ordinance", "municipal code", "county code", "code of ordinances"),
}

ARTIFACT_KEYWORDS: tuple[str, ...] = (
    ".pdf",
    ".doc",
    ".docx",
    "agenda packet",
    "meeting agenda",
    "meeting minutes",
    "ordinance",
    "code chapter",
    "code title",
)

PORTAL_KEYWORDS: tuple[str, ...] = (
    "calendar",
    "meetings",
    "departments",
    "city clerk",
    "board of supervisors",
    "portal",
    "agendacenter",
    "legistar",
)


class BenchmarkSearchProvider(Protocol):
    """Provider contract for benchmark lane adapters."""

    async def search(self, query: str, *, query_id: str, count: int) -> list[dict[str, Any]]:
        """Return normalized-ish search results."""

    async def close(self) -> None:
        """Release provider resources."""


@dataclass(frozen=True)
class LaneRunResult:
    """Aggregated benchmark output for one lane."""

    lane: str
    metrics: dict[str, Any]
    query_results: list[dict[str, Any]]


def extract_domain(url: str) -> str:
    """Extract normalized domain from URL."""
    if not url:
        return ""
    try:
        return (urlparse(url).netloc or "").lower().lstrip("www.")
    except Exception:
        return ""


def resolve_searxng_dependency(searxng_base_url: str | None) -> str | None:
    """Fail-closed dependency check for live SearXNG benchmark lane."""
    if searxng_base_url and searxng_base_url.strip():
        return None
    return "SEARXNG_BASE_URL"


def normalize_results(raw_results: Any) -> list[dict[str, Any]]:
    """Normalize heterogeneous search result shapes into dictionaries."""
    if raw_results is None:
        return []

    if hasattr(raw_results, "results"):
        items = list(getattr(raw_results, "results") or [])
    elif isinstance(raw_results, list):
        items = raw_results
    else:
        return []

    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(item)
            continue
        if hasattr(item, "model_dump"):
            normalized.append(item.model_dump())
            continue
        normalized.append(
            {
                "url": getattr(item, "url", "") or getattr(item, "link", ""),
                "link": getattr(item, "link", "") or getattr(item, "url", ""),
                "title": getattr(item, "title", ""),
                "snippet": getattr(item, "snippet", ""),
                "content": getattr(item, "content", ""),
            }
        )

    return normalized


def is_official_source(domain: str, official_domain_hints: Iterable[str]) -> bool:
    """Determine if a domain looks official for local-government discovery."""
    normalized_hints = {hint.lower().lstrip("www.") for hint in official_domain_hints if hint}
    if not domain:
        return False
    if domain.endswith(".gov"):
        return True
    if domain in normalized_hints:
        return True
    return any(domain.endswith(f".{hint}") for hint in normalized_hints)


def classify_result(
    result: dict[str, Any],
    *,
    intent: str,
    official_domain_hints: Iterable[str],
) -> dict[str, Any]:
    """Classify one result for benchmark metrics."""
    url = str(result.get("url") or result.get("link") or "").strip()
    title = str(result.get("title") or "").strip()
    snippet = str(result.get("snippet") or result.get("content") or "").strip()
    domain = extract_domain(url)

    joined_text = " ".join([url.lower(), title.lower(), snippet.lower()])
    intent_terms = INTENT_KEYWORDS.get(intent, ())

    artifact_candidate = any(token in joined_text for token in ARTIFACT_KEYWORDS)
    portal_candidate = (
        any(token in joined_text for token in PORTAL_KEYWORDS) and not artifact_candidate
    )
    intent_match = any(token in joined_text for token in intent_terms)
    official = is_official_source(domain, official_domain_hints)
    useful = official and intent_match

    return {
        "url": url,
        "title": title,
        "snippet": snippet,
        "domain": domain,
        "is_official": official,
        "is_artifact_candidate": artifact_candidate,
        "is_portal_candidate": portal_candidate,
        "is_intent_match": intent_match,
        "is_useful": useful,
    }


def evaluate_query(
    *,
    lane: str,
    query_spec: dict[str, Any],
    raw_results: Any,
    latency_ms: int,
    error: str | None,
) -> dict[str, Any]:
    """Evaluate one query run and return machine-readable per-query metrics."""
    normalized = normalize_results(raw_results)
    classified = [
        classify_result(
            item,
            intent=str(query_spec["intent"]),
            official_domain_hints=query_spec.get("official_domain_hints", []),
        )
        for item in normalized
    ]

    urls = [item["url"] for item in classified if item["url"]]
    unique_urls = list(dict.fromkeys(urls))
    duplicate_url_count = max(0, len(urls) - len(unique_urls))

    top5 = classified[:5]
    official_source_top5 = any(item["is_official"] for item in top5)
    useful_items = [item for item in classified if item["is_useful"]]
    unique_useful = list(dict.fromkeys(item["url"] for item in useful_items if item["url"]))
    artifact_useful_count = sum(1 for item in useful_items if item["is_artifact_candidate"])
    portal_useful_count = sum(1 for item in useful_items if item["is_portal_candidate"])

    failure_mode = None
    if error:
        lowered = error.lower()
        if "timeout" in lowered:
            failure_mode = "timeout"
        elif "401" in lowered or "403" in lowered or "unauthorized" in lowered:
            failure_mode = "auth_or_access"
        elif "429" in lowered:
            failure_mode = "rate_limited"
        else:
            failure_mode = "other_error"

    return {
        "lane": lane,
        "query_id": query_spec["id"],
        "jurisdiction": query_spec["jurisdiction"],
        "intent": query_spec["intent"],
        "query": query_spec["query"],
        "result_count": len(classified),
        "non_empty": len(classified) > 0,
        "official_source_top5": official_source_top5,
        "useful_url_count": len(useful_items),
        "unique_useful_url_count": len(unique_useful),
        "useful_urls": unique_useful,
        "artifact_useful_count": artifact_useful_count,
        "portal_useful_count": portal_useful_count,
        "duplicate_url_count": duplicate_url_count,
        "duplicate_url_rate": (
            duplicate_url_count / len(urls)
            if urls
            else 0.0
        ),
        "latency_ms": max(0, latency_ms),
        "hard_failure": error is not None,
        "failure_mode": failure_mode,
        "error": error,
        "top_results": [
            {
                "url": item["url"],
                "title": item["title"],
                "domain": item["domain"],
                "is_official": item["is_official"],
                "is_useful": item["is_useful"],
            }
            for item in top5
        ],
    }


def summarize_lane_metrics(lane: str, query_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate query-level evaluations into required lane metrics."""
    total = len(query_results)
    if total == 0:
        return {
            "lane": lane,
            "query_count": 0,
            "empty_result_rate": 0.0,
            "non_empty_result_rate": 0.0,
            "official_source_top5_rate": 0.0,
            "useful_url_yield": 0.0,
            "unique_useful_url_yield": 0.0,
            "artifact_vs_portal_rate": 0.0,
            "duplicate_url_rate": 0.0,
            "median_latency_ms": 0,
            "hard_failure_rate": 0.0,
            "failure_modes": {},
            "representative_samples": [],
        }

    empty_count = sum(1 for row in query_results if not row["non_empty"])
    non_empty_count = total - empty_count
    official_top5_count = sum(1 for row in query_results if row["official_source_top5"])
    useful_url_total = sum(int(row["useful_url_count"]) for row in query_results)
    unique_useful_total = len(
        {
            url
            for row in query_results
            for url in row.get("useful_urls", [])
        }
    )
    artifact_total = sum(int(row["artifact_useful_count"]) for row in query_results)
    portal_total = sum(int(row["portal_useful_count"]) for row in query_results)
    duplicate_total = sum(int(row["duplicate_url_count"]) for row in query_results)
    total_urls = sum(int(row["result_count"]) for row in query_results)
    failure_count = sum(1 for row in query_results if row["hard_failure"])
    latencies = [int(row["latency_ms"]) for row in query_results if row["latency_ms"] >= 0]

    failure_modes: dict[str, int] = {}
    for row in query_results:
        mode = row.get("failure_mode")
        if not mode:
            continue
        failure_modes[mode] = failure_modes.get(mode, 0) + 1

    representative_samples = [
        {
            "query_id": row["query_id"],
            "query": row["query"],
            "top_results": row["top_results"][:3],
            "hard_failure": row["hard_failure"],
            "failure_mode": row["failure_mode"],
        }
        for row in query_results[:4]
    ]

    artifact_portal_denominator = artifact_total + portal_total
    return {
        "lane": lane,
        "query_count": total,
        "empty_result_rate": empty_count / total,
        "non_empty_result_rate": non_empty_count / total,
        "official_source_top5_rate": official_top5_count / total,
        "useful_url_yield": useful_url_total / total,
        "unique_useful_url_yield": unique_useful_total / total,
        "artifact_vs_portal_rate": (
            artifact_total / artifact_portal_denominator
            if artifact_portal_denominator > 0
            else 0.0
        ),
        "duplicate_url_rate": (
            duplicate_total / total_urls
            if total_urls > 0
            else 0.0
        ),
        "median_latency_ms": int(median(latencies)) if latencies else 0,
        "hard_failure_rate": failure_count / total,
        "failure_modes": failure_modes,
        "representative_samples": representative_samples,
    }


async def run_lane_benchmark(
    *,
    lane: str,
    matrix: list[dict[str, Any]],
    provider: BenchmarkSearchProvider,
    result_count: int = DEFAULT_RESULT_COUNT,
) -> LaneRunResult:
    """Run one benchmark lane against a deterministic matrix."""
    per_query_results: list[dict[str, Any]] = []
    for query_spec in matrix:
        started = time.perf_counter()
        error: str | None = None
        raw_results: Any = []
        try:
            raw_results = await provider.search(
                str(query_spec["query"]),
                query_id=str(query_spec["id"]),
                count=result_count,
            )
        except Exception as exc:
            error = str(exc)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        per_query_results.append(
            evaluate_query(
                lane=lane,
                query_spec=query_spec,
                raw_results=raw_results,
                latency_ms=elapsed_ms,
                error=error,
            )
        )

    return LaneRunResult(
        lane=lane,
        metrics=summarize_lane_metrics(lane, per_query_results),
        query_results=per_query_results,
    )


class BaselineSearchProvider:
    """Round 1 baseline adapter for current resilient web-search lane."""

    def __init__(self, api_key: str | None) -> None:
        from services.llm.web_search_factory import create_web_search_client

        # Avoid invalid blank Authorization headers when key is absent.
        self.client = create_web_search_client(api_key=api_key or "missing-zai-key")

    async def search(self, query: str, *, query_id: str, count: int) -> list[dict[str, Any]]:
        _ = query_id
        return normalize_results(await self.client.search(query=query, count=count))

    async def close(self) -> None:
        await self.client.close()


class SearxngSearchProvider:
    """Benchmark-scoped adapter for a live SearXNG endpoint."""

    def __init__(self, base_url: str, timeout_s: float = 20.0) -> None:
        import httpx

        normalized_base = base_url.strip().rstrip("/")
        self.base_url = normalized_base
        self.client = httpx.AsyncClient(timeout=max(1.0, timeout_s))

    async def search(self, query: str, *, query_id: str, count: int) -> list[dict[str, Any]]:
        _ = query_id
        endpoint = f"{self.base_url}/search"
        response = await self.client.get(
            endpoint,
            params={"q": query, "format": "json"},
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])
        normalized: list[dict[str, Any]] = []
        for item in results:
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            normalized.append(
                {
                    "url": url,
                    "link": url,
                    "title": str(item.get("title") or "").strip(),
                    "snippet": str(item.get("content") or "").strip(),
                }
            )
        return normalized[:count]

    async def close(self) -> None:
        await self.client.aclose()


class FixtureSearchProvider:
    """Fixture-backed provider for deterministic evaluation and tests."""

    def __init__(self, results_by_query_id: dict[str, list[dict[str, Any]]]) -> None:
        self.results_by_query_id = results_by_query_id

    async def search(self, query: str, *, query_id: str, count: int) -> list[dict[str, Any]]:
        _ = query
        return normalize_results(self.results_by_query_id.get(query_id, []))[:count]

    async def close(self) -> None:
        return
