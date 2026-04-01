from datetime import datetime, timezone

import pytest

from scripts.substrate.inspect_substrate_health import (
    apply_filters,
    build_summary,
    normalize_row,
    parse_args,
)


def test_parse_args_supports_filters() -> None:
    args = parse_args(
        [
            "--hours",
            "24",
            "--limit",
            "10",
            "--promotion-state",
            "durable_raw",
            "--trust-tier",
            "primary_government",
            "--ingestion-stage",
            "parsed",
            "--include-legacy",
        ]
    )
    assert args.hours == 24
    assert args.limit == 10
    assert args.promotion_state == "durable_raw"
    assert args.trust_tier == "primary_government"
    assert args.ingestion_stage == "parsed"
    assert args.include_legacy is True


def test_normalize_row_merges_promotion_and_ingestion_truth() -> None:
    row = {
        "id": "scrape-1",
        "created_at": datetime.now(timezone.utc),
        "processed": False,
        "error_message": "Vector Upsert Failed: expected 4096 dimensions, not 1536",
        "raw_url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=1",
        "storage_uri": "s3://bucket/key",
        "source_id": "source-1",
        "source_name": "San Jose Meetings",
        "source_url": "https://sanjose.legistar.com/",
        "source_metadata": {
            "trust_tier": "primary_government",
            "source_type": "meetings",
        },
        "raw_metadata": {
            "canonical_url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=1",
            "document_type": "meeting_detail",
            "content_class": "html_text",
            "trust_host_classification": "official_civic_partner",
            "promotion_state": "durable_raw",
            "promotion_method": "rules",
            "promotion_reason_category": "unclear",
            "ingestion_truth": {
                "stage": "vector_upsert_failed",
                "retrievable": False,
            },
        },
    }

    normalized = normalize_row(row)
    assert normalized["raw_scrape_id"] == "scrape-1"
    assert normalized["canonical_url"] == "https://sanjose.legistar.com/MeetingDetail.aspx?ID=1"
    assert normalized["trust_tier"] == "primary_government"
    assert normalized["promotion_state"] == "durable_raw"
    assert normalized["promotion_reason_category"] == "unclear"
    assert normalized["ingestion_stage"] == "vector_upsert_failed"
    assert normalized["retrievable"] is False
    assert normalized["last_error"] == "Vector Upsert Failed: expected 4096 dimensions, not 1536"
    assert normalized["recent_errors"][0] == normalized["last_error"]
    assert normalized["storage_uri_present"] is True
    assert normalized["legacy_unknown"] is False


def test_normalize_row_marks_missing_truth_as_legacy_unknown() -> None:
    row = {
        "id": "legacy-1",
        "created_at": datetime.now(timezone.utc),
        "processed": True,
        "error_message": None,
        "raw_url": "https://example.com/legacy",
        "storage_uri": None,
        "source_id": "source-1",
        "source_name": "Legacy",
        "source_url": "https://example.com",
        "source_metadata": {},
        "raw_metadata": {},
    }

    normalized = normalize_row(row)
    assert normalized["legacy_unknown"] is True
    assert normalized["ingestion_stage"] == "legacy_unknown"
    assert normalized["promotion_state"] is None


def test_apply_filters_hides_legacy_by_default() -> None:
    records = [
        {
            "promotion_state": None,
            "trust_tier": None,
            "ingestion_stage": "legacy_unknown",
            "legacy_unknown": True,
        },
        {
            "promotion_state": "durable_raw",
            "trust_tier": "primary_government",
            "ingestion_stage": "ingest_skipped_non_text",
            "legacy_unknown": False,
        },
    ]

    filtered = apply_filters(
        records,
        promotion_state=None,
        trust_tier=None,
        ingestion_stage=None,
        include_legacy=False,
    )
    assert len(filtered) == 1
    assert filtered[0]["promotion_state"] == "durable_raw"


def test_build_summary_counts_error_and_retrievable() -> None:
    summary = build_summary(
        [
            {
                "promotion_state": "durable_raw",
                "trust_tier": "primary_government",
                "ingestion_stage": "ingest_skipped_non_text",
                "legacy_unknown": False,
                "retrievable": False,
                "last_error": None,
            },
            {
                "promotion_state": "promoted_substrate",
                "trust_tier": "primary_government",
                "ingestion_stage": "embedded",
                "legacy_unknown": False,
                "retrievable": True,
                "last_error": "test",
            },
        ]
    )

    assert summary["record_count"] == 2
    assert summary["promotion_states"]["durable_raw"] == 1
    assert summary["promotion_states"]["promoted_substrate"] == 1
    assert summary["retrievable_true_count"] == 1
    assert summary["error_count"] == 1
