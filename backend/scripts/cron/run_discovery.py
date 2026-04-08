#!/usr/bin/env python3
"""
Discovery Cron
Runs AutoDiscoveryService to find new sources (URLs) for jurisdictions.
Saves them to 'sources' table for the Universal Harvester.
"""

import sys
import os
import logging
import asyncio
import json
import argparse
import inspect
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from db.postgres_client import PostgresDB
from llm_common import WebSearchClient
from services.auto_discovery_service import AutoDiscoveryService as SearchDiscoveryService
from services.discovery.search_discovery import (
    SearchDiscoveryService as LegacySearchDiscoveryService,
)
from services.discovery.classifier_validation import (
    ClassifierAcceptanceGate,
    EvaluationMetrics,
    passes_acceptance_gate,
)
from services.discovery.service import AutoDiscoveryService as DiscoveryClassifierService

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("discovery")

CLASSIFIER_MIN_CONFIDENCE = 0.75
DEFAULT_QUERY_PROVIDER_BUDGET = 5
DEFAULT_CLASSIFIER_PROVIDER_BUDGET = 50
DEFAULT_QUERY_CACHE_TTL_HOURS = 72
VALIDATION_REPORT_PATH = (
    Path(__file__).resolve().parents[1]
    / "verification"
    / "artifacts"
    / "discovery_classifier_validation_report.json"
)


class ResilientWebSearchClient:
    """Use llm_common search first, then fail over to legacy structured discovery search."""

    def __init__(self, primary_client, fallback_service=None):
        self.primary_client = primary_client
        self.fallback_service = fallback_service

    async def search(self, query: str):
        try:
            primary_results = await self.primary_client.search(query)
            if primary_results:
                return primary_results
            logger.warning("Primary search returned no results; trying fallback for query '%s'", query)
        except Exception as exc:
            logger.warning("Primary search failed for query '%s': %s", query, exc)

        if not self.fallback_service:
            return []

        try:
            return await self.fallback_service.find_urls(query, count=10)
        except Exception as exc:
            logger.warning("Fallback search failed for query '%s': %s", query, exc)
            return []


_OBVIOUS_JUNK_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "tiktok.com",
    "reddit.com",
    "linkedin.com",
    "yelp.com",
    "zillow.com",
}


def _normalize_url_for_cache(url: str) -> str:
    """Normalize URL to maximize exact-cache hits without changing authority/path semantics."""
    parts = urlsplit((url or "").strip())
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    query_pairs = parse_qsl(parts.query, keep_blank_values=False)
    filtered_pairs = [
        (k, v)
        for k, v in query_pairs
        if not k.lower().startswith("utm_")
    ]
    normalized_query = urlencode(sorted(filtered_pairs))
    return urlunsplit((scheme, netloc, path, normalized_query, ""))


def _is_obvious_junk_candidate(url: str) -> bool:
    netloc = urlsplit((url or "").strip()).netloc.lower()
    host = netloc.split(":")[0]
    return any(host == domain or host.endswith(f".{domain}") for domain in _OBVIOUS_JUNK_DOMAINS)


def _normalize_jurisdiction_scope(values: list[str] | None) -> set[str] | None:
    """Normalize optional jurisdiction scope list into casefolded names."""
    if not values:
        return None
    normalized = {
        value.strip().casefold()
        for value in values
        if value and value.strip()
    }
    return normalized or None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run discovery cron with optional bounded scope.")
    parser.add_argument(
        "--jurisdiction",
        action="append",
        default=[],
        help="Jurisdiction name to include. Repeat for multiple jurisdictions.",
    )
    parser.add_argument(
        "--jurisdictions",
        default="",
        help="Comma-separated jurisdiction names to include.",
    )
    parser.add_argument(
        "--max-queries-per-jurisdiction",
        type=int,
        default=None,
        help="Optional cap for number of discovery queries per jurisdiction (for bounded validation runs).",
    )
    parser.add_argument(
        "--query-provider-budget",
        type=int,
        default=None,
        help="Max count of provider-backed query-generation calls allowed per invocation.",
    )
    parser.add_argument(
        "--classifier-provider-budget",
        type=int,
        default=None,
        help="Max count of provider-backed classifier calls allowed per invocation.",
    )
    return parser.parse_args()


def _load_classifier_validation_contract() -> tuple[bool, dict]:
    """Load and verify classifier acceptance contract report."""
    if not VALIDATION_REPORT_PATH.exists():
        return False, {
            "status": "failed",
            "reason": "validation_report_missing",
            "report_path": str(VALIDATION_REPORT_PATH),
        }

    try:
        payload = json.loads(VALIDATION_REPORT_PATH.read_text())
        recommendation = payload.get("recommendation", {})
        metrics_payload = recommendation.get("metrics")
        gate_payload = payload.get("gate_requirements", {})
        report_says_pass = bool(recommendation.get("passes_acceptance_gate", False))
        metrics = EvaluationMetrics.model_validate(metrics_payload)
        gate = ClassifierAcceptanceGate.model_validate(gate_payload)
        computed_pass = passes_acceptance_gate(metrics, gate)
    except Exception as exc:
        return False, {
            "status": "failed",
            "reason": "validation_report_invalid",
            "error": str(exc),
            "report_path": str(VALIDATION_REPORT_PATH),
        }

    if not (report_says_pass and computed_pass):
        return False, {
            "status": "failed",
            "reason": "acceptance_gate_failed",
            "report_path": str(VALIDATION_REPORT_PATH),
            "report_pass": report_says_pass,
            "computed_pass": computed_pass,
            "metrics": metrics.model_dump(),
            "gate_requirements": gate.model_dump(),
        }

    return True, {
        "status": "passed",
        "reason": "acceptance_gate_passed",
        "report_path": str(VALIDATION_REPORT_PATH),
        "min_confidence": CLASSIFIER_MIN_CONFIDENCE,
        "metrics": metrics.model_dump(),
        "gate_requirements": gate.model_dump(),
    }


async def main(
    jurisdiction_scope: set[str] | None = None,
    max_queries_per_jurisdiction: int | None = None,
    query_provider_budget: int | None = None,
    classifier_provider_budget: int | None = None,
):
    task_id = str(uuid4())
    logger.info(f"🚀 Starting Discovery (Task {task_id})")
    
    db = PostgresDB()
    primary_search_client = WebSearchClient(
        api_key=os.environ.get("ZAI_API_KEY", "mock-key"),
    )
    fallback_search_service = LegacySearchDiscoveryService(
        api_key=os.environ.get("ZAI_API_KEY"),
    )
    search_client = ResilientWebSearchClient(
        primary_client=primary_search_client,
        fallback_service=fallback_search_service,
    )
    discovery_service = SearchDiscoveryService(search_client=search_client, db_client=db)
    classifier_service = DiscoveryClassifierService()
    gate_enabled, gate_contract = _load_classifier_validation_contract()
    classifier_trusted = classifier_service.client is not None
    query_provider_budget_limit = (
        query_provider_budget
        if query_provider_budget is not None
        else int(os.environ.get("DISCOVERY_QUERY_PROVIDER_BUDGET", str(DEFAULT_QUERY_PROVIDER_BUDGET)))
    )
    classifier_provider_budget_limit = (
        classifier_provider_budget
        if classifier_provider_budget is not None
        else int(
            os.environ.get(
                "DISCOVERY_CLASSIFIER_PROVIDER_BUDGET",
                str(DEFAULT_CLASSIFIER_PROVIDER_BUDGET),
            )
        )
    )
    query_provider_calls_used = 0
    classifier_provider_calls_used = 0
    
    # 1. Log Start
    try:
        await db.create_admin_task(
            task_id=task_id,
            task_type='research',
            jurisdiction='all',
            status='running'
        )
    except Exception as e:
        logger.error(f"Failed to create admin task: {e}")
        
    try:
        # 2. Get Jurisdictions
        # For now, just active ones or all. Let's do all.
        jurisdictions_rows = await db._fetch("SELECT * FROM jurisdictions")
        all_jurisdictions = [dict(row) for row in jurisdictions_rows]
        if jurisdiction_scope:
            jurisdictions = [
                jur
                for jur in all_jurisdictions
                if str(jur.get("name", "")).casefold() in jurisdiction_scope
            ]
        else:
            jurisdictions = all_jurisdictions
        
        results = {
            "found": 0,
            "accepted": 0,
            "new": 0,
            "duplicates": 0,
            "rejected": 0,
            "query_cache_hits": 0,
            "classifier_cache_hits": 0,
            "classifier_cache_positive_reuse": 0,
            "rejected_by_reason": {
                "batch_gate_fail_closed": 0,
                "classifier_untrusted_fail_closed": 0,
                "classifier_error_fail_closed": 0,
                "not_scrapable": 0,
                "low_confidence": 0,
                "heuristic_obvious_junk": 0,
                "provider_budget_exhausted": 0,
            },
            "batch_gate": gate_contract,
            "classifier_trusted": classifier_trusted,
            "classifier_min_confidence": CLASSIFIER_MIN_CONFIDENCE,
            "jurisdiction_scope": sorted(jurisdiction_scope) if jurisdiction_scope else "all",
            "jurisdictions_processed": len(jurisdictions),
            "jurisdictions_available": len(all_jurisdictions),
            "max_queries_per_jurisdiction": max_queries_per_jurisdiction,
            "query_provider_budget_limit": query_provider_budget_limit,
            "query_provider_calls_used": 0,
            "classifier_provider_budget_limit": classifier_provider_budget_limit,
            "classifier_provider_calls_used": 0,
        }

        if not gate_enabled:
            logger.error("Discovery source creation fail-closed: validation gate not satisfied")
            logger.error("Gate details: %s", gate_contract)
        if not classifier_trusted:
            logger.error("Discovery source creation fail-closed: classifier client unavailable")

        for jur in jurisdictions:
            logger.info(f"🔎 Discovering for {jur['name']}...")
            jurisdiction_id = str(jur["id"])
            
            # Run Discovery
            allow_provider_query_generation = query_provider_calls_used < max(
                query_provider_budget_limit,
                0,
            )
            discover_kwargs = {
                "allow_provider_query_generation": allow_provider_query_generation,
                "query_cache_ttl_hours": int(
                    os.environ.get(
                        "DISCOVERY_QUERY_CACHE_TTL_HOURS",
                        str(DEFAULT_QUERY_CACHE_TTL_HOURS),
                    )
                ),
            }
            if max_queries_per_jurisdiction is not None:
                discover_kwargs["max_queries"] = max_queries_per_jurisdiction
            discovered_items = await discovery_service.discover_sources(
                jur['name'],
                jur.get('type', 'city'),
                **discover_kwargs,
            )
            discovery_stats = getattr(discovery_service, "last_discovery_stats", {}) or {}
            if discovery_stats.get("query_cache_hit"):
                results["query_cache_hits"] += 1
            if discovery_stats.get("query_provider_used"):
                query_provider_calls_used += 1
            
            for item in discovered_items:
                results["found"] += 1
                candidate_url = item.get("url")

                if not candidate_url:
                    results["rejected"] += 1
                    results["rejected_by_reason"]["classifier_error_fail_closed"] += 1
                    logger.info("   - Rejected (missing URL in discovery item)")
                    continue

                if _is_obvious_junk_candidate(candidate_url):
                    results["rejected"] += 1
                    results["rejected_by_reason"]["heuristic_obvious_junk"] += 1
                    logger.info("   - Rejected (heuristic obvious junk): %s", candidate_url)
                    continue

                if not gate_enabled:
                    results["rejected"] += 1
                    results["rejected_by_reason"]["batch_gate_fail_closed"] += 1
                    logger.info("   - Rejected (batch gate): %s", candidate_url)
                    continue

                if not classifier_trusted:
                    results["rejected"] += 1
                    results["rejected_by_reason"]["classifier_untrusted_fail_closed"] += 1
                    logger.info("   - Rejected (classifier unavailable): %s", candidate_url)
                    continue

                normalized_url = _normalize_url_for_cache(candidate_url)
                classification = None
                cached_payload = None
                cache_reader = getattr(db, "get_discovery_classifier_cache", None)
                if cache_reader and inspect.iscoroutinefunction(cache_reader):
                    cached_payload = await cache_reader(
                        normalized_url=normalized_url,
                        classifier_version=classifier_service.classifier_version,
                    )
                if cached_payload:
                    cached_decision = classifier_service.response_from_cache_payload(cached_payload)
                    if cached_decision:
                        classification = cached_decision
                        results["classifier_cache_hits"] += 1
                        if (
                            classification.is_scrapable
                            and classification.confidence >= CLASSIFIER_MIN_CONFIDENCE
                        ):
                            results["classifier_cache_positive_reuse"] += 1

                try:
                    if classification is None:
                        if classifier_provider_calls_used >= max(classifier_provider_budget_limit, 0):
                            results["rejected"] += 1
                            results["rejected_by_reason"]["provider_budget_exhausted"] += 1
                            logger.info(
                                "   - Rejected (classifier provider budget exhausted): %s",
                                candidate_url,
                            )
                            continue
                        classification = await classifier_service.discover_url(
                            url=candidate_url,
                            page_text=item.get("snippet", ""),
                        )
                        classifier_provider_calls_used += 1
                        cache_writer = getattr(db, "upsert_discovery_classifier_cache", None)
                        if cache_writer and inspect.iscoroutinefunction(cache_writer):
                            await cache_writer(
                                normalized_url=normalized_url,
                                classifier_version=classifier_service.classifier_version,
                                decision=classifier_service.response_to_cache_payload(classification),
                            )
                except Exception as exc:
                    logger.warning("Classifier failure for %s: %s", candidate_url, exc)
                    results["rejected"] += 1
                    results["rejected_by_reason"]["classifier_error_fail_closed"] += 1
                    continue

                if not classification.is_scrapable:
                    results["rejected"] += 1
                    results["rejected_by_reason"]["not_scrapable"] += 1
                    logger.info(
                        "   - Rejected (not scrapable): %s (confidence=%.2f)",
                        candidate_url,
                        classification.confidence,
                    )
                    continue

                if classification.confidence < CLASSIFIER_MIN_CONFIDENCE:
                    results["rejected"] += 1
                    results["rejected_by_reason"]["low_confidence"] += 1
                    logger.info(
                        "   - Rejected (confidence %.2f < %.2f): %s",
                        classification.confidence,
                        CLASSIFIER_MIN_CONFIDENCE,
                        candidate_url,
                    )
                    continue

                results["accepted"] += 1

                existing = await db._fetchrow(
                    "SELECT id FROM sources WHERE jurisdiction_id = $1 AND url = $2",
                    jurisdiction_id,
                    candidate_url,
                )

                if existing:
                    results["duplicates"] += 1
                    logger.info(f"   = Duplicate (skip): {item['title']}")
                    continue

                await db.create_source({
                    'jurisdiction_id': jurisdiction_id,
                    'name': item.get('title') or candidate_url,
                    'type': 'web',
                    'url': candidate_url,
                    'scrape_url': candidate_url,
                    'metadata': {
                        'category': item.get('category', ''),
                        'snippet': item.get('snippet', ''),
                        'discovery_query': item.get('discovery_query'),
                        'classifier': {
                            'is_scrapable': classification.is_scrapable,
                            'confidence': classification.confidence,
                            'source_type': classification.source_type,
                            'recommended_spider': classification.recommended_spider,
                            'reasoning': classification.reasoning,
                        },
                        'discovered_at': datetime.now().isoformat(),
                    }
                })
                results["new"] += 1
                logger.info(
                    "   + Added: %s (confidence=%.2f)",
                    item.get('title') or candidate_url,
                    classification.confidence,
                )
        
        # 3. Log Success
        results["query_provider_calls_used"] = query_provider_calls_used
        results["classifier_provider_calls_used"] = classifier_provider_calls_used
        logger.info(f"🏁 Discovery Complete. {results}")
        
        await db.update_admin_task(
            task_id=task_id,
            status='completed',
            result=results
        )

    except Exception as e:
        logger.error(f"❌ Critical Failure: {e}")
        try:
            await db.update_admin_task(
                task_id=task_id,
                status='failed',
                error=str(e)
            )
        except Exception:
             pass
        sys.exit(1)

if __name__ == "__main__":
    args = _parse_args()
    scope_values = list(args.jurisdiction)
    if args.jurisdictions:
        scope_values.extend(item for item in args.jurisdictions.split(","))
    scope = _normalize_jurisdiction_scope(scope_values)
    asyncio.run(
        main(
            jurisdiction_scope=scope,
            max_queries_per_jurisdiction=args.max_queries_per_jurisdiction,
            query_provider_budget=args.query_provider_budget,
            classifier_provider_budget=args.classifier_provider_budget,
        )
    )
