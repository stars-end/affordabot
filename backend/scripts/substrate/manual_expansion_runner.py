#!/usr/bin/env python3
"""Bounded execution path for manual substrate expansion runs."""

from __future__ import annotations

import json
import os
from argparse import Namespace
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from db.postgres_client import PostgresDB
from scripts.cron.run_daily_scrape import EMBEDDING_DIMENSIONS
from scripts.cron.run_daily_scrape import ScrapeJob
from scripts.substrate.manual_capture import capture_document
from scripts.substrate.manual_capture import parse_metadata_blob
from scripts.substrate.substrate_inspection_report import (
    generate_substrate_inspection_report,
    write_report_artifact,
)
from services.scraper.registry import SCRAPERS
from services.substrate_promotion import classify_trust
from services.vector_backend_factory import create_vector_backend


ASSET_CLASS_TO_DOCUMENT_TYPES = {
    "meeting_details": {"meeting_detail"},
    "agendas": {"agenda"},
    "minutes": {"minutes"},
    "agenda_packets": {"agenda_packet"},
    "attachments": {"attachment"},
    "staff_reports": {"staff_report"},
    "municipal_code": {"municipal_code"},
}


@dataclass(frozen=True)
class SourceTarget:
    jurisdiction_slug: str
    jurisdiction_name: str
    jurisdiction_type: str
    asset_class: str
    source_id: str
    source_name: str
    source_type: str
    document_type: str
    url: str
    title: str
    trust_tier: str


def _slugify(value: str) -> str:
    return (value or "").strip().lower().replace("_", "-").replace(" ", "-")


def _manual_run_id() -> str:
    return f"manual-substrate-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"


async def _build_ingestion_service(db: PostgresDB) -> Any:
    from llm_common.embeddings.openai import OpenAIEmbeddingService
    from services.ingestion_service import IngestionService
    from services.storage.s3_storage import S3Storage

    if os.environ.get("OPENROUTER_API_KEY"):
        embedding_service = OpenAIEmbeddingService(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            model="qwen/qwen3-embedding-8b",
            dimensions=EMBEDDING_DIMENSIONS,
        )
    else:

        class MockEmbeddingService:
            async def embed_query(self, text: str) -> list[float]:
                return [0.1] * EMBEDDING_DIMENSIONS

            async def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * EMBEDDING_DIMENSIONS for _ in texts]

        embedding_service = MockEmbeddingService()

    async def embed_fn(text: str) -> list[float]:
        return await embedding_service.embed_query(text)

    vector_backend = create_vector_backend(
        postgres_client=db,
        embedding_fn=embed_fn,
    )
    return IngestionService(
        postgres_client=db,
        vector_backend=vector_backend,
        embedding_service=embedding_service,
        storage_backend=S3Storage(),
    )


async def _fetch_source_rows(db: PostgresDB) -> list[dict[str, Any]]:
    rows = await db._fetch(
        """
        SELECT
          s.id,
          s.name,
          s.type,
          s.url,
          s.metadata,
          j.name AS jurisdiction_name,
          j.type AS jurisdiction_type
        FROM sources s
        JOIN jurisdictions j ON j.id::text = s.jurisdiction_id
        ORDER BY j.name, s.type, s.name
        """
    )
    return [dict(row) for row in rows]


def _resolve_source_targets(
    *,
    source_rows: list[dict[str, Any]],
    jurisdictions: list[str],
    asset_classes: list[str],
    max_documents_per_source: int,
) -> tuple[list[SourceTarget], list[dict[str, Any]]]:
    requested_slugs = {_slugify(item) for item in jurisdictions}
    targets: list[SourceTarget] = []
    failures: list[dict[str, Any]] = []

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in source_rows:
        grouped.setdefault((_slugify(row["jurisdiction_name"]), row["type"]), []).append(row)

    for jurisdiction in jurisdictions:
        jurisdiction_slug = _slugify(jurisdiction)
        for asset_class in asset_classes:
            if asset_class == "legislation":
                continue

            document_types = ASSET_CLASS_TO_DOCUMENT_TYPES.get(asset_class)
            if not document_types:
                failures.append(
                    {
                        "jurisdiction": jurisdiction_slug,
                        "asset_class": asset_class,
                        "reason": "unsupported_asset_class",
                    }
                )
                continue

            matching_rows: list[dict[str, Any]] = []
            for row in source_rows:
                row_slug = _slugify(row["jurisdiction_name"])
                if row_slug != jurisdiction_slug:
                    continue
                metadata = parse_metadata_blob(row.get("metadata"))
                document_type = (metadata.get("document_type") or "").strip().lower()
                url = (row.get("url") or "").strip()
                if not url or url.startswith("unknown://"):
                    continue
                if document_type not in document_types:
                    continue
                matching_rows.append(row)

            if not matching_rows:
                failures.append(
                    {
                        "jurisdiction": jurisdiction_slug,
                        "asset_class": asset_class,
                        "reason": "no_matching_sources",
                    }
                )
                continue

            for row in matching_rows[:max_documents_per_source]:
                metadata = parse_metadata_blob(row.get("metadata"))
                url = (row.get("url") or "").strip()
                trust_tier, _ = classify_trust(
                    canonical_url=url,
                    trust_tier=metadata.get("trust_tier"),
                )
                targets.append(
                    SourceTarget(
                        jurisdiction_slug=jurisdiction_slug,
                        jurisdiction_name=row["jurisdiction_name"],
                        jurisdiction_type=row["jurisdiction_type"],
                        asset_class=asset_class,
                        source_id=str(row["id"]),
                        source_name=row["name"],
                        source_type=row["type"],
                        document_type=metadata.get("document_type") or next(iter(document_types)),
                        url=url,
                        title=metadata.get("title") or row["name"] or url,
                        trust_tier=trust_tier,
                    )
                )

    return targets, failures


async def _stamp_manual_run_metadata(
    *,
    db: PostgresDB,
    scrape_id: str,
    run_id: str,
    run_label: str,
    asset_class: str,
    jurisdiction_slug: str,
) -> None:
    row = await db._fetchrow("SELECT metadata FROM raw_scrapes WHERE id = $1", scrape_id)
    metadata = parse_metadata_blob(row["metadata"] if row else {})
    metadata.update(
        {
            "manual_run_id": run_id,
            "manual_run_label": run_label,
            "manual_asset_class": asset_class,
            "manual_jurisdiction_slug": jurisdiction_slug,
            "manual_trigger_source": "windmill_manual_substrate_expansion",
        }
    )
    await db._execute(
        "UPDATE raw_scrapes SET metadata = $1 WHERE id = $2",
        json.dumps(metadata),
        scrape_id,
    )


async def _execute_source_target(
    *,
    db: PostgresDB,
    target: SourceTarget,
    run_id: str,
    run_label: str,
    ingest: bool,
) -> dict[str, Any]:
    args = Namespace(
        url=target.url,
        jurisdiction_name=target.jurisdiction_name,
        jurisdiction_type=target.jurisdiction_type,
        source_name=target.source_name,
        source_type=target.source_type,
        document_type=target.document_type,
        trust_tier=target.trust_tier,
        capture_method="manual_substrate_expansion",
        title=target.title,
        ingest=ingest,
    )
    result = await capture_document(args)
    scrape_id = result.get("scrape_id")
    if scrape_id:
        await _stamp_manual_run_metadata(
            db=db,
            scrape_id=scrape_id,
            run_id=run_id,
            run_label=run_label,
            asset_class=target.asset_class,
            jurisdiction_slug=target.jurisdiction_slug,
        )
    return result


async def _execute_legislation_capture(
    *,
    db: PostgresDB,
    job: ScrapeJob,
    slug: str,
    run_id: str,
    run_label: str,
    max_documents_per_source: int,
    ingest: bool,
    ingestion_service: Any | None,
) -> tuple[int, list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    scraper_entry = SCRAPERS.get(slug)
    if not scraper_entry:
        return 0, [
            {
                "jurisdiction": slug,
                "asset_class": "legislation",
                "reason": "unsupported_jurisdiction",
            }
        ]

    scraper_class, jurisdiction_type = scraper_entry
    scraper = scraper_class()
    bills = await scraper.scrape()
    selected_bills = bills[:max_documents_per_source]

    jurisdiction_id = await db.get_or_create_jurisdiction(
        scraper.jurisdiction_name,
        jurisdiction_type,
    )
    if not jurisdiction_id:
        return 0, [
            {
                "jurisdiction": slug,
                "asset_class": "legislation",
                "reason": "jurisdiction_resolution_failed",
            }
        ]

    if slug == "california":
        source_name = "California Legislature (OpenStates + leginfo)"
        source_url = "https://leginfo.legislature.ca.gov"
    else:
        source_name = f"{slug} API"
        source_url = f"https://webapi.legistar.com/v1/{slug}/matters"

    source_id = await db.get_or_create_source(
        jurisdiction_id,
        source_name,
        "legislation_api",
        url=source_url,
    )
    if not source_id:
        return 0, [
            {
                "jurisdiction": slug,
                "asset_class": "legislation",
                "reason": "source_resolution_failed",
            }
        ]

    created = 0
    for bill in selected_bills:
        if slug == "california":
            if not bill.text or len(bill.text) < 100:
                failures.append(
                    {
                        "jurisdiction": slug,
                        "asset_class": "legislation",
                        "bill_number": bill.bill_number,
                        "reason": "insufficient_bill_text",
                    }
                )
                continue
            scrape_record = job._build_california_scrape_record(bill, source_id, scraper)
        else:
            scrape_record = job._build_generic_scrape_record(
                bill,
                source_id,
                slug,
                source_url,
            )

        metadata = dict(scrape_record.get("metadata") or {})
        metadata.update(
            {
                "manual_run_id": run_id,
                "manual_run_label": run_label,
                "manual_asset_class": "legislation",
                "manual_jurisdiction_slug": slug,
                "manual_trigger_source": "windmill_manual_substrate_expansion",
            }
        )
        scrape_record["metadata"] = metadata

        scrape_id = await db.create_raw_scrape(scrape_record)
        if not scrape_id:
            failures.append(
                {
                    "jurisdiction": slug,
                    "asset_class": "legislation",
                    "bill_number": bill.bill_number,
                    "reason": "raw_scrape_insert_failed",
                }
            )
            continue

        created += 1
        if ingest and ingestion_service is not None:
            try:
                await ingestion_service.process_raw_scrape(scrape_id)
            except Exception as exc:  # pragma: no cover - runtime safety path
                failures.append(
                    {
                        "jurisdiction": slug,
                        "asset_class": "legislation",
                        "bill_number": bill.bill_number,
                        "reason": "ingestion_failed",
                        "detail": str(exc),
                    }
                )

    if not selected_bills:
        failures.append(
            {
                "jurisdiction": slug,
                "asset_class": "legislation",
                "reason": "no_bills_returned",
            }
        )
    return created, failures


def _resolved_targets_payload(
    *,
    source_targets: list[SourceTarget],
    legislation_slugs: list[str],
    max_documents_per_source: int,
) -> dict[str, Any]:
    by_jurisdiction: Counter[str] = Counter()
    by_asset_class: Counter[str] = Counter()

    for target in source_targets:
        by_jurisdiction[target.jurisdiction_slug] += 1
        by_asset_class[target.asset_class] += 1
    for slug in legislation_slugs:
        by_jurisdiction[slug] += 1
        by_asset_class["legislation"] += 1

    count = sum(by_jurisdiction.values())
    return {
        "count": count,
        "by_jurisdiction": dict(by_jurisdiction),
        "by_asset_class": dict(by_asset_class),
        "max_documents_per_source": max_documents_per_source,
        "potential_target_documents": (
            len(source_targets) + len(legislation_slugs)
        )
        * max_documents_per_source,
    }


async def run_manual_substrate_expansion(manifest: dict[str, Any]) -> dict[str, Any]:
    db = PostgresDB()
    await db.connect()
    run_id = _manual_run_id()
    run_label = manifest["run_label"]
    triggered_at = datetime.now(timezone.utc).isoformat()

    try:
        source_rows = await _fetch_source_rows(db)
        source_targets, failures = _resolve_source_targets(
            source_rows=source_rows,
            jurisdictions=manifest["jurisdictions"],
            asset_classes=manifest["asset_classes"],
            max_documents_per_source=manifest["max_documents_per_source"],
        )

        legislation_slugs = [
            _slugify(item)
            for item in manifest["jurisdictions"]
            if "legislation" in manifest["asset_classes"] and _slugify(item) in SCRAPERS
        ]
        if "legislation" in manifest["asset_classes"]:
            unsupported_legislation = {
                _slugify(item)
                for item in manifest["jurisdictions"]
                if _slugify(item) not in SCRAPERS
            }
            failures.extend(
                {
                    "jurisdiction": slug,
                    "asset_class": "legislation",
                    "reason": "unsupported_jurisdiction",
                }
                for slug in sorted(unsupported_legislation)
            )

        ingest = manifest["run_mode"] == "capture_and_ingest"
        ingestion_service = await _build_ingestion_service(db) if ingest else None
        job = ScrapeJob(db)

        for target in source_targets:
            try:
                await _execute_source_target(
                    db=db,
                    target=target,
                    run_id=run_id,
                    run_label=run_label,
                    ingest=ingest,
                )
            except Exception as exc:  # pragma: no cover - runtime safety path
                failures.append(
                    {
                        "jurisdiction": target.jurisdiction_slug,
                        "asset_class": target.asset_class,
                        "url": target.url,
                        "reason": "capture_failed",
                        "detail": str(exc),
                    }
                )

        for slug in legislation_slugs:
            _, legislation_failures = await _execute_legislation_capture(
                db=db,
                job=job,
                slug=slug,
                run_id=run_id,
                run_label=run_label,
                max_documents_per_source=manifest["max_documents_per_source"],
                ingest=ingest,
                ingestion_service=ingestion_service,
            )
            failures.extend(legislation_failures)

        report = await generate_substrate_inspection_report(
            db=db,
            run_id=run_id,
            run_id_key="manual_run_id",
            sample_size_per_bucket=manifest["sample_size_per_bucket"],
        )
        resolved_targets = _resolved_targets_payload(
            source_targets=source_targets,
            legislation_slugs=legislation_slugs,
            max_documents_per_source=manifest["max_documents_per_source"],
        )
        capture_summary = {
            "raw_scrapes_created": report["raw_scrapes_total"],
            "by_content_class": report["content_class_counts"],
            "by_trust_tier": report["trust_tier_counts"],
        }
        ingestion_summary = {
            "run_mode": manifest["run_mode"],
            "ocr_mode": manifest["ocr_mode"],
            "ocr_fallback_invocations": 0,
            "by_stage": report["ingestion_truth_stage_counts"],
        }
        promotion_summary = {
            "captured_candidate": report["promotion_state_counts"].get(
                "captured_candidate", 0
            ),
            "durable_raw": report["promotion_state_counts"].get("durable_raw", 0),
            "promoted_substrate": report["promotion_state_counts"].get(
                "promoted_substrate", 0
            ),
        }
        report["requested"] = manifest
        report["resolved_targets"] = resolved_targets
        report["capture_summary"] = capture_summary
        report["ingestion_summary"] = ingestion_summary
        report["promotion_summary"] = promotion_summary
        report["failures"] = failures
        artifact_path = write_report_artifact(report=report)

        status = "succeeded"
        if failures and report["raw_scrapes_total"] > 0:
            status = "partial_success"
        if report["raw_scrapes_total"] == 0 and failures:
            status = "failed"

        return {
            "job": "manual_substrate_expansion",
            "status": status,
            "run_id": run_id,
            "run_label": run_label,
            "requested": manifest,
            "resolved_targets": resolved_targets,
            "capture_summary": capture_summary,
            "ingestion_summary": ingestion_summary,
            "promotion_summary": promotion_summary,
            "failures": failures,
            "inspection_report": {
                "run_id": run_id,
                "available": True,
                "artifact_path": str(artifact_path),
            },
            "triggered_at": triggered_at,
        }
    finally:
        await db.close()
