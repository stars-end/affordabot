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

from services.storage.s3_storage import S3Storage
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
BINARY_CONTENT_CLASSES = {"pdf_binary", "binary_blob"}


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


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


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
        "canonical_document_key": _text(ctx.row.get("canonical_document_key")),
        "previous_raw_scrape_id": _text(ctx.row.get("previous_raw_scrape_id")),
        "revision_number": ctx.row.get("revision_number"),
        "last_seen_at": _iso(ctx.row.get("last_seen_at")),
        "seen_count": ctx.row.get("seen_count"),
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


def _storage_key(ctx: RowContext) -> str:
    storage_uri = _text(ctx.row.get("storage_uri"))
    if storage_uri:
        return storage_uri
    data = parse_json_blob(ctx.row.get("data"))
    return _text(data.get("content_storage_uri"))


def _is_object_verification_relevant(ctx: RowContext) -> bool:
    content_class = _text(ctx.metadata.get("content_class")).lower()
    if content_class in BINARY_CONTENT_CLASSES:
        return True
    return bool(_storage_key(ctx))


async def _build_object_storage_integrity_check(
    *,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    relevant_rows: list[RowContext] = []
    for row in rows:
        ctx = _context(row)
        if _is_object_verification_relevant(ctx):
            relevant_rows.append(ctx)

    if not relevant_rows:
        return {
            "status": "skipped_no_relevant_rows",
            "relevant_rows": 0,
            "verified_readable_count": 0,
            "missing_reference_count": 0,
            "unreadable_count": 0,
            "missing_reference_samples": [],
            "unreadable_samples": [],
        }

    storage = S3Storage()
    if not storage.client:
        return {
            "status": "skipped_storage_not_configured",
            "relevant_rows": len(relevant_rows),
            "verified_readable_count": 0,
            "missing_reference_count": 0,
            "unreadable_count": 0,
            "missing_reference_samples": [],
            "unreadable_samples": [],
        }

    verified_readable_count = 0
    missing_reference_samples: list[dict[str, Any]] = []
    unreadable_samples: list[dict[str, Any]] = []

    for ctx in relevant_rows:
        key = _storage_key(ctx)
        if not key:
            if len(missing_reference_samples) < 10:
                missing_reference_samples.append(
                    {
                        "raw_scrape_id": _text(ctx.row.get("id")),
                        "content_class": _text(ctx.metadata.get("content_class")),
                        "reason": "missing_storage_uri_or_content_storage_uri",
                    }
                )
            continue

        try:
            await storage.download(key)
            verified_readable_count += 1
        except Exception as exc:  # pragma: no cover - network/runtime path
            if len(unreadable_samples) < 10:
                unreadable_samples.append(
                    {
                        "raw_scrape_id": _text(ctx.row.get("id")),
                        "storage_key": key,
                        "error": str(exc),
                    }
                )

    missing_reference_count = len(missing_reference_samples)
    unreadable_count = len(unreadable_samples)

    status = "pass"
    if missing_reference_count > 0 or unreadable_count > 0:
        status = "fail"

    return {
        "status": status,
        "relevant_rows": len(relevant_rows),
        "verified_readable_count": verified_readable_count,
        "missing_reference_count": missing_reference_count,
        "unreadable_count": unreadable_count,
        "missing_reference_samples": missing_reference_samples,
        "unreadable_samples": unreadable_samples,
    }


async def _build_vector_integrity_check(
    *,
    db: Any,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    retrievable_rows: list[RowContext] = []
    for row in rows:
        ctx = _context(row)
        stage = _text(ctx.truth.get("stage")).lower()
        retrievable = _truthy(ctx.truth.get("retrievable")) or stage == "retrievable"
        if retrievable:
            retrievable_rows.append(ctx)

    if not retrievable_rows:
        return {
            "status": "skipped_no_retrievable_rows",
            "retrievable_rows": 0,
            "with_document_id_count": 0,
            "missing_document_id_count": 0,
            "rows_with_chunks_count": 0,
            "rows_with_zero_chunks_count": 0,
            "total_chunk_rows_for_retrievable": 0,
            "zero_chunk_samples": [],
        }

    chunk_count_cache: dict[str, int] = {}
    rows_with_chunks_count = 0
    rows_with_zero_chunks_count = 0
    missing_document_id_count = 0
    total_chunk_rows_for_retrievable = 0
    zero_chunk_samples: list[dict[str, Any]] = []

    for ctx in retrievable_rows:
        document_id = _text(ctx.row.get("document_id")) or _text(ctx.truth.get("document_id"))
        if not document_id:
            missing_document_id_count += 1
            continue

        if document_id not in chunk_count_cache:
            count_row = await db._fetchrow(
                "SELECT COUNT(*) AS cnt FROM document_chunks WHERE document_id = $1",
                document_id,
            )
            cnt = 0
            if count_row and count_row.get("cnt") is not None:
                cnt = int(count_row["cnt"])
            chunk_count_cache[document_id] = cnt

        chunk_count = chunk_count_cache[document_id]
        total_chunk_rows_for_retrievable += chunk_count
        if chunk_count > 0:
            rows_with_chunks_count += 1
        else:
            rows_with_zero_chunks_count += 1
            if len(zero_chunk_samples) < 10:
                zero_chunk_samples.append(
                    {
                        "raw_scrape_id": _text(ctx.row.get("id")),
                        "document_id": document_id,
                    }
                )

    status = "pass"
    if missing_document_id_count > 0 or rows_with_zero_chunks_count > 0:
        status = "fail"

    return {
        "status": status,
        "retrievable_rows": len(retrievable_rows),
        "with_document_id_count": len(retrievable_rows) - missing_document_id_count,
        "missing_document_id_count": missing_document_id_count,
        "rows_with_chunks_count": rows_with_chunks_count,
        "rows_with_zero_chunks_count": rows_with_zero_chunks_count,
        "total_chunk_rows_for_retrievable": total_chunk_rows_for_retrievable,
        "zero_chunk_samples": zero_chunk_samples,
    }


def _build_run_coverage_check(
    *,
    stamped_raw_scrapes_count: int,
    resolved_targets_count: int | None,
    attempted_targets_count: int | None,
    attempted_raw_capture_operations: int | None,
) -> dict[str, Any]:
    if (
        resolved_targets_count is None
        or attempted_targets_count is None
        or attempted_raw_capture_operations is None
    ):
        return {
            "status": "insufficient_context",
            "stamped_raw_scrapes_count": stamped_raw_scrapes_count,
            "resolved_targets_count": resolved_targets_count,
            "attempted_targets_count": attempted_targets_count,
            "attempted_raw_capture_operations": attempted_raw_capture_operations,
            "target_attempt_gap": None,
            "missing_stamped_rows_from_attempted_capture_ops": None,
            "unexpected_extra_stamped_rows": None,
        }

    target_attempt_gap = max(0, resolved_targets_count - attempted_targets_count)
    missing_stamped_rows = max(
        0, attempted_raw_capture_operations - stamped_raw_scrapes_count
    )
    unexpected_extra_stamped_rows = max(
        0, stamped_raw_scrapes_count - attempted_raw_capture_operations
    )

    status = "pass"
    if unexpected_extra_stamped_rows > 0:
        status = "fail"
    elif target_attempt_gap > 0 or missing_stamped_rows > 0:
        status = "warn"

    return {
        "status": status,
        "stamped_raw_scrapes_count": stamped_raw_scrapes_count,
        "resolved_targets_count": resolved_targets_count,
        "attempted_targets_count": attempted_targets_count,
        "attempted_raw_capture_operations": attempted_raw_capture_operations,
        "target_attempt_gap": target_attempt_gap,
        "missing_stamped_rows_from_attempted_capture_ops": missing_stamped_rows,
        "unexpected_extra_stamped_rows": unexpected_extra_stamped_rows,
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
    unique_canonical_documents: set[str] = set()
    revisioned_rows_count = 0
    seen_again_rows_count = 0

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

        canonical_document_key = _text(ctx.row.get("canonical_document_key"))
        if canonical_document_key:
            unique_canonical_documents.add(canonical_document_key)

        revision_number = ctx.row.get("revision_number")
        if isinstance(revision_number, int) and revision_number > 1:
            revisioned_rows_count += 1

        seen_count = ctx.row.get("seen_count")
        if isinstance(seen_count, int) and seen_count > 1:
            seen_again_rows_count += 1

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
        "unique_canonical_documents": len(unique_canonical_documents),
        "revisioned_rows_count": revisioned_rows_count,
        "seen_again_rows_count": seen_again_rows_count,
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
          rs.data,
          rs.error_message,
          rs.storage_uri,
          rs.document_id,
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


async def generate_storage_integrity_checks(
    *,
    db: Any,
    run_id: str,
    run_id_key: str = "manual_run_id",
    resolved_targets_count: int | None = None,
    attempted_targets_count: int | None = None,
    attempted_raw_capture_operations: int | None = None,
) -> dict[str, Any]:
    rows = await fetch_raw_scrapes_for_run(db=db, run_id=run_id, run_id_key=run_id_key)
    object_storage_check = await _build_object_storage_integrity_check(rows=rows)
    vector_integrity_check = await _build_vector_integrity_check(db=db, rows=rows)
    run_coverage_check = _build_run_coverage_check(
        stamped_raw_scrapes_count=len(rows),
        resolved_targets_count=resolved_targets_count,
        attempted_targets_count=attempted_targets_count,
        attempted_raw_capture_operations=attempted_raw_capture_operations,
    )

    statuses = {
        object_storage_check["status"],
        vector_integrity_check["status"],
        run_coverage_check["status"],
    }
    overall_status = "pass"
    if "fail" in statuses:
        overall_status = "fail"
    elif statuses.intersection(
        {"warn", "insufficient_context", "skipped_no_relevant_rows", "skipped_no_retrievable_rows", "skipped_storage_not_configured"}
    ):
        overall_status = "warn"

    return {
        "run_id": run_id,
        "run_id_key": run_id_key,
        "generated_at": now_iso(),
        "raw_scrapes_total": len(rows),
        "overall_status": overall_status,
        "object_storage_check": object_storage_check,
        "vector_integrity_check": vector_integrity_check,
        "run_coverage_check": run_coverage_check,
    }


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
