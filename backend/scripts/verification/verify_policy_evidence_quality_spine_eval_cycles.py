#!/usr/bin/env python3
"""Build strict eval-cycle artifacts for policy-evidence quality spine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS_DIR = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
)
DEFAULT_SCORECARD_PATH = ARTIFACTS_DIR / "quality_spine_scorecard.json"
DEFAULT_RETRY_LEDGER_PATH = ARTIFACTS_DIR / "retry_ledger.json"
DEFAULT_LIVE_STORAGE_PATH = ARTIFACTS_DIR / "quality_spine_live_storage_probe.json"
DEFAULT_LIVE_CYCLE_PATH = ARTIFACTS_DIR / "live_cycle_01_windmill_domain_run.json"
DEFAULT_OUTPUT_JSON = ARTIFACTS_DIR / "quality_spine_eval_cycles_report.json"
DEFAULT_OUTPUT_MD = ARTIFACTS_DIR / "quality_spine_eval_cycles_report.md"

VALID_STATUSES = {"pass", "not_proven", "fail"}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_status(value: str | None) -> str:
    if value in VALID_STATUSES:
        return str(value)
    return "not_proven"


def _status_rank(status: str) -> int:
    if status == "fail":
        return 2
    if status == "not_proven":
        return 1
    return 0


def _combine_status(statuses: list[str]) -> str:
    rank = max((_status_rank(_normalize_status(item)) for item in statuses), default=0)
    if rank == 2:
        return "fail"
    if rank == 1:
        return "not_proven"
    return "pass"


def _gate_entry(status: str, details: str) -> dict[str, str]:
    return {"status": _normalize_status(status), "details": details}


def _extract_backend_run_id(live_cycle: dict[str, Any] | None) -> str | None:
    if not isinstance(live_cycle, dict):
        return None
    refs = _extract_summarize_refs(live_cycle)
    if isinstance(refs, dict):
        for key in ("backend_run_id", "run_id"):
            run_id = refs.get(key)
            if isinstance(run_id, str) and run_id.strip():
                return run_id.strip()
    result_payload = live_cycle.get("result_payload")
    if not isinstance(result_payload, dict):
        return None
    scope_results = result_payload.get("scope_results")
    if not isinstance(scope_results, list):
        return None
    for scope in scope_results:
        if not isinstance(scope, dict):
            continue
        backend_response = scope.get("backend_response")
        if not isinstance(backend_response, dict):
            continue
        refs = backend_response.get("refs")
        if not isinstance(refs, dict):
            continue
        run_id = refs.get("run_id")
        if isinstance(run_id, str) and run_id.strip():
            return run_id.strip()
    return None


def _extract_scope_result(live_cycle: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(live_cycle, dict):
        return None
    result_payload = live_cycle.get("result_payload")
    if not isinstance(result_payload, dict):
        return None
    scope_results = result_payload.get("scope_results")
    if not isinstance(scope_results, list):
        return None
    for scope in scope_results:
        if isinstance(scope, dict):
            return scope
    return None


def _extract_summarize_run_step(live_cycle: dict[str, Any] | None) -> dict[str, Any] | None:
    scope = _extract_scope_result(live_cycle)
    if not isinstance(scope, dict):
        return None
    steps = scope.get("steps")
    if not isinstance(steps, dict):
        return None
    summarize_run = steps.get("summarize_run")
    return summarize_run if isinstance(summarize_run, dict) else None


def _extract_summarize_refs(live_cycle: dict[str, Any] | None) -> dict[str, Any]:
    summarize_run = _extract_summarize_run_step(live_cycle)
    if not isinstance(summarize_run, dict):
        return {}
    refs = summarize_run.get("refs")
    if isinstance(refs, dict):
        return refs
    return {}


def _extract_policy_package(live_cycle: dict[str, Any] | None) -> dict[str, Any]:
    summarize_run = _extract_summarize_run_step(live_cycle)
    if not isinstance(summarize_run, dict):
        return {}
    details = summarize_run.get("details")
    if not isinstance(details, dict):
        return {}
    package = details.get("policy_evidence_package")
    return package if isinstance(package, dict) else {}


def _extract_package_run_context(live_cycle: dict[str, Any] | None) -> dict[str, Any]:
    package = _extract_policy_package(live_cycle)
    payload = package.get("package_payload")
    if not isinstance(payload, dict):
        return {}
    run_context = payload.get("run_context")
    return run_context if isinstance(run_context, dict) else {}


def _extract_package_artifact_uri(live_cycle: dict[str, Any] | None) -> str | None:
    refs = _extract_summarize_refs(live_cycle)
    value = refs.get("package_artifact_uri")
    if isinstance(value, str) and value.strip():
        return value.strip()
    package = _extract_policy_package(live_cycle)
    package_refs = package.get("refs")
    if isinstance(package_refs, dict):
        nested = package_refs.get("package_artifact_uri")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


def _extract_package_id(live_cycle: dict[str, Any] | None) -> str | None:
    refs = _extract_summarize_refs(live_cycle)
    value = refs.get("package_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    package = _extract_policy_package(live_cycle)
    package_refs = package.get("refs")
    if isinstance(package_refs, dict):
        nested = package_refs.get("package_id")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


def _extract_provider_status(live_cycle: dict[str, Any] | None) -> str | None:
    if not isinstance(live_cycle, dict):
        return None
    bakeoff = live_cycle.get("search_provider_bakeoff")
    if isinstance(bakeoff, dict):
        for key in ("status", "verdict", "selected_provider", "provider"):
            value = bakeoff.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    scope = _extract_scope_result(live_cycle)
    if not isinstance(scope, dict):
        return None
    steps = scope.get("steps")
    if not isinstance(steps, dict):
        return None
    search_materialize = steps.get("search_materialize")
    if not isinstance(search_materialize, dict):
        return None
    details = search_materialize.get("details")
    if not isinstance(details, dict):
        return None
    for key in ("search_provider_status", "provider_status", "provider"):
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_quality_conclusion(live_cycle: dict[str, Any] | None) -> str:
    run_context = _extract_package_run_context(live_cycle)
    if run_context:
        if bool(run_context.get("secondary_research_needed")):
            return "secondary_research_needed"
    package = _extract_policy_package(live_cycle)
    storage_result = package.get("storage_result")
    if isinstance(storage_result, dict):
        if bool(storage_result.get("fail_closed")):
            return "fail_closed"
    if not isinstance(live_cycle, dict):
        return "not_proven"
    value = live_cycle.get("full_run_readiness")
    if isinstance(value, str) and value.strip():
        return value.strip()
    value = live_cycle.get("classification")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "not_proven"


def _extract_cycle_number(path: Path) -> int | None:
    match = re.search(r"live_cycle_(\d+)", path.name)
    if not match:
        return None
    return int(match.group(1))


def _resolve_live_cycle_artifacts(paths: list[Path]) -> list[Path]:
    resolved: list[Path] = []
    seen: set[str] = set()
    for item in paths:
        path_str = str(item)
        matches: list[Path] = []
        if any(char in path_str for char in ("*", "?", "[")):
            if item.is_absolute():
                parent = item.parent
                if parent.exists():
                    matches = sorted(parent.glob(item.name))
            else:
                matches = sorted(REPO_ROOT.glob(path_str))
        if not matches:
            matches = [item]
        for match in matches:
            key = str(match.resolve()) if match.exists() else str(match)
            if key in seen:
                continue
            seen.add(key)
            resolved.append(match)
    return resolved


def _extract_read_fetch_step(live_cycle: dict[str, Any] | None) -> dict[str, Any] | None:
    scope = _extract_scope_result(live_cycle)
    if not isinstance(scope, dict):
        return None
    steps = scope.get("steps")
    if not isinstance(steps, dict):
        return None
    read_fetch = steps.get("read_fetch")
    return read_fetch if isinstance(read_fetch, dict) else None


def _extract_cycle_selected_url(live_cycle: dict[str, Any] | None) -> str | None:
    read_fetch = _extract_read_fetch_step(live_cycle)
    if not isinstance(read_fetch, dict):
        return None
    details = read_fetch.get("details")
    if not isinstance(details, dict):
        return None
    candidate_audit = details.get("candidate_audit")
    if isinstance(candidate_audit, list):
        for row in candidate_audit:
            if not isinstance(row, dict):
                continue
            if str(row.get("outcome") or "") != "materialized_raw_scrape":
                continue
            url = row.get("url")
            if isinstance(url, str) and url.strip():
                return url.strip()
    ranked = details.get("ranked_candidates")
    if isinstance(ranked, list):
        for row in ranked:
            if not isinstance(row, dict):
                continue
            rank = int(row.get("rank") or 0)
            if rank != 1:
                continue
            url = row.get("url")
            if isinstance(url, str) and url.strip():
                return url.strip()
    return None


def _extract_cycle_reader_artifact_uri(live_cycle: dict[str, Any] | None) -> str | None:
    refs = _extract_summarize_refs(live_cycle)
    if isinstance(refs, dict):
        direct = refs.get("reader_artifact_uri")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
    read_fetch = _extract_read_fetch_step(live_cycle)
    if not isinstance(read_fetch, dict):
        return None
    refs = read_fetch.get("refs")
    if not isinstance(refs, dict):
        return None
    artifact_refs = refs.get("artifact_refs")
    if not isinstance(artifact_refs, list):
        return None
    for item in artifact_refs:
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def _storage_gate(live_storage_probe: dict[str, Any] | None, key: str, missing_details: str) -> dict[str, str]:
    if not isinstance(live_storage_probe, dict):
        return _gate_entry("not_proven", missing_details)
    gates = live_storage_probe.get("gates")
    if not isinstance(gates, dict):
        return _gate_entry("not_proven", missing_details)
    node = gates.get(key)
    if not isinstance(node, dict):
        return _gate_entry("not_proven", missing_details)
    status = _normalize_status(str(node.get("status") or "not_proven"))
    details = str(node.get("details") or missing_details)
    return _gate_entry(status, details)


def _taxonomy_gate(scorecard: dict[str, Any], key: str, missing_details: str) -> dict[str, str]:
    taxonomy = scorecard.get("taxonomy")
    if not isinstance(taxonomy, dict):
        return _gate_entry("not_proven", missing_details)
    node = taxonomy.get(key)
    if not isinstance(node, dict):
        return _gate_entry("not_proven", missing_details)
    status = _normalize_status(str(node.get("status") or "not_proven"))
    details = str(node.get("details") or missing_details)
    return _gate_entry(status, details)


def _build_gate_statuses(
    *,
    scorecard: dict[str, Any],
    live_storage_probe: dict[str, Any] | None,
    live_cycle: dict[str, Any] | None,
    economic_status: dict[str, Any] | None,
) -> dict[str, dict[str, str]]:
    cycle_storage_result: dict[str, Any] = {}
    package = _extract_policy_package(live_cycle)
    if package:
        storage_result = package.get("storage_result")
        if isinstance(storage_result, dict):
            cycle_storage_result = storage_result

    scraped_quality = _taxonomy_gate(
        scorecard,
        "scraped/search",
        "scraped quality taxonomy missing",
    )
    reader_taxonomy = _taxonomy_gate(
        scorecard,
        "reader",
        "reader taxonomy missing",
    )
    scraped_quality = _gate_entry(
        _combine_status([scraped_quality["status"], reader_taxonomy["status"]]),
        f"scraped/search={scraped_quality['status']}, reader={reader_taxonomy['status']}",
    )

    structured_taxonomy = _taxonomy_gate(
        scorecard,
        "structured-source",
        "structured-source taxonomy missing",
    )
    scope = _extract_scope_result(live_cycle)
    structured_family_seen = False
    if isinstance(scope, dict):
        scope_item = scope.get("scope_item")
        if isinstance(scope_item, dict):
            source_family = str(scope_item.get("source_family") or "")
            if source_family in {"legistar", "openstates", "ckan", "socrata", "arcgis"}:
                structured_family_seen = True
    structured_quality = structured_taxonomy
    if structured_taxonomy["status"] == "pass" and not structured_family_seen:
        structured_quality = _gate_entry(
            "not_proven",
            "scorecard indicates structured pass, but live cycle lacks structured source-family evidence",
        )

    postgres_gate = _storage_gate(
        live_storage_probe,
        "postgres_package_row",
        "live storage probe missing postgres package linkage evidence",
    )
    if (
        postgres_gate["status"] == "not_proven"
        and postgres_gate["details"] == "live storage probe missing postgres package linkage evidence"
    ):
        package_id = _extract_package_id(live_cycle)
        backend_run_id = _extract_backend_run_id(live_cycle)
        if package_id and backend_run_id:
            postgres_gate = _gate_entry(
                "not_proven",
                "cycle artifact includes package_id and backend_run_id; db storage probe still missing",
            )

    minio_gate = _storage_gate(
        live_storage_probe,
        "minio_object_readback",
        "live storage probe missing MinIO readback evidence",
    )
    if (
        minio_gate["status"] == "not_proven"
        and minio_gate["details"] == "live storage probe missing MinIO readback evidence"
        and cycle_storage_result
    ):
        status = str(cycle_storage_result.get("artifact_readback_status") or "").strip()
        write_status = str(cycle_storage_result.get("artifact_write_status") or "").strip()
        if status == "proven":
            minio_gate = _gate_entry("pass", "cycle artifact reports artifact_readback_status=proven")
        elif status:
            minio_gate = _gate_entry(
                "not_proven",
                f"cycle artifact reports artifact_readback_status={status} (artifact_write_status={write_status or 'unknown'})",
            )

    pgvector_gate = _storage_gate(
        live_storage_probe,
        "pgvector_derivation",
        "live storage probe missing pgvector derivation evidence",
    )
    if (
        pgvector_gate["status"] == "not_proven"
        and pgvector_gate["details"] == "live storage probe missing pgvector derivation evidence"
        and cycle_storage_result
    ):
        truth_role = str(cycle_storage_result.get("pgvector_truth_role") or "").strip()
        if truth_role == "derived_index":
            pgvector_gate = _gate_entry(
                "not_proven",
                "cycle artifact reports pgvector_truth_role=derived_index; chunk-level live probe is still missing",
            )

    windmill_status = "not_proven"
    windmill_details = "windmill run evidence missing from cycle artifact"
    if isinstance(live_cycle, dict):
        manual_run = live_cycle.get("manual_run")
        if isinstance(manual_run, dict):
            job_id = manual_run.get("windmill_job_id")
            final_status = str(manual_run.get("final_status") or "")
            if isinstance(job_id, str) and job_id.strip() and final_status == "succeeded":
                windmill_status = "pass"
                windmill_details = "live windmill flow run succeeded with concrete windmill_job_id"
            elif isinstance(job_id, str) and job_id.strip():
                windmill_status = "fail"
                windmill_details = f"windmill job present but final_status={final_status or 'unknown'}"
    windmill_gate = _gate_entry(windmill_status, windmill_details)

    llm_taxonomy = _taxonomy_gate(
        scorecard,
        "LLM narrative",
        "LLM narrative taxonomy missing",
    )
    llm_gate = llm_taxonomy
    if isinstance(economic_status, dict):
        canonical_run_id = str(economic_status.get("canonical_pipeline_run_id") or "")
        canonical_step_id = str(economic_status.get("canonical_pipeline_step_id") or "")
        if canonical_run_id and canonical_step_id:
            llm_gate = _gate_entry("pass", "economic status endpoint returned canonical LLM run+step ids")
    elif llm_taxonomy["status"] == "pass":
        llm_gate = _gate_entry(
            "not_proven",
            "taxonomy indicates pass but economic status endpoint evidence is missing",
        )

    sufficiency = _taxonomy_gate(
        scorecard,
        "sufficiency gate",
        "sufficiency taxonomy missing",
    )
    economic_reasoning = _taxonomy_gate(
        scorecard,
        "economic reasoning",
        "economic reasoning taxonomy missing",
    )
    economic_status_gate = _gate_entry(
        _combine_status([sufficiency["status"], economic_reasoning["status"]]),
        f"sufficiency={sufficiency['status']}, economic_reasoning={economic_reasoning['status']}",
    )
    if isinstance(economic_status, dict):
        endpoint_state = str(economic_status.get("analysis_status") or "").strip()
        if endpoint_state:
            if endpoint_state in {"decision_grade", "ready"}:
                economic_status_gate = _gate_entry("pass", f"analysis_status_endpoint={endpoint_state}")
            elif endpoint_state in {"insufficient", "blocked"}:
                economic_status_gate = _gate_entry("fail", f"analysis_status_endpoint={endpoint_state}")
            else:
                economic_status_gate = _gate_entry("not_proven", f"analysis_status_endpoint={endpoint_state}")

    admin_gate = _gate_entry(
        "not_proven",
        "economic analysis status endpoint artifact missing",
    )
    if isinstance(economic_status, dict):
        endpoint_ok = bool(economic_status.get("endpoint_ok"))
        admin_gate = _gate_entry(
            "pass" if endpoint_ok else "fail",
            "analysis-status endpoint response captured" if endpoint_ok else "analysis-status endpoint returned error",
        )

    unified_status = _combine_status(
        [
            scraped_quality["status"],
            structured_quality["status"],
            postgres_gate["status"],
            minio_gate["status"],
            pgvector_gate["status"],
        ]
    )
    unified_details = (
        f"scraped={scraped_quality['status']}, "
        f"structured={structured_quality['status']}, "
        f"postgres={postgres_gate['status']}, "
        f"minio={minio_gate['status']}, "
        f"pgvector={pgvector_gate['status']}"
    )
    unified_gate = _gate_entry(unified_status, unified_details)

    return {
        "scraped_quality": scraped_quality,
        "structured_quality": structured_quality,
        "unified_package": unified_gate,
        "postgres": postgres_gate,
        "minio": minio_gate,
        "pgvector": pgvector_gate,
        "windmill": windmill_gate,
        "llm_narrative": llm_gate,
        "economic_analysis": economic_status_gate,
        "admin_read_model": admin_gate,
    }


def _build_recommendations(gates: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    failed = [name for name, node in gates.items() if node["status"] == "fail"]
    not_proven = [name for name, node in gates.items() if node["status"] == "not_proven"]
    mapping = {
        "scraped_quality": "Improve selected-artifact search/ranker quality and verify top-candidate relevance metrics.",
        "structured_quality": "Run a structured-source family in live cycle and verify provenance/storage joins.",
        "unified_package": "Ensure scraped+structured+storage gates pass in the same run with one package_id.",
        "postgres": "Persist and verify policy_evidence_packages row linked to exact backend_run_id.",
        "minio": "Repair MinIO object readback for current run artifact_refs.",
        "pgvector": "Verify document_chunks + embeddings tied to the same document_id from run refs.",
        "windmill": "Capture successful live windmill_job_id and backend_run_id linkage in the same cycle.",
        "llm_narrative": "Persist canonical LLM analysis run+step ids and bind to package_id.",
        "economic_analysis": "Improve quantitative evidence to pass economic analysis status endpoint.",
        "admin_read_model": "Capture and store /analysis-status endpoint response artifact for the cycle.",
    }
    ordered = failed + [name for name in not_proven if name not in failed]
    return {
        "failed_gates": failed,
        "not_proven_gates": not_proven,
        "next_tweaks": [mapping[name] for name in ordered if name in mapping],
    }


def _build_cycle_ledger(
    *,
    scorecard: dict[str, Any],
    gates: dict[str, dict[str, str]],
    recommendations: dict[str, list[str]],
    live_cycles: list[dict[str, Any]],
    live_storage_probe: dict[str, Any] | None,
    economic_status: dict[str, Any] | None,
    deploy_sha: str | None,
    max_cycles: int,
) -> list[dict[str, Any]]:
    matrix_attempt = scorecard.get("matrix_attempt")
    if not isinstance(matrix_attempt, dict):
        matrix_attempt = {}
    current_retry_round = int(matrix_attempt.get("retry_round") or 0)
    current_retry_round = max(0, min(current_retry_round, max_cycles - 1))

    default_package_id = ""
    vertical_package = scorecard.get("vertical_package")
    if isinstance(vertical_package, dict):
        default_package_id = str(vertical_package.get("package_id") or "")
    if not default_package_id and isinstance(live_storage_probe, dict):
        inputs = live_storage_probe.get("inputs")
        if isinstance(inputs, dict):
            default_package_id = str(inputs.get("package_id") or "")

    minio_gate = gates["minio"]
    pgvector_gate = gates["pgvector"]
    postgres_gate = gates["postgres"]

    pgvector_chunks = None
    pgvector_embedded = None
    if isinstance(live_storage_probe, dict):
        pgvector_node = (live_storage_probe.get("gates") or {}).get("pgvector_derivation")
        if isinstance(pgvector_node, dict):
            pgvector_chunks = pgvector_node.get("total_chunks")
            pgvector_embedded = pgvector_node.get("with_embedding")

    economic_endpoint = None
    if isinstance(economic_status, dict):
        economic_endpoint = str(economic_status.get("analysis_status") or "") or None

    cycle_rows: list[dict[str, Any]] = []
    cycle_map: dict[int, dict[str, Any]] = {}
    for payload in live_cycles:
        cycle_num_raw = payload.get("cycle_number")
        if not isinstance(cycle_num_raw, int) or cycle_num_raw <= 0:
            continue
        cycle_map[cycle_num_raw] = payload

    for idx in range(max_cycles):
        cycle_num = idx + 1
        cycle_payload = cycle_map.get(cycle_num)
        live_cycle = cycle_payload.get("artifact") if isinstance(cycle_payload, dict) else None
        has_cycle_artifact = isinstance(live_cycle, dict)
        is_current = has_cycle_artifact or (not cycle_map and idx == current_retry_round)
        status = "not_executed"
        verdict = None
        next_tweak = recommendations["next_tweaks"][0] if recommendations["next_tweaks"] else ""
        targeted_tweak = str(matrix_attempt.get("targeted_tweak") or "unspecified")

        windmill_job_id = None
        if isinstance(live_cycle, dict):
            manual_run = live_cycle.get("manual_run")
            if isinstance(manual_run, dict):
                raw_job = manual_run.get("windmill_job_id")
                if isinstance(raw_job, str) and raw_job.strip():
                    windmill_job_id = raw_job.strip()
        backend_run_id = _extract_backend_run_id(live_cycle)
        selected_url = _extract_cycle_selected_url(live_cycle)
        artifact_uri = _extract_cycle_reader_artifact_uri(live_cycle)
        package_id = _extract_package_id(live_cycle) or default_package_id or None
        package_artifact_uri = _extract_package_artifact_uri(live_cycle)
        run_context = _extract_package_run_context(live_cycle)
        mechanism_family_hint = str(run_context.get("mechanism_family_hint") or "") or None
        impact_mode_hint = str(run_context.get("impact_mode_hint") or "") or None
        secondary_research_needed = (
            bool(run_context.get("secondary_research_needed"))
            if run_context
            else None
        )
        provider_status = _extract_provider_status(live_cycle)
        quality_conclusion = _extract_quality_conclusion(live_cycle) if has_cycle_artifact else None

        if is_current:
            status = "completed"
            verdict = "fail" if recommendations["failed_gates"] else ("partial" if recommendations["not_proven_gates"] else "pass")
            next_tweak = recommendations["next_tweaks"][0] if recommendations["next_tweaks"] else "none"
        row = {
            "cycle_number": cycle_num,
            "status": status,
            "targeted_tweak": targeted_tweak if is_current else "",
            "deploy_sha": deploy_sha if is_current else None,
            "windmill_job_id": windmill_job_id if is_current else None,
            "backend_run_id": backend_run_id if is_current else None,
            "package_id": package_id if is_current else None,
            "package_artifact_uri": package_artifact_uri if is_current else None,
            "selected_url": selected_url if is_current else None,
            "reader_artifact_uri": artifact_uri if is_current else None,
            "provider_status": provider_status if is_current else None,
            "mechanism_family_hint": mechanism_family_hint if is_current else None,
            "impact_mode_hint": impact_mode_hint if is_current else None,
            "secondary_research_needed": secondary_research_needed if is_current else None,
            "quality_conclusion": quality_conclusion if is_current else None,
            "minio_readback": minio_gate["status"] if is_current else "not_proven",
            "pgvector_chunk_stats": (
                {"total_chunks": pgvector_chunks, "with_embedding": pgvector_embedded}
                if is_current
                else None
            ),
            "package_row_linkage": postgres_gate["status"] if is_current else "not_proven",
            "economic_status_endpoint": economic_endpoint if is_current else None,
            "verdict": verdict,
            "next_tweak": next_tweak,
        }
        cycle_rows.append(row)
    return cycle_rows


def build_eval_cycles_report(
    *,
    scorecard: dict[str, Any],
    retry_ledger: dict[str, Any] | None,
    live_storage_probe: dict[str, Any] | None,
    live_cycle: dict[str, Any] | None,
    economic_status: dict[str, Any] | None,
    max_cycles: int,
    deploy_sha: str | None,
    live_cycles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    bounded_max_cycles = max(1, min(int(max_cycles), 10))
    all_live_cycles = live_cycles if live_cycles else []
    primary_live_cycle = live_cycle
    if all_live_cycles and primary_live_cycle is None:
        first = all_live_cycles[0].get("artifact")
        primary_live_cycle = first if isinstance(first, dict) else None
    if not all_live_cycles and primary_live_cycle is not None:
        all_live_cycles = [{"cycle_number": 1, "artifact": primary_live_cycle}]

    gates = _build_gate_statuses(
        scorecard=scorecard,
        live_storage_probe=live_storage_probe,
        live_cycle=primary_live_cycle,
        economic_status=economic_status,
    )
    recommendations = _build_recommendations(gates)
    verdict = "fail" if recommendations["failed_gates"] else ("partial" if recommendations["not_proven_gates"] else "pass")
    matrix_attempt = scorecard.get("matrix_attempt")
    if not isinstance(matrix_attempt, dict):
        matrix_attempt = {}

    cycle_ledger = _build_cycle_ledger(
        scorecard=scorecard,
        gates=gates,
        recommendations=recommendations,
        live_cycles=all_live_cycles,
        live_storage_probe=live_storage_probe,
        economic_status=economic_status,
        deploy_sha=deploy_sha,
        max_cycles=bounded_max_cycles,
    )
    cycle_1 = cycle_ledger[0] if cycle_ledger else {}
    cycle_1_partial_reason = (
        "Cycle 1 is partial: selected evidence was economically insufficient, "
        "structured lane is not proven in this run, and admin/economic endpoint "
        "proof is missing."
    )

    return {
        "feature_key": "bd-3wefe.13",
        "max_cycles": bounded_max_cycles,
        "current_cycle_input": matrix_attempt,
        "gate_categories": gates,
        "recommendations": recommendations,
        "final_verdict": verdict,
        "cycle_ledger": cycle_ledger,
        "cycle_1_assessment": {
            "artifact": "docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_01_windmill_domain_run.json",
            "status": "partial",
            "reason": cycle_1_partial_reason,
            "windmill_job_id": cycle_1.get("windmill_job_id"),
            "backend_run_id": cycle_1.get("backend_run_id"),
        },
        "artifact_sources": {
            "scorecard_present": True,
            "retry_ledger_present": retry_ledger is not None,
            "live_storage_probe_present": live_storage_probe is not None,
            "live_cycle_present": primary_live_cycle is not None,
            "live_cycle_artifact_count": len(all_live_cycles),
            "economic_status_present": economic_status is not None,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Policy Evidence Quality Spine Eval Cycles",
        "",
        f"- feature_key: `{report['feature_key']}`",
        f"- final_verdict: `{report['final_verdict']}`",
        f"- max_cycles: `{report['max_cycles']}`",
        "",
        "## Gate status",
        "",
        "| Gate | Status | Details |",
        "| --- | --- | --- |",
    ]
    for gate in (
        "scraped_quality",
        "structured_quality",
        "unified_package",
        "postgres",
        "minio",
        "pgvector",
        "windmill",
        "llm_narrative",
        "economic_analysis",
        "admin_read_model",
    ):
        item = report["gate_categories"][gate]
        lines.append(f"| {gate} | {item['status']} | {item['details']} |")

    lines.extend(
        [
            "",
            "## Cycle 1 assessment",
            "",
            f"- artifact: `{report['cycle_1_assessment']['artifact']}`",
            f"- status: `{report['cycle_1_assessment']['status']}`",
            f"- reason: {report['cycle_1_assessment']['reason']}",
            "",
            "## Recommended tweaks",
            "",
        ]
    )
    for tweak in report["recommendations"]["next_tweaks"]:
        lines.append(f"- {tweak}")

    lines.extend(
        [
            "",
            "## Cycle ledger",
            "",
            "| Cycle | Status | Deploy SHA | Windmill Job | Backend Run | Package | Package Artifact | Selected URL | Reader Artifact | Provider | Mechanism | Impact Mode | Secondary Research | Quality Conclusion | Verdict | Next tweak |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for cycle in report["cycle_ledger"]:
        lines.append(
            f"| {cycle.get('cycle_number')} | {cycle.get('status')} | "
            f"{cycle.get('deploy_sha') or '-'} | {cycle.get('windmill_job_id') or '-'} | "
            f"{cycle.get('backend_run_id') or '-'} | {cycle.get('package_id') or '-'} | "
            f"{cycle.get('package_artifact_uri') or '-'} | {cycle.get('selected_url') or '-'} | "
            f"{cycle.get('reader_artifact_uri') or '-'} | {cycle.get('provider_status') or '-'} | "
            f"{cycle.get('mechanism_family_hint') or '-'} | {cycle.get('impact_mode_hint') or '-'} | "
            f"{cycle.get('secondary_research_needed') if cycle.get('secondary_research_needed') is not None else '-'} | "
            f"{cycle.get('quality_conclusion') or '-'} | "
            f"{cycle.get('verdict') or '-'} | {cycle.get('next_tweak') or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD_PATH)
    parser.add_argument("--retry-ledger", type=Path, default=DEFAULT_RETRY_LEDGER_PATH)
    parser.add_argument("--live-storage-probe", type=Path, default=DEFAULT_LIVE_STORAGE_PATH)
    parser.add_argument(
        "--live-cycle-artifact",
        type=Path,
        action="append",
        default=None,
        help="Cycle artifact path. Repeat flag to include multiple cycles.",
    )
    parser.add_argument("--economic-status", type=Path, default=None)
    parser.add_argument("--deploy-sha", default=None)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--max-cycles", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    scorecard = _load_json(args.scorecard)
    if scorecard is None:
        raise SystemExit(f"missing scorecard artifact: {args.scorecard}")
    retry_ledger = _load_json(args.retry_ledger)
    live_storage_probe = _load_json(args.live_storage_probe)
    raw_live_cycle_paths = args.live_cycle_artifact or [DEFAULT_LIVE_CYCLE_PATH]
    live_cycle_paths = _resolve_live_cycle_artifacts(raw_live_cycle_paths)
    live_cycle_entries: list[dict[str, Any]] = []
    fallback_cycle_number = 1
    for path in live_cycle_paths:
        payload = _load_json(path)
        if payload is None:
            continue
        cycle_number = _extract_cycle_number(path) or fallback_cycle_number
        fallback_cycle_number = max(fallback_cycle_number, cycle_number + 1)
        live_cycle_entries.append(
            {
                "cycle_number": cycle_number,
                "artifact": payload,
                "artifact_path": str(path),
            }
        )
    live_cycle_entries.sort(key=lambda item: int(item.get("cycle_number") or 0))
    live_cycle = None
    if live_cycle_entries:
        first_cycle = live_cycle_entries[0]
        maybe_payload = first_cycle.get("artifact")
        if isinstance(maybe_payload, dict):
            live_cycle = maybe_payload
    economic_status = _load_json(args.economic_status) if args.economic_status else None
    report = build_eval_cycles_report(
        scorecard=scorecard,
        retry_ledger=retry_ledger,
        live_storage_probe=live_storage_probe,
        live_cycle=live_cycle,
        live_cycles=live_cycle_entries,
        economic_status=economic_status,
        max_cycles=args.max_cycles,
        deploy_sha=args.deploy_sha,
    )
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.out_md.write_text(render_markdown(report), encoding="utf-8")
    print(
        "policy_evidence_quality_spine_eval_cycles complete: "
        f"verdict={report['final_verdict']} max_cycles={report['max_cycles']}"
    )
    return 1 if report["final_verdict"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
