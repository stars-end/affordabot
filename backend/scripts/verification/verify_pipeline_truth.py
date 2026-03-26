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
from typing import Any, Dict, List

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(BACKEND_ROOT))

MECHANISM_REQUIRED_STEPS = [
    "impact_discovery",
    "mode_selection",
    "parameter_resolution",
    "sufficiency_gate",
    "parameter_validation",
]

STEP_NAME_BY_INDEX = {
    1: "ingestion_source",
    2: "chunk_index",
    3: "research_discovery",
    4: "impact_discovery",
    5: "mode_selection",
    6: "parameter_resolution",
    7: "sufficiency_gate",
    8: "generate",
    9: "parameter_validation",
    10: "review",
    11: "refine",
    12: "persistence",
    13: "notify_debug",
}
STEP_INDEX_BY_NAME = {name: idx for idx, name in STEP_NAME_BY_INDEX.items()}


def _prefix_boundary(steps_summary: List[Dict[str, Any]], run_status: str) -> str | None:
    for step in steps_summary:
        if step["step_name"] != "notify_debug":
            continue
        output = step.get("output_result") or {}
        boundary = output.get("prefix_boundary")
        if boundary:
            return str(boundary)
    if run_status == "prefix_halted" and steps_summary:
        return f"stopped_after_{steps_summary[-1]['step_name']}"
    return None


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
               l.sufficiency_state, l.insufficiency_reason, l.quantification_eligible
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
    def _json_or_value(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

    def _step_has_keys(step_output: Dict[str, Any], required_keys: List[str]) -> bool:
        return all(key in step_output for key in required_keys)

    def _parameter_validation_shape_valid(step: Dict[str, Any]) -> bool:
        output = step.get("output_result", {}) or {}
        if _step_has_keys(
            output,
            [
                "schema_valid",
                "arithmetic_valid",
                "bound_construction_valid",
                "claim_support_valid",
                "validation_failures",
            ],
        ):
            return True
        return (
            step.get("status") == "skipped"
            and output.get("skipped") is True
            and isinstance(output.get("reason"), str)
        )

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
    failed_pipe_query = """
        SELECT id, status, started_at, completed_at, error, result, trigger_source
        FROM pipeline_runs
        WHERE LOWER(bill_id) LIKE LOWER($1)
          AND status = 'failed'
        ORDER BY completed_at DESC NULLS LAST, started_at DESC
        LIMIT 1
    """
    latest_pipe = await db._fetchrow(latest_pipe_query, f"%{bill_id}%")
    completed_pipe = await db._fetchrow(completed_pipe_query, f"%{bill_id}%")
    failed_pipe = await db._fetchrow(failed_pipe_query, f"%{bill_id}%")
    pipe = latest_pipe or completed_pipe or failed_pipe
    if pipe:
        selected_pipe = pipe
        selected_head = "latest_run"
        if latest_pipe and latest_pipe.get("status") != "completed" and completed_pipe:
            selected_pipe = completed_pipe
            selected_head = "latest_completed_run"
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
            SELECT step_number, step_name, status, output_result
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
                    "output_result": _json_or_value(r.get("output_result")) or {},
                }
                for r in step_rows
            ]
            if step_rows
            else []
        )
        step_names = [s["step_name"] for s in steps_summary]
        has_persistence = any(
            s["step_name"] == "persistence" and s["status"] == "completed"
            for s in steps_summary
        )
        is_prefix_run = str(trigger_source).startswith("prefix:") or selected_pipe.get(
            "status"
        ) == "prefix_halted"
        is_fixture_run = str(trigger_source).startswith("fixture:") or selected_pipe.get(
            "status"
        ) == "fixture_invalid"
        prefix_boundary = _prefix_boundary(steps_summary, selected_pipe.get("status"))
        halted_step = None
        if prefix_boundary and prefix_boundary.startswith("stopped_after_step_"):
            try:
                halted_step = STEP_NAME_BY_INDEX[
                    int(prefix_boundary.rsplit("_", 1)[1])
                ]
            except (ValueError, KeyError):
                halted_step = None
        elif prefix_boundary and prefix_boundary.startswith("stopped_after_"):
            halted_step = prefix_boundary.split("stopped_after_", 1)[1]
        elif is_prefix_run and steps_summary:
            halted_step = steps_summary[-1]["step_name"]

        missing_expected_steps: List[str] = []
        if not is_prefix_run:
            missing_expected_steps = [
                step_name
                for step_name in MECHANISM_REQUIRED_STEPS
                if step_name not in step_names
            ]
        expected_prefix_steps: List[str] = []
        missing_prefix_steps: List[str] = []
        if is_prefix_run and halted_step and halted_step in STEP_INDEX_BY_NAME:
            boundary_index = STEP_INDEX_BY_NAME[halted_step]
            expected_prefix_steps = [
                STEP_NAME_BY_INDEX[idx] for idx in range(1, boundary_index + 1)
            ]
            missing_prefix_steps = [
                step_name for step_name in expected_prefix_steps if step_name not in step_names
            ]

        step_map = {item["step_name"]: item for item in steps_summary}
        mechanism_checks = {
            "impact_discovery": {
                "present": "impact_discovery" in step_map,
                "valid_shape": _step_has_keys(
                    step_map.get("impact_discovery", {}).get("output_result", {}),
                    ["impacts"],
                )
                if "impact_discovery" in step_map
                else False,
            },
            "mode_selection": {
                "present": "mode_selection" in step_map,
                "valid_shape": _step_has_keys(
                    step_map.get("mode_selection", {}).get("output_result", {}),
                    [
                        "candidate_modes",
                        "selected_mode",
                        "rejected_modes",
                        "selection_rationale",
                        "ambiguity_status",
                        "composition_candidate",
                    ],
                )
                if "mode_selection" in step_map
                else False,
            },
            "parameter_resolution": {
                "present": "parameter_resolution" in step_map,
                "valid_shape": _step_has_keys(
                    step_map.get("parameter_resolution", {}).get("output_result", {}),
                    [
                        "required_parameters",
                        "resolved_parameters",
                        "missing_parameters",
                        "source_hierarchy_status",
                        "excerpt_validation_status",
                        "literature_confidence",
                        "dominant_uncertainty_parameters",
                    ],
                )
                if "parameter_resolution" in step_map
                else False,
            },
            "sufficiency_gate": {
                "present": "sufficiency_gate" in step_map,
                "valid_shape": _step_has_keys(
                    step_map.get("sufficiency_gate", {}).get("output_result", {}),
                    [
                        "overall_quantification_eligible",
                        "overall_sufficiency_state",
                        "impact_gate_summaries",
                        "bill_level_failures",
                    ],
                )
                if "sufficiency_gate" in step_map
                else False,
            },
            "parameter_validation": {
                "present": "parameter_validation" in step_map,
                "valid_shape": _parameter_validation_shape_valid(
                    step_map.get("parameter_validation", {})
                )
                if "parameter_validation" in step_map
                else False,
            },
        }
        generate_output = step_map.get("generate", {}).get("output_result", {}) or {}
        validate_output = (
            step_map.get("parameter_validation", {}).get("output_result", {}) or {}
        )
        persistence_output = (
            step_map.get("persistence", {}).get("output_result", {}) or {}
        )
        persistence_truth_mismatches = []
        if persistence_output and validate_output:
            if validate_output.get("overall_sufficiency_state") and (
                persistence_output.get("sufficiency_state")
                != validate_output.get("overall_sufficiency_state")
            ):
                persistence_truth_mismatches.append(
                    "persistence.sufficiency_state != parameter_validation.overall_sufficiency_state"
                )
            if "overall_quantification_eligible" in validate_output and (
                persistence_output.get("quantification_eligible")
                != validate_output.get("overall_quantification_eligible")
            ):
                persistence_truth_mismatches.append(
                    "persistence.quantification_eligible != parameter_validation.overall_quantification_eligible"
                )
        if persistence_output and generate_output:
            if (
                persistence_output.get("aggregate_scenario_bounds")
                != generate_output.get("aggregate_scenario_bounds")
                and persistence_output.get("aggregate_scenario_bounds") is not None
                and generate_output.get("aggregate_scenario_bounds") is not None
            ):
                persistence_truth_mismatches.append(
                    "persistence.aggregate_scenario_bounds != generate.aggregate_scenario_bounds"
                )

        result["stages"]["pipeline_run"] = {
            "run_id": str(selected_pipe["id"]),
            "status": selected_pipe["status"],
            "trigger_source": trigger_source,
            "is_prefix_run": is_prefix_run,
            "is_fixture_run": is_fixture_run,
            "prefix_boundary": prefix_boundary,
            "halted_after_step": halted_step,
            "source_text_present": pipe_result.get("source_text_present"),
            "rag_chunks_retrieved": pipe_result.get("rag_chunks_retrieved", 0),
            "quantification_eligible": pipe_result.get("quantification_eligible"),
            "pipeline_steps": steps_summary,
            "persistence_step_present": has_persistence,
            "mechanism_checks": mechanism_checks,
            "missing_expected_steps": missing_expected_steps,
            "expected_prefix_steps": expected_prefix_steps,
            "missing_prefix_steps": missing_prefix_steps,
            "run_heads": {
                "selected_head": selected_head,
                "latest_run_id": str(latest_pipe["id"]) if latest_pipe else None,
                "latest_completed_run_id": str(completed_pipe["id"])
                if completed_pipe
                else None,
                "latest_failed_run_id": str(failed_pipe["id"]) if failed_pipe else None,
            },
            "persistence_truth": {
                "checked": bool(persistence_output),
                "matches_validated_payload": len(persistence_truth_mismatches) == 0,
                "mismatches": persistence_truth_mismatches,
            },
        }
        if latest_pipe:
            result["stages"]["pipeline_run"]["latest_run_id"] = str(latest_pipe["id"])
            result["stages"]["pipeline_run"]["latest_run_status"] = latest_pipe["status"]
        if not has_persistence and selected_pipe["status"] == "completed":
            result["issues"].append(
                "Pipeline completed but no persistence step recorded"
            )
        if missing_expected_steps:
            result["issues"].append(
                f"Missing expected mechanism steps: {', '.join(missing_expected_steps)}"
            )
        if missing_prefix_steps:
            result["issues"].append(
                f"Prefix run missing expected boundary steps: {', '.join(missing_prefix_steps)}"
            )
        invalid_checks = [
            name
            for name, check in mechanism_checks.items()
            if check["present"] and not check["valid_shape"]
        ]
        if invalid_checks:
            result["issues"].append(
                f"Mechanism step payloads invalid: {', '.join(invalid_checks)}"
            )
        if persistence_truth_mismatches:
            result["issues"].append(
                f"Persistence truth mismatch: {', '.join(persistence_truth_mismatches)}"
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
