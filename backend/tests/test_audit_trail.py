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
    import os

    # Set custom artifact directory BEFORE importing module
    artifact_dir = str(tmp_path / "audit_artifacts")
    monkeypatch.setenv("ARTIFACT_DIR", artifact_dir)

    # Reimport AuditLogger to pick up new env var
    import importlib
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
    import os

    artifact_dir = str(tmp_path / "audit_artifacts")
    monkeypatch.setenv("ARTIFACT_DIR", artifact_dir)

    import importlib
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
    import os

    artifact_dir = str(tmp_path / "audit_artifacts")
    monkeypatch.setenv("ARTIFACT_DIR", artifact_dir)

    import importlib
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
    import os

    artifact_dir = str(tmp_path / "audit_artifacts")
    monkeypatch.setenv("ARTIFACT_DIR", artifact_dir)

    import importlib
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
