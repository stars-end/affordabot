#!/usr/bin/env python3
"""Search/source quality bakeoff harness for bd-9qjof.8."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FEATURE_KEY = "bd-9qjof.8"
DEFAULT_QUERY = "San Jose CA city council meeting minutes housing"
DEFAULT_SEARX_ENDPOINT = "https://searxng-railway-production-79aa.up.railway.app/search"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_TOP_K = 5
DEFAULT_PROVIDERS = ("searxng", "tavily", "exa")
DEFAULT_USER_AGENT = "affordabot-dev-bakeoff/1.0"

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT_JSON = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "search-source-quality-bakeoff"
    / "artifacts"
    / "search_source_quality_bakeoff_report.json"
)
DEFAULT_OUT_MD = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "search-source-quality-bakeoff"
    / "artifacts"
    / "search_source_quality_bakeoff_report.md"
)

EXA_SEARCH_URL = "https://api.exa.ai/search"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"

OFFICIAL_DOMAIN_SIGNS = (
    ".gov",
    ".ca.gov",
    ".us",
    "legistar.com",
    "granicus.com",
)
NON_PRIMARY_SOURCE_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "nextdoor.com",
    "tripadvisor.com",
    "wikipedia.org",
    "youtube.com",
    "yelp.com",
)
STRONG_SOURCE_TERMS = (
    "agenda",
    "minutes",
    "meeting",
    "city council",
    "planning commission",
    "staff report",
    "resolution",
    "ordinance",
    "legistar",
    "granicus",
    "pdf",
)
HOUSING_TERMS = (
    "housing",
    "zoning",
    "planning",
    "permit",
    "affordable",
    "development",
    "land use",
    "rent",
)
NAV_ONLY_NEGATIVE_TERMS = (
    "home",
    "residents",
    "businesses",
    "jobs",
    "menu",
    "accessibility",
    "contact us",
    "privacy policy",
    "site map",
)


@dataclass(frozen=True)
class QuerySpec:
    query: str
    id: str = "adhoc"
    jurisdiction: str = ""
    source_family: str = "adhoc"
    expected_signal_terms: tuple[str, ...] = ()
    preferred_domains: tuple[str, ...] = ()
    preferred_url_patterns: tuple[str, ...] = ()

    @property
    def is_negative_control(self) -> bool:
        return self.source_family.startswith("negative")


@dataclass(frozen=True)
class BakeoffConfig:
    providers: tuple[str, ...]
    queries: tuple[QuerySpec, ...]
    top_k: int
    timeout_seconds: int
    searx_endpoint: str
    out_json: Path
    out_md: Path


def _request_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=body, method=method.upper())
    for key, value in headers.items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        content = response.read()
    if not content:
        return {}
    return json.loads(content.decode("utf-8"))


def _canonicalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    path = parsed.path.rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _official_domain(url: str) -> bool:
    host = urllib.parse.urlsplit(url).netloc.lower()
    return any(sign in host for sign in OFFICIAL_DOMAIN_SIGNS)


def _preferred_domain(url: str, query: QuerySpec) -> bool:
    host = urllib.parse.urlsplit(url).netloc.lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in query.preferred_domains)


def _host_matches_jurisdiction(url: str, query: QuerySpec) -> bool:
    if not query.jurisdiction:
        return False
    host = urllib.parse.urlsplit(url).netloc.lower()
    host_key = "".join(char for char in host if char.isalnum())
    if "county" in query.jurisdiction.lower() and "county" not in host_key:
        return False
    words = [
        word
        for word in ("".join(char if char.isalnum() else " " for char in query.jurisdiction.lower())).split()
        if word not in {"ca", "california", "city", "county"} and len(word) >= 3
    ]
    if not words:
        return False
    if any(len(word) >= 5 and word in host_key for word in words):
        return True
    return len(words) >= 2 and "".join(words[:2]) in host_key


def _non_primary_source_domain(url: str) -> bool:
    host = urllib.parse.urlsplit(url).netloc.lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in NON_PRIMARY_SOURCE_DOMAINS)


def _preferred_url_pattern(url: str, query: QuerySpec) -> bool:
    lowered = url.lower()
    return any(pattern.lower() in lowered for pattern in query.preferred_url_patterns)


def _expected_signal_count(combined: str, query: QuerySpec) -> int:
    lowered = combined.lower()
    return sum(1 for term in query.expected_signal_terms if term.lower() in lowered)


def _reader_ready_signals(url: str, combined: str) -> int:
    count = 0
    if _contains_any(combined, STRONG_SOURCE_TERMS):
        count += 1
    if url.lower().endswith(".pdf") or "/pdf/" in url.lower() or ".ashx" in url.lower():
        count += 1
    if _contains_any(combined, ("legistar", "granicus", "meetingdetail", "agendaviewer")):
        count += 1
    return count


def _ensure_query_spec(query: QuerySpec | str) -> QuerySpec:
    return query if isinstance(query, QuerySpec) else QuerySpec(query=str(query))


def _score_result(
    *,
    query: QuerySpec | str,
    url: str,
    title: str,
    snippet: str,
    duplicate: bool,
) -> tuple[float, list[str]]:
    query = _ensure_query_spec(query)
    combined = f"{title} {snippet} {url}".strip().lower()
    score = 0
    signals: list[str] = []

    if _non_primary_source_domain(url):
        signals.append("non_primary_source_domain")
        return 0.0, signals

    has_preferred_domain = _preferred_domain(url, query)
    host_matches_jurisdiction = _host_matches_jurisdiction(url, query)
    has_official_domain = _official_domain(url)
    has_public_records_platform = _contains_any(combined, ("legistar", "granicus"))

    if has_preferred_domain:
        score += 30
        signals.append("preferred_domain")
    elif query.preferred_domains and not host_matches_jurisdiction:
        signals.append("jurisdiction_mismatch")
        return 0.0, signals
    elif has_official_domain:
        score += 15
        signals.append("official_domain")
    elif has_public_records_platform:
        score += 15
        signals.append("public_records_platform")
    elif not query.is_negative_control and query.preferred_domains:
        signals.append("non_official_source")
        return 0.0, signals

    if _preferred_url_pattern(url, query):
        score += 15
        signals.append("preferred_url_pattern")

    expected_count = _expected_signal_count(combined, query)
    if expected_count >= 3:
        score += 15
        signals.append("expected_signal_terms_3plus")
    elif expected_count == 2:
        score += 10
        signals.append("expected_signal_terms_2")
    elif expected_count == 1:
        score += 5
        signals.append("expected_signal_terms_1")

    if _contains_any(combined, STRONG_SOURCE_TERMS):
        score += 15
        signals.append("meeting_source_terms")

    if _contains_any(combined, HOUSING_TERMS) and _contains_any(query.query.lower(), HOUSING_TERMS):
        score += 10
        signals.append("housing_planning_terms")

    if url.lower().endswith(".pdf") or "/pdf/" in url.lower() or ".ashx" in url.lower():
        score += 10
        signals.append("pdf_signal")

    if has_public_records_platform:
        score += 10
        signals.append("public_records_platform")

    if _contains_any(combined, NAV_ONLY_NEGATIVE_TERMS):
        score -= 30
        signals.append("nav_only_negative")
    if duplicate:
        score -= 10
        signals.append("duplicate")

    if query.is_negative_control:
        score = min(score, 40)
        signals.append("negative_control_cap")

    return round(float(max(0, min(100, score))), 2), signals


def _normalize_records(
    *,
    provider: str,
    query: QuerySpec | str,
    raw_results: list[dict[str, Any]],
    top_k: int,
    source_label: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in raw_results[:top_k]:
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        title = str(item.get("title") or "").strip()
        snippet = str(item.get("snippet") or item.get("content") or "").strip()
        canonical = _canonicalize_url(url)
        duplicate = canonical in seen_urls
        seen_urls.add(canonical)
        score, signals = _score_result(
            query=query,
            url=url,
            title=title,
            snippet=snippet,
            duplicate=duplicate,
        )
        normalized.append(
            {
                "url": url,
                "canonical_url": canonical,
                "title": title,
                "snippet": snippet,
                "source": source_label,
                "score": score,
                "signals": signals,
                "duplicate": duplicate,
            }
        )
    return normalized


def _probe_searxng(
    *,
    query: QuerySpec | str,
    endpoint: str,
    top_k: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    query = _ensure_query_spec(query)
    started = time.monotonic()
    params = urllib.parse.urlencode({"q": query.query, "format": "json"})
    url = f"{endpoint}?{params}"
    try:
        payload = _request_json(
            method="GET",
            url=url,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            payload=None,
            timeout_seconds=timeout_seconds,
        )
        raw_results = payload.get("results", [])
        top_results = _normalize_records(
            provider="searxng",
            query=query,
            raw_results=[_searx_item(item) for item in raw_results if isinstance(item, dict)],
            top_k=top_k,
            source_label="searxng",
        )
        elapsed = int((time.monotonic() - started) * 1000)
        return _provider_probe(
            provider="searxng",
            query=query.query,
            status="succeeded",
            latency_ms=elapsed,
            result_count=len(raw_results),
            top_results=top_results,
            endpoint=endpoint,
        )
    except urllib.error.HTTPError as exc:
        return _provider_error(
            provider="searxng",
            query=query.query,
            endpoint=endpoint,
            exc=exc,
            started=started,
        )
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        return _provider_probe(
            provider="searxng",
            query=query.query,
            status="failed",
            latency_ms=elapsed,
            result_count=0,
            top_results=[],
            endpoint=endpoint,
            failure_classification=type(exc).__name__.lower(),
            error=str(exc),
        )


def _probe_tavily(
    *,
    query: QuerySpec | str,
    api_key: str | None,
    top_k: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    query = _ensure_query_spec(query)
    if not api_key:
        return _provider_probe(
            provider="tavily",
            query=query.query,
            status="not_configured",
            latency_ms=0,
            result_count=0,
            top_results=[],
            failure_classification="missing_api_key",
        )
    started = time.monotonic()
    payload = {
        "query": query.query,
        "search_depth": "basic",
        "include_raw_content": False,
        "max_results": top_k,
    }
    try:
        body = _request_json(
            method="POST",
            url=TAVILY_SEARCH_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": DEFAULT_USER_AGENT,
            },
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        raw_results = body.get("results", [])
        top_results = _normalize_records(
            provider="tavily",
            query=query,
            raw_results=[_tavily_item(item) for item in raw_results if isinstance(item, dict)],
            top_k=top_k,
            source_label="tavily",
        )
        elapsed = int((time.monotonic() - started) * 1000)
        return _provider_probe(
            provider="tavily",
            query=query.query,
            status="succeeded",
            latency_ms=elapsed,
            result_count=len(raw_results),
            top_results=top_results,
            endpoint=TAVILY_SEARCH_URL,
        )
    except urllib.error.HTTPError as exc:
        return _provider_error(
            provider="tavily",
            query=query.query,
            endpoint=TAVILY_SEARCH_URL,
            exc=exc,
            started=started,
        )
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        return _provider_probe(
            provider="tavily",
            query=query.query,
            status="failed",
            latency_ms=elapsed,
            result_count=0,
            top_results=[],
            endpoint=TAVILY_SEARCH_URL,
            failure_classification=type(exc).__name__.lower(),
            error=str(exc),
        )


def _probe_exa(
    *,
    query: QuerySpec | str,
    api_key: str | None,
    top_k: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    query = _ensure_query_spec(query)
    if not api_key:
        return _provider_probe(
            provider="exa",
            query=query.query,
            status="not_configured",
            latency_ms=0,
            result_count=0,
            top_results=[],
            failure_classification="missing_api_key",
        )
    started = time.monotonic()
    payload = {
        "query": query.query,
        "numResults": top_k,
        "type": "auto",
        "contents": {
            "highlights": {
                "maxCharacters": 400,
            }
        },
    }
    try:
        body = _request_json(
            method="POST",
            url=EXA_SEARCH_URL,
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "User-Agent": DEFAULT_USER_AGENT,
            },
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        raw_results = body.get("results", [])
        top_results = _normalize_records(
            provider="exa",
            query=query,
            raw_results=[_exa_item(item) for item in raw_results if isinstance(item, dict)],
            top_k=top_k,
            source_label="exa",
        )
        elapsed = int((time.monotonic() - started) * 1000)
        return _provider_probe(
            provider="exa",
            query=query.query,
            status="succeeded",
            latency_ms=elapsed,
            result_count=len(raw_results),
            top_results=top_results,
            endpoint=EXA_SEARCH_URL,
        )
    except urllib.error.HTTPError as exc:
        return _provider_error(
            provider="exa",
            query=query.query,
            endpoint=EXA_SEARCH_URL,
            exc=exc,
            started=started,
        )
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        return _provider_probe(
            provider="exa",
            query=query.query,
            status="failed",
            latency_ms=elapsed,
            result_count=0,
            top_results=[],
            endpoint=EXA_SEARCH_URL,
            failure_classification=type(exc).__name__.lower(),
            error=str(exc),
        )


def _provider_error(
    *,
    provider: str,
    query: str,
    endpoint: str,
    exc: urllib.error.HTTPError,
    started: float,
) -> dict[str, Any]:
    elapsed = int((time.monotonic() - started) * 1000)
    failure = f"http_{exc.code}"
    return _provider_probe(
        provider=provider,
        query=query,
        status="failed",
        latency_ms=elapsed,
        result_count=0,
        top_results=[],
        endpoint=endpoint,
        failure_classification=failure,
        error=str(exc),
    )


def _provider_probe(
    *,
    provider: str,
    query: str,
    status: str,
    latency_ms: int,
    result_count: int,
    top_results: list[dict[str, Any]],
    endpoint: str | None = None,
    failure_classification: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    top_score = max((item["score"] for item in top_results), default=0.0)
    avg_score = round(statistics.fmean([item["score"] for item in top_results]), 2) if top_results else 0.0
    return {
        "provider": provider,
        "query": query,
        "status": status,
        "endpoint": endpoint,
        "latency_ms": latency_ms,
        "result_count": result_count,
        "top_results": top_results,
        "top_score": top_score,
        "average_score": avg_score,
        "failure_classification": failure_classification,
        "error": error,
    }


def _searx_item(item: dict[str, Any]) -> dict[str, str]:
    return {
        "url": str(item.get("url") or ""),
        "title": str(item.get("title") or ""),
        "snippet": str(item.get("content") or ""),
    }


def _tavily_item(item: dict[str, Any]) -> dict[str, str]:
    return {
        "url": str(item.get("url") or ""),
        "title": str(item.get("title") or ""),
        "snippet": str(item.get("content") or ""),
    }


def _exa_item(item: dict[str, Any]) -> dict[str, str]:
    highlights = item.get("highlights") or []
    snippet = ""
    if isinstance(highlights, list) and highlights:
        snippet = str(highlights[0])
    return {
        "url": str(item.get("url") or ""),
        "title": str(item.get("title") or ""),
        "snippet": snippet,
    }


def _best_result(probe: dict[str, Any]) -> dict[str, Any] | None:
    top_results = probe.get("top_results") or []
    if not top_results:
        return None
    return sorted(top_results, key=lambda item: item["score"], reverse=True)[0]


def _percent(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 1) if denominator else 0.0


def _p90(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.9)))
    return int(ordered[index])


def _summarize_by_provider(probes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provider_map: dict[str, list[dict[str, Any]]] = {}
    for probe in probes:
        provider_map.setdefault(probe["provider"], []).append(probe)

    summaries: list[dict[str, Any]] = []
    for provider, records in sorted(provider_map.items()):
        successes = [rec for rec in records if rec["status"] == "succeeded"]
        quality_successes = [rec for rec in successes if rec["top_score"] >= 60]
        success_rate = _percent(len(successes), len(records))
        query_success_rate = _percent(len(quality_successes), len(records))
        median_latency = int(statistics.median([rec["latency_ms"] for rec in successes])) if successes else 0
        p90_latency = _p90([rec["latency_ms"] for rec in successes])
        mean_top_score = round(statistics.fmean([rec["top_score"] for rec in successes]), 2) if successes else 0.0
        mean_avg_score = (
            round(statistics.fmean([rec["average_score"] for rec in successes]), 2) if successes else 0.0
        )
        median_query_score = (
            round(float(statistics.median([rec["top_score"] for rec in successes])), 2) if successes else 0.0
        )
        reader_ready_count = 0
        official_hit_count = 0
        for rec in successes:
            best_result = _best_result(rec)
            if best_result is None:
                continue
            signals = set(best_result["signals"])
            reader_signals = signals & {"meeting_source_terms", "pdf_signal", "public_records_platform"}
            if len(reader_signals) >= 2:
                reader_ready_count += 1
            top3_signals = {signal for item in rec["top_results"][:3] for signal in item["signals"]}
            if top3_signals & {"preferred_domain", "official_domain", "public_records_platform"}:
                official_hit_count += 1
        reader_ready_rate = _percent(reader_ready_count, len(records))
        official_domain_hit_rate = _percent(official_hit_count, len(records))
        error_count = len([rec for rec in records if rec["status"] == "failed"])
        rate_limit_count = len([rec for rec in records if rec.get("failure_classification") == "http_429"])
        error_rate = round(error_count / len(records), 3) if records else 0.0
        rate_limit_rate = round(rate_limit_count / len(records), 3) if records else 0.0
        reliability_score = round(max(0.0, 100 - (error_rate * 100) - (rate_limit_rate * 150)), 2)
        provider_score = round(
            (0.55 * median_query_score)
            + (0.15 * query_success_rate)
            + (0.10 * reader_ready_rate)
            + (0.10 * official_domain_hit_rate)
            + (0.10 * reliability_score),
            2,
        )
        eligible_for_mvp = (
            provider_score >= 75
            and query_success_rate >= 70
            and reader_ready_rate >= 65
            and official_domain_hit_rate >= 70
            and error_rate <= 0.05
            and rate_limit_rate <= 0.03
        )
        failures = sorted({rec["failure_classification"] for rec in records if rec.get("failure_classification")})
        summaries.append(
            {
                "provider": provider,
                "queries_tested": len(records),
                "success_rate_percent": success_rate,
                "query_success_rate_percent": query_success_rate,
                "median_latency_ms": median_latency,
                "p90_latency_ms": p90_latency,
                "mean_top_score": mean_top_score,
                "mean_average_score": mean_avg_score,
                "median_query_score": median_query_score,
                "reader_ready_rate_percent": reader_ready_rate,
                "official_domain_hit_rate_percent": official_domain_hit_rate,
                "error_rate": error_rate,
                "rate_limit_rate": rate_limit_rate,
                "reliability_score": reliability_score,
                "provider_score": provider_score,
                "eligible_for_mvp": eligible_for_mvp,
                "failures": failures,
            }
        )
    return summaries


def _recommend_provider(provider_summary: list[dict[str, Any]]) -> dict[str, Any]:
    if not provider_summary:
        return {"provider": None, "reason": "no_providers"}

    ranked = sorted(
        provider_summary,
        key=lambda item: (
            item["eligible_for_mvp"],
            item["provider_score"],
            item["median_query_score"],
            -item["p90_latency_ms"],
        ),
        reverse=True,
    )
    best = ranked[0]
    mvp_ready = bool(best["eligible_for_mvp"])
    return {
        "provider": best["provider"],
        "reason": "mvp_eligible_highest_weighted_score"
        if mvp_ready
        else "no_provider_meets_mvp_threshold_best_candidate_only",
        "mvp_ready": mvp_ready,
        "action": "select_provider_for_mvp"
        if mvp_ready
        else "do_not_lock_provider_run_full_reader_gate_or_tune_corpus",
        "score_components": {
            "provider_score": best["provider_score"],
            "query_success_rate_percent": best["query_success_rate_percent"],
            "median_query_score": best["median_query_score"],
            "reader_ready_rate_percent": best["reader_ready_rate_percent"],
            "official_domain_hit_rate_percent": best["official_domain_hit_rate_percent"],
            "p90_latency_ms": best["p90_latency_ms"],
            "median_latency_ms": best["median_latency_ms"],
        },
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Search Source Quality Bakeoff")
    lines.append("")
    lines.append(f"- Generated at: `{report['generated_at']}`")
    lines.append(f"- Feature key: `{report['feature_key']}`")
    lines.append(f"- Providers: `{', '.join(report['providers'])}`")
    lines.append(f"- Top-k: `{report['top_k']}`")
    lines.append(f"- Timeout seconds: `{report['timeout_seconds']}`")
    lines.append("")
    lines.append("## Provider Summary")
    lines.append("")
    lines.append(
        "| Provider | Provider score | MVP eligible | Query success % | Reader-ready % | Official hit % | "
        "Median score | P90 latency (ms) | Failures |"
    )
    lines.append("|---|---:|---|---:|---:|---:|---:|---:|---|")
    for row in report["provider_summary"]:
        lines.append(
            "| "
            f"{row['provider']} | {row['provider_score']:.2f} | {row['eligible_for_mvp']} | "
            f"{row['query_success_rate_percent']:.1f} | {row['reader_ready_rate_percent']:.1f} | "
            f"{row['official_domain_hit_rate_percent']:.1f} | {row['median_query_score']:.2f} | "
            f"{row['p90_latency_ms']} | "
            f"{', '.join(row['failures']) if row['failures'] else '-'} |"
        )
    lines.append("")
    recommendation = report["recommendation"]
    lines.append("## Recommendation")
    lines.append("")
    lines.append(f"- Best candidate: `{recommendation.get('provider')}`")
    lines.append(f"- MVP ready: `{recommendation.get('mvp_ready')}`")
    lines.append(f"- Reason: `{recommendation.get('reason')}`")
    lines.append(f"- Action: `{recommendation.get('action')}`")
    lines.append("")
    lines.append("## Query Winners")
    lines.append("")
    lines.append("| Query | Winner | Top score | URL |")
    lines.append("|---|---|---:|---|")
    for query_summary in report["query_summary"]:
        lines.append(
            f"| {query_summary['query']} | {query_summary['winner_provider']} | "
            f"{query_summary['winner_top_score']:.2f} | {query_summary['winner_url'] or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _summarize_queries(probes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    query_map: dict[str, list[dict[str, Any]]] = {}
    for probe in probes:
        query_map.setdefault(probe["query"], []).append(probe)

    summaries: list[dict[str, Any]] = []
    for query, records in query_map.items():
        succeeded = [item for item in records if item["status"] == "succeeded"]
        if not succeeded:
            summaries.append(
                {
                    "query": query,
                    "winner_provider": "none",
                    "winner_top_score": 0.0,
                    "winner_url": None,
                }
            )
            continue
        best = sorted(
            succeeded,
            key=lambda item: (item["top_score"], item["average_score"], -item["latency_ms"]),
            reverse=True,
        )[0]
        best_result = _best_result(best)
        winner_url = best_result["url"] if best_result else None
        summaries.append(
            {
                "query": query,
                "winner_provider": best["provider"],
                "winner_top_score": best["top_score"],
                "winner_url": winner_url,
            }
        )
    return summaries


def _run_bakeoff(config: BakeoffConfig) -> dict[str, Any]:
    exa_key = _env("EXA_API_KEY")
    tavily_key = _env("TAVILY_API_KEY")
    probes: list[dict[str, Any]] = []

    for query_item in config.queries:
        query = query_item if isinstance(query_item, QuerySpec) else QuerySpec(query=str(query_item))
        for provider in config.providers:
            if provider == "searxng":
                probes.append(
                    _probe_searxng(
                        query=query,
                        endpoint=config.searx_endpoint,
                        top_k=config.top_k,
                        timeout_seconds=config.timeout_seconds,
                    )
                )
                continue
            if provider == "tavily":
                probes.append(
                    _probe_tavily(
                        query=query,
                        api_key=tavily_key,
                        top_k=config.top_k,
                        timeout_seconds=config.timeout_seconds,
                    )
                )
                continue
            if provider == "exa":
                probes.append(
                    _probe_exa(
                        query=query,
                        api_key=exa_key,
                        top_k=config.top_k,
                        timeout_seconds=config.timeout_seconds,
                    )
                )
                continue
            probes.append(
                _provider_probe(
                    provider=provider,
                    query=query.query,
                    status="not_supported",
                    latency_ms=0,
                    result_count=0,
                    top_results=[],
                    failure_classification="unsupported_provider",
                )
            )

    summary = _summarize_by_provider(probes)
    query_summary = _summarize_queries(probes)
    recommendation = _recommend_provider(summary)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "feature_key": FEATURE_KEY,
        "providers": list(config.providers),
        "queries": [
            asdict(query) if isinstance(query, QuerySpec) else asdict(QuerySpec(query=str(query)))
            for query in config.queries
        ],
        "top_k": config.top_k,
        "timeout_seconds": config.timeout_seconds,
        "searx_endpoint": config.searx_endpoint,
        "probes": probes,
        "provider_summary": summary,
        "query_summary": query_summary,
        "recommendation": recommendation,
    }


def _env(name: str) -> str | None:
    import os

    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _parse_queries(args: argparse.Namespace) -> tuple[QuerySpec, ...]:
    values: list[QuerySpec] = []
    for query in args.query:
        query = query.strip()
        if query:
            values.append(QuerySpec(query=query))
    if args.query_file:
        content = args.query_file.read_text(encoding="utf-8")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("queries"), list):
            for item in payload["queries"]:
                if isinstance(item, dict):
                    query = str(item.get("query") or "").strip()
                    if query:
                        values.append(
                            QuerySpec(
                                query=query,
                                id=str(item.get("id") or "adhoc").strip() or "adhoc",
                                jurisdiction=str(item.get("jurisdiction") or "").strip(),
                                source_family=str(item.get("source_family") or "adhoc").strip() or "adhoc",
                                expected_signal_terms=tuple(
                                    str(term).strip()
                                    for term in item.get("expected_signal_terms", [])
                                    if str(term).strip()
                                ),
                                preferred_domains=tuple(
                                    str(domain).strip().lower()
                                    for domain in item.get("preferred_domains", [])
                                    if str(domain).strip()
                                ),
                                preferred_url_patterns=tuple(
                                    str(pattern).strip()
                                    for pattern in item.get("preferred_url_patterns", [])
                                    if str(pattern).strip()
                                ),
                            )
                        )
                elif isinstance(item, str) and item.strip():
                    values.append(QuerySpec(query=item.strip()))
        else:
            for line in content.splitlines():
                line = line.strip()
                if line:
                    values.append(QuerySpec(query=line))
    if not values:
        values.append(QuerySpec(query=DEFAULT_QUERY))

    deduped: dict[str, QuerySpec] = {}
    for value in values:
        deduped.setdefault(value.query, value)
    return tuple(deduped.values())


def _parse_providers(args: argparse.Namespace) -> tuple[str, ...]:
    cleaned = tuple(dict.fromkeys(item.strip().lower() for item in args.provider if item.strip()))
    return cleaned or DEFAULT_PROVIDERS


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search/source quality bakeoff harness.")
    parser.add_argument("--provider", action="append", default=[])
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--query-file", type=Path, default=None)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--searx-endpoint", default=DEFAULT_SEARX_ENDPOINT)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = BakeoffConfig(
        providers=_parse_providers(args),
        queries=_parse_queries(args),
        top_k=max(1, args.top_k),
        timeout_seconds=max(1, args.timeout_seconds),
        searx_endpoint=args.searx_endpoint.strip(),
        out_json=args.out_json,
        out_md=args.out_md,
    )
    report = _run_bakeoff(config)
    config.out_json.parent.mkdir(parents=True, exist_ok=True)
    config.out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown = _render_markdown(report)
    config.out_md.parent.mkdir(parents=True, exist_ok=True)
    config.out_md.write_text(markdown, encoding="utf-8")
    print(f"Wrote JSON report: {config.out_json}")
    print(f"Wrote Markdown report: {config.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
