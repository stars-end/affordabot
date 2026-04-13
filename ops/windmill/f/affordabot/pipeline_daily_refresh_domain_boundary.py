"""Windmill script surface for Path B orchestration skeleton.

This file intentionally models orchestration behavior only:
- build scope matrix (jurisdiction x source family)
- invoke coarse domain commands via stubs
- branch on freshness status (blocked vs usable)
- aggregate run summary + failure handler surface

No direct product writes are performed here.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional


CONTRACT_VERSION = "2026-04-13.windmill-domain.v1"
USABLE_STATUSES = {"fresh", "stale_but_usable", "empty_but_usable"}
BLOCKED_STATUSES = {"stale_blocked", "empty_blocked"}


def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _envelope(
    *,
    step: str,
    contract_version: str,
    architecture_path: str,
    windmill_workspace: str,
    windmill_flow_path: str,
    windmill_run_id: str,
    windmill_job_id: str,
    idempotency_key: str,
    scope_item: Dict[str, str],
    scope_index: int,
    mode: str,
) -> Dict[str, Any]:
    jurisdiction = scope_item.get("jurisdiction", "")
    source_family = scope_item.get("source_family", "")
    scope_key = f"{jurisdiction}|{source_family}|{scope_index}"
    return {
        "contract_version": contract_version,
        "architecture_path": architecture_path,
        "orchestrator": "windmill",
        "windmill_workspace": windmill_workspace,
        "windmill_flow_path": windmill_flow_path,
        "windmill_run_id": windmill_run_id,
        "windmill_job_id": windmill_job_id,
        "windmill_step_id": step,
        "idempotency_key": idempotency_key,
        "jurisdiction_id": jurisdiction,
        "jurisdiction_name": jurisdiction,
        "source_family": source_family,
        "scope_index": scope_index,
        "scope_key": scope_key,
        "mode": mode,
    }


def _invoke_command_stub(
    *,
    command: str,
    envelope: Dict[str, Any],
    stale_status: str,
    previous_step_output: Optional[Dict[str, Any]],
    search_query: Optional[str],
    analysis_question: Optional[str],
) -> Dict[str, Any]:
    if command == "search_materialize":
        return {
            "status": "fresh",
            "snapshot_id": f"snapshot-{_stable_hash(envelope['scope_key'])}",
            "result_count": 2,
            "query": search_query,
            "envelope": envelope,
            "invoked_command": command,
        }

    if command == "freshness_gate":
        if stale_status not in USABLE_STATUSES | BLOCKED_STATUSES:
            return {
                "status": "source_error",
                "error": "invalid_stale_status",
                "envelope": envelope,
                "invoked_command": command,
            }
        return {
            "status": stale_status,
            "age_seconds": 3600,
            "envelope": envelope,
            "invoked_command": command,
        }

    if command == "read_fetch":
        if not previous_step_output:
            return {
                "status": "reader_error",
                "error": "missing_freshness_gate_output",
                "envelope": envelope,
                "invoked_command": command,
            }
        return {
            "status": "fresh",
            "canonical_document_key": f"doc-{_stable_hash(envelope['scope_key'])}",
            "reader_record_id": f"reader-{_stable_hash(envelope['windmill_run_id'])}",
            "envelope": envelope,
            "invoked_command": command,
        }

    if command == "index":
        if not previous_step_output:
            return {
                "status": "storage_error",
                "error": "missing_read_fetch_output",
                "envelope": envelope,
                "invoked_command": command,
            }
        return {
            "status": "fresh",
            "chunks_total": 5,
            "chunks_created": 5,
            "envelope": envelope,
            "invoked_command": command,
        }

    if command == "analyze":
        if not previous_step_output:
            return {
                "status": "analysis_error",
                "error": "missing_index_output",
                "envelope": envelope,
                "invoked_command": command,
            }
        return {
            "status": "fresh",
            "analysis_id": f"analysis-{_stable_hash(envelope['idempotency_key'])}",
            "question": analysis_question,
            "envelope": envelope,
            "invoked_command": command,
        }

    if command == "summarize_run":
        terminal_status = previous_step_output.get("status") if previous_step_output else "source_error"
        flow_status = "blocked" if terminal_status in BLOCKED_STATUSES else "succeeded"
        if terminal_status not in USABLE_STATUSES | BLOCKED_STATUSES | {"fresh", "succeeded"}:
            flow_status = "failed"
        return {
            "status": flow_status,
            "terminal_step_status": terminal_status,
            "summary": "Path B orchestration skeleton. Product writes belong to affordabot commands.",
            "envelope": envelope,
            "invoked_command": command,
        }

    return {
        "status": "source_error",
        "error": f"unsupported_command:{command}",
        "envelope": envelope,
        "invoked_command": command,
    }


def _build_scope_matrix(jurisdictions: List[str], source_families: List[str]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for jurisdiction in jurisdictions:
        for source_family in source_families:
            items.append(
                {
                    "jurisdiction": jurisdiction,
                    "source_family": source_family,
                    "scope_key": f"{jurisdiction.lower()}::{source_family.lower()}",
                }
            )
    return {
        "status": "ready",
        "scope_items": items,
        "scope_count": len(items),
    }


def _run_scope_pipeline(
    *,
    contract_version: str,
    architecture_path: str,
    windmill_workspace: str,
    windmill_flow_path: str,
    windmill_run_id: str,
    windmill_job_id: str,
    idempotency_key: str,
    mode: str,
    scope_item: Dict[str, str],
    scope_index: int,
    stale_status: str,
    search_query: Optional[str],
    analysis_question: Optional[str],
) -> Dict[str, Any]:
    steps: Dict[str, Dict[str, Any]] = {}

    def run_step(command: str, previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        env = _envelope(
            step=command,
            contract_version=contract_version,
            architecture_path=architecture_path,
            windmill_workspace=windmill_workspace,
            windmill_flow_path=windmill_flow_path,
            windmill_run_id=windmill_run_id,
            windmill_job_id=f"{windmill_job_id}:{scope_index}:{command}",
            idempotency_key=idempotency_key,
            scope_item=scope_item,
            scope_index=scope_index,
            mode=mode,
        )
        return _invoke_command_stub(
            command=command,
            envelope=env,
            stale_status=stale_status,
            previous_step_output=previous,
            search_query=search_query,
            analysis_question=analysis_question,
        )

    steps["search_materialize"] = run_step("search_materialize")
    steps["freshness_gate"] = run_step("freshness_gate", previous=steps["search_materialize"])
    freshness_status = steps["freshness_gate"].get("status", "source_error")

    if freshness_status in BLOCKED_STATUSES:
        steps["summarize_run"] = run_step("summarize_run", previous=steps["freshness_gate"])
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": "blocked",
            "steps": steps,
            "alert": f"freshness_gate:{freshness_status}",
        }

    if freshness_status not in USABLE_STATUSES:
        steps["summarize_run"] = run_step("summarize_run", previous=steps["freshness_gate"])
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": "failed",
            "steps": steps,
            "alert": f"freshness_gate:{freshness_status}",
        }

    steps["read_fetch"] = run_step("read_fetch", previous=steps["freshness_gate"])
    if steps["read_fetch"].get("status") != "fresh":
        steps["summarize_run"] = run_step("summarize_run", previous=steps["read_fetch"])
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": "failed",
            "steps": steps,
            "alert": f"read_fetch:{steps['read_fetch'].get('status')}",
        }

    steps["index"] = run_step("index", previous=steps["read_fetch"])
    if steps["index"].get("status") != "fresh":
        steps["summarize_run"] = run_step("summarize_run", previous=steps["index"])
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": "failed",
            "steps": steps,
            "alert": f"index:{steps['index'].get('status')}",
        }

    steps["analyze"] = run_step("analyze", previous=steps["index"])
    steps["summarize_run"] = run_step("summarize_run", previous=steps["analyze"])
    return {
        "scope_item": scope_item,
        "scope_index": scope_index,
        "status": "succeeded" if steps["analyze"].get("status") == "fresh" else "failed",
        "steps": steps,
        "alert": "",
    }


def _aggregate_scope_results(scope_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(scope_results)
    blocked = sum(1 for result in scope_results if result.get("status") == "blocked")
    failed = sum(1 for result in scope_results if result.get("status") == "failed")
    succeeded = sum(1 for result in scope_results if result.get("status") == "succeeded")
    alerts = [result["alert"] for result in scope_results if result.get("alert")]
    run_status = "failed" if failed > 0 or blocked > 0 else "succeeded"
    return {
        "status": run_status,
        "scope_total": total,
        "scope_succeeded": succeeded,
        "scope_blocked": blocked,
        "scope_failed": failed,
        "alerts": alerts,
        "scope_results": scope_results,
    }


def main(
    step: str,
    contract_version: str = CONTRACT_VERSION,
    architecture_path: str = "affordabot_domain_boundary",
    windmill_workspace: str = "affordabot",
    windmill_flow_path: str = "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
    windmill_run_id: str = "windmill-run-id",
    windmill_job_id: str = "windmill-job-id",
    idempotency_key: str = "run:2026-04-13",
    mode: str = "scheduled",
    jurisdictions: Optional[List[str]] = None,
    source_families: Optional[List[str]] = None,
    scope_item: Optional[Dict[str, str]] = None,
    scope_index: int = 0,
    stale_status: str = "fresh",
    search_query: Optional[str] = None,
    analysis_question: Optional[str] = None,
    previous_step_output: Optional[Dict[str, Any]] = None,
    scope_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    jurisdictions = jurisdictions or ["San Jose CA"]
    source_families = source_families or ["meeting_minutes"]

    if step == "build_scope_matrix":
        return _build_scope_matrix(jurisdictions, source_families)

    if step == "run_scope_pipeline":
        if not scope_item:
            return {"status": "failed", "error": "missing_scope_item"}
        return _run_scope_pipeline(
            contract_version=contract_version,
            architecture_path=architecture_path,
            windmill_workspace=windmill_workspace,
            windmill_flow_path=windmill_flow_path,
            windmill_run_id=windmill_run_id,
            windmill_job_id=windmill_job_id,
            idempotency_key=idempotency_key,
            mode=mode,
            scope_item=scope_item,
            scope_index=scope_index,
            stale_status=stale_status,
            search_query=search_query,
            analysis_question=analysis_question,
        )

    if step == "aggregate_run_summary":
        return _aggregate_scope_results(scope_results or [])

    if step == "failure_handler":
        return {
            "status": "failed",
            "summary": "Windmill failure handler for Path B orchestration skeleton.",
            "last_step": previous_step_output,
            "windmill_run_id": windmill_run_id,
            "windmill_job_id": windmill_job_id,
            "contract_version": contract_version,
        }

    return {"status": "source_error", "error": f"unsupported_step:{step}"}
