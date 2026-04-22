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
DEFAULT_SOURCE_CATALOG_PATH = ARTIFACTS_DIR / "live_cycle_08_structured_source_catalog.json"
DEFAULT_OUTPUT_JSON = ARTIFACTS_DIR / "quality_spine_eval_cycles_report.json"
DEFAULT_OUTPUT_MD = ARTIFACTS_DIR / "quality_spine_eval_cycles_report.md"

VALID_STATUSES = {"pass", "partial", "not_proven", "fail"}
MAX_SUPPORTED_CYCLES = 30

GATE_DEFINITIONS: dict[str, dict[str, str]] = {
    "D1": {"name": "source_catalog", "domain": "data_moat", "severity": "blocking"},
    "D2": {"name": "scraped_evidence_quality", "domain": "data_moat", "severity": "blocking"},
    "D3": {"name": "structured_evidence_quality", "domain": "data_moat", "severity": "blocking"},
    "D4": {"name": "unified_package_identity", "domain": "data_moat", "severity": "blocking"},
    "D5": {"name": "storage_readback", "domain": "data_moat", "severity": "blocking"},
    "D6": {"name": "windmill_integration", "domain": "data_moat", "severity": "blocking"},
    "E1": {"name": "mechanism_coverage", "domain": "economic_analysis", "severity": "blocking"},
    "E2": {"name": "sufficiency_gate", "domain": "economic_analysis", "severity": "blocking"},
    "E3": {"name": "secondary_research_loop", "domain": "economic_analysis", "severity": "blocking"},
    "E4": {"name": "canonical_llm_binding", "domain": "economic_analysis", "severity": "blocking"},
    "E5": {"name": "decision_grade_quality", "domain": "economic_analysis", "severity": "blocking"},
    "E6": {"name": "admin_read_model", "domain": "economic_analysis", "severity": "nonblocking"},
    "M1": {"name": "manual_data_audit", "domain": "manual_audit", "severity": "blocking"},
    "M2": {"name": "manual_economic_audit", "domain": "manual_audit", "severity": "blocking"},
    "M3": {"name": "manual_gate_decision", "domain": "manual_audit", "severity": "blocking"},
}


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
        return 3
    if status == "not_proven":
        return 2
    if status == "partial":
        return 1
    return 0


def _combine_status(statuses: list[str]) -> str:
    rank = max((_status_rank(_normalize_status(item)) for item in statuses), default=0)
    if rank == 3:
        return "fail"
    if rank == 2:
        return "not_proven"
    if rank == 1:
        return "partial"
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
                matches = sorted(Path.cwd().glob(path_str))
                if not matches:
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


def _gate_record(code: str, status: str, details: str) -> dict[str, str]:
    definition = GATE_DEFINITIONS[code]
    return {
        "code": code,
        "name": definition["name"],
        "domain": definition["domain"],
        "severity": definition["severity"],
        "status": _normalize_status(status),
        "details": details,
    }


def _source_catalog_gate(
    *,
    source_catalog: dict[str, Any] | None,
    live_cycle: dict[str, Any] | None,
) -> dict[str, str]:
    candidates: list[dict[str, Any]] = []
    if isinstance(source_catalog, dict):
        raw_sources = source_catalog.get("structured_sources")
        if isinstance(raw_sources, list):
            candidates.extend(item for item in raw_sources if isinstance(item, dict))

    run_catalog = _extract_package_run_context(live_cycle).get("structured_source_catalog")
    if isinstance(run_catalog, list):
        candidates.extend(item for item in run_catalog if isinstance(item, dict))

    unique: dict[str, dict[str, Any]] = {}
    for item in candidates:
        family = str(item.get("source_family") or item.get("provider") or "").strip()
        if family:
            unique[family] = item

    required_fields = {
        "source_family",
        "free_status",
        "signup_or_key",
        "access_method",
        "jurisdiction_coverage",
        "policy_domain_relevance",
        "storage_target",
        "economic_usefulness_score",
    }
    complete_families = [
        family
        for family, item in unique.items()
        if required_fields.issubset(set(item.keys()))
    ]
    free_ingestible = [
        family
        for family, item in unique.items()
        if str(item.get("free_status") or "").startswith("free")
        and str(item.get("access_method") or "").strip()
    ]

    if len(complete_families) >= 2 and len(free_ingestible) >= 2:
        status = "pass"
    elif complete_families or free_ingestible:
        status = "partial"
    else:
        status = "not_proven"
    return _gate_record(
        "D1",
        status,
        (
            f"catalog_families={sorted(unique)}, "
            f"complete_families={sorted(complete_families)}, "
            f"free_ingestible={sorted(free_ingestible)}"
        ),
    )


def _build_gate_statuses(
    *,
    scorecard: dict[str, Any],
    live_storage_probe: dict[str, Any] | None,
    live_cycle: dict[str, Any] | None,
    economic_status: dict[str, Any] | None,
    source_catalog: dict[str, Any] | None,
    manual_data_audit_path: Path | None,
    manual_economic_audit_path: Path | None,
    manual_gate_decision_path: Path | None,
) -> dict[str, dict[str, str]]:
    cycle_storage_result: dict[str, Any] = {}
    package = _extract_policy_package(live_cycle)
    if package:
        storage_result = package.get("storage_result")
        if isinstance(storage_result, dict):
            cycle_storage_result = storage_result

    scraped_taxonomy = _taxonomy_gate(
        scorecard,
        "scraped/search",
        "scraped quality taxonomy missing",
    )
    reader_taxonomy = _taxonomy_gate(
        scorecard,
        "reader",
        "reader taxonomy missing",
    )
    scraped_status = _combine_status([scraped_taxonomy["status"], reader_taxonomy["status"]])
    selected_url = _extract_cycle_selected_url(live_cycle)
    if scraped_status == "pass" and not selected_url:
        scraped_status = "partial"
    source_catalog_gate = _source_catalog_gate(
        source_catalog=source_catalog,
        live_cycle=live_cycle,
    )

    scraped_quality = _gate_record(
        "D2",
        scraped_status,
        (
            f"scraped/search={scraped_taxonomy['status']}, reader={reader_taxonomy['status']}, "
            f"selected_url={'present' if selected_url else 'missing'}"
        ),
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
            "partial",
            "scorecard indicates structured pass, but live cycle lacks structured source-family evidence",
        )
    run_context = _extract_package_run_context(live_cycle)
    structured_sources = run_context.get("structured_sources")
    structured_source_count = (
        len(structured_sources)
        if isinstance(structured_sources, list)
        else 0
    )
    if structured_source_count and structured_quality["status"] == "not_proven":
        structured_quality = _gate_entry(
            "partial",
            f"run_context contains structured_sources count={structured_source_count}; manual quality audit still pending",
        )
    structured_quality = _gate_record("D3", structured_quality["status"], structured_quality["details"])

    postgres_gate_entry = _storage_gate(
        live_storage_probe,
        "postgres_package_row",
        "live storage probe missing postgres package linkage evidence",
    )
    if (
        postgres_gate_entry["status"] == "not_proven"
        and postgres_gate_entry["details"] == "live storage probe missing postgres package linkage evidence"
    ):
        package_id = _extract_package_id(live_cycle)
        backend_run_id = _extract_backend_run_id(live_cycle)
        if package_id and backend_run_id:
            postgres_gate_entry = _gate_entry(
                "partial",
                "cycle artifact includes package_id and backend_run_id; db storage probe still missing",
            )
    postgres_gate = _gate_record("D5", postgres_gate_entry["status"], postgres_gate_entry["details"])

    minio_gate_entry = _storage_gate(
        live_storage_probe,
        "minio_object_readback",
        "live storage probe missing MinIO readback evidence",
    )
    if (
        minio_gate_entry["status"] == "not_proven"
        and minio_gate_entry["details"] == "live storage probe missing MinIO readback evidence"
        and cycle_storage_result
    ):
        status = str(cycle_storage_result.get("artifact_readback_status") or "").strip()
        write_status = str(cycle_storage_result.get("artifact_write_status") or "").strip()
        if status == "proven":
            minio_gate_entry = _gate_entry("pass", "cycle artifact reports artifact_readback_status=proven")
        elif status:
            minio_gate_entry = _gate_entry(
                "partial",
                f"cycle artifact reports artifact_readback_status={status} (artifact_write_status={write_status or 'unknown'})",
            )
    minio_gate = _gate_record("D5", minio_gate_entry["status"], minio_gate_entry["details"])

    pgvector_gate_entry = _storage_gate(
        live_storage_probe,
        "pgvector_derivation",
        "live storage probe missing pgvector derivation evidence",
    )
    if (
        pgvector_gate_entry["status"] == "not_proven"
        and pgvector_gate_entry["details"] == "live storage probe missing pgvector derivation evidence"
        and cycle_storage_result
    ):
        truth_role = str(cycle_storage_result.get("pgvector_truth_role") or "").strip()
        if truth_role == "derived_index":
            pgvector_gate_entry = _gate_entry(
                "partial",
                "cycle artifact reports pgvector_truth_role=derived_index; chunk-level live probe is still missing",
            )
    pgvector_gate = _gate_record("D5", pgvector_gate_entry["status"], pgvector_gate_entry["details"])

    storage_status = _combine_status(
        [postgres_gate["status"], minio_gate["status"], pgvector_gate["status"]]
    )
    storage_gate = _gate_record(
        "D5",
        storage_status,
        (
            f"postgres={postgres_gate['status']} ({postgres_gate['details']}), "
            f"minio={minio_gate['status']} ({minio_gate['details']}), "
            f"pgvector={pgvector_gate['status']} ({pgvector_gate['details']})"
        ),
    )

    windmill_status = "not_proven"
    windmill_details = "windmill run evidence missing from cycle artifact"
    if isinstance(live_cycle, dict):
        manual_run = live_cycle.get("manual_run")
        if isinstance(manual_run, dict):
            job_id = manual_run.get("windmill_job_id")
            final_status = str(manual_run.get("final_status") or "")
            backend_run_id = _extract_backend_run_id(live_cycle)
            if isinstance(job_id, str) and job_id.strip() and final_status == "succeeded":
                windmill_status = "pass" if backend_run_id else "partial"
                windmill_details = (
                    "live windmill flow run succeeded with concrete windmill_job_id"
                    + (", backend_run_id linked" if backend_run_id else ", backend_run_id missing")
                )
            elif isinstance(job_id, str) and job_id.strip():
                windmill_status = "fail"
                windmill_details = f"windmill job present but final_status={final_status or 'unknown'}"
    windmill_gate = _gate_record("D6", windmill_status, windmill_details)

    llm_taxonomy = _taxonomy_gate(
        scorecard,
        "LLM narrative",
        "LLM narrative taxonomy missing",
    )
    llm_gate_entry = llm_taxonomy
    if isinstance(economic_status, dict):
        canonical_run_id = str(economic_status.get("canonical_pipeline_run_id") or "")
        canonical_step_id = str(economic_status.get("canonical_pipeline_step_id") or "")
        if canonical_run_id and canonical_step_id:
            llm_gate_entry = _gate_entry("pass", "economic status endpoint returned canonical LLM run+step ids")
    elif llm_taxonomy["status"] == "pass":
        llm_gate_entry = _gate_entry(
            "not_proven",
            "taxonomy indicates pass but economic status endpoint evidence is missing",
        )
    llm_gate = _gate_record("E4", llm_gate_entry["status"], llm_gate_entry["details"])

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
    economic_status_gate_entry = _gate_entry(
        _combine_status([sufficiency["status"], economic_reasoning["status"]]),
        f"sufficiency={sufficiency['status']}, economic_reasoning={economic_reasoning['status']}",
    )
    if isinstance(economic_status, dict):
        endpoint_state = str(economic_status.get("analysis_status") or "").strip()
        if endpoint_state:
            if endpoint_state in {"decision_grade", "ready"}:
                economic_status_gate_entry = _gate_entry("pass", f"analysis_status_endpoint={endpoint_state}")
            elif endpoint_state in {"insufficient", "blocked"}:
                economic_status_gate_entry = _gate_entry("fail", f"analysis_status_endpoint={endpoint_state}")
            else:
                economic_status_gate_entry = _gate_entry("partial", f"analysis_status_endpoint={endpoint_state}")
    economic_status_gate = _gate_record("E2", economic_status_gate_entry["status"], economic_status_gate_entry["details"])

    admin_gate_entry = _gate_entry(
        "not_proven",
        "economic analysis status endpoint artifact missing",
    )
    if isinstance(economic_status, dict):
        endpoint_ok = bool(economic_status.get("endpoint_ok"))
        admin_gate_entry = _gate_entry(
            "pass" if endpoint_ok else "fail",
            "analysis-status endpoint response captured" if endpoint_ok else "analysis-status endpoint returned error",
        )
    admin_gate = _gate_record("E6", admin_gate_entry["status"], admin_gate_entry["details"])

    package_id = _extract_package_id(live_cycle)
    canonical_document_key = str(_extract_package_run_context(live_cycle).get("canonical_document_key") or "").strip()
    package_artifact_uri = _extract_package_artifact_uri(live_cycle)
    package_signal = "pass" if package_id and package_artifact_uri else ("partial" if package_id else "not_proven")

    unified_status = _combine_status(
        [scraped_quality["status"], structured_quality["status"], package_signal]
    )
    unified_details = (
        f"scraped={scraped_quality['status']}, "
        f"structured={structured_quality['status']}, "
        f"package_id={'present' if package_id else 'missing'}, "
        f"package_artifact={'present' if package_artifact_uri else 'missing'}, "
        f"canonical_document_key={'present' if canonical_document_key else 'missing'}, "
        f"structured_sources={structured_source_count}"
    )
    unified_gate = _gate_record("D4", unified_status, unified_details)

    mechanism = str(_extract_package_run_context(live_cycle).get("mechanism_family_hint") or "").strip()
    impact_mode = str(_extract_package_run_context(live_cycle).get("impact_mode_hint") or "").strip()
    mechanism_gate = _gate_record(
        "E1",
        "pass" if mechanism and impact_mode else ("partial" if mechanism or impact_mode else "not_proven"),
        (
            f"mechanism_family_hint={mechanism or 'missing'}, "
            f"impact_mode_hint={impact_mode or 'missing'}"
        ),
    )

    secondary_needed = _extract_package_run_context(live_cycle).get("secondary_research_needed")
    if isinstance(secondary_needed, bool):
        sec_status = "partial" if secondary_needed else "pass"
        sec_details = "secondary_research_needed=true" if secondary_needed else "secondary_research_needed=false"
    else:
        sec_status = "not_proven"
        sec_details = "secondary research signal missing from run_context"
    if isinstance(economic_status, dict):
        analysis_state = str(economic_status.get("analysis_status") or "").strip()
        if analysis_state == "secondary_research_needed":
            sec_status = "partial"
            sec_details = "analysis_status confirms secondary_research_needed"
        elif analysis_state in {"decision_grade", "ready"}:
            sec_status = "pass"
            sec_details = f"analysis_status={analysis_state}"
    secondary_research_gate = _gate_record("E3", sec_status, sec_details)

    decision_grade_status = "not_proven"
    decision_grade_details = "decision-grade evidence missing"
    if isinstance(economic_status, dict):
        verdict = str(economic_status.get("decision_grade_verdict") or "").strip()
        if verdict == "decision_grade":
            decision_grade_status = "pass"
            decision_grade_details = "decision_grade_verdict=decision_grade"
        elif verdict:
            decision_grade_status = "partial"
            decision_grade_details = f"decision_grade_verdict={verdict}"
    decision_grade_gate = _gate_record("E5", decision_grade_status, decision_grade_details)

    manual_data_gate = _gate_record(
        "M1",
        "pass" if manual_data_audit_path and manual_data_audit_path.exists() else "not_proven",
        f"manual_data_audit_path={manual_data_audit_path}" if manual_data_audit_path else "manual data audit markdown path missing",
    )
    manual_economic_gate = _gate_record(
        "M2",
        "pass" if manual_economic_audit_path and manual_economic_audit_path.exists() else "not_proven",
        f"manual_economic_audit_path={manual_economic_audit_path}" if manual_economic_audit_path else "manual economic audit markdown path missing",
    )
    manual_decision_gate = _gate_record(
        "M3",
        "pass" if manual_gate_decision_path and manual_gate_decision_path.exists() else "not_proven",
        f"manual_gate_decision_path={manual_gate_decision_path}" if manual_gate_decision_path else "manual gate decision markdown path missing",
    )

    return {
        "D1": source_catalog_gate,
        "D2": scraped_quality,
        "D3": structured_quality,
        "D4": unified_gate,
        "D5": storage_gate,
        "D6": windmill_gate,
        "E1": mechanism_gate,
        "E2": economic_status_gate,
        "E3": secondary_research_gate,
        "E4": llm_gate,
        "E5": decision_grade_gate,
        "E6": admin_gate,
        "M1": manual_data_gate,
        "M2": manual_economic_gate,
        "M3": manual_decision_gate,
    }


def _gate_groups(gates: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {"data_moat": [], "economic_analysis": [], "manual_audit": []}
    for code, gate in gates.items():
        grouped.setdefault(gate["domain"], []).append(code)
    for key in grouped:
        grouped[key] = sorted(grouped[key])
    return grouped


def _build_recommendations(gates: dict[str, dict[str, str]]) -> dict[str, Any]:
    failed = [code for code, node in gates.items() if node["status"] == "fail"]
    unresolved = [code for code, node in gates.items() if node["status"] in {"not_proven", "partial"}]
    mapping = {
        "D1": "Complete the source catalog with free/API/raw access, coverage, storage, and economic usefulness fields.",
        "D2": "Improve selected-artifact search/ranker quality and verify top-candidate relevance metrics.",
        "D3": "Run structured-source enrichment in the live cycle and verify source-family provenance.",
        "D4": "Ensure scraped+structured inputs dedupe into the same package_id with canonical identity.",
        "D5": "Persist/read back Postgres package row, MinIO artifacts, and pgvector chunks for the current package.",
        "D6": "Capture successful live windmill_job_id and backend_run_id linkage in the same cycle.",
        "E1": "Strengthen mechanism coverage to include both direct and indirect cost pathways in run_context.",
        "E2": "Raise sufficiency from partial/not_proven to pass using source-bound economic evidence.",
        "E3": "Productize secondary-research loop and bind returned artifacts to the same package_id.",
        "E4": "Persist canonical LLM analysis run+step ids and bind to package_id.",
        "E5": "Meet decision-grade rubric with explicit assumptions, uncertainty, and bounded conclusion.",
        "E6": "Capture and store /analysis-status endpoint response artifact for the cycle.",
        "M1": "Write manual San Jose data moat audit markdown for this cycle.",
        "M2": "Write manual San Jose economic-analysis audit markdown for this cycle.",
        "M3": "Write explicit manual stop/continue gate decision markdown for this cycle.",
    }
    ordered = failed + [code for code in unresolved if code not in failed]
    groups = _gate_groups(gates)
    progress: dict[str, dict[str, int]] = {}
    for domain, codes in groups.items():
        progress[domain] = {
            "total": len(codes),
            "pass": sum(1 for code in codes if gates[code]["status"] == "pass"),
            "partial": sum(1 for code in codes if gates[code]["status"] == "partial"),
            "not_proven": sum(1 for code in codes if gates[code]["status"] == "not_proven"),
            "fail": sum(1 for code in codes if gates[code]["status"] == "fail"),
        }
    return {
        "failed_gates": failed,
        "unresolved_gates": unresolved,
        "next_tweaks": [mapping[code] for code in ordered if code in mapping],
        "progress": progress,
    }


def _build_cycle_gate_snapshot(
    *,
    base_gates: dict[str, dict[str, str]],
    live_cycle: dict[str, Any] | None,
    economic_status: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
) -> dict[str, dict[str, str]]:
    snapshot = {code: dict(node) for code, node in base_gates.items()}
    run_context = _extract_package_run_context(live_cycle)
    selected_url = _extract_cycle_selected_url(live_cycle)
    package_id = _extract_package_id(live_cycle)
    package_artifact_uri = _extract_package_artifact_uri(live_cycle)

    if isinstance(live_cycle, dict):
        snapshot["D2"]["status"] = "pass" if selected_url else "partial"
        snapshot["D2"]["details"] = f"selected_url={'present' if selected_url else 'missing'}"
        structured_sources = run_context.get("structured_sources")
        structured_count = len(structured_sources) if isinstance(structured_sources, list) else 0
        if structured_count:
            snapshot["D3"]["status"] = "partial"
            snapshot["D3"]["details"] = f"structured_sources present count={structured_count}; manual quality audit pending"
        snapshot["D4"]["status"] = "pass" if package_id and package_artifact_uri else ("partial" if package_id else "not_proven")
        snapshot["D4"]["details"] = (
            f"package_id={'present' if package_id else 'missing'}, "
            f"package_artifact={'present' if package_artifact_uri else 'missing'}"
        )
        manual_run = live_cycle.get("manual_run")
        if isinstance(manual_run, dict):
            windmill_job_id = str(manual_run.get("windmill_job_id") or "").strip()
            final_status = str(manual_run.get("final_status") or "").strip()
            if windmill_job_id and final_status == "succeeded":
                snapshot["D6"]["status"] = "pass" if _extract_backend_run_id(live_cycle) else "partial"
                snapshot["D6"]["details"] = f"windmill_job_id={windmill_job_id}, backend_run_id={'present' if _extract_backend_run_id(live_cycle) else 'missing'}"
        mechanism = str(run_context.get("mechanism_family_hint") or "").strip()
        impact_mode = str(run_context.get("impact_mode_hint") or "").strip()
        snapshot["E1"]["status"] = "pass" if mechanism and impact_mode else ("partial" if mechanism or impact_mode else "not_proven")
        snapshot["E1"]["details"] = f"mechanism={mechanism or 'missing'} impact_mode={impact_mode or 'missing'}"
        secondary = run_context.get("secondary_research_needed")
        if isinstance(secondary, bool):
            snapshot["E3"]["status"] = "partial" if secondary else "pass"
            snapshot["E3"]["details"] = f"secondary_research_needed={secondary}"
    if isinstance(economic_status, dict):
        endpoint_state = str(economic_status.get("analysis_status") or "").strip()
        if endpoint_state:
            snapshot["E2"]["status"] = "pass" if endpoint_state in {"decision_grade", "ready"} else "partial"
            snapshot["E2"]["details"] = f"analysis_status_endpoint={endpoint_state}"
            if endpoint_state in {"insufficient", "blocked"}:
                snapshot["E2"]["status"] = "fail"
        if bool(economic_status.get("endpoint_ok")):
            snapshot["E6"]["status"] = "pass"
            snapshot["E6"]["details"] = "analysis-status endpoint response captured"
    if isinstance(metadata, dict):
        overrides = metadata.get("gate_overrides")
        if isinstance(overrides, dict):
            for code, value in overrides.items():
                if code not in snapshot or not isinstance(value, dict):
                    continue
                if "status" in value:
                    snapshot[code]["status"] = _normalize_status(str(value["status"]))
                if "details" in value:
                    snapshot[code]["details"] = str(value["details"])
    return snapshot


def _gate_deltas(
    previous: dict[str, dict[str, str]] | None,
    current: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    if not previous:
        return {}
    deltas: dict[str, dict[str, str]] = {}
    for code, node in current.items():
        prev = previous.get(code)
        if not prev:
            continue
        if prev.get("status") != node.get("status"):
            deltas[code] = {
                "from": str(prev.get("status")),
                "to": str(node.get("status")),
            }
    return deltas


def _load_cycle_metadata(paths: list[Path]) -> dict[int, dict[str, Any]]:
    metadata: dict[int, dict[str, Any]] = {}
    for path in paths:
        payload = _load_json(path)
        if payload is None:
            continue
        entries: list[dict[str, Any]] = []
        if isinstance(payload.get("cycles"), list):
            entries = [entry for entry in payload["cycles"] if isinstance(entry, dict)]
        elif isinstance(payload, dict):
            entries = [payload]
        for entry in entries:
            cycle_num = entry.get("cycle_number")
            if not isinstance(cycle_num, int) or cycle_num <= 0:
                continue
            metadata[cycle_num] = entry
    return metadata


def _build_cycle_ledger(
    *,
    scorecard: dict[str, Any],
    gates: dict[str, dict[str, str]],
    recommendations: dict[str, Any],
    live_cycles: list[dict[str, Any]],
    live_storage_probe: dict[str, Any] | None,
    economic_status: dict[str, Any] | None,
    deploy_sha: str | None,
    max_cycles: int,
    cycle_metadata: dict[int, dict[str, Any]],
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

    storage_gate = gates["D5"]

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

    previous_gate_snapshot: dict[str, dict[str, str]] | None = None
    for idx in range(max_cycles):
        cycle_num = idx + 1
        cycle_payload = cycle_map.get(cycle_num)
        metadata = cycle_metadata.get(cycle_num, {})
        live_cycle = cycle_payload.get("artifact") if isinstance(cycle_payload, dict) else None
        has_cycle_artifact = isinstance(live_cycle, dict)
        has_metadata = bool(metadata)
        is_current = has_cycle_artifact or has_metadata or (not cycle_map and idx == current_retry_round)
        status = "not_executed"
        verdict = None
        next_tweak = recommendations["next_tweaks"][0] if recommendations["next_tweaks"] else ""
        targeted_tweak = str(matrix_attempt.get("targeted_tweak") or "unspecified")
        if isinstance(metadata.get("targeted_tweak"), str):
            targeted_tweak = metadata["targeted_tweak"]

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

        cycle_gate_snapshot = _build_cycle_gate_snapshot(
            base_gates=gates,
            live_cycle=live_cycle,
            economic_status=economic_status,
            metadata=metadata,
        ) if is_current else {}
        gate_deltas = _gate_deltas(previous_gate_snapshot, cycle_gate_snapshot) if is_current else {}
        if is_current:
            previous_gate_snapshot = cycle_gate_snapshot

        commands_executed = metadata.get("commands_executed")
        if not isinstance(commands_executed, list):
            commands_executed = []
        code_config_tweaks = metadata.get("code_config_tweaks")
        if not isinstance(code_config_tweaks, list):
            code_config_tweaks = []
        extra_artifacts = metadata.get("artifacts")
        if not isinstance(extra_artifacts, list):
            extra_artifacts = []
        blocker_proof = metadata.get("external_blocker_proof")
        if not isinstance(blocker_proof, list):
            blocker_proof = []

        if is_current:
            blocking_unresolved = [
                code
                for code, gate in cycle_gate_snapshot.items()
                if gate["severity"] == "blocking" and gate["status"] != "pass"
            ]
            all_gates_reached = not blocking_unresolved
            attempted_fix = bool(
                commands_executed
                or code_config_tweaks
                or windmill_job_id
                or backend_run_id
                or deploy_sha
                or bool(metadata.get("attempted_fix"))
            )
            has_blocker_proof = bool(blocker_proof)
            if attempted_fix or has_blocker_proof or all_gates_reached:
                status = "completed"
            else:
                status = "guard_blocked"
            cycle_failed = any(
                gate["severity"] == "blocking" and gate["status"] == "fail"
                for gate in cycle_gate_snapshot.values()
            )
            cycle_unresolved = any(
                gate["severity"] == "blocking" and gate["status"] in {"partial", "not_proven"}
                for gate in cycle_gate_snapshot.values()
            )
            verdict = "fail" if cycle_failed else ("partial" if cycle_unresolved else "pass")
            next_tweak = recommendations["next_tweaks"][0] if recommendations["next_tweaks"] else "none"
            stop_continue = (
                "stop_ready_for_review"
                if verdict == "pass"
                else ("continue_fix_failed_gate" if verdict == "fail" else "continue_prove_remaining")
            )
        else:
            stop_continue = "continue"
        row = {
            "cycle_number": cycle_num,
            "status": status,
            "targeted_tweak": targeted_tweak if is_current else "",
            "inputs": metadata.get("inputs") if is_current else None,
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
            "storage_readback": storage_gate["status"] if is_current else "not_proven",
            "minio_readback": storage_gate["status"] if is_current else "not_proven",
            "pgvector_chunk_stats": (
                {"total_chunks": pgvector_chunks, "with_embedding": pgvector_embedded}
                if is_current
                else None
            ),
            "package_row_linkage": storage_gate["status"] if is_current else "not_proven",
            "economic_status_endpoint": economic_endpoint if is_current else None,
            "commands_executed": commands_executed if is_current else [],
            "code_config_tweaks": code_config_tweaks if is_current else [],
            "artifacts": (
                ([str(cycle_payload.get("artifact_path"))] if isinstance(cycle_payload, dict) and cycle_payload.get("artifact_path") else [])
                + [str(item) for item in extra_artifacts]
            ) if is_current else [],
            "external_blocker_proof": blocker_proof if is_current else [],
            "gate_snapshot": cycle_gate_snapshot if is_current else {},
            "gate_deltas": gate_deltas if is_current else {},
            "verdict": verdict,
            "stop_continue_decision": stop_continue if is_current else "continue",
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
    source_catalog: dict[str, Any] | None = None,
    live_cycles: list[dict[str, Any]] | None = None,
    cycle_metadata: dict[int, dict[str, Any]] | None = None,
    manual_data_audit_path: Path | None = None,
    manual_economic_audit_path: Path | None = None,
    manual_gate_decision_path: Path | None = None,
) -> dict[str, Any]:
    bounded_max_cycles = max(1, min(int(max_cycles), MAX_SUPPORTED_CYCLES))
    all_live_cycles = live_cycles if live_cycles else []
    metadata_map = cycle_metadata or {}
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
        source_catalog=source_catalog,
        manual_data_audit_path=manual_data_audit_path,
        manual_economic_audit_path=manual_economic_audit_path,
        manual_gate_decision_path=manual_gate_decision_path,
    )
    recommendations = _build_recommendations(gates)
    verdict = "fail" if recommendations["failed_gates"] else ("partial" if recommendations["unresolved_gates"] else "pass")
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
        cycle_metadata=metadata_map,
    )
    cycle_1 = cycle_ledger[0] if cycle_ledger else {}
    cycle_1_partial_reason = (
        "Cycle 1 is partial: selected evidence was economically insufficient, "
        "structured lane is not proven in this run, and admin/economic endpoint "
        "proof is missing."
    )

    return {
        "feature_key": "bd-3wefe.13",
        "gate_contract_version": "v2",
        "max_cycles": bounded_max_cycles,
        "current_cycle_input": matrix_attempt,
        "gates": gates,
        "recommendations": recommendations,
        "final_verdict": verdict,
        "cycle_ledger": cycle_ledger,
        "domain_progress": recommendations["progress"],
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
            "source_catalog_present": source_catalog is not None,
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
        "## Domain Progress",
        "",
        "| Domain | Pass | Partial | Not proven | Fail | Total |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for domain in ("data_moat", "economic_analysis", "manual_audit"):
        stats = report["domain_progress"][domain]
        lines.append(
            f"| {domain} | {stats['pass']} | {stats['partial']} | {stats['not_proven']} | {stats['fail']} | {stats['total']} |"
        )

    lines.extend(
        [
            "",
            "## Gate Status",
            "",
            "| Gate | Domain | Severity | Status | Details |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for code in ("D1", "D2", "D3", "D4", "D5", "D6", "E1", "E2", "E3", "E4", "E5", "E6", "M1", "M2", "M3"):
        item = report["gates"][code]
        lines.append(f"| {code} ({item['name']}) | {item['domain']} | {item['severity']} | {item['status']} | {item['details']} |")

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
            "| Cycle | Status | Verdict | Decision | Windmill Job | Backend Run | Package | Artifacts | Gate deltas | Next tweak |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for cycle in report["cycle_ledger"]:
        delta_count = len(cycle.get("gate_deltas") or {})
        artifact_count = len(cycle.get("artifacts") or [])
        lines.append(
            f"| {cycle.get('cycle_number')} | {cycle.get('status')} | "
            f"{cycle.get('verdict') or '-'} | {cycle.get('stop_continue_decision') or '-'} | "
            f"{cycle.get('windmill_job_id') or '-'} | {cycle.get('backend_run_id') or '-'} | "
            f"{cycle.get('package_id') or '-'} | {artifact_count} | {delta_count} | {cycle.get('next_tweak') or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD_PATH)
    parser.add_argument("--retry-ledger", type=Path, default=DEFAULT_RETRY_LEDGER_PATH)
    parser.add_argument("--out-retry-ledger", type=Path, default=DEFAULT_RETRY_LEDGER_PATH)
    parser.add_argument("--live-storage-probe", type=Path, default=DEFAULT_LIVE_STORAGE_PATH)
    parser.add_argument("--source-catalog", type=Path, default=DEFAULT_SOURCE_CATALOG_PATH)
    parser.add_argument(
        "--live-cycle-artifact",
        type=Path,
        action="append",
        default=None,
        help="Cycle artifact path. Repeat flag to include multiple cycles.",
    )
    parser.add_argument("--economic-status", type=Path, default=None)
    parser.add_argument("--current-package-status", type=Path, default=None)
    parser.add_argument("--cycle-metadata", type=Path, action="append", default=None)
    parser.add_argument("--manual-data-audit-md", type=Path, default=None)
    parser.add_argument("--manual-economic-audit-md", type=Path, default=None)
    parser.add_argument("--manual-gate-decision-md", type=Path, default=None)
    parser.add_argument("--deploy-sha", default=None)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--max-cycles", type=int, default=MAX_SUPPORTED_CYCLES)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    scorecard = _load_json(args.scorecard)
    if scorecard is None:
        raise SystemExit(f"missing scorecard artifact: {args.scorecard}")
    retry_ledger = _load_json(args.retry_ledger)
    live_storage_probe = _load_json(args.live_storage_probe)
    source_catalog = _load_json(args.source_catalog)
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
    economic_status_path = args.economic_status or args.current_package_status
    economic_status = _load_json(economic_status_path) if economic_status_path else None
    cycle_metadata_paths = args.cycle_metadata or []
    cycle_metadata = _load_cycle_metadata(cycle_metadata_paths)
    report = build_eval_cycles_report(
        scorecard=scorecard,
        retry_ledger=retry_ledger,
        live_storage_probe=live_storage_probe,
        source_catalog=source_catalog,
        live_cycle=live_cycle,
        live_cycles=live_cycle_entries,
        economic_status=economic_status,
        cycle_metadata=cycle_metadata,
        manual_data_audit_path=args.manual_data_audit_md,
        manual_economic_audit_path=args.manual_economic_audit_md,
        manual_gate_decision_path=args.manual_gate_decision_md,
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
    args.out_retry_ledger.parent.mkdir(parents=True, exist_ok=True)
    retry_payload = retry_ledger if isinstance(retry_ledger, dict) else {"feature_key": report["feature_key"], "attempts": []}
    retry_payload["gate_contract_version"] = report["gate_contract_version"]
    retry_payload["max_retry_rounds"] = report["max_cycles"]
    retry_payload["attempts"] = [
        {
            "attempt_id": f"cycle_{row['cycle_number']}",
            "status": row["status"],
            "result_verdict": row["verdict"],
            "tweaks_applied": row.get("code_config_tweaks", []),
            "commands_executed": row.get("commands_executed", []),
            "stop_continue_decision": row.get("stop_continue_decision"),
            "gate_snapshot": row.get("gate_snapshot", {}),
            "gate_deltas": row.get("gate_deltas", {}),
            "external_blocker_proof": row.get("external_blocker_proof", []),
        }
        for row in report["cycle_ledger"]
    ]
    args.out_retry_ledger.write_text(json.dumps(retry_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "policy_evidence_quality_spine_eval_cycles complete: "
        f"verdict={report['final_verdict']} max_cycles={report['max_cycles']}"
    )
    return 1 if report["final_verdict"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
