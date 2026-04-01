#!/usr/bin/env python3
"""Inspect substrate capture health with promotion and ingestion truth together."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from db.postgres_client import PostgresDB


def parse_json_blob(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=168, help="Look back window")
    parser.add_argument("--limit", type=int, default=50, help="Row limit")
    parser.add_argument("--promotion-state")
    parser.add_argument("--trust-tier")
    parser.add_argument("--ingestion-stage")
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="Include historical rows with no staged ingestion truth",
    )
    return parser.parse_args(argv)


async def fetch_rows(db: "PostgresDB", *, hours: int, limit: int) -> list[dict[str, Any]]:
    rows = await db._fetch(
        """
        SELECT
          rs.id,
          rs.created_at,
          rs.processed,
          rs.error_message,
          rs.url AS raw_url,
          rs.storage_uri,
          rs.metadata AS raw_metadata,
          s.id AS source_id,
          s.name AS source_name,
          s.url AS source_url,
          s.metadata AS source_metadata
        FROM raw_scrapes rs
        LEFT JOIN sources s ON s.id = rs.source_id
        WHERE rs.created_at >= NOW() - (($1::text || ' hours')::interval)
        ORDER BY rs.created_at DESC
        LIMIT $2
        """,
        hours,
        limit,
    )
    return [dict(row) for row in rows]


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    raw_metadata = parse_json_blob(row.get("raw_metadata"))
    source_metadata = parse_json_blob(row.get("source_metadata"))
    merged = {**source_metadata, **raw_metadata}
    ingestion_truth = parse_json_blob(merged.get("ingestion_truth"))
    promotion_state = merged.get("promotion_state")
    legacy_unknown = not ingestion_truth and promotion_state is None

    canonical_url = (
        merged.get("canonical_url")
        or row.get("raw_url")
        or row.get("source_url")
        or ""
    )
    stage = ingestion_truth.get("stage") or ("legacy_unknown" if legacy_unknown else None)
    recent_errors: list[str] = []
    for value in (
        row.get("error_message"),
        merged.get("promotion_error"),
        ingestion_truth.get("last_error"),
        ingestion_truth.get("ingest_skipped_reason"),
    ):
        text = str(value or "").strip()
        if text and text not in recent_errors:
            recent_errors.append(text)

    return {
        "raw_scrape_id": row.get("id"),
        "created_at": row.get("created_at"),
        "processed": row.get("processed"),
        "error_message": row.get("error_message"),
        "storage_uri_present": bool(row.get("storage_uri")),
        "source_id": row.get("source_id"),
        "source_name": row.get("source_name"),
        "source_url": row.get("source_url"),
        "canonical_url": canonical_url,
        "trust_host_classification": merged.get("trust_host_classification"),
        "trust_tier": merged.get("trust_tier"),
        "document_type": merged.get("document_type"),
        "source_type": merged.get("source_type"),
        "content_class": merged.get("content_class"),
        "promotion_state": promotion_state,
        "promotion_method": merged.get("promotion_method"),
        "promotion_reason_category": merged.get("promotion_reason_category"),
        "promotion_error": merged.get("promotion_error"),
        "ingestion_stage": stage,
        "retrievable": ingestion_truth.get("retrievable"),
        "last_error": recent_errors[0] if recent_errors else None,
        "recent_errors": recent_errors[:5],
        "legacy_unknown": legacy_unknown,
    }


def apply_filters(
    records: list[dict[str, Any]],
    *,
    promotion_state: str | None,
    trust_tier: str | None,
    ingestion_stage: str | None,
    include_legacy: bool,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    target_state = (promotion_state or "").strip().lower()
    target_tier = (trust_tier or "").strip().lower()
    target_stage = (ingestion_stage or "").strip().lower()
    for record in records:
        if not include_legacy and record["legacy_unknown"]:
            continue
        if target_state and (record.get("promotion_state") or "").strip().lower() != target_state:
            continue
        if target_tier and (record.get("trust_tier") or "").strip().lower() != target_tier:
            continue
        if target_stage and (record.get("ingestion_stage") or "").strip().lower() != target_stage:
            continue
        filtered.append(record)
    return filtered


def build_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "record_count": len(records),
        "promotion_states": dict(
            Counter((record.get("promotion_state") or "null") for record in records)
        ),
        "trust_tiers": dict(
            Counter((record.get("trust_tier") or "null") for record in records)
        ),
        "ingestion_stages": dict(
            Counter((record.get("ingestion_stage") or "null") for record in records)
        ),
        "legacy_unknown_count": sum(1 for record in records if record["legacy_unknown"]),
        "retrievable_true_count": sum(1 for record in records if record.get("retrievable") is True),
        "error_count": sum(1 for record in records if record.get("last_error")),
    }


async def inspect_substrate(args: argparse.Namespace) -> dict[str, Any]:
    from db.postgres_client import PostgresDB

    db = PostgresDB()
    rows = await fetch_rows(db, hours=args.hours, limit=args.limit)
    normalized = [normalize_row(row) for row in rows]
    filtered = apply_filters(
        normalized,
        promotion_state=args.promotion_state,
        trust_tier=args.trust_tier,
        ingestion_stage=args.ingestion_stage,
        include_legacy=args.include_legacy,
    )
    return {
        "filters": {
            "hours": args.hours,
            "limit": args.limit,
            "promotion_state": args.promotion_state,
            "trust_tier": args.trust_tier,
            "ingestion_stage": args.ingestion_stage,
            "include_legacy": args.include_legacy,
        },
        "summary": build_summary(filtered),
        "records": filtered,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(list(argv) if argv is not None else list(sys.argv[1:]))
    payload = asyncio.run(inspect_substrate(args))
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
