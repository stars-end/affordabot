"""
Slack summary emitter for manual pipeline runs (bd-hvji.6).

Reads pipeline_steps for a completed run, formats per-stage proof summaries,
and posts to Slack with deep-links back to the canonical audit surface.

Reuses the Windmill send_slack_alert webhook pattern. Does not create
a second truth store.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ADMIN_BASE_URL = os.environ.get(
    "ADMIN_BASE_URL",
    os.environ.get("BACKEND_PUBLIC_URL", "https://affordabot.up.railway.app"),
)

STAGE_PROOF_BUILDERS = {
    "ingestion_source": "_build_ingestion_proof",
    "chunk_index": "_build_chunk_index_proof",
    "research": "_build_research_proof",
    "research_discovery": "_build_research_proof",
    "impact_discovery": "_build_impact_discovery_proof",
    "mode_selection": "_build_mode_selection_proof",
    "parameter_resolution": "_build_parameter_resolution_proof",
    "sufficiency_gate": "_build_sufficiency_proof",
    "generate": "_build_generate_proof",
    "parameter_validation": "_build_parameter_validation_proof",
    "review": "_build_review_proof",
    "refine": "_build_refine_proof",
    "persistence": "_build_persistence_proof",
    "notify_debug": "_build_notify_debug_proof",
    "pipeline_failure": "_build_failure_proof",
}

_BUILDERS = {}


def build_audit_url(run_id: str) -> str:
    base = ADMIN_BASE_URL.rstrip("/")
    return f"{base}/admin/audits/trace/{run_id}"


def build_bill_truth_url(jurisdiction: str, bill_id: str) -> str:
    base = ADMIN_BASE_URL.rstrip("/")
    jur_slug = jurisdiction.lower().replace(" ", "-")
    return f"{base}/admin/bill-truth/{jur_slug}/{bill_id}"


def format_slack_summary(
    run_id: str,
    bill_id: str,
    jurisdiction: str,
    status: str,
    started_at: Optional[str],
    completed_at: Optional[str],
    trigger_source: str,
    steps: List[Dict[str, Any]],
    result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    proof_lines = []
    for step in steps:
        step_name = step.get("step_name", "unknown")
        step_status = step.get("status", "unknown")
        output = step.get("output_result") or {}

        builder_name = STAGE_PROOF_BUILDERS.get(step_name)
        if builder_name and builder_name in globals():
            line = globals()[builder_name](step_status, output)
            if line:
                proof_lines.append(line)
        else:
            proof_lines.append(f"*{step_name}*: {step_status} (no detailed proof)")

    audit_url = build_audit_url(run_id)
    bill_url = build_bill_truth_url(jurisdiction, bill_id)

    duration_str = ""
    if started_at and completed_at:
        try:
            start = datetime.fromisoformat(started_at)
            end = datetime.fromisoformat(completed_at)
            delta = end - start
            mins, secs = divmod(int(delta.total_seconds()), 60)
            duration_str = f" ({mins}m {secs}s)" if mins else f" ({secs}s)"
        except (ValueError, TypeError):
            pass

    is_prefix_run = str(trigger_source).startswith("prefix:") or status == "prefix_halted"
    if status == "completed":
        status_emoji = "✅"
    elif status == "prefix_halted":
        status_emoji = "🔬"
    else:
        status_emoji = "🔴"

    run_label = None
    if str(trigger_source).startswith("prefix:"):
        run_label = str(trigger_source).split("prefix:", 1)[1]

    if is_prefix_run:
        boundary = next(
            (
                (step.get("output_result") or {}).get("prefix_boundary")
                for step in steps
                if step.get("step_name") == "notify_debug"
                and (step.get("output_result") or {}).get("prefix_boundary")
            ),
            None,
        )
        title = (
            f"{status_emoji} Prefix pipeline: {bill_id} ({jurisdiction})"
            f"{duration_str}"
        )
        if run_label:
            title += f" [{run_label}]"
        if boundary:
            title += f" [{boundary}]"
    else:
        title = f"{status_emoji} Manual pipeline: {bill_id} ({jurisdiction}){duration_str}"

    proof_text = (
        "\n".join(proof_lines) if proof_lines else "No pipeline steps recorded."
    )

    sufficiency_note = ""
    if result:
        suff = result.get("sufficiency_state") or result.get("analysis", {}).get(
            "sufficiency_state"
        )
        if suff:
            sufficiency_note = f"\n*Sufficiency*: `{suff}`"

    message = (
        f"{proof_text}{sufficiency_note}\n\n"
        f"<{audit_url}|Full Audit Trace> · "
        f"<{bill_url}|Bill Truth>"
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hostname = os.uname().nodename.split(".")[0]

    payload = {
        "text": title,
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{title}*"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"trigger={trigger_source} | host={hostname} | time={timestamp}",
                    }
                ],
            },
        ],
    }
    return payload


async def emit_slack_summary(
    webhook_url: Optional[str],
    run_id: str,
    bill_id: str,
    jurisdiction: str,
    status: str,
    started_at: Optional[str],
    completed_at: Optional[str],
    trigger_source: str,
    steps: List[Dict[str, Any]],
    result: Optional[Dict[str, Any]] = None,
) -> bool:
    if not webhook_url:
        logger.info("No Slack webhook configured, skipping manual-run summary")
        return False

    payload = format_slack_summary(
        run_id=run_id,
        bill_id=bill_id,
        jurisdiction=jurisdiction,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        trigger_source=trigger_source,
        steps=steps,
        result=result,
    )

    try:
        import urllib.request

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status < 400:
                logger.info("Slack manual-run summary sent for run %s", run_id)
                return True
            logger.warning("Slack returned %d for manual-run summary", resp.status)
            return False
    except Exception as exc:
        logger.error("Failed to send Slack manual-run summary: %s", exc)
        return False


async def load_and_emit(
    db: Any,
    webhook_url: Optional[str],
    run_id: str,
    trigger_source: str,
) -> bool:
    try:
        run_row = await db._fetchrow(
            "SELECT id, bill_id, jurisdiction, status, started_at, completed_at, result "
            "FROM pipeline_runs WHERE id::text = $1",
            run_id,
        )
        if not run_row:
            logger.warning("Cannot emit Slack summary: run %s not found", run_id)
            return False

        result = (
            json.loads(run_row["result"])
            if isinstance(run_row["result"], str)
            else (run_row["result"] or {})
        )

        step_rows = await db._fetch(
            "SELECT step_number, step_name, status, output_result "
            "FROM pipeline_steps WHERE run_id::text = $1 "
            "ORDER BY step_number ASC",
            run_id,
        )
        steps = []
        for s in step_rows:
            out = s["output_result"]
            if isinstance(out, str):
                try:
                    out = json.loads(out)
                except (json.JSONDecodeError, TypeError):
                    out = {}
            steps.append(
                {
                    "step_number": s["step_number"],
                    "step_name": s["step_name"],
                    "status": s["status"],
                    "output_result": out,
                }
            )

        return await emit_slack_summary(
            webhook_url=webhook_url,
            run_id=str(run_row["id"]),
            bill_id=run_row["bill_id"],
            jurisdiction=run_row["jurisdiction"],
            status=run_row["status"],
            started_at=str(run_row["started_at"]) if run_row["started_at"] else None,
            completed_at=str(run_row["completed_at"])
            if run_row["completed_at"]
            else None,
            trigger_source=trigger_source,
            steps=steps,
            result=result,
        )
    except Exception as exc:
        logger.error("load_and_emit failed for run %s: %s", run_id, exc)
        return False


def _build_ingestion_proof(status: str, output: Dict) -> str:
    if status == "skipped":
        return "Scrape/source: skipped — no raw scrape found for this bill."
    raw_id = output.get("raw_scrape_id", "?")
    src_url = output.get("source_url", "?")
    has_text = output.get("source_text_present", False)
    text_tag = "present" if has_text else "MISSING"
    return f"Scrape/source: `{raw_id}` from `{src_url}` — bill text {text_tag}."


def _build_research_proof(status: str, output: Dict) -> str:
    rag = output.get("rag_chunks", 0)
    web = output.get("web_sources", 0)
    envelopes = output.get("evidence_envelopes", 0)
    sufficient = output.get("is_sufficient", False)
    reason = output.get("insufficiency_reason", "")
    tag = "sufficient" if sufficient else "insufficient"
    line = f"Research: {rag} RAG chunks, {web} web sources, {envelopes} evidence envelopes — {tag}."
    if reason:
        line += f" Reason: {reason}"
    return line


def _build_impact_discovery_proof(status: str, output: Dict) -> str:
    impacts = output.get("impacts", [])
    hints = []
    for item in impacts[:3]:
        hints.extend(item.get("candidate_mode_hints", []))
    hint_text = ", ".join(dict.fromkeys(hints)) if hints else "none"
    return f"Impact discovery: {len(impacts)} candidates, mode hints `{hint_text}`."


def _build_mode_selection_proof(status: str, output: Dict) -> str:
    selected = output.get("selected_mode", "?")
    ambiguity = output.get("ambiguity_status", "?")
    rejected = len(output.get("rejected_modes", []))
    return (
        f"Mode selection: selected `{selected}`, ambiguity `{ambiguity}`, "
        f"{rejected} rejected modes."
    )


def _build_parameter_resolution_proof(status: str, output: Dict) -> str:
    resolved = len(output.get("resolved_parameters", {}) or {})
    missing = len(output.get("missing_parameters", []) or [])
    dominant = output.get("dominant_uncertainty_parameters", []) or []
    dominant_text = ", ".join(dominant[:3]) if dominant else "none"
    return (
        f"Parameter resolution: {resolved} resolved, {missing} missing, "
        f"dominant uncertainty `{dominant_text}`."
    )


def _build_sufficiency_proof(status: str, output: Dict) -> str:
    state = output.get("overall_sufficiency_state", output.get("sufficiency_state", "?"))
    eligible = output.get("overall_quantification_eligible", output.get("quantification_eligible", False))
    impacts = output.get("impact_gate_summaries", []) or []
    failures = output.get("bill_level_failures", []) or []
    return (
        f"Sufficiency gate: `{state}`, eligible={eligible}, "
        f"impact gates={len(impacts)}, failures={len(failures)}."
    )


def _build_generate_proof(status: str, output: Dict) -> str:
    suff = output.get("sufficiency_state", "?")
    impacts = len(output.get("impacts", []))
    quant = output.get("quantification_eligible", False)
    quant_tag = "eligible" if quant else "blocked"
    agg = output.get("aggregate_scenario_bounds")
    agg_tag = "with aggregate bounds" if agg else "without aggregate bounds"
    return (
        f"Generate: {impacts} impacts, sufficiency `{suff}`, "
        f"quantification {quant_tag}, {agg_tag}."
    )


def _build_parameter_validation_proof(status: str, output: Dict) -> str:
    schema_valid = output.get("schema_valid", False)
    arithmetic_valid = output.get("arithmetic_valid", False)
    bounds_valid = output.get("bound_construction_valid", False)
    claims_valid = output.get("claim_support_valid", False)
    failures = output.get("validation_failures", []) or []
    return (
        "Parameter validation: "
        f"schema={schema_valid}, arithmetic={arithmetic_valid}, "
        f"bounds={bounds_valid}, claims={claims_valid}, failures={len(failures)}."
    )


def _build_review_proof(status: str, output: Dict) -> str:
    passed = output.get("passed", False)
    errors = output.get("factual_errors", [])
    missing = output.get("missing_impacts", [])
    tag = "passed" if passed else "FAILED"
    detail = ""
    if errors:
        detail += f" {len(errors)} factual errors."
    if missing:
        detail += f" {len(missing)} missing impacts."
    return f"Review: {tag}.{detail}"


def _build_refine_proof(status: str, output: Dict) -> str:
    impacts = len(output.get("impacts", []))
    return f"Refine: {impacts} impacts after revision."


def _build_failure_proof(status: str, output: Dict) -> str:
    error = output.get("error", "unknown")
    return f"Pipeline failure: `{str(error)[:200]}`."


def _build_chunk_index_proof(status: str, output: Dict) -> str:
    chunks = output.get("chunk_count", output.get("chunks_created", 0))
    doc_id = output.get("document_id", "?")
    if status == "skipped":
        return "Chunk/index: skipped — no documents to index."
    return f"Chunk/index: {chunks} chunks created for document `{doc_id}`."


def _build_persistence_proof(status: str, output: Dict) -> str:
    stored = output.get("analysis_stored", False)
    leg_id = output.get("legislation_id", "?")
    impacts = output.get("impacts_count", 0)
    suff = output.get("sufficiency_state", "?")
    quant = output.get("quantification_eligible", False)
    aggregate_bounds = output.get("aggregate_scenario_bounds")

    if not stored:
        return "Persistence: analysis NOT stored."

    parts = [f"Persisted to legislation `{leg_id}`: {impacts} impacts"]
    parts.append(f"sufficiency `{suff}`")
    if quant and aggregate_bounds is not None:
        parts.append(f"aggregate_bounds={aggregate_bounds}")
    elif quant and output.get("total_impact_p50") is not None:
        parts.append(f"p50={output.get('total_impact_p50')}")
    elif quant:
        parts.append("quantification eligible (no aggregate bounds)")
    else:
        parts.append("quantification blocked")

    return "Persistence: " + ", ".join(parts) + "."


def _build_notify_debug_proof(status: str, output: Dict) -> str:
    prefix_boundary = output.get("prefix_boundary")
    state = output.get("status", status)
    if prefix_boundary:
        return f"Notify/debug: {state}, prefix boundary `{prefix_boundary}`."
    return f"Notify/debug: {state}."
