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
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from db.postgres_client import PostgresDB
from llm_common import WebSearchClient
from services.auto_discovery_service import AutoDiscoveryService as SearchDiscoveryService
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
VALIDATION_REPORT_PATH = (
    Path(__file__).resolve().parents[1]
    / "verification"
    / "artifacts"
    / "discovery_classifier_validation_report.json"
)


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


async def main():
    task_id = str(uuid4())
    logger.info(f"🚀 Starting Discovery (Task {task_id})")
    
    db = PostgresDB()
    search_client = WebSearchClient(
        api_key=os.environ.get("ZAI_API_KEY", "mock-key"),
    )
    discovery_service = SearchDiscoveryService(search_client=search_client, db_client=db)
    classifier_service = DiscoveryClassifierService()
    gate_enabled, gate_contract = _load_classifier_validation_contract()
    classifier_trusted = classifier_service.client is not None
    
    # 1. Log Start
    try:
        await db.create_admin_task(
            task_id=task_id,
            task_type='discovery',
            jurisdiction='all',
            status='running'
        )
    except Exception as e:
        logger.error(f"Failed to create admin task: {e}")
        
    try:
        # 2. Get Jurisdictions
        # For now, just active ones or all. Let's do all.
        jurisdictions_rows = await db._fetch("SELECT * FROM jurisdictions")
        jurisdictions = [dict(row) for row in jurisdictions_rows]
        
        results = {
            "found": 0,
            "accepted": 0,
            "new": 0,
            "duplicates": 0,
            "rejected": 0,
            "rejected_by_reason": {
                "batch_gate_fail_closed": 0,
                "classifier_untrusted_fail_closed": 0,
                "classifier_error_fail_closed": 0,
                "not_scrapable": 0,
                "low_confidence": 0,
            },
            "batch_gate": gate_contract,
            "classifier_trusted": classifier_trusted,
            "classifier_min_confidence": CLASSIFIER_MIN_CONFIDENCE,
        }

        if not gate_enabled:
            logger.error("Discovery source creation fail-closed: validation gate not satisfied")
            logger.error("Gate details: %s", gate_contract)
        if not classifier_trusted:
            logger.error("Discovery source creation fail-closed: classifier client unavailable")

        for jur in jurisdictions:
            logger.info(f"🔎 Discovering for {jur['name']}...")
            
            # Run Discovery
            discovered_items = await discovery_service.discover_sources(jur['name'], jur.get('type', 'city'))
            
            for item in discovered_items:
                results["found"] += 1
                candidate_url = item.get("url")

                if not candidate_url:
                    results["rejected"] += 1
                    results["rejected_by_reason"]["classifier_error_fail_closed"] += 1
                    logger.info("   - Rejected (missing URL in discovery item)")
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

                try:
                    classification = await classifier_service.discover_url(
                        url=candidate_url,
                        page_text=item.get("snippet", ""),
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
                    jur['id'],
                    candidate_url,
                )

                if existing:
                    results["duplicates"] += 1
                    logger.info(f"   = Duplicate (skip): {item['title']}")
                    continue

                await db.create_source({
                    'jurisdiction_id': str(jur['id']),
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
    asyncio.run(main())
