#!/usr/bin/env python3
"""Generate substrate inspection artifacts for a single manual expansion run."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.substrate_promotion import parse_json_blob

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"

PROMOTED_SUBSTRATE = "promoted_substrate"
DURABLE_RAW = "durable_raw"
CAPTURED_CANDIDATE = "captured_candidate"

SUCCESS_STAGES = {
    "raw_captured",
    "ingest_started",
    "blob_stored",
    "parsed",
    "chunked",
    "embedded",
    "upserted",
    "retrievable",
}

DENIED_STYLE_REASONS = {
    "captured_untrusted_needs_review",
    "untrusted_source",
    "index_or_shell_page",
    "insufficient_substance",
    "legacy_unknown",
}

FAILURE_STAGE_HINTS = ("fail", "error", "exception")


@dataclass(frozen=True)
class RowContext:
    row: dict[str, Any]
    metadata: dict[str, Any]
    truth: dict[str, Any]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    return dict(row)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return _text(value)


def _context(raw_row: Any) -> RowContext:
    row = _to_dict(raw_row)
    metadata = parse_json_blob(row.get("metadata"))
    truth = parse_json_blob(metadata.get("ingestion_truth"))
    return RowContext(row=row, metadata=metadata, truth=truth)


def _sample_bucket(ctx: RowContext) -> str | None:
    state = _text(ctx.metadata.get("promotion_state")).lower()
    reason = _text(ctx.metadata.get("promotion_reason_category")).lower()
    trust_tier = _text(ctx.metadata.get("trust_tier")).lower()

    if state == PROMOTED_SUBSTRATE:
        return "promoted"
    if state == DURABLE_RAW:
        return "durable_raw"
    if state == CAPTURED_CANDIDATE:
        if reason in DENIED_STYLE_REASONS or trust_tier == "non_official":
            return "denied_style"
        return "candidate"
    return None


def _failure_bucket(ctx: RowContext) -> str | None:
    stage = _text(ctx.truth.get("stage")).lower()
    reason = _text(ctx.metadata.get("promotion_reason_category")).lower()
    row_error = _text(ctx.row.get("error_message"))

    if stage and stage not in SUCCESS_STAGES:
        if any(token in stage for token in FAILURE_STAGE_HINTS):
            return f"ingestion_stage:{stage}"
    if row_error:
        return "raw_capture_error"
    if reason in DENIED_STYLE_REASONS:
        return f"promotion_reason:{reason}"
    if _text(ctx.metadata.get("promotion_state")).lower() == CAPTURED_CANDIDATE:
        if _text(ctx.metadata.get("trust_tier")).lower() == "non_official":
            return "promotion_reason:untrusted_source"
    return None


def _sample_row(ctx: RowContext) -> dict[str, Any]:
    return {
        "raw_scrape_id": _text(ctx.row.get("id")),
        "created_at": _iso(ctx.row.get("created_at")),
        "url": _text(ctx.row.get("url")),
        "source_url": _text(ctx.row.get("source_url")),
        "source_name": _text(ctx.row.get("source_name")),
        "source_type": _text(ctx.row.get("source_type")),
        "jurisdiction_name": _text(ctx.row.get("jurisdiction_name")),
        "document_type": _text(ctx.metadata.get("document_type")),
        "content_class": _text(ctx.metadata.get("content_class")),
        "trust_tier": _text(ctx.metadata.get("trust_tier")),
        "promotion_state": _text(ctx.metadata.get("promotion_state")),
        "promotion_reason_category": _text(ctx.metadata.get("promotion_reason_category")),
        "ingestion_stage": _text(ctx.truth.get("stage")),
        "retrievable": bool(ctx.truth.get("retrievable")),
        "error_message": _text(ctx.row.get("error_message")),
    }


def build_substrate_inspection_report(
    *,
    run_id: str,
    rows: list[dict[str, Any]],
    run_id_key: str = "manual_run_id",
    sample_size_per_bucket: int = 5,
) -> dict[str, Any]:
    promotion_counts: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    trust_counts: Counter[str] = Counter()
    content_class_counts: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()

    samples: dict[str, list[dict[str, Any]]] = {
        "promoted": [],
        "durable_raw": [],
        "candidate": [],
        "denied_style": [],
    }

    for raw_row in rows:
        ctx = _context(raw_row)

        promotion_state = _text(ctx.metadata.get("promotion_state")) or "missing"
        promotion_counts[promotion_state] += 1

        stage = _text(ctx.truth.get("stage")) or "missing"
        stage_counts[stage] += 1

        trust_tier = _text(ctx.metadata.get("trust_tier")) or "missing"
        trust_counts[trust_tier] += 1

        content_class = _text(ctx.metadata.get("content_class")) or "missing"
        content_class_counts[content_class] += 1

        failure_bucket = _failure_bucket(ctx)
        if failure_bucket:
            failure_counts[failure_bucket] += 1

        bucket = _sample_bucket(ctx)
        if bucket and len(samples[bucket]) < sample_size_per_bucket:
            samples[bucket].append(_sample_row(ctx))

    top_failures = [
        {"bucket": bucket, "count": count}
        for bucket, count in failure_counts.most_common(10)
    ]

    return {
        "run_id": run_id,
        "run_id_key": run_id_key,
        "generated_at": now_iso(),
        "raw_scrapes_total": len(rows),
        "promotion_state_counts": dict(promotion_counts),
        "ingestion_truth_stage_counts": dict(stage_counts),
        "trust_tier_counts": dict(trust_counts),
        "content_class_counts": dict(content_class_counts),
        "top_failure_buckets": top_failures,
        "samples": samples,
    }


async def fetch_raw_scrapes_for_run(
    *,
    db: Any,
    run_id: str,
    run_id_key: str = "manual_run_id",
) -> list[dict[str, Any]]:
    rows = await db._fetch(
        """
        SELECT
          rs.id,
          rs.created_at,
          rs.url,
          rs.error_message,
          rs.metadata,
          s.url AS source_url,
          s.type AS source_type,
          s.name AS source_name,
          j.name AS jurisdiction_name
        FROM raw_scrapes rs
        LEFT JOIN sources s ON s.id = rs.source_id
        LEFT JOIN jurisdictions j ON j.id::text = s.jurisdiction_id
        WHERE COALESCE(rs.metadata->>$1, '') = $2
        ORDER BY rs.created_at DESC
        """,
        run_id_key,
        run_id,
    )
    return [_to_dict(row) for row in rows]


async def generate_substrate_inspection_report(
    *,
    db: Any,
    run_id: str,
    run_id_key: str = "manual_run_id",
    sample_size_per_bucket: int = 5,
) -> dict[str, Any]:
    rows = await fetch_raw_scrapes_for_run(db=db, run_id=run_id, run_id_key=run_id_key)
    return build_substrate_inspection_report(
        run_id=run_id,
        rows=rows,
        run_id_key=run_id_key,
        sample_size_per_bucket=sample_size_per_bucket,
    )


def write_report_artifact(
    *,
    report: dict[str, Any],
    output_path: Path | None = None,
) -> Path:
    target = output_path or (ARTIFACT_DIR / f"{report['run_id']}_substrate_inspection_report.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Manual expansion run identifier.")
    parser.add_argument(
        "--run-id-key",
        default="manual_run_id",
        help="Metadata key used to stamp the run id in raw_scrapes.metadata.",
    )
    parser.add_argument(
        "--sample-size-per-bucket",
        type=int,
        default=5,
        help="Max sample rows per summary bucket.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path for the report JSON artifact.",
    )
    return parser.parse_args()


async def _main_async(args: argparse.Namespace) -> Path:
    from db.postgres_client import PostgresDB

    db = PostgresDB()
    report = await generate_substrate_inspection_report(
        db=db,
        run_id=args.run_id,
        run_id_key=args.run_id_key,
        sample_size_per_bucket=args.sample_size_per_bucket,
    )
    output_path = Path(args.output) if args.output else None
    artifact_path = write_report_artifact(report=report, output_path=output_path)
    print(json.dumps({"artifact_path": str(artifact_path), "run_id": args.run_id}, indent=2))
    return artifact_path


def main() -> None:
    args = parse_args()
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
