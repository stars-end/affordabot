#!/usr/bin/env python3
"""Bounded execution path for manual substrate expansion runs."""

from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.request
from argparse import Namespace
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from urllib.parse import urljoin
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from db.postgres_client import PostgresDB
from scripts.cron.run_daily_scrape import EMBEDDING_DIMENSIONS
from scripts.cron.run_daily_scrape import ScrapeJob
from scripts.substrate.manual_capture import capture_document
from scripts.substrate.manual_capture import parse_metadata_blob
from scripts.substrate.substrate_inspection_report import (
    generate_storage_integrity_checks,
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

CUSTOM_ARCHIVE_PROVIDER_FAMILY = "custom_archive_document_center"
CUSTOM_ARCHIVE_ROOT_DOCUMENT_TYPE = "meeting_archive_root"
DEFAULT_ARCHIVE_DOCUMENT_TYPES = {"agenda", "minutes"}
AGENDA_KEYWORDS = ("agenda", "agendas")
MINUTES_KEYWORDS = ("minutes", "minute")

ANCHOR_LINK_PATTERN = re.compile(
    r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
LABEL_PATTERN = re.compile(
    r"<label[^>]*for=[\"']([^\"']+)[\"'][^>]*>(.*?)</label>",
    re.IGNORECASE | re.DOTALL,
)
SELECT_PATTERN = re.compile(
    r"<select(?P<attrs>[^>]*)>(?P<inner>.*?)</select>",
    re.IGNORECASE | re.DOTALL,
)
OPTION_PATTERN = re.compile(
    r"<option[^>]*value=[\"']([^\"']+)[\"'][^>]*>(.*?)</option>",
    re.IGNORECASE | re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")


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


def _strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_PATTERN.sub(" ", value or ""))).strip()


def _normalize_url(url: str, *, root_url: str) -> str:
    absolute = urljoin(root_url, html.unescape(url or "").strip())
    parts = urlsplit(absolute)
    cleaned = parts._replace(fragment="")
    return urlunsplit(cleaned)


def _infer_archive_document_type(*, url: str, text: str) -> str | None:
    combined = f"{url} {text}".strip().lower()
    has_agenda = any(keyword in combined for keyword in AGENDA_KEYWORDS)
    has_minutes = any(keyword in combined for keyword in MINUTES_KEYWORDS)
    if has_agenda and not has_minutes:
        return "agenda"
    if has_minutes and not has_agenda:
        return "minutes"
    return None


def _extract_anchor_candidates(*, page_html: str, root_url: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for href, text_html in ANCHOR_LINK_PATTERN.findall(page_html):
        candidate_url = _normalize_url(href, root_url=root_url)
        if not candidate_url.startswith(("http://", "https://")):
            continue
        text = _strip_tags(text_html)
        document_type = _infer_archive_document_type(url=candidate_url, text=text)
        if not document_type:
            continue
        title = text or candidate_url
        candidates.append(
            {
                "url": candidate_url,
                "title": title,
                "document_type": document_type,
            }
        )
    return candidates


def _extract_civicplus_archive_candidates(
    *,
    page_html: str,
    root_url: str,
    required_label_keywords: set[str] | None = None,
) -> list[dict[str, str]]:
    label_by_for: dict[str, str] = {}
    for label_for, label_text_html in LABEL_PATTERN.findall(page_html):
        label_by_for[label_for.strip()] = _strip_tags(label_text_html)

    candidates: list[dict[str, str]] = []
    for select_match in SELECT_PATTERN.finditer(page_html):
        attrs = select_match.group("attrs") or ""
        inner = select_match.group("inner") or ""
        onchange_match = re.search(r"ViewArchive\(this,\s*(\d+),", attrs, re.IGNORECASE)
        if not onchange_match:
            continue
        amid = onchange_match.group(1)
        select_id_match = re.search(r"\bid=[\"']([^\"']+)[\"']", attrs, re.IGNORECASE)
        select_id = select_id_match.group(1) if select_id_match else ""
        label_text = label_by_for.get(select_id, "")
        if required_label_keywords:
            label_lower = label_text.lower()
            if not any(keyword in label_lower for keyword in required_label_keywords):
                continue

        for option_value, option_text_html in OPTION_PATTERN.findall(inner):
            value = (option_value or "").strip()
            if value in {"", "-1", "-2"}:
                continue
            parts = value.split("_")
            if len(parts) < 4:
                continue
            is_recent = parts[2] == "1"
            item_id = parts[3]
            if is_recent:
                candidate_url = _normalize_url(
                    f"Archive.aspx?AMID={amid}&Type=Recent",
                    root_url=root_url,
                )
            else:
                candidate_url = _normalize_url(
                    f"Archive.aspx?AMID={amid}&ADID={item_id}",
                    root_url=root_url,
                )
            option_text = _strip_tags(option_text_html)
            combined_text = " - ".join(part for part in (label_text, option_text) if part)
            document_type = _infer_archive_document_type(
                url=candidate_url,
                text=combined_text,
            )
            if not document_type:
                continue
            title = combined_text or candidate_url
            candidates.append(
                {
                    "url": candidate_url,
                    "title": title,
                    "document_type": document_type,
                }
            )
    return candidates


def _to_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _discover_custom_archive_candidates(
    *,
    row: dict[str, Any],
) -> tuple[list[dict[str, str]], str | None]:
    metadata = parse_metadata_blob(row.get("metadata"))
    fetch_url = (metadata.get("archive_fetch_url") or row.get("url") or "").strip()
    if not fetch_url:
        return [], "missing_archive_fetch_url"

    extraction_mode = (metadata.get("extraction_mode") or "anchors").strip().lower()
    allowed_prefixes = _to_string_list(metadata.get("url_allowlist_prefixes"))
    required_url_keywords = [keyword.lower() for keyword in _to_string_list(metadata.get("required_url_keywords"))]
    required_label_keywords = {
        keyword.lower() for keyword in _to_string_list(metadata.get("required_label_keywords"))
    }
    supported_document_types = {
        item.lower() for item in _to_string_list(metadata.get("supported_document_types"))
    } or set(DEFAULT_ARCHIVE_DOCUMENT_TYPES)

    try:
        with urllib.request.urlopen(fetch_url, timeout=20) as response:
            page_html = response.read().decode("utf-8", "replace")
    except Exception as exc:  # pragma: no cover - runtime safety path
        return [], str(exc)

    candidates: list[dict[str, str]] = []
    if extraction_mode in {"anchors", "mixed", "auto"}:
        candidates.extend(
            _extract_anchor_candidates(
                page_html=page_html,
                root_url=fetch_url,
            )
        )
    if extraction_mode in {"civicplus_archive_options", "mixed", "auto"}:
        candidates.extend(
            _extract_civicplus_archive_candidates(
                page_html=page_html,
                root_url=fetch_url,
                required_label_keywords=required_label_keywords or None,
            )
        )

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        candidate_url = candidate["url"]
        candidate_document_type = candidate["document_type"]
        if candidate_document_type not in supported_document_types:
            continue
        if allowed_prefixes and not any(
            candidate_url.lower().startswith(prefix.lower()) for prefix in allowed_prefixes
        ):
            continue
        if required_url_keywords and not any(
            keyword in candidate_url.lower() for keyword in required_url_keywords
        ):
            continue
        key = (candidate_url, candidate_document_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped, None


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
    targets: list[SourceTarget] = []
    failures: list[dict[str, Any]] = []
    custom_archive_cache: dict[str, tuple[list[dict[str, str]], str | None]] = {}
    reported_custom_archive_failures: set[tuple[str, str, str]] = set()

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

            matching_targets: list[SourceTarget] = []
            for row in source_rows:
                row_slug = _slugify(row["jurisdiction_name"])
                if row_slug != jurisdiction_slug:
                    continue
                metadata = parse_metadata_blob(row.get("metadata"))
                document_type = (metadata.get("document_type") or "").strip().lower()
                url = (row.get("url") or "").strip()
                if not url or url.startswith("unknown://"):
                    continue
                if document_type in document_types:
                    trust_tier, _ = classify_trust(
                        canonical_url=url,
                        trust_tier=metadata.get("trust_tier"),
                    )
                    matching_targets.append(
                        SourceTarget(
                            jurisdiction_slug=jurisdiction_slug,
                            jurisdiction_name=row["jurisdiction_name"],
                            jurisdiction_type=row["jurisdiction_type"],
                            asset_class=asset_class,
                            source_id=str(row["id"]),
                            source_name=row["name"],
                            source_type=row["type"],
                            document_type=document_type or next(iter(document_types)),
                            url=url,
                            title=metadata.get("title") or row["name"] or url,
                            trust_tier=trust_tier,
                        )
                    )
                    continue

                provider_family = (metadata.get("provider_family") or "").strip().lower()
                if provider_family != CUSTOM_ARCHIVE_PROVIDER_FAMILY:
                    continue
                if document_type != CUSTOM_ARCHIVE_ROOT_DOCUMENT_TYPE:
                    continue
                if asset_class not in {"agendas", "minutes"}:
                    continue

                source_cache_key = str(row.get("id") or row.get("url") or "")
                if source_cache_key not in custom_archive_cache:
                    custom_archive_cache[source_cache_key] = _discover_custom_archive_candidates(row=row)
                discovered_candidates, discovery_error = custom_archive_cache[source_cache_key]

                if discovery_error:
                    failure_key = (jurisdiction_slug, asset_class, source_cache_key)
                    if failure_key not in reported_custom_archive_failures:
                        reported_custom_archive_failures.add(failure_key)
                        failures.append(
                            {
                                "jurisdiction": jurisdiction_slug,
                                "asset_class": asset_class,
                                "reason": "custom_archive_discovery_failed",
                                "source_url": url,
                                "detail": discovery_error,
                            }
                        )
                    continue

                for candidate in discovered_candidates:
                    if candidate["document_type"] not in document_types:
                        continue
                    candidate_url = candidate["url"]
                    trust_tier, _ = classify_trust(
                        canonical_url=candidate_url,
                        trust_tier=metadata.get("trust_tier"),
                    )
                    matching_targets.append(
                        SourceTarget(
                            jurisdiction_slug=jurisdiction_slug,
                            jurisdiction_name=row["jurisdiction_name"],
                            jurisdiction_type=row["jurisdiction_type"],
                            asset_class=asset_class,
                            source_id=str(row["id"]),
                            source_name=metadata.get("source_label") or row["name"],
                            source_type="meeting_document",
                            document_type=candidate["document_type"],
                            url=candidate_url,
                            title=candidate.get("title") or candidate_url,
                            trust_tier=trust_tier,
                        )
                    )

            deduped_targets: list[SourceTarget] = []
            seen_urls: set[tuple[str, str]] = set()
            for target in matching_targets:
                dedupe_key = (target.url, target.document_type)
                if dedupe_key in seen_urls:
                    continue
                seen_urls.add(dedupe_key)
                deduped_targets.append(target)

            if not deduped_targets:
                failures.append(
                    {
                        "jurisdiction": jurisdiction_slug,
                        "asset_class": asset_class,
                        "reason": "no_matching_sources",
                    }
                )
                continue

            targets.extend(deduped_targets[:max_documents_per_source])

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
    capture_metrics: dict[str, int] | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    if capture_metrics is not None:
        capture_metrics["attempted_raw_captures"] = 0

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
    try:
        bills = await scraper.scrape()
    except Exception as exc:  # pragma: no cover - runtime safety path
        return 0, [
            {
                "jurisdiction": slug,
                "asset_class": "legislation",
                "reason": "scrape_failed",
                "detail": str(exc),
            }
        ]
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
    attempted_raw_captures = 0
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

        attempted_raw_captures += 1
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
    if capture_metrics is not None:
        capture_metrics["attempted_raw_captures"] = attempted_raw_captures
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
        attempted_targets_count = 0
        attempted_raw_capture_operations = 0

        for target in source_targets:
            attempted_targets_count += 1
            attempted_raw_capture_operations += 1
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
            attempted_targets_count += 1
            legislation_capture_metrics: dict[str, int] = {}
            _, legislation_failures = await _execute_legislation_capture(
                db=db,
                job=job,
                slug=slug,
                run_id=run_id,
                run_label=run_label,
                max_documents_per_source=manifest["max_documents_per_source"],
                ingest=ingest,
                ingestion_service=ingestion_service,
                capture_metrics=legislation_capture_metrics,
            )
            attempted_raw_capture_operations += int(
                legislation_capture_metrics.get("attempted_raw_captures", 0)
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
        storage_integrity_checks = await generate_storage_integrity_checks(
            db=db,
            run_id=run_id,
            run_id_key="manual_run_id",
            resolved_targets_count=resolved_targets["count"],
            attempted_targets_count=attempted_targets_count,
            attempted_raw_capture_operations=attempted_raw_capture_operations,
        )
        report["requested"] = manifest
        report["resolved_targets"] = resolved_targets
        report["capture_summary"] = capture_summary
        report["ingestion_summary"] = ingestion_summary
        report["promotion_summary"] = promotion_summary
        report["storage_integrity_checks"] = storage_integrity_checks
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
            "storage_integrity_checks": storage_integrity_checks,
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
