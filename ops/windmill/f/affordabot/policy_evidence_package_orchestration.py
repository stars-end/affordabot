"""Windmill orchestration surface for policy evidence package flow.

This script intentionally owns orchestration only. It never ranks sources,
selects assumptions, computes economic formulas, or writes storage directly.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

import requests


CONTRACT_VERSION = "2026-04-15.windmill-policy-evidence.v1"
ALLOWED_COMMAND_CLIENTS = {"stub", "backend_endpoint"}
READY_STATUSES = {"ready"}
BLOCKED_STATUSES = {"blocked", "insufficient"}
BACKEND_ENDPOINT_CONNECT_TIMEOUT_SECONDS = 5
BACKEND_ENDPOINT_READ_TIMEOUT_SECONDS = 600
BACKEND_COMMAND_ENDPOINT_PATH = "/cron/pipeline/policy-evidence/command"


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


def _normalize_backend_endpoint_url(endpoint_url: str) -> str:
    candidate = endpoint_url.rstrip("/")
    if not candidate:
        return ""
    if candidate.endswith(BACKEND_COMMAND_ENDPOINT_PATH):
        return candidate
    return f"{candidate}{BACKEND_COMMAND_ENDPOINT_PATH}"


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


def _backend_endpoint_command(
    *,
    command_name: str,
    refs: dict[str, str],
    jurisdiction: str,
    query_family: str,
    package_id: str,
    package_readiness_status: str,
    gate_status: str,
    previous: Optional[dict[str, Any]],
    backend_endpoint_url: Optional[str],
    backend_endpoint_auth_token: Optional[str],
    backend_endpoint_timeout_seconds: int,
) -> dict[str, Any]:
    endpoint_url = _normalize_backend_endpoint_url((backend_endpoint_url or "").strip())
    auth_token = (backend_endpoint_auth_token or "").strip()
    if not endpoint_url:
        return {
            "status": "failed",
            "command_name": command_name,
            "refs": refs,
            "decision_reason": "backend_endpoint_missing_configuration",
            "retry_class": "non_retryable_validation",
            "error": "backend_endpoint_missing_configuration",
            "error_details": {"missing": ["backend_endpoint_url"]},
        }
    if not auth_token:
        return {
            "status": "failed",
            "command_name": command_name,
            "refs": refs,
            "decision_reason": "backend_endpoint_missing_configuration",
            "retry_class": "non_retryable_validation",
            "error": "backend_endpoint_missing_configuration",
            "error_details": {"missing": ["backend_endpoint_auth_token"]},
        }

    timeout_seconds = max(1, int(backend_endpoint_timeout_seconds))
    timeout_tuple = (BACKEND_ENDPOINT_CONNECT_TIMEOUT_SECONDS, timeout_seconds)
    request_headers = {
        "Authorization": f"Bearer {auth_token}",
        "X-PR-CRON-SECRET": auth_token,
        "X-PR-CRON-SOURCE": refs["windmill_flow_path"],
        "Content-Type": "application/json",
    }
    request_payload = {
        "command_name": command_name,
        "refs": refs,
        "jurisdiction": jurisdiction,
        "query_family": query_family,
        "package_id": package_id,
        "package_readiness_status": package_readiness_status,
        "gate_status": gate_status,
        "previous_step_output": previous,
    }

    try:
        response = requests.post(
            endpoint_url,
            json=request_payload,
            headers=request_headers,
            timeout=timeout_tuple,
        )
    except requests.RequestException as exc:
        return {
            "status": "failed",
            "command_name": command_name,
            "refs": refs,
            "decision_reason": "backend_endpoint_request_error",
            "retry_class": "retryable_transport_error",
            "error": "backend_endpoint_request_error",
            "error_details": {"detail": str(exc), "endpoint_url": endpoint_url},
        }

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = {"raw_text": response.text}

    if response.status_code >= 400:
        return {
            "status": "failed",
            "command_name": command_name,
            "refs": refs,
            "decision_reason": "backend_endpoint_http_error",
            "retry_class": "retryable_http_error",
            "error": "backend_endpoint_http_error",
            "error_details": {
                "http_status": response.status_code,
                "endpoint_url": endpoint_url,
                "response": response_payload,
            },
        }

    if not isinstance(response_payload, dict):
        return {
            "status": "failed",
            "command_name": command_name,
            "refs": refs,
            "decision_reason": "backend_endpoint_invalid_response",
            "retry_class": "non_retryable_validation",
            "error": "backend_endpoint_invalid_response",
            "error_details": {
                "detail": "response payload is not an object",
                "endpoint_url": endpoint_url,
            },
        }

    status = str(response_payload.get("status") or "").strip()
    if not status:
        return {
            "status": "failed",
            "command_name": command_name,
            "refs": refs,
            "decision_reason": "backend_endpoint_invalid_response",
            "retry_class": "non_retryable_validation",
            "error": "backend_endpoint_invalid_response",
            "error_details": {
                "detail": "missing status in response payload",
                "endpoint_url": endpoint_url,
                "response": response_payload,
            },
        }

    passthrough = dict(response_payload)
    passthrough.setdefault("command_name", command_name)
    passthrough.setdefault("refs", refs)
    passthrough.setdefault("jurisdiction", jurisdiction)
    passthrough.setdefault("query_family", query_family)
    passthrough.setdefault("decision_reason", "backend_endpoint_passthrough")
    passthrough.setdefault("retry_class", "none")
    return passthrough


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
    backend_endpoint_url: Optional[str],
    backend_endpoint_auth_token: Optional[str],
    backend_endpoint_timeout_seconds: int,
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
        if command_client == "stub":
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
        else:
            output = _backend_endpoint_command(
                command_name=command_name,
                refs=step_refs,
                jurisdiction=jurisdiction,
                query_family=query_family,
                package_id=package_id,
                package_readiness_status=package_readiness_status,
                gate_status=gate_status,
                previous=previous,
                backend_endpoint_url=backend_endpoint_url,
                backend_endpoint_auth_token=backend_endpoint_auth_token,
                backend_endpoint_timeout_seconds=backend_endpoint_timeout_seconds,
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
    backend_endpoint_url: Optional[str] = None,
    backend_endpoint_auth_token: Optional[str] = None,
    backend_endpoint_timeout_seconds: int = BACKEND_ENDPOINT_READ_TIMEOUT_SECONDS,
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
            backend_endpoint_url=backend_endpoint_url,
            backend_endpoint_auth_token=backend_endpoint_auth_token,
            backend_endpoint_timeout_seconds=backend_endpoint_timeout_seconds,
        )
    if step == "failure_handler":
        return {
            "status": "failed",
            "contract_version": contract_version,
            "decision_reason": "failure_handler_invoked",
            "error": previous_step_output or {"error": "unknown"},
        }
    return {"status": "failed", "error": f"unsupported_step:{step}"}
