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
    "research": "_build_research_proof",
    "sufficiency_gate": "_build_sufficiency_proof",
    "generate": "_build_generate_proof",
    "review": "_build_review_proof",
    "refine": "_build_refine_proof",
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

    status_emoji = "✅" if status == "completed" else "🔴"

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


def _build_sufficiency_proof(status: str, output: Dict) -> str:
    state = output.get("sufficiency_state", "?")
    rag = output.get("rag_chunks_retrieved", 0)
    sources = output.get("web_research_sources_found", 0)
    return f"Sufficiency gate: `{state}` — {rag} chunks, {sources} web sources."


def _build_generate_proof(status: str, output: Dict) -> str:
    suff = output.get("sufficiency_state", "?")
    impacts = len(output.get("impacts", []))
    quant = output.get("quantification_eligible", False)
    quant_tag = "eligible" if quant else "blocked"
    return f"Generate: {impacts} impacts, sufficiency `{suff}`, quantification {quant_tag}."


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
