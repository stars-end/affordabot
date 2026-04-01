#!/usr/bin/env python3
"""Evaluate substrate promotion candidates with rules-first fallback."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from typing import Any

from db.postgres_client import PostgresDB
from services.substrate_promotion import GLM46VPromotionBoundary
from services.substrate_promotion import apply_promotion_decision
from services.substrate_promotion import evaluate_with_fallback
from services.substrate_promotion import parse_json_blob


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--enable-llm", action="store_true")
    return parser.parse_args()


async def fetch_candidates(db: PostgresDB, limit: int) -> list[dict[str, Any]]:
    rows = await db._fetch(
        """
        SELECT
          rs.id,
          rs.url AS raw_url,
          rs.metadata AS raw_metadata,
          s.url AS source_url,
          s.metadata AS source_metadata
        FROM raw_scrapes rs
        JOIN sources s ON s.id = rs.source_id
        WHERE COALESCE(rs.metadata->>'promotion_state', '') IN ('', 'captured_candidate', 'durable_raw')
        ORDER BY rs.created_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(row) for row in rows]


def merge_eval_metadata(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    raw_metadata = parse_json_blob(row.get("raw_metadata"))
    source_metadata = parse_json_blob(row.get("source_metadata"))
    eval_metadata = {**source_metadata, **raw_metadata}

    canonical_url = (
        eval_metadata.get("canonical_url")
        or row.get("raw_url")
        or row.get("source_url")
        or ""
    )
    eval_metadata["canonical_url"] = canonical_url
    eval_metadata.setdefault("url", row.get("raw_url") or row.get("source_url") or "")
    if "trust_tier" not in eval_metadata:
        eval_metadata["trust_tier"] = source_metadata.get("trust_tier")
    return raw_metadata, eval_metadata, canonical_url


async def evaluate_candidates(args: argparse.Namespace) -> dict[str, Any]:
    db = PostgresDB()
    rows = await fetch_candidates(db, args.limit)

    llm_boundary = GLM46VPromotionBoundary(
        api_key=os.getenv("ZAI_API_KEY"),
        enabled=args.enable_llm or os.getenv("SUBSTRATE_PROMOTION_ENABLE_LLM") == "1",
    )

    method_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    updated = 0

    for row in rows:
        raw_metadata, eval_metadata, canonical_url = merge_eval_metadata(row)
        decision = await evaluate_with_fallback(
            metadata=eval_metadata,
            llm_boundary=llm_boundary,
        )
        updated_metadata = dict(raw_metadata)
        for key in (
            "canonical_url",
            "document_type",
            "source_type",
            "content_class",
            "trust_tier",
            "capture_method",
            "substrate_version",
            "title",
            "preview_text",
            "ingestion_truth",
        ):
            if key not in updated_metadata and key in eval_metadata:
                updated_metadata[key] = eval_metadata[key]

        updated_metadata = apply_promotion_decision(
            metadata=updated_metadata,
            decision=decision,
            canonical_url=canonical_url,
        )
        method_counts[decision.method] += 1
        reason_counts[decision.reason_category] += 1

        if not args.dry_run:
            await db._execute(
                "UPDATE raw_scrapes SET metadata = $1 WHERE id = $2",
                json.dumps(updated_metadata),
                row["id"],
            )
            updated += 1

    return {
        "candidate_count": len(rows),
        "updated_count": updated,
        "dry_run": args.dry_run,
        "method_counts": dict(method_counts),
        "reason_counts": dict(reason_counts),
        "llm_enabled": llm_boundary.enabled,
        "llm_model": llm_boundary.model,
    }


def main() -> None:
    args = parse_args()
    result = asyncio.run(evaluate_candidates(args))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
