"""Windmill script surface for Path B orchestration review.

This script models step-level orchestration payloads for the domain-boundary pipeline.
It is committed for flow-shape review and contract comparison with Path A.
"""

from typing import Any, Dict, Optional


def _step_result(
    step: str,
    envelope: Dict[str, Any],
    stale_status: str,
    previous_step_output: Optional[Dict[str, Any]],
    search_query: Optional[str],
    analysis_question: Optional[str],
) -> Dict[str, Any]:
    if step == "search_materialize":
        return {
            "status": "fresh",
            "snapshot_id": "snapshot-579c45d51063aaef",
            "result_count": 2,
            "query": search_query,
            "envelope": envelope,
        }

    if step == "freshness_gate":
        if stale_status not in {"fresh", "stale_but_usable", "stale_blocked"}:
            return {"status": "source_error", "error": "invalid_stale_status", "envelope": envelope}
        return {"status": stale_status, "age_seconds": 3600, "envelope": envelope}

    if step == "read_fetch":
        if not previous_step_output:
            return {"status": "reader_error", "error": "missing_freshness_gate_output", "envelope": envelope}
        return {
            "status": "fresh",
            "canonical_document_key": "san-jose-ca::a653e7debe31e650",
            "artifact_ref": "minio://affordabot-artifacts/San_Jose_CA/ecf092f9a92f34b1.md",
            "envelope": envelope,
        }

    if step == "index":
        if not previous_step_output:
            return {"status": "storage_error", "error": "missing_read_fetch_output", "envelope": envelope}
        return {
            "status": "fresh",
            "chunks_total": 5,
            "chunks_created": 5,
            "envelope": envelope,
        }

    if step == "analyze":
        if not previous_step_output:
            return {"status": "analysis_error", "error": "missing_index_output", "envelope": envelope}
        return {
            "status": "fresh",
            "analysis_id": "analysis-ebbbe7e0f3aeac41",
            "question": analysis_question,
            "envelope": envelope,
        }

    if step == "summarize_run":
        return {
            "status": "succeeded",
            "summary": "Path B flow-shape export. Domain writes belong to affordabot commands.",
            "envelope": envelope,
        }

    return {"status": "source_error", "error": f"unsupported_step:{step}", "envelope": envelope}


def main(
    step: str,
    contract_version: str = "2026-04-12.windmill-storage-bakeoff.v1",
    architecture_path: str = "affordabot_domain_boundary",
    windmill_workspace: str = "affordabot",
    windmill_flow_path: str = "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
    windmill_run_id: str = "windmill-run-id",
    windmill_job_id: str = "windmill-job-id",
    idempotency_key: str = "san-jose-ca:meeting_minutes:2026-04-12",
    jurisdiction: str = "San Jose CA",
    source_family: str = "meeting_minutes",
    stale_status: str = "fresh",
    search_query: Optional[str] = None,
    analysis_question: Optional[str] = None,
    previous_step_output: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    envelope = {
        "contract_version": contract_version,
        "architecture_path": architecture_path,
        "orchestrator": "windmill",
        "windmill_workspace": windmill_workspace,
        "windmill_flow_path": windmill_flow_path,
        "windmill_run_id": windmill_run_id,
        "windmill_job_id": windmill_job_id,
        "idempotency_key": idempotency_key,
        "jurisdiction": jurisdiction,
        "source_family": source_family,
    }

    return _step_result(
        step=step,
        envelope=envelope,
        stale_status=stale_status,
        previous_step_output=previous_step_output,
        search_query=search_query,
        analysis_question=analysis_question,
    )
