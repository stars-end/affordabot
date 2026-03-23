"""
Pipeline truth diagnostic utility (bd-tytc.7).

Traces a single bill through every lifecycle stage:
  Scrape -> Raw Text -> Vector Chunks -> Research Proofs -> Analysis

Usage:
  python backend/scripts/verification/verify_pipeline_truth.py --jurisdiction california --bill-id "SB 277"
  python backend/scripts/verification/verify_pipeline_truth.py --jurisdiction california --bill-id "ACR 117"
  python backend/scripts/verification/verify_pipeline_truth.py --all-california
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(BACKEND_ROOT))


async def diagnose_bill(db, jurisdiction: str, bill_id: str) -> dict:
    """Run full truth diagnostic for a single bill."""
    result = {
        "jurisdiction": jurisdiction,
        "bill_id": bill_id,
        "stages": {},
        "issues": [],
        "verdict": "unknown",
    }

    # Stage 1: Raw scrape
    scrape_query = """
        SELECT rs.id, rs.url, rs.created_at, rs.content_hash, rs.metadata, rs.data
        FROM raw_scrapes rs
        LEFT JOIN sources s ON rs.source_id = s.id
        LEFT JOIN jurisdictions j ON s.jurisdiction_id::uuid = j.id
        WHERE LOWER(j.name) LIKE '%' || LOWER($1) || '%'
          AND rs.metadata::json->>'bill_number' ILIKE $2
        ORDER BY rs.created_at DESC
        LIMIT 1
    """
    scrape = await db._fetchrow(scrape_query, jurisdiction, f"%{bill_id}%")
    if not scrape:
        result["stages"]["scrape"] = {"status": "missing"}
        result["issues"].append("No raw scrape found")
        result["verdict"] = "no_scrape"
        return result

    metadata = (
        json.loads(scrape["metadata"])
        if isinstance(scrape["metadata"], str)
        else (scrape["metadata"] or {})
    )
    data = (
        json.loads(scrape["data"])
        if isinstance(scrape["data"], str)
        else (scrape.get("data") or {})
    )
    content = data.get("content", "")
    content_len = len(content) if content else 0
    extraction_status = metadata.get("extraction_status", "unknown")

    result["stages"]["scrape"] = {
        "status": "found",
        "raw_scrape_id": str(scrape["id"]),
        "url": scrape["url"],
        "content_length": content_len,
        "extraction_status": extraction_status,
        "source_type": metadata.get("source_type"),
        "source_url": metadata.get("source_url"),
    }

    if extraction_status != "success":
        result["issues"].append(f"Extraction status: {extraction_status}")
    if content_len < 100:
        result["issues"].append(f"Content too short: {content_len} chars")

    # Stage 2: Vector chunks
    document_id = metadata.get("document_id")
    chunk_count = 0
    chunk_lookup_method = "none"

    if document_id:
        chunk_query = (
            "SELECT COUNT(*) as cnt FROM document_chunks WHERE document_id = $1"
        )
        chunk_row = await db._fetchrow(chunk_query, document_id)
        chunk_count = chunk_row["cnt"] if chunk_row else 0

    if chunk_count == 0:
        meta_chunk_query = (
            "SELECT COUNT(*) as cnt FROM document_chunks "
            "WHERE metadata::json->>'bill_number' = $1"
        )
        meta_row = await db._fetchrow(meta_chunk_query, bill_id)
        meta_count = meta_row["cnt"] if meta_row else 0
        if meta_count > 0:
            chunk_count = meta_count
            chunk_lookup_method = "metadata_bill_number"
    else:
        chunk_lookup_method = "document_id"

    result["stages"]["vector_chunks"] = {
        "document_id": document_id,
        "chunk_count": chunk_count,
        "lookup_method": chunk_lookup_method,
        "status": "indexed" if chunk_count > 0 else "missing",
    }
    if chunk_count == 0 and extraction_status == "success":
        result["issues"].append("Bill text not chunked/embedded")

    # Stage 3: Legislation record
    leg_query = """
        SELECT l.id, l.bill_number, l.title, l.analysis_status,
               l.sufficiency_state, l.insufficiency_reason, l.quantification_eligible, l.total_impact_p50
        FROM legislation l
        LEFT JOIN jurisdictions j ON l.jurisdiction_id = j.id
        WHERE LOWER(j.name) LIKE '%' || LOWER($1) || '%'
          AND LOWER(l.bill_number) LIKE LOWER($2)
        ORDER BY l.created_at DESC
        LIMIT 1
    """
    leg = await db._fetchrow(leg_query, jurisdiction, f"%{bill_id}%")
    if leg:
        result["stages"]["legislation"] = {
            "status": "found",
            "analysis_status": leg.get("analysis_status"),
            "sufficiency_state": leg.get("sufficiency_state"),
            "insufficiency_reason": leg.get("insufficiency_reason"),
            "quantification_eligible": leg.get("quantification_eligible"),
            "total_impact_p50": leg.get("total_impact_p50"),
        }
        if leg.get("sufficiency_state") in (
            "research_incomplete",
            "insufficient_evidence",
        ):
            result["issues"].append(f"Sufficiency: {leg.get('sufficiency_state')}")
    else:
        result["stages"]["legislation"] = {"status": "missing"}
        result["issues"].append("No legislation record")

    # Stage 4: Pipeline run
    latest_pipe_query = """
        SELECT id, status, started_at, completed_at, error, result, trigger_source
        FROM pipeline_runs
        WHERE LOWER(bill_id) LIKE LOWER($1)
        ORDER BY started_at DESC
        LIMIT 1
    """
    completed_pipe_query = """
        SELECT id, status, started_at, completed_at, error, result, trigger_source
        FROM pipeline_runs
        WHERE LOWER(bill_id) LIKE LOWER($1)
          AND status = 'completed'
        ORDER BY completed_at DESC NULLS LAST, started_at DESC
        LIMIT 1
    """
    latest_pipe = await db._fetchrow(latest_pipe_query, f"%{bill_id}%")
    completed_pipe = await db._fetchrow(completed_pipe_query, f"%{bill_id}%")
    pipe = latest_pipe or completed_pipe
    if pipe:
        selected_pipe = pipe
        if latest_pipe and latest_pipe.get("status") != "completed" and completed_pipe:
            selected_pipe = completed_pipe
            result["issues"].append(
                "Latest pipeline run not completed; audited latest completed run instead"
            )
        pipe_result = (
            json.loads(selected_pipe["result"])
            if isinstance(selected_pipe["result"], str)
            else (selected_pipe["result"] or {})
        )
        trigger_source = selected_pipe.get("trigger_source", "manual")

        steps_query = """
            SELECT step_number, step_name, status
            FROM pipeline_steps
            WHERE run_id = $1
            ORDER BY step_number ASC
        """
        step_rows = await db._fetch(steps_query, str(selected_pipe["id"]))
        steps_summary = (
            [
                {
                    "step_number": r["step_number"],
                    "step_name": r["step_name"],
                    "status": r["status"],
                }
                for r in step_rows
            ]
            if step_rows
            else []
        )
        has_persistence = any(
            s["step_name"] == "persistence" and s["status"] == "completed"
            for s in steps_summary
        )

        result["stages"]["pipeline_run"] = {
            "run_id": str(selected_pipe["id"]),
            "status": selected_pipe["status"],
            "trigger_source": trigger_source,
            "source_text_present": pipe_result.get("source_text_present"),
            "rag_chunks_retrieved": pipe_result.get("rag_chunks_retrieved", 0),
            "quantification_eligible": pipe_result.get("quantification_eligible"),
            "pipeline_steps": steps_summary,
            "persistence_step_present": has_persistence,
        }
        if latest_pipe:
            result["stages"]["pipeline_run"]["latest_run_id"] = str(latest_pipe["id"])
            result["stages"]["pipeline_run"]["latest_run_status"] = latest_pipe["status"]
        if not has_persistence and selected_pipe["status"] == "completed":
            result["issues"].append(
                "Pipeline completed but no persistence step recorded"
            )
    else:
        result["stages"]["pipeline_run"] = {"status": "missing"}
        result["issues"].append("No pipeline run found")

    # Verdict
    critical = ["No scrape", "No legislation", "No pipeline run"]
    warnings = [i for i in result["issues"] if "Extraction status" not in i]

    if any(any(c in issue for c in critical) for issue in result["issues"]):
        result["verdict"] = "critical_gaps"
    elif warnings:
        result["verdict"] = "warnings"
    elif result["issues"]:
        result["verdict"] = "minor_issues"
    else:
        result["verdict"] = "healthy"

    return result


async def main():
    parser = argparse.ArgumentParser(description="Pipeline truth diagnostic")
    parser.add_argument("--jurisdiction", default=None)
    parser.add_argument("--bill-id", default=None)
    parser.add_argument("--all-california", action="store_true")
    args = parser.parse_args()

    from db.postgres_client import PostgresDB

    db = PostgresDB()
    await db.connect()

    try:
        if args.all_california:
            bills = ["SB 277", "ACR 117"]
            results = {}
            for bill_id in bills:
                results[bill_id] = await diagnose_bill(db, "california", bill_id)
            print(json.dumps(results, indent=2, default=str))
        elif args.jurisdiction and args.bill_id:
            result = await diagnose_bill(db, args.jurisdiction, args.bill_id)
            print(json.dumps(result, indent=2, default=str))
        else:
            parser.error(
                "Must provide --bill-id (with --jurisdiction) or --all-california"
            )
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
