"""
Test audit trail functionality (pipeline_steps).

This test verifies audit trail system that logs pipeline execution steps.
"""

import pytest
import json
from pathlib import Path


@pytest.mark.asyncio
async def test_audit_logger_structure():
    """Test AuditLogger initialization and structure."""
    from services.audit.logger import AuditLogger

    run_id = "test-audit-run-001"
    audit = AuditLogger(run_id, None)

    assert audit.run_id == run_id
    assert audit.steps == []
    assert audit.db is None


@pytest.mark.asyncio
async def test_audit_logger_writes_to_file(tmp_path, monkeypatch):
    """Test that AuditLogger writes JSON artifacts to file."""

    # Set custom artifact directory BEFORE importing module
    artifact_dir = str(tmp_path / "audit_artifacts")
    monkeypatch.setenv("ARTIFACT_DIR", artifact_dir)

    # Reimport AuditLogger to pick up new env var
    import sys

    if "services.audit.logger" in sys.modules:
        del sys.modules["services.audit.logger"]
    from services.audit.logger import AuditLogger

    run_id = "test-audit-run-003"
    audit = AuditLogger(run_id, None)

    # Log step
    await audit.log_step(
        step_number=1,
        step_name="step1",
        status="completed",
        input_context={},
        output_result={},
        duration_ms=100,
    )

    # Verify file was created
    log_file = Path(artifact_dir) / f"audit_{run_id}.json"
    assert log_file.exists()

    # Verify file content
    with open(log_file, "r") as f:
        steps = json.load(f)
        assert len(steps) == 1
        assert steps[0]["step_name"] == "step1"
        assert steps[0]["status"] == "completed"
        assert steps[0]["run_id"] == run_id
        assert steps[0]["step_number"] == 1


@pytest.mark.asyncio
async def test_audit_logger_multiple_steps(tmp_path, monkeypatch):
    """Test that AuditLogger handles multiple steps correctly."""

    artifact_dir = str(tmp_path / "audit_artifacts")
    monkeypatch.setenv("ARTIFACT_DIR", artifact_dir)

    import sys

    if "services.audit.logger" in sys.modules:
        del sys.modules["services.audit.logger"]
    from services.audit.logger import AuditLogger

    run_id = "test-audit-run-004"
    audit = AuditLogger(run_id, None)

    # Log multiple steps
    await audit.log_step(
        step_number=1,
        step_name="research",
        status="completed",
        input_context={"bill_id": "TEST-001"},
        output_result={"result": "test"},
        duration_ms=1000,
    )

    await audit.log_step(
        step_number=2,
        step_name="generate",
        status="completed",
        input_context={},
        output_result={"analysis": "test result"},
        duration_ms=1500,
    )

    # Verify file contains all steps
    log_file = Path(artifact_dir) / f"audit_{run_id}.json"
    with open(log_file, "r") as f:
        steps = json.load(f)
        assert len(steps) == 2
        assert steps[0]["step_name"] == "research"
        assert steps[1]["step_name"] == "generate"
        assert steps[0]["step_number"] == 1
        assert steps[1]["step_number"] == 2


@pytest.mark.asyncio
async def test_audit_logger_step_structure(tmp_path, monkeypatch):
    """Test that logged steps have all required fields."""

    artifact_dir = str(tmp_path / "audit_artifacts")
    monkeypatch.setenv("ARTIFACT_DIR", artifact_dir)

    import sys

    if "services.audit.logger" in sys.modules:
        del sys.modules["services.audit.logger"]
    from services.audit.logger import AuditLogger

    run_id = "test-audit-run-005"
    audit = AuditLogger(run_id, None)

    await audit.log_step(
        step_number=1,
        step_name="test_step",
        status="completed",
        input_context={"input_key": "input_value"},
        output_result={"output_key": "output_value"},
        model_info={"model": "test-model", "provider": "test-provider"},
        duration_ms=500,
    )

    # Verify step structure
    log_file = Path(artifact_dir) / f"audit_{run_id}.json"
    with open(log_file, "r") as f:
        steps = json.load(f)
        assert len(steps) == 1
        step = steps[0]

        # Verify all required fields
        assert "run_id" in step
        assert "step_number" in step
        assert "step_name" in step
        assert "status" in step
        assert "input_context" in step
        assert "output_result" in step
        assert "model_info" in step
        assert "duration_ms" in step
        assert "timestamp" in step

        # Verify values
        assert step["run_id"] == run_id
        assert step["step_number"] == 1
        assert step["step_name"] == "test_step"
        assert step["status"] == "completed"
        assert step["duration_ms"] == 500


@pytest.mark.asyncio
async def test_audit_logger_failed_step(tmp_path, monkeypatch):
    """Test that AuditLogger logs failed steps correctly."""

    artifact_dir = str(tmp_path / "audit_artifacts")
    monkeypatch.setenv("ARTIFACT_DIR", artifact_dir)

    import sys

    if "services.audit.logger" in sys.modules:
        del sys.modules["services.audit.logger"]
    from services.audit.logger import AuditLogger

    run_id = "test-audit-run-006"
    audit = AuditLogger(run_id, None)

    await audit.log_step(
        step_number=2,
        step_name="failed_step",
        status="failed",
        input_context={"attempt": 1},
        output_result={"error": "Test failure message"},
        model_info={"model": "test-model"},
        duration_ms=500,
    )

    # Verify failed step is logged
    log_file = Path(artifact_dir) / f"audit_{run_id}.json"
    with open(log_file, "r") as f:
        steps = json.load(f)
        assert len(steps) == 1
        assert steps[0]["status"] == "failed"
        assert "error" in steps[0]["output_result"]


@pytest.mark.asyncio
async def test_slack_summary_format_includes_audit_link():
    """Slack summary payload must include deep-link to /admin/audits/trace/{run_id}."""
    from services.slack_summary import format_slack_summary, build_audit_url

    run_id = "abc-123"
    bill_id = "SB-277"
    jurisdiction = "California"
    steps = [
        {
            "step_name": "ingestion_source",
            "status": "completed",
            "output_result": {
                "raw_scrape_id": "scrape-1",
                "source_url": "https://leginfo.ca.gov",
                "source_text_present": True,
            },
        },
        {
            "step_name": "chunk_index",
            "status": "completed",
            "output_result": {
                "chunk_count": 12,
                "document_id": "doc-abc-123",
            },
        },
        {
            "step_name": "research",
            "status": "completed",
            "output_result": {
                "rag_chunks": 3,
                "web_sources": 2,
                "evidence_envelopes": 2,
                "is_sufficient": True,
            },
        },
        {
            "step_name": "sufficiency_gate",
            "status": "completed",
            "output_result": {
                "sufficiency_state": "quantified",
                "rag_chunks_retrieved": 3,
                "web_research_sources_found": 2,
            },
        },
        {
            "step_name": "generate",
            "status": "completed",
            "output_result": {
                "sufficiency_state": "quantified",
                "impacts": [{"impact_number": 1}],
                "quantification_eligible": True,
            },
        },
        {
            "step_name": "review",
            "status": "completed",
            "output_result": {
                "passed": True,
                "factual_errors": [],
                "missing_impacts": [],
            },
        },
        {
            "step_name": "persistence",
            "status": "completed",
            "output_result": {
                "analysis_stored": True,
                "legislation_id": "leg-42",
                "impacts_count": 1,
                "sufficiency_state": "quantified",
                "quantification_eligible": True,
                "total_impact_p50": 15000,
            },
        },
    ]

    payload = format_slack_summary(
        run_id=run_id,
        bill_id=bill_id,
        jurisdiction=jurisdiction,
        status="completed",
        started_at="2026-03-21T10:00:00Z",
        completed_at="2026-03-21T10:05:00Z",
        trigger_source="manual",
        steps=steps,
        result={"sufficiency_state": "quantified"},
    )

    assert "blocks" in payload
    assert len(payload["blocks"]) == 3
    blocks_text = str(payload["blocks"])

    assert build_audit_url(run_id) in blocks_text
    assert "/admin/bill-truth/" in blocks_text
    assert "trigger=manual" in blocks_text
    assert "Scrape/source" in blocks_text
    assert "Chunk/index" in blocks_text
    assert "Research:" in blocks_text
    assert "Sufficiency gate:" in blocks_text
    assert "Generate:" in blocks_text
    assert "Review:" in blocks_text
    assert "Persistence:" in blocks_text


@pytest.mark.asyncio
async def test_slack_summary_failure_format():
    """Slack summary for failed runs includes error details."""
    from services.slack_summary import format_slack_summary

    payload = format_slack_summary(
        run_id="fail-1",
        bill_id="TEST-001",
        jurisdiction="California",
        status="failed",
        started_at="2026-03-21T10:00:00Z",
        completed_at="2026-03-21T10:01:00Z",
        trigger_source="manual",
        steps=[
            {
                "step_name": "pipeline_failure",
                "status": "failed",
                "output_result": {"error": "Rate limit exceeded"},
            }
        ],
    )

    blocks_text = str(payload["blocks"])
    assert "Pipeline failure" in blocks_text
    assert "Rate limit exceeded" in blocks_text
    assert "/admin/audits/trace/fail-1" in blocks_text


@pytest.mark.asyncio
async def test_slack_summary_skipped_without_webhook():
    """emit_slack_summary returns False gracefully when no webhook is configured."""
    from services.slack_summary import emit_slack_summary

    result = await emit_slack_summary(
        webhook_url=None,
        run_id="test-1",
        bill_id="SB-1",
        jurisdiction="CA",
        status="completed",
        started_at="2026-03-21T10:00:00Z",
        completed_at="2026-03-21T10:05:00Z",
        trigger_source="manual",
        steps=[],
    )
    assert result is False


@pytest.mark.asyncio
async def test_audit_link_generation():
    """build_audit_url and build_bill_truth_url produce correct paths."""
    from services.slack_summary import build_audit_url, build_bill_truth_url

    audit = build_audit_url("run-42")
    assert "/admin/audits/trace/run-42" in audit
    truth = build_bill_truth_url("California", "SB-277")
    assert "/admin/bill-truth/california/SB-277" in truth
