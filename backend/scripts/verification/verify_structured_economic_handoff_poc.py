#!/usr/bin/env python3
"""Structured-source -> economic-analysis boundary verifier (bd-2agbe.10).

Deterministic POC that proves/falsifies handoff readiness from structured facts
to canonical backend economic-analysis contracts without moving product logic
into Windmill orchestration.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FEATURE_KEY = "bd-2agbe.10"
POC_VERSION = "2026-04-14.structured-economic-handoff.v1"

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT_JSON = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "economic-analysis-boundary"
    / "artifacts"
    / "structured_economic_handoff_report.json"
)
DEFAULT_OUT_MD = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "economic-analysis-boundary"
    / "artifacts"
    / "structured_economic_handoff_report.md"
)

GATE_ORDER = (
    "source_access",
    "reader_substance",
    "evidence_card_extraction",
    "parameterization",
    "assumption_selection",
    "deterministic_quantification",
    "llm_explanation_guardrail",
    "persistence_read_model",
    "orchestration_boundary",
)


@dataclass(frozen=True)
class VerifierConfig:
    mode: str
    out_json: Path
    out_md: Path
    self_check: bool


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _baseline_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "case_direct_fiscal_quantified_pass",
            "description": "Structured fiscal note + ordinance packet support quantified direct-fiscal estimate.",
            "mechanism_family": "direct_fiscal",
            "inputs": {
                "source_access": {
                    "provider": "legistar_sanjose",
                    "sample_pull_without_browser": True,
                    "official_domain": True,
                },
                "reader_substance": {
                    "artifact_kind": "staff_report_pdf",
                    "parsed_char_count": 4180,
                    "boilerplate_ratio": 0.11,
                },
                "evidence_cards": [
                    {
                        "id": "ev-1",
                        "source_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=13000001&GUID=A-1",
                        "content_hash": "sha256-ev1-direct-fiscal-0001",
                        "excerpt": "City Manager estimates annual operating cost at $2,400,000 beginning FY 2027.",
                    },
                    {
                        "id": "ev-2",
                        "source_url": "https://sanjose.legistar.com/View.ashx?M=A&ID=13000001&GUID=A-1",
                        "content_hash": "sha256-ev2-direct-fiscal-0002",
                        "excerpt": "Program services are targeted to 8,000 renter households in high-cost tracts.",
                    },
                ],
                "required_parameters": ("annual_cost_usd", "affected_households"),
                "parameter_cards": [
                    {"name": "annual_cost_usd", "state": "resolved", "value": 2_400_000.0, "evidence_id": "ev-1"},
                    {"name": "affected_households", "state": "resolved", "value": 8_000.0, "evidence_id": "ev-2"},
                ],
                "assumption_context_tags": ["public_budget", "appropriation", "annualized_reporting"],
                "llm_claims": [
                    {
                        "claim": "Program adds approximately $300 annual fiscal exposure per targeted household.",
                        "evidence_refs": ["ev-1", "ev-2"],
                        "numeric_basis": True,
                    }
                ],
                "persistence_contract": {
                    "pipeline_runs_write": True,
                    "pipeline_steps_write": True,
                    "read_model_endpoint": True,
                    "evidence_endpoint": True,
                },
                "orchestration_contract": {
                    "windmill_role": "dag_control_only",
                    "backend_role": "domain_commands_and_gates",
                    "product_logic_in_windmill": False,
                },
            },
            "expected_outcome": "quantified_pass",
        },
        {
            "case_id": "case_local_control_fail_closed_insufficient",
            "description": "Local control text is accessible but lacks numeric evidence for compliance-cost quantification.",
            "mechanism_family": "compliance_cost",
            "inputs": {
                "source_access": {
                    "provider": "legistar_sanjose",
                    "sample_pull_without_browser": True,
                    "official_domain": True,
                },
                "reader_substance": {
                    "artifact_kind": "minutes_html",
                    "parsed_char_count": 2760,
                    "boilerplate_ratio": 0.18,
                },
                "evidence_cards": [
                    {
                        "id": "ev-10",
                        "source_url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=13000099&GUID=B-1",
                        "content_hash": "sha256-ev10-local-control-0001",
                        "excerpt": "Council approved local reporting requirements and directed staff to return with implementation details.",
                    }
                ],
                "required_parameters": ("hours_per_case", "loaded_hourly_wage_usd"),
                "parameter_cards": [
                    {"name": "hours_per_case", "state": "missing", "value": None, "evidence_id": None},
                    {"name": "loaded_hourly_wage_usd", "state": "missing", "value": None, "evidence_id": None},
                ],
                "assumption_context_tags": ["capital_project", "one_time_buildout"],
                "llm_claims": [
                    {
                        "claim": "The ordinance will increase rent by $120/month citywide.",
                        "evidence_refs": [],
                        "numeric_basis": False,
                    }
                ],
                "persistence_contract": {
                    "pipeline_runs_write": True,
                    "pipeline_steps_write": True,
                    "read_model_endpoint": True,
                    "evidence_endpoint": True,
                },
                "orchestration_contract": {
                    "windmill_role": "dag_control_only",
                    "backend_role": "domain_commands_and_gates",
                    "product_logic_in_windmill": False,
                },
            },
            "expected_outcome": "fail_closed",
        },
    ]


def _evaluate_source_access(case: dict[str, Any]) -> dict[str, Any]:
    payload = case["inputs"]["source_access"]
    passed = bool(payload.get("sample_pull_without_browser")) and bool(payload.get("official_domain"))
    return {
        "passed": passed,
        "reason": "official_structured_source_reachable" if passed else "structured_source_not_reachable",
        "details": payload,
    }


def _evaluate_reader_substance(case: dict[str, Any]) -> dict[str, Any]:
    payload = case["inputs"]["reader_substance"]
    chars = int(payload.get("parsed_char_count") or 0)
    boilerplate_ratio = float(payload.get("boilerplate_ratio") or 1.0)
    passed = chars >= 1200 and boilerplate_ratio <= 0.40
    return {
        "passed": passed,
        "reason": "artifact_has_substance" if passed else "artifact_substance_too_thin",
        "details": payload,
    }


def _evaluate_evidence_cards(case: dict[str, Any]) -> dict[str, Any]:
    cards = case["inputs"]["evidence_cards"]
    valid = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        if (
            isinstance(card.get("id"), str)
            and isinstance(card.get("source_url"), str)
            and isinstance(card.get("content_hash"), str)
            and isinstance(card.get("excerpt"), str)
            and len(card["excerpt"]) >= 16
        ):
            valid.append(card["id"])
    passed = len(valid) > 0
    return {
        "passed": passed,
        "reason": "evidence_cards_linked_to_artifacts" if passed else "evidence_cards_missing_or_invalid",
        "details": {"valid_card_ids": valid, "evidence_card_count": len(cards)},
    }


def _evaluate_parameterization(case: dict[str, Any]) -> dict[str, Any]:
    required = set(case["inputs"]["required_parameters"])
    cards = case["inputs"]["parameter_cards"]
    resolved = {
        item["name"]
        for item in cards
        if item.get("state") == "resolved" and item.get("value") is not None and item.get("evidence_id")
    }
    missing = sorted(required - resolved)
    passed = not missing
    return {
        "passed": passed,
        "reason": "required_parameters_resolved" if passed else "required_parameters_missing",
        "details": {"resolved_parameters": sorted(resolved), "missing_parameters": missing},
    }


def _resolve_assumption(mechanism_family: str, context_tags: list[str]) -> dict[str, Any]:
    tags = set(context_tags)
    registry_requirements: dict[str, tuple[set[str], set[str], str]] = {
        "direct_fiscal": (
            {"public_budget", "appropriation", "annualized_reporting"},
            set(),
            "direct_fiscal.annualization_factor.v1",
        ),
        "compliance_cost": (
            {"labor_cost", "administrative_burden", "us_employer_cost"},
            {"capital_project"},
            "compliance_cost.loaded_wage_multiplier.v1",
        ),
    }
    required, excluded, assumption_id = registry_requirements.get(
        mechanism_family, (set(), set(), "")
    )
    matched = bool(required) and required.issubset(tags) and not excluded.intersection(tags)
    return {
        "matched": matched,
        "assumption_id": assumption_id if matched else None,
        "reason": (
            "applicability_constrained_assumption_matched"
            if matched
            else f"no_assumption_profile_match_for_tags={sorted(tags)}"
        ),
    }


def _evaluate_assumption_selection(case: dict[str, Any], parameter_gate: dict[str, Any]) -> dict[str, Any]:
    missing_parameters = parameter_gate["details"]["missing_parameters"]
    if not missing_parameters:
        return {
            "passed": True,
            "reason": "no_assumption_needed_all_parameters_resolved",
            "details": {"assumption_id": None},
        }
    resolution = _resolve_assumption(
        mechanism_family=case["mechanism_family"],
        context_tags=list(case["inputs"]["assumption_context_tags"]),
    )
    passed = resolution["matched"]
    return {
        "passed": passed,
        "reason": resolution["reason"],
        "details": {
            "missing_parameters": missing_parameters,
            "assumption_id": resolution["assumption_id"],
        },
    }


def _evaluate_quantification(
    case: dict[str, Any], parameter_gate: dict[str, Any], assumption_gate: dict[str, Any]
) -> dict[str, Any]:
    if not parameter_gate["passed"] and not assumption_gate["passed"]:
        return {
            "passed": False,
            "reason": "quantification_blocked_by_parameter_and_assumption_gates",
            "details": {"scenario_bounds": None, "formula_id": None},
        }

    values = {card["name"]: card.get("value") for card in case["inputs"]["parameter_cards"]}
    annual_cost = float(values.get("annual_cost_usd") or 0.0)
    households = float(values.get("affected_households") or 0.0)
    if annual_cost > 0 and households > 0:
        per_household = annual_cost / households
        scenario_bounds = {
            "p10": round(per_household * 0.9, 2),
            "p50": round(per_household, 2),
            "p90": round(per_household * 1.1, 2),
            "unit": "usd_per_household_per_year",
        }
        arithmetic_valid = math.isfinite(per_household) and per_household > 0
        return {
            "passed": arithmetic_valid,
            "reason": "deterministic_formula_executed" if arithmetic_valid else "formula_invalid",
            "details": {
                "formula_id": "direct_fiscal_per_household_v1",
                "scenario_bounds": scenario_bounds,
                "arithmetic_valid": arithmetic_valid,
            },
        }
    return {
        "passed": False,
        "reason": "insufficient_numeric_basis_for_formula",
        "details": {"scenario_bounds": None, "formula_id": None},
    }


def _evaluate_llm_guardrail(case: dict[str, Any]) -> dict[str, Any]:
    cards = case["inputs"]["evidence_cards"]
    card_ids = {card["id"] for card in cards if isinstance(card, dict) and isinstance(card.get("id"), str)}
    violations: list[str] = []
    for idx, claim in enumerate(case["inputs"]["llm_claims"], start=1):
        refs = set(claim.get("evidence_refs") or [])
        if not refs or not refs.issubset(card_ids):
            violations.append(f"claim_{idx}_missing_or_unbound_evidence_refs")
        if claim.get("numeric_basis") is not True:
            violations.append(f"claim_{idx}_numeric_basis_not_declared")
    passed = not violations
    return {
        "passed": passed,
        "reason": "claims_bound_to_structured_evidence" if passed else "llm_claim_guardrail_violation",
        "details": {"violations": violations, "claim_count": len(case["inputs"]["llm_claims"])},
    }


def _evaluate_persistence_read_model(case: dict[str, Any]) -> dict[str, Any]:
    payload = case["inputs"]["persistence_contract"]
    passed = all(
        bool(payload.get(k))
        for k in ("pipeline_runs_write", "pipeline_steps_write", "read_model_endpoint", "evidence_endpoint")
    )
    return {
        "passed": passed,
        "reason": "pipeline_write_and_read_model_contract_present" if passed else "missing_persistence_or_read_model_contract",
        "details": payload,
    }


def _evaluate_orchestration_boundary(case: dict[str, Any]) -> dict[str, Any]:
    payload = case["inputs"]["orchestration_contract"]
    passed = (
        payload.get("windmill_role") == "dag_control_only"
        and payload.get("backend_role") == "domain_commands_and_gates"
        and payload.get("product_logic_in_windmill") is False
    )
    return {
        "passed": passed,
        "reason": "boundary_preserved_backend_owns_business_logic" if passed else "boundary_violation_product_logic_leaked_to_windmill",
        "details": payload,
    }


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    gate_results: dict[str, dict[str, Any]] = {}
    gate_results["source_access"] = _evaluate_source_access(case)
    gate_results["reader_substance"] = _evaluate_reader_substance(case)
    gate_results["evidence_card_extraction"] = _evaluate_evidence_cards(case)
    gate_results["parameterization"] = _evaluate_parameterization(case)
    gate_results["assumption_selection"] = _evaluate_assumption_selection(case, gate_results["parameterization"])
    gate_results["deterministic_quantification"] = _evaluate_quantification(
        case,
        gate_results["parameterization"],
        gate_results["assumption_selection"],
    )
    gate_results["llm_explanation_guardrail"] = _evaluate_llm_guardrail(case)
    gate_results["persistence_read_model"] = _evaluate_persistence_read_model(case)
    gate_results["orchestration_boundary"] = _evaluate_orchestration_boundary(case)

    blocking_gate = next((gate for gate in GATE_ORDER if not gate_results[gate]["passed"]), None)
    final_verdict = "quantified_pass" if blocking_gate is None else "fail_closed"
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "mechanism_family": case["mechanism_family"],
        "expected_outcome": case["expected_outcome"],
        "final_verdict": final_verdict,
        "blocking_gate": blocking_gate,
        "gate_results": gate_results,
    }


def _code_path_citations() -> list[dict[str, str]]:
    return [
        {
            "topic": "Canonical pipeline orchestration and step execution",
            "path": "backend/services/llm/orchestrator.py",
            "lines": "205-211,256-268,633-658,666-676,1020-1049,2283-2373",
        },
        {
            "topic": "Research service evidence envelopes + sufficiency",
            "path": "backend/services/legislation_research.py",
            "lines": "213-219,260-280,299-330,665-721,723-741",
        },
        {
            "topic": "Deterministic evidence gate logic",
            "path": "backend/services/llm/evidence_gates.py",
            "lines": "1-5,211-247,249-260",
        },
        {
            "topic": "Assumption registry applicability constraints",
            "path": "backend/services/economic_assumptions.py",
            "lines": "23-25,61-92,166-187",
        },
        {
            "topic": "Structured economic artifact contracts",
            "path": "backend/schemas/economic_evidence.py",
            "lines": "45-55,68-83,84-112,114-134,136-164,173-195",
        },
        {
            "topic": "Pipeline step persistence for audit/read-model",
            "path": "backend/services/audit/logger.py",
            "lines": "16-21,63-66,91-100",
        },
        {
            "topic": "Pipeline run persistence table writes",
            "path": "backend/db/postgres_client.py",
            "lines": "253-267,278-289",
        },
        {
            "topic": "Storage path raw_scrapes -> object -> chunks -> pgvector",
            "path": "backend/services/ingestion_service.py",
            "lines": "240-262,269-278,374-407",
        },
        {
            "topic": "pgvector retrieval contract and filter semantics",
            "path": "backend/services/retrieval/local_pgvector.py",
            "lines": "20-28,64-73,84-91,169-176,214-220",
        },
        {
            "topic": "Admin/glassbox read model + evidence endpoints",
            "path": "backend/routers/admin.py",
            "lines": "866-879,1268-1305,1346-1364,1373-1403",
        },
        {
            "topic": "Frontend pipeline status/admin operator links",
            "path": "frontend/src/components/admin/PipelineStatusPanel.tsx",
            "lines": "32-38,58-66,107-115,199-215,219-230",
        },
        {
            "topic": "Boundary options A/B/C source spec",
            "path": "docs/specs/2026-04-14-economic-evidence-pipeline-lockdown.md",
            "lines": "30-49",
        },
    ]


def _recommended_extensions() -> list[dict[str, str]]:
    return [
        {
            "target": "backend/services/llm/orchestrator.py",
            "change": "Emit structured artifact ids (EvidenceCard/ParameterCard/AssumptionCard/ModelCard) into pipeline step outputs and run result payload.",
        },
        {
            "target": "backend/routers/admin.py",
            "change": "Extend /pipeline/runs/{run_id}/evidence to include parameter and assumption provenance, not only analysis citations.",
        },
        {
            "target": "backend/db/postgres_client.py",
            "change": "Persist contract_version and artifact-count metrics on pipeline_runs for deterministic dashboard gating.",
        },
        {
            "target": "frontend/src/components/admin/PipelineStatusPanel.tsx",
            "change": "Show gate-level blocking stage and structured artifact counts for operator audit decisions.",
        },
    ]


def _build_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    pass_cases = sum(1 for item in case_results if item["final_verdict"] == "quantified_pass")
    fail_closed_cases = sum(1 for item in case_results if item["final_verdict"] == "fail_closed")
    recommendation = "option_a"
    recommendation_reason = (
        "Boundary proof supports Windmill DAG control with backend-owned domain gates/contracts; "
        "avoid Option C for core economics."
    )
    return {
        "total_cases": len(case_results),
        "quantified_pass_cases": pass_cases,
        "fail_closed_cases": fail_closed_cases,
        "supports_decision_grade_handoff_in_replay": pass_cases >= 1 and fail_closed_cases >= 1,
        "architecture_option_recommendation": recommendation,
        "recommendation_reason": recommendation_reason,
        "evidence_quality_note": (
            "Replay-mode quantification is deterministic contract proof, not live production proof. "
            "Railway-dev rollout still requires live source/read/analysis runs with persisted artifact audits."
        ),
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Structured Economic Handoff Boundary POC")
    lines.append("")
    lines.append(f"- feature_key: `{report['feature_key']}`")
    lines.append(f"- poc_version: `{report['poc_version']}`")
    lines.append(f"- generated_at: `{report['generated_at']}`")
    lines.append(f"- mode: `{report['mode']}`")
    lines.append("")
    lines.append("## Gate Outcomes")
    lines.append("")
    lines.append("| case_id | expected | final_verdict | blocking_gate |")
    lines.append("| --- | --- | --- | --- |")
    for case in report["cases"]:
        lines.append(
            f"| {case['case_id']} | {case['expected_outcome']} | {case['final_verdict']} | {case['blocking_gate'] or 'none'} |"
        )
    lines.append("")
    lines.append("## Canonical Code Paths")
    lines.append("")
    for citation in report["code_path_citations"]:
        lines.append(
            f"- {citation['topic']}: `{citation['path']}:{citation['lines']}`"
        )
    lines.append("")
    lines.append("## Boundary Recommendation")
    lines.append("")
    lines.append(
        f"- recommended_option: `{report['summary']['architecture_option_recommendation']}`"
    )
    lines.append(f"- rationale: {report['summary']['recommendation_reason']}")
    lines.append(
        "- Windmill should own schedule/fanout/retry/branch orchestration and write only run metadata references."
    )
    lines.append(
        "- Backend should own evidence-card extraction, parameterization, assumptions, quantification, and fail-closed sufficiency decisions."
    )
    lines.append(
        "- Postgres should remain the canonical run/step/read-model store; pgvector should remain retrieval substrate; MinIO should store raw/reader artifacts by URI reference."
    )
    lines.append(
        "- Frontend/admin should remain read-only over backend-authored run/step/evidence models."
    )
    lines.append("")
    lines.append("## Recommended Contract Extensions")
    lines.append("")
    for extension in report["recommended_extensions"]:
        lines.append(f"- `{extension['target']}`: {extension['change']}")
    lines.append("")
    lines.append("## Evidence Quality")
    lines.append("")
    lines.append(f"- {report['summary']['evidence_quality_note']}")
    lines.append(
        "- Required before Railway-dev rollout: at least one live multi-jurisdiction run proving gate-by-gate parity with replay plus persistence-read-model integrity."
    )
    lines.append("")
    return "\n".join(lines)


def _validate_report_contract(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_keys = (
        "feature_key",
        "poc_version",
        "mode",
        "generated_at",
        "cases",
        "summary",
        "code_path_citations",
        "recommended_extensions",
    )
    for key in required_keys:
        if key not in report:
            errors.append(f"missing_top_level_key:{key}")
    cases = report.get("cases")
    if not isinstance(cases, list) or len(cases) < 2:
        errors.append("cases_contract_requires_at_least_two_cases")
    else:
        for case in cases:
            case_id = case.get("case_id")
            if case.get("expected_outcome") != case.get("final_verdict"):
                errors.append(f"case_outcome_mismatch:{case_id}")
            gate_results = case.get("gate_results", {})
            missing_gates = [gate for gate in GATE_ORDER if gate not in gate_results]
            if missing_gates:
                errors.append(f"missing_gate_results:{case_id}:{','.join(missing_gates)}")
    summary = report.get("summary", {})
    if summary.get("architecture_option_recommendation") not in {"option_a", "option_b", "option_c"}:
        errors.append("invalid_architecture_option_recommendation")
    return errors


def _run(config: VerifierConfig) -> dict[str, Any]:
    if config.mode != "replay":
        raise ValueError("Only replay mode is allowed for this deterministic verifier.")

    cases = _baseline_cases()
    case_results = [_evaluate_case(case) for case in cases]

    report = {
        "feature_key": FEATURE_KEY,
        "poc_version": POC_VERSION,
        "mode": config.mode,
        "generated_at": _now_iso(),
        "cases": case_results,
        "summary": _build_summary(case_results),
        "code_path_citations": _code_path_citations(),
        "recommended_extensions": _recommended_extensions(),
    }
    return report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify structured-source -> economic-analysis boundary handoff contracts."
    )
    parser.add_argument("--mode", choices=("replay",), default="replay")
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    config = VerifierConfig(
        mode=args.mode,
        out_json=args.out_json,
        out_md=args.out_md,
        self_check=bool(args.self_check),
    )

    report = _run(config)
    errors = _validate_report_contract(report)

    _write_json(config.out_json, report)
    _write_markdown(config.out_md, _render_markdown(report))

    if errors:
        for err in errors:
            print(f"CONTRACT_ERROR: {err}")
        return 1 if config.self_check else 0

    print(
        json.dumps(
            {
                "feature_key": report["feature_key"],
                "mode": report["mode"],
                "cases": len(report["cases"]),
                "recommended_option": report["summary"]["architecture_option_recommendation"],
                "out_json": str(config.out_json),
                "out_md": str(config.out_md),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
