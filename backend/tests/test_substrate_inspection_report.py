from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from scripts.substrate.substrate_inspection_report import (
    build_substrate_inspection_report,
    fetch_raw_scrapes_for_run,
    generate_storage_integrity_checks,
    generate_substrate_inspection_report,
    write_report_artifact,
)


def _row(
    *,
    row_id: str,
    promotion_state: str,
    trust_tier: str,
    stage: str,
    reason: str = "",
    error_message: str = "",
    storage_uri: str = "",
    data: dict | None = None,
    document_id: str | None = None,
) -> dict:
    return {
        "id": row_id,
        "created_at": datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc),
        "url": f"https://example.org/{row_id}",
        "source_url": "https://source.example.org",
        "source_name": "Example Source",
        "source_type": "meetings",
        "jurisdiction_name": "City of Test",
        "error_message": error_message,
        "storage_uri": storage_uri,
        "data": data or {},
        "document_id": document_id,
        "metadata": {
            "document_type": "agenda",
            "content_class": "html_text",
            "promotion_state": promotion_state,
            "promotion_reason_category": reason,
            "trust_tier": trust_tier,
            "ingestion_truth": {
                "stage": stage,
                "retrievable": stage == "retrievable",
            },
        },
    }


def test_build_substrate_inspection_report_aggregates_counts_and_samples():
    rows = [
        _row(
            row_id="promoted-1",
            promotion_state="promoted_substrate",
            trust_tier="primary_government",
            stage="retrievable",
        ),
        _row(
            row_id="durable-1",
            promotion_state="durable_raw",
            trust_tier="official_partner",
            stage="raw_captured",
        ),
        _row(
            row_id="candidate-1",
            promotion_state="captured_candidate",
            trust_tier="official_partner",
            stage="raw_captured",
            reason="captured_preserved_official",
        ),
        _row(
            row_id="denied-1",
            promotion_state="captured_candidate",
            trust_tier="non_official",
            stage="raw_captured",
            reason="captured_untrusted_needs_review",
        ),
        _row(
            row_id="failed-1",
            promotion_state="durable_raw",
            trust_tier="official_partner",
            stage="vector_upsert_failed",
            error_message="upsert crashed",
        ),
    ]

    report = build_substrate_inspection_report(
        run_id="run-42",
        rows=rows,
        sample_size_per_bucket=2,
    )

    assert report["run_id"] == "run-42"
    assert report["raw_scrapes_total"] == 5
    assert report["promotion_state_counts"]["promoted_substrate"] == 1
    assert report["promotion_state_counts"]["durable_raw"] == 2
    assert report["promotion_state_counts"]["captured_candidate"] == 2
    assert report["ingestion_truth_stage_counts"]["vector_upsert_failed"] == 1
    assert report["trust_tier_counts"]["primary_government"] == 1
    assert report["trust_tier_counts"]["official_partner"] == 3
    assert report["trust_tier_counts"]["non_official"] == 1
    assert report["content_class_counts"]["html_text"] == 5

    top_failure_names = {item["bucket"] for item in report["top_failure_buckets"]}
    assert "ingestion_stage:vector_upsert_failed" in top_failure_names
    assert "promotion_reason:captured_untrusted_needs_review" in top_failure_names

    assert len(report["samples"]["promoted"]) == 1
    assert len(report["samples"]["durable_raw"]) == 2
    assert len(report["samples"]["candidate"]) == 1
    assert len(report["samples"]["denied_style"]) == 1
    assert report["samples"]["denied_style"][0]["raw_scrape_id"] == "denied-1"


def test_build_substrate_inspection_report_handles_missing_metadata():
    report = build_substrate_inspection_report(
        run_id="run-empty",
        rows=[{"id": "x1", "metadata": {}}],
    )

    assert report["promotion_state_counts"]["missing"] == 1
    assert report["ingestion_truth_stage_counts"]["missing"] == 1
    assert report["trust_tier_counts"]["missing"] == 1
    assert report["top_failure_buckets"] == []


@pytest.mark.asyncio
async def test_fetch_raw_scrapes_for_run_queries_by_metadata_key():
    db = AsyncMock()
    db._fetch.return_value = [
        {
            "id": "abc",
            "metadata": {"manual_run_id": "run-99"},
            "created_at": datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc),
        }
    ]

    rows = await fetch_raw_scrapes_for_run(
        db=db,
        run_id="run-99",
        run_id_key="manual_run_id",
    )

    assert len(rows) == 1
    assert rows[0]["id"] == "abc"
    assert db._fetch.await_count == 1
    call = db._fetch.await_args
    assert "COALESCE(rs.metadata->>$1, '') = $2" in call.args[0]
    assert call.args[1] == "manual_run_id"
    assert call.args[2] == "run-99"


@pytest.mark.asyncio
async def test_generate_substrate_inspection_report_uses_fetch_and_build():
    db = AsyncMock()
    db._fetch.return_value = [
        _row(
            row_id="promoted-one",
            promotion_state="promoted_substrate",
            trust_tier="primary_government",
            stage="retrievable",
        )
    ]

    report = await generate_substrate_inspection_report(
        db=db,
        run_id="run-generate",
    )

    assert report["run_id"] == "run-generate"
    assert report["raw_scrapes_total"] == 1
    assert report["promotion_state_counts"]["promoted_substrate"] == 1


@pytest.mark.asyncio
async def test_generate_storage_integrity_checks_passes_when_storage_and_vectors_match(
    monkeypatch,
):
    rows = [
        _row(
            row_id="pdf-1",
            promotion_state="durable_raw",
            trust_tier="primary_government",
            stage="retrievable",
            storage_uri="objects/pdfs/pdf-1.pdf",
            document_id="doc-1",
        )
    ]
    rows[0]["metadata"]["content_class"] = "pdf_binary"
    rows[0]["metadata"]["ingestion_truth"]["retrievable"] = True

    db = AsyncMock()

    async def _fetch_side_effect(query, *args):
        if "FROM raw_scrapes rs" in query:
            return rows
        raise AssertionError(f"unexpected fetch query: {query}")

    async def _fetchrow_side_effect(query, *args):
        if "COUNT(*) AS cnt FROM document_chunks" in query:
            return {"cnt": 2}
        raise AssertionError(f"unexpected fetchrow query: {query}")

    db._fetch.side_effect = _fetch_side_effect
    db._fetchrow.side_effect = _fetchrow_side_effect

    class FakeStorage:
        def __init__(self):
            self.client = object()

        async def download(self, path):
            assert path == "objects/pdfs/pdf-1.pdf"
            return b"%PDF"

    monkeypatch.setattr(
        "scripts.substrate.substrate_inspection_report.S3Storage",
        FakeStorage,
    )

    report = await generate_storage_integrity_checks(
        db=db,
        run_id="run-storage-pass",
        resolved_targets_count=1,
        attempted_targets_count=1,
        attempted_raw_capture_operations=1,
    )

    assert report["overall_status"] == "pass"
    assert report["object_storage_check"]["status"] == "pass"
    assert report["vector_integrity_check"]["status"] == "pass"
    assert report["run_coverage_check"]["status"] == "pass"


@pytest.mark.asyncio
async def test_generate_storage_integrity_checks_flags_failures_and_gaps(monkeypatch):
    rows = [
        _row(
            row_id="pdf-2",
            promotion_state="durable_raw",
            trust_tier="primary_government",
            stage="retrievable",
            storage_uri="",
            document_id="doc-2",
        )
    ]
    rows[0]["metadata"]["content_class"] = "pdf_binary"
    rows[0]["metadata"]["ingestion_truth"]["retrievable"] = True

    db = AsyncMock()

    async def _fetch_side_effect(query, *args):
        if "FROM raw_scrapes rs" in query:
            return rows
        raise AssertionError(f"unexpected fetch query: {query}")

    async def _fetchrow_side_effect(query, *args):
        if "COUNT(*) AS cnt FROM document_chunks" in query:
            return {"cnt": 0}
        raise AssertionError(f"unexpected fetchrow query: {query}")

    db._fetch.side_effect = _fetch_side_effect
    db._fetchrow.side_effect = _fetchrow_side_effect

    class FakeStorage:
        def __init__(self):
            self.client = object()

        async def download(self, path):
            return b""

    monkeypatch.setattr(
        "scripts.substrate.substrate_inspection_report.S3Storage",
        FakeStorage,
    )

    report = await generate_storage_integrity_checks(
        db=db,
        run_id="run-storage-fail",
        resolved_targets_count=2,
        attempted_targets_count=1,
        attempted_raw_capture_operations=3,
    )

    assert report["overall_status"] == "fail"
    assert report["object_storage_check"]["status"] == "fail"
    assert report["object_storage_check"]["missing_reference_count"] == 1
    assert report["vector_integrity_check"]["status"] == "fail"
    assert report["vector_integrity_check"]["rows_with_zero_chunks_count"] == 1
    assert report["run_coverage_check"]["status"] == "warn"
    assert report["run_coverage_check"]["target_attempt_gap"] == 1
    assert report["run_coverage_check"]["missing_stamped_rows_from_attempted_capture_ops"] == 2


def test_write_report_artifact_writes_json(tmp_path: Path):
    report = {
        "run_id": "run-file",
        "raw_scrapes_total": 0,
        "promotion_state_counts": {},
        "ingestion_truth_stage_counts": {},
        "trust_tier_counts": {},
        "content_class_counts": {},
        "top_failure_buckets": [],
        "samples": {
            "promoted": [],
            "durable_raw": [],
            "candidate": [],
            "denied_style": [],
        },
    }

    target = tmp_path / "report.json"
    written = write_report_artifact(report=report, output_path=target)

    assert written == target
    assert target.exists()
    assert '"run_id": "run-file"' in target.read_text(encoding="utf-8")
