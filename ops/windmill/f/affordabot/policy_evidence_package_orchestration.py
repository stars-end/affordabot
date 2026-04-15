"""Windmill orchestration surface for policy evidence package flow.

This script intentionally owns orchestration only. It never ranks sources,
selects assumptions, computes economic formulas, or writes storage directly.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional


CONTRACT_VERSION = "2026-04-15.windmill-policy-evidence.v1"
ALLOWED_COMMAND_CLIENTS = {"stub"}
READY_STATUSES = {"ready"}
BLOCKED_STATUSES = {"blocked", "insufficient"}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _refs(
    *,
    windmill_workspace: str,
    windmill_flow_path: str,
    windmill_run_id: str,
    windmill_job_id: str,
    windmill_step_id: str,
    idempotency_key: str,
) -> dict[str, str]:
    return {
        "windmill_workspace": windmill_workspace,
        "windmill_flow_path": windmill_flow_path,
        "windmill_run_id": windmill_run_id,
        "windmill_job_id": windmill_job_id,
        "windmill_step_id": windmill_step_id,
        "idempotency_key": idempotency_key,
    }


def _stub_command(
    *,
    command_name: str,
    refs: dict[str, str],
    jurisdiction: str,
    query_family: str,
    package_id: str,
    package_readiness_status: str,
    gate_status: str,
    previous: Optional[dict[str, Any]],
) -> dict[str, Any]:
    command_id = f"cmd-{_hash(json.dumps({'name': command_name, **refs}, sort_keys=True))}"
    base = {
        "status": "succeeded",
        "command_name": command_name,
        "command_id": command_id,
        "decision_reason": "ok",
        "retry_class": "none",
        "refs": refs,
        "jurisdiction": jurisdiction,
        "query_family": query_family,
    }

    if command_name == "fetch_scraped_candidates":
        return {
            **base,
            "scraped_snapshot_id": f"snap-scraped-{_hash(jurisdiction + query_family)}",
            "scraped_candidate_count": 3,
        }
    if command_name == "fetch_structured_candidates":
        return {
            **base,
            "structured_snapshot_id": f"snap-structured-{_hash(jurisdiction)}",
            "structured_candidate_count": 2,
        }
    if command_name == "build_policy_evidence_package":
        if not previous:
            return {
                **base,
                "status": "failed",
                "decision_reason": "missing_inputs",
                "retry_class": "non_retryable_validation",
                "error": "build_requires_candidate_inputs",
            }
        return {
            **base,
            "package_id": package_id,
            "package_readiness_status": package_readiness_status,
            "gate_status": gate_status,
        }
    if command_name == "persist_readback_boundary":
        if not previous:
            return {
                **base,
                "status": "failed",
                "decision_reason": "missing_package",
                "retry_class": "non_retryable_validation",
                "error": "persist_requires_package_output",
            }
        return {
            **base,
            "package_id": package_id,
            "storage_refs": {
                "postgres_package_row": f"policy_evidence_packages:{package_id}",
                "minio_package_artifact": (
                    f"minio://policy-evidence/packages/{package_id}.json"
                ),
                "pgvector_chunk_projection": (
                    f"pgvector://document_chunks/{_hash(package_id)}"
                ),
            },
            "decision_reason": "persist_boundary_called",
        }
    if command_name == "evaluate_package_readiness":
        if package_readiness_status in BLOCKED_STATUSES:
            return {
                **base,
                "status": "blocked",
                "package_id": package_id,
                "package_readiness_status": package_readiness_status,
                "gate_status": gate_status,
                "decision_reason": "package_not_ready_for_economic_handoff",
                "retry_class": "retry_after_new_evidence",
            }
        return {
            **base,
            "package_id": package_id,
            "package_readiness_status": "ready",
            "gate_status": gate_status,
            "decision_reason": "package_ready_for_economic_handoff",
        }
    if command_name == "summarize_orchestration":
        previous_status = previous.get("status", "failed") if previous else "failed"
        flow_status = "succeeded" if previous_status == "succeeded" else "blocked"
        return {
            **base,
            "status": flow_status,
            "package_id": package_id,
            "package_readiness_status": package_readiness_status,
            "gate_status": gate_status,
            "decision_reason": (
                "orchestration_completed"
                if flow_status == "succeeded"
                else "orchestration_blocked"
            ),
        }

    return {
        **base,
        "status": "failed",
        "decision_reason": "unsupported_command",
        "retry_class": "non_retryable_validation",
        "error": f"unsupported_command:{command_name}",
    }


def _run_scope_pipeline(
    *,
    contract_version: str,
    windmill_workspace: str,
    windmill_flow_path: str,
    windmill_run_id: str,
    windmill_job_id: str,
    idempotency_key: str,
    jurisdiction: str,
    query_family: str,
    package_id: str,
    package_readiness_status: str,
    gate_status: str,
    command_client: str,
) -> dict[str, Any]:
    if command_client not in ALLOWED_COMMAND_CLIENTS:
        return {
            "status": "failed",
            "error": f"unsupported_command_client:{command_client}",
            "contract_version": contract_version,
        }

    steps: dict[str, Any] = {}

    def invoke(step_name: str, command_name: str, previous: Optional[dict[str, Any]]) -> dict[str, Any]:
        step_refs = _refs(
            windmill_workspace=windmill_workspace,
            windmill_flow_path=windmill_flow_path,
            windmill_run_id=windmill_run_id,
            windmill_job_id=f"{windmill_job_id}:{step_name}",
            windmill_step_id=step_name,
            idempotency_key=idempotency_key,
        )
        output = _stub_command(
            command_name=command_name,
            refs=step_refs,
            jurisdiction=jurisdiction,
            query_family=query_family,
            package_id=package_id,
            package_readiness_status=package_readiness_status,
            gate_status=gate_status,
            previous=previous,
        )
        output["contract_version"] = contract_version
        steps[step_name] = output
        return output

    scraped = invoke("fetch_scraped_candidates", "fetch_scraped_candidates", None)
    structured = invoke("fetch_structured_candidates", "fetch_structured_candidates", scraped)
    build = invoke(
        "build_policy_evidence_package",
        "build_policy_evidence_package",
        {"scraped": scraped, "structured": structured},
    )
    persist = invoke("persist_readback_boundary", "persist_readback_boundary", build)
    gate = invoke("evaluate_package_readiness", "evaluate_package_readiness", persist)
    summary = invoke("summarize_orchestration", "summarize_orchestration", gate)

    flow_status = summary["status"]
    return {
        "status": flow_status,
        "contract_version": contract_version,
        "command_client": command_client,
        "windmill_run_id": windmill_run_id,
        "package_id": package_id,
        "package_readiness_status": gate.get("package_readiness_status", package_readiness_status),
        "gate_status": gate.get("gate_status", gate_status),
        "retry_class": gate.get("retry_class", "none"),
        "decision_reason": gate.get("decision_reason", "unknown"),
        "storage_refs": persist.get("storage_refs", {}),
        "steps": steps,
    }


def main(
    *,
    step: str,
    contract_version: str = CONTRACT_VERSION,
    windmill_workspace: str = "affordabot",
    windmill_flow_path: str = "f/affordabot/policy_evidence_package_orchestration__flow",
    windmill_run_id: str = "windmill-run-id",
    windmill_job_id: str = "windmill-job-id",
    idempotency_key: str = "run:bd-3wefe.12",
    jurisdiction: str = "San Jose CA",
    query_family: str = "meeting_minutes",
    package_id: str = "pkg-bd-3wefe.12-sample",
    package_readiness_status: str = "ready",
    gate_status: str = "quantified",
    command_client: str = "stub",
    previous_step_output: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if step == "run_scope_pipeline":
        return _run_scope_pipeline(
            contract_version=contract_version,
            windmill_workspace=windmill_workspace,
            windmill_flow_path=windmill_flow_path,
            windmill_run_id=windmill_run_id,
            windmill_job_id=windmill_job_id,
            idempotency_key=idempotency_key,
            jurisdiction=jurisdiction,
            query_family=query_family,
            package_id=package_id,
            package_readiness_status=package_readiness_status,
            gate_status=gate_status,
            command_client=command_client,
        )
    if step == "failure_handler":
        return {
            "status": "failed",
            "contract_version": contract_version,
            "decision_reason": "failure_handler_invoked",
            "error": previous_step_output or {"error": "unknown"},
        }
    return {"status": "failed", "error": f"unsupported_step:{step}"}

