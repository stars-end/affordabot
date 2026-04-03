#!/usr/bin/env python3
"""Bounded execution path for manual substrate expansion runs."""

from __future__ import annotations

import json
import os
import re
from argparse import Namespace
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import urljoin
from urllib.parse import urlparse
from uuid import uuid4

import httpx

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

HANDLER_SUPPORTED_DOCUMENT_TYPES = {
    "legistar_calendar": {
        "meeting_detail",
        "agenda",
        "minutes",
        "agenda_packet",
        "attachment",
        "staff_report",
    },
    "sunnyvale_agendas": {
        "meeting_detail",
        "agenda",
        "minutes",
        "agenda_packet",
        "attachment",
    },
    "agenda_center": {
        "agenda",
        "minutes",
        "agenda_packet",
        "attachment",
        "staff_report",
    },
    "municode": {"municipal_code"},
}

ANCHOR_PATTERN = re.compile(
    r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',
    flags=re.IGNORECASE | re.DOTALL,
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


@dataclass(frozen=True)
class SourceSeed:
    jurisdiction_slug: str
    jurisdiction_name: str
    jurisdiction_type: str
    asset_class: str
    source_name: str
    source_type: str
    url: str
    document_type: str
    title: str
    source_method: str
    handler: str
    trust_tier: str


PACK_A_SOURCE_DEFAULTS: tuple[SourceSeed, ...] = (
    SourceSeed(
        jurisdiction_slug="san-jose",
        jurisdiction_name="City of San Jose",
        jurisdiction_type="city",
        asset_class="meeting_details",
        source_name="San Jose Meetings Calendar",
        source_type="meetings",
        url="https://sanjose.legistar.com/Calendar.aspx",
        document_type="meeting_detail",
        title="San Jose Meeting Detail Calendar",
        source_method="scrape",
        handler="legistar_calendar",
        trust_tier="official_partner",
    ),
    SourceSeed(
        jurisdiction_slug="san-jose",
        jurisdiction_name="City of San Jose",
        jurisdiction_type="city",
        asset_class="agendas",
        source_name="San Jose Agendas",
        source_type="meetings",
        url="https://sanjose.legistar.com/Calendar.aspx",
        document_type="agenda",
        title="San Jose Agendas",
        source_method="scrape",
        handler="legistar_calendar",
        trust_tier="official_partner",
    ),
    SourceSeed(
        jurisdiction_slug="san-jose",
        jurisdiction_name="City of San Jose",
        jurisdiction_type="city",
        asset_class="minutes",
        source_name="San Jose Minutes",
        source_type="meetings",
        url="https://sanjose.legistar.com/Calendar.aspx",
        document_type="minutes",
        title="San Jose Minutes",
        source_method="scrape",
        handler="legistar_calendar",
        trust_tier="official_partner",
    ),
    SourceSeed(
        jurisdiction_slug="san-jose",
        jurisdiction_name="City of San Jose",
        jurisdiction_type="city",
        asset_class="municipal_code",
        source_name="San Jose Municipal Code",
        source_type="code",
        url="https://library.municode.com/ca/san_jose/codes/code_of_ordinances",
        document_type="municipal_code",
        title="San Jose Municipal Code",
        source_method="scrape",
        handler="municode",
        trust_tier="official_partner",
    ),
    SourceSeed(
        jurisdiction_slug="santa-clara-county",
        jurisdiction_name="County of Santa Clara",
        jurisdiction_type="county",
        asset_class="meeting_details",
        source_name="Santa Clara County Meetings Calendar",
        source_type="meetings",
        url="https://sccgov.legistar.com/Calendar.aspx",
        document_type="meeting_detail",
        title="Santa Clara County Meeting Detail Calendar",
        source_method="scrape",
        handler="legistar_calendar",
        trust_tier="official_partner",
    ),
    SourceSeed(
        jurisdiction_slug="santa-clara-county",
        jurisdiction_name="County of Santa Clara",
        jurisdiction_type="county",
        asset_class="agendas",
        source_name="Santa Clara County Agendas",
        source_type="meetings",
        url="https://sccgov.legistar.com/Calendar.aspx",
        document_type="agenda",
        title="Santa Clara County Agendas",
        source_method="scrape",
        handler="legistar_calendar",
        trust_tier="official_partner",
    ),
    SourceSeed(
        jurisdiction_slug="santa-clara-county",
        jurisdiction_name="County of Santa Clara",
        jurisdiction_type="county",
        asset_class="minutes",
        source_name="Santa Clara County Minutes",
        source_type="meetings",
        url="https://sccgov.legistar.com/Calendar.aspx",
        document_type="minutes",
        title="Santa Clara County Minutes",
        source_method="scrape",
        handler="legistar_calendar",
        trust_tier="official_partner",
    ),
    SourceSeed(
        jurisdiction_slug="saratoga",
        jurisdiction_name="City of Saratoga",
        jurisdiction_type="city",
        asset_class="agendas",
        source_name="Saratoga Agenda Center",
        source_type="meetings",
        url="https://www.saratoga.ca.us/AgendaCenter",
        document_type="agenda",
        title="Saratoga Agenda Center",
        source_method="scrape",
        handler="agenda_center",
        trust_tier="official_partner",
    ),
    SourceSeed(
        jurisdiction_slug="saratoga",
        jurisdiction_name="City of Saratoga",
        jurisdiction_type="city",
        asset_class="minutes",
        source_name="Saratoga Minutes",
        source_type="meetings",
        url="https://www.saratoga.ca.us/AgendaCenter",
        document_type="minutes",
        title="Saratoga Minutes",
        source_method="scrape",
        handler="agenda_center",
        trust_tier="official_partner",
    ),
    SourceSeed(
        jurisdiction_slug="sunnyvale",
        jurisdiction_name="City of Sunnyvale",
        jurisdiction_type="city",
        asset_class="meeting_details",
        source_name="Sunnyvale Meetings Calendar",
        source_type="meetings",
        url="https://sunnyvaleca.legistar.com/Calendar.aspx",
        document_type="meeting_detail",
        title="Sunnyvale Meeting Detail Calendar",
        source_method="scrape",
        handler="sunnyvale_agendas",
        trust_tier="official_partner",
    ),
    SourceSeed(
        jurisdiction_slug="sunnyvale",
        jurisdiction_name="City of Sunnyvale",
        jurisdiction_type="city",
        asset_class="agendas",
        source_name="Sunnyvale Agendas",
        source_type="meetings",
        url="https://sunnyvaleca.legistar.com/Calendar.aspx",
        document_type="agenda",
        title="Sunnyvale Agendas",
        source_method="scrape",
        handler="sunnyvale_agendas",
        trust_tier="official_partner",
    ),
    SourceSeed(
        jurisdiction_slug="sunnyvale",
        jurisdiction_name="City of Sunnyvale",
        jurisdiction_type="city",
        asset_class="minutes",
        source_name="Sunnyvale Minutes",
        source_type="meetings",
        url="https://sunnyvaleca.legistar.com/Calendar.aspx",
        document_type="minutes",
        title="Sunnyvale Minutes",
        source_method="scrape",
        handler="sunnyvale_agendas",
        trust_tier="official_partner",
    ),
)


def _slugify(value: str) -> str:
    return (value or "").strip().lower().replace("_", "-").replace(" ", "-")


def _slug_aliases(value: str) -> set[str]:
    slug = _slugify(value)
    aliases = {slug}
    if slug.startswith("city-of-"):
        aliases.add(slug[len("city-of-") :])
    if slug.startswith("county-of-"):
        core = slug[len("county-of-") :]
        aliases.add(core)
        aliases.add(f"{core}-county")
    if slug.startswith("state-of-"):
        aliases.add(slug[len("state-of-") :])
    if slug.endswith("-county"):
        core = slug[: -len("-county")]
        aliases.add(core)
        aliases.add(f"county-of-{core}")
    return aliases


def _jurisdiction_matches(row_jurisdiction_name: str, requested_slug: str) -> bool:
    requested = _slugify(requested_slug)
    aliases = _slug_aliases(row_jurisdiction_name)
    return requested in aliases


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
          s.handler,
          s.metadata,
          j.name AS jurisdiction_name,
          j.type AS jurisdiction_type
        FROM sources s
        JOIN jurisdictions j ON j.id::text = s.jurisdiction_id
        ORDER BY j.name, s.type, s.name
        """
    )
    return [dict(row) for row in rows]


def _normalize_handler(row: dict[str, Any], metadata: dict[str, Any]) -> str:
    return ((row.get("handler") or metadata.get("handler") or "").strip().lower())


def _source_row_supports_asset(
    *,
    row: dict[str, Any],
    metadata: dict[str, Any],
    document_types: set[str],
) -> bool:
    handler = _normalize_handler(row, metadata)
    if handler in HANDLER_SUPPORTED_DOCUMENT_TYPES:
        return bool(
            HANDLER_SUPPORTED_DOCUMENT_TYPES[handler].intersection(document_types)
        )
    document_type = (metadata.get("document_type") or "").strip().lower()
    return document_type in document_types


def _document_type_from_link_label(
    label: str,
    *,
    href: str = "",
    anchor_html: str = "",
) -> str | None:
    lowered = (label or "").strip().lower()
    href_lower = (href or "").strip().lower()
    anchor_lower = (anchor_html or "").strip().lower()
    signal = " ".join(part for part in (lowered, href_lower, anchor_lower) if part)
    if not signal:
        return None

    if "meetingdetail.aspx" in href_lower or "meeting detail" in signal:
        return "meeting_detail"
    if "view.ashx?m=pa" in href_lower:
        return "agenda_packet"
    if "view.ashx?m=m" in href_lower:
        return "minutes"
    if "view.ashx?m=a" in href_lower:
        return "agenda"

    lowered = signal
    if "meeting detail" in lowered or "details" in lowered:
        return "meeting_detail"
    if "staff report" in lowered:
        return "staff_report"
    if "agenda packet" in lowered or "packet" in lowered:
        return "agenda_packet"
    if "attach" in lowered:
        return "attachment"
    if "minute" in lowered:
        return "minutes"
    if "agenda" in lowered:
        return "agenda"
    return None


def _extract_document_links(*, html_text: str, base_url: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for match in ANCHOR_PATTERN.finditer(html_text or ""):
        href = (match.group("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue

        raw_label = match.group("label") or ""
        label = unescape(TAG_PATTERN.sub(" ", raw_label))
        label = " ".join(label.split())
        document_type = _document_type_from_link_label(
            label,
            href=href,
            anchor_html=match.group(0),
        )
        if not document_type:
            continue

        candidates.append(
            {
                "url": urljoin(base_url, href),
                "title": label or href,
                "document_type": document_type,
            }
        )
    return candidates


def _candidate_allowed_for_handler(*, handler: str, candidate_url: str) -> bool:
    if handler != "sunnyvale_agendas":
        return True

    host = (urlparse(candidate_url).hostname or "").lower()
    return host.endswith("sunnyvaleca.legistar.com")


def _root_candidate(
    *,
    row: dict[str, Any],
    metadata: dict[str, Any],
    url: str,
    document_types: set[str],
) -> list[dict[str, str]]:
    row_document_type = (metadata.get("document_type") or "").strip().lower()
    if row_document_type in document_types:
        return [
            {
                "url": url,
                "title": metadata.get("title") or row.get("name") or url,
                "document_type": row_document_type,
            }
        ]
    return []


async def _expand_source_row_targets(
    *,
    client: httpx.AsyncClient,
    row: dict[str, Any],
    metadata: dict[str, Any],
    document_types: set[str],
    max_documents_per_source: int,
) -> list[dict[str, str]]:
    url = (row.get("url") or "").strip()
    if not url or url.startswith("unknown://"):
        return []

    handler = _normalize_handler(row, metadata)
    if handler not in HANDLER_SUPPORTED_DOCUMENT_TYPES:
        return _root_candidate(
            row=row,
            metadata=metadata,
            url=url,
            document_types=document_types,
        )

    if handler == "municode":
        return _root_candidate(
            row=row,
            metadata=metadata,
            url=url,
            document_types=document_types,
        )

    try:
        response = await client.get(url, timeout=20.0)
        if response.status_code >= 400:
            return _root_candidate(
                row=row,
                metadata=metadata,
                url=url,
                document_types=document_types,
            )
        extracted = _extract_document_links(html_text=response.text, base_url=url)
    except Exception:
        return _root_candidate(
            row=row,
            metadata=metadata,
            url=url,
            document_types=document_types,
        )

    filtered = [
        candidate
        for candidate in extracted
        if candidate["document_type"] in document_types
        and _candidate_allowed_for_handler(
            handler=handler,
            candidate_url=candidate["url"],
        )
    ]

    # Keep deterministic, bounded, and deduplicated expansion output per source.
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in filtered:
        key = (candidate["url"], candidate["document_type"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
        if len(deduped) >= max_documents_per_source:
            break

    if deduped:
        return deduped

    return _root_candidate(
        row=row,
        metadata=metadata,
        url=url,
        document_types=document_types,
    )


async def _ensure_pack_a_source_inventory(
    *,
    db: PostgresDB,
    jurisdictions: list[str],
    asset_classes: list[str],
) -> dict[str, Any]:
    requested_jurisdictions = {_slugify(value) for value in jurisdictions}
    requested_assets = set(asset_classes) - {"legislation"}
    attempted = 0
    upserted = 0
    failures: list[dict[str, Any]] = []

    for seed in PACK_A_SOURCE_DEFAULTS:
        if seed.jurisdiction_slug not in requested_jurisdictions:
            continue
        if seed.asset_class not in requested_assets:
            continue

        attempted += 1
        jurisdiction_id = await db.get_or_create_jurisdiction(
            seed.jurisdiction_name,
            seed.jurisdiction_type,
        )
        if not jurisdiction_id:
            failures.append(
                {
                    "jurisdiction": seed.jurisdiction_slug,
                    "asset_class": seed.asset_class,
                    "reason": "jurisdiction_resolution_failed",
                }
            )
            continue

        source = await db.upsert_source(
            {
                "jurisdiction_id": jurisdiction_id,
                "name": seed.source_name,
                "type": seed.source_type,
                "url": seed.url,
                "status": "active",
                "source_method": seed.source_method,
                "handler": seed.handler,
                "metadata": {
                    "document_type": seed.document_type,
                    "title": seed.title,
                    "trust_tier": seed.trust_tier,
                    "provider_family": "pack_a_default",
                    "seeded_by": "manual_substrate_expansion",
                },
            }
        )
        if source and source.get("id"):
            upserted += 1
        else:
            failures.append(
                {
                    "jurisdiction": seed.jurisdiction_slug,
                    "asset_class": seed.asset_class,
                    "reason": "source_upsert_failed",
                    "url": seed.url,
                }
            )

    return {
        "attempted": attempted,
        "upserted": upserted,
        "failures": failures,
    }


async def _resolve_source_targets(
    *,
    source_rows: list[dict[str, Any]],
    jurisdictions: list[str],
    asset_classes: list[str],
    max_documents_per_source: int,
) -> tuple[list[SourceTarget], list[dict[str, Any]]]:
    targets: list[SourceTarget] = []
    failures: list[dict[str, Any]] = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
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
                    if not _jurisdiction_matches(row["jurisdiction_name"], jurisdiction_slug):
                        continue
                    metadata = parse_metadata_blob(row.get("metadata"))
                    url = (row.get("url") or "").strip()
                    if not url or url.startswith("unknown://"):
                        continue
                    if not _source_row_supports_asset(
                        row=row,
                        metadata=metadata,
                        document_types=document_types,
                    ):
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

                asset_targets: list[SourceTarget] = []
                for row in matching_rows:
                    metadata = parse_metadata_blob(row.get("metadata"))
                    expanded_candidates = await _expand_source_row_targets(
                        client=client,
                        row=row,
                        metadata=metadata,
                        document_types=document_types,
                        max_documents_per_source=max_documents_per_source,
                    )
                    for candidate in expanded_candidates:
                        candidate_url = (candidate.get("url") or "").strip()
                        if not candidate_url:
                            continue
                        trust_tier, _ = classify_trust(
                            canonical_url=candidate_url,
                            trust_tier=metadata.get("trust_tier"),
                        )
                        asset_targets.append(
                            SourceTarget(
                                jurisdiction_slug=jurisdiction_slug,
                                jurisdiction_name=row["jurisdiction_name"],
                                jurisdiction_type=row["jurisdiction_type"],
                                asset_class=asset_class,
                                source_id=str(row["id"]),
                                source_name=row["name"],
                                source_type=row["type"],
                                document_type=candidate["document_type"],
                                url=candidate_url,
                                title=candidate.get("title") or row["name"] or candidate_url,
                                trust_tier=trust_tier,
                            )
                        )

                deduped_targets: list[SourceTarget] = []
                seen: set[tuple[str, str]] = set()
                for target in asset_targets:
                    key = (target.url, target.document_type)
                    if key in seen:
                        continue
                    seen.add(key)
                    deduped_targets.append(target)
                    if len(deduped_targets) >= max_documents_per_source:
                        break

                if not deduped_targets:
                    failures.append(
                        {
                            "jurisdiction": jurisdiction_slug,
                            "asset_class": asset_class,
                            "reason": "no_matching_sources",
                        }
                    )
                    continue

                targets.extend(deduped_targets)

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
        source_inventory = await _ensure_pack_a_source_inventory(
            db=db,
            jurisdictions=manifest["jurisdictions"],
            asset_classes=manifest["asset_classes"],
        )
        source_rows = await _fetch_source_rows(db)
        source_targets, failures = await _resolve_source_targets(
            source_rows=source_rows,
            jurisdictions=manifest["jurisdictions"],
            asset_classes=manifest["asset_classes"],
            max_documents_per_source=manifest["max_documents_per_source"],
        )
        failures.extend(source_inventory["failures"])

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
        report["source_inventory"] = source_inventory
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
            "source_inventory": source_inventory,
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
