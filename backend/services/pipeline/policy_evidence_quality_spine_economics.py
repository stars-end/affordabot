"""Economic quality-spine evaluator for bd-3wefe.13 (Agent B lane).

This service evaluates whether a vertical PolicyEvidencePackage candidate is
good enough to hand off to canonical economic analysis semantics. It consumes
Agent A's horizontal matrix artifact when available and falls back to a
contract-compatible deterministic fixture when it is not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from schemas.economic_evidence import GateVerdict, MechanismFamily
from schemas.policy_evidence_package import PolicyEvidencePackage, StorageSystem
from services.pipeline.policy_economic_mechanism_cases import (
    PolicyEconomicMechanismCaseService,
)
from services.pipeline.policy_evidence_package_storage import (
    InMemoryArtifactProbe,
    InMemoryArtifactWriter,
    InMemoryPolicyEvidencePackageStore,
    PolicyEvidencePackageStorageService,
)
from services.pipeline.policy_evidence_package_sufficiency import (
    PackageReadinessLevel,
    PolicyEvidencePackageSufficiencyService,
)


QUALITY_BUCKETS = (
    "scraped/search",
    "reader",
    "structured-source",
    "identity/dedupe",
    "storage/read-back",
    "Windmill/orchestration",
    "sufficiency gate",
    "economic reasoning",
    "LLM narrative",
    "frontend/read-model auditability",
)

ECONOMIC_QUALITY_DIMENSIONS = (
    "mechanism_graph_validity",
    "parameter_provenance",
    "assumption_governance",
    "arithmetic_integrity",
    "uncertainty_sensitivity",
    "unsupported_claim_rejection",
    "user_facing_conclusion_quality",
)

ECONOMIC_PARAMETER_NAME_HINTS = (
    "cost",
    "fee",
    "tax",
    "rate",
    "rent",
    "price",
    "income",
    "wage",
    "subsid",
    "benefit",
    "burden",
    "pass_through",
    "pass-through",
    "incidence",
    "take_up",
    "take-up",
    "adoption",
    "household",
    "consumer",
    "unit",
    "units",
    "elastic",
    "spend",
)

ECONOMIC_PARAMETER_UNIT_HINTS = (
    "usd_per_sqft",
    "usd_per_square_foot",
    "dollars_per_sqft",
    "dollars_per_square_foot",
    "$/sqft",
    "usd/sqft",
    "usd_per_unit",
    "usd_per_project",
)

DIAGNOSTIC_PARAMETER_NAME_HINTS = (
    "event_id",
    "body_id",
    "dataset_match_count",
    "record_id",
    "meeting_id",
    "session_id",
    "legid",
    "gid",
    "uuid",
    "hash",
    "metadata",
)

ASSUMPTION_PLACEHOLDER_PATTERNS = (
    r"\bmapped mechanism assumption\b",
    r"\bsource evidence and policy context\b",
    r"\bplaceholder\b",
)

FEE_CATEGORY_HINTS = (
    "office_large",
    "office_small",
    "office",
    "retail",
    "industrial",
    "hotel",
    "residential",
    "commercial",
    "mixed_use",
)

PAYMENT_TIMING_PATTERNS = (
    "prior to building permit issuance",
    "before building permit issuance",
    "at permit issuance",
    "upon permit issuance",
    "prior to occupancy",
    "before occupancy",
    "at occupancy",
)

SQFT_UNIT_ALIASES = {
    "usd_per_sqft",
    "usd_per_square_foot",
    "dollars_per_sqft",
    "dollars_per_square_foot",
    "$/sqft",
    "usd/sqft",
}


@dataclass(frozen=True)
class MatrixInput:
    payload: dict[str, Any] | None
    source_path: str
    source_mode: str


class PolicyEvidenceQualitySpineEconomicsService:
    """Build deterministic quality-spine economics scorecards and read models."""

    def evaluate(
        self,
        *,
        matrix_input: MatrixInput,
        max_cycles: int = 10,
        preferred_package_id: str | None = None,
    ) -> dict[str, Any]:
        bounded_max_cycles = max(1, min(int(max_cycles), 10))
        matrix_packages = self._extract_package_candidates(matrix_input.payload)
        used_fallback = not matrix_packages
        package_payload: dict[str, Any]
        fallback_note: str | None = None
        if used_fallback:
            package_payload = self._fallback_vertical_package()
            fallback_note = (
                "horizontal_matrix.json missing or lacked package payload; "
                "used deterministic mechanism fixture"
            )
            matrix_source_mode = "fallback_fixture"
        else:
            package_payload = self._select_vertical_candidate(
                matrix_packages,
                preferred_package_id=preferred_package_id,
            )
            matrix_source_mode = matrix_input.source_mode

        package = PolicyEvidencePackage.model_validate(package_payload)
        storage_eval = self._persist_for_readback(package_payload)
        record = storage_eval["record"]
        sufficiency = PolicyEvidencePackageSufficiencyService().evaluate(record=record)

        category_results = self._build_taxonomy(
            package=package,
            matrix_payload=matrix_input.payload or {},
            matrix_source_mode=matrix_source_mode,
            storage_eval=storage_eval,
            sufficiency=sufficiency,
        )
        category_failures = [
            bucket for bucket, result in category_results.items() if result["status"] == "fail"
        ]
        category_not_proven = [
            bucket
            for bucket, result in category_results.items()
            if result["status"] == "not_proven"
        ]

        vertical_output = self._build_vertical_economic_output(package=package, sufficiency=sufficiency)
        economic_quality = self._build_economic_quality_rubric(
            package=package,
            sufficiency=sufficiency,
            vertical_output=vertical_output,
        )
        fixture_case_coverage = self._build_fixture_case_coverage()
        read_model_output = self._build_read_model_output(
            package=package,
            sufficiency=sufficiency,
            vertical_output=vertical_output,
            taxonomy=category_results,
            economic_quality=economic_quality,
        )
        quality_missing_evidence = self._build_missing_evidence(
            taxonomy=category_results,
            economic_quality=economic_quality,
            readiness_level=sufficiency.readiness_level.value,
            blocking_gate=(
                None
                if sufficiency.blocking_gate is None
                else sufficiency.blocking_gate.value
            ),
        )
        decision_grade_verdict = (
            "decision_grade"
            if (
                not category_failures
                and not category_not_proven
                and economic_quality["verdict"] == "decision_grade"
                and sufficiency.readiness_level == PackageReadinessLevel.ECONOMIC_HANDOFF_READY
            )
            else "not_decision_grade"
        )
        scorecard = {
            "feature_key": "bd-3wefe.13",
            "generated_at": datetime.now(UTC).isoformat(),
            "report_version": "2026-04-15.policy-evidence-quality-spine-economics.v1",
            "matrix_attempt": self._matrix_attempt_metadata(matrix_input.payload or {}),
            "matrix_source": {
                "mode": matrix_source_mode,
                "path": matrix_input.source_path,
                "fallback_note": fallback_note,
                "candidate_package_count": len(matrix_packages),
                "used_package_id": package.package_id,
            },
            "vertical_package": {
                "package_id": package.package_id,
                "canonical_document_key": package.canonical_document_key,
                "jurisdiction": package.jurisdiction,
                "policy_identifier": package.policy_identifier,
                "source_lanes": [lane.value for lane in package.source_lanes],
            },
            "taxonomy": category_results,
            "sufficiency_result": {
                "passed": sufficiency.passed,
                "readiness_level": sufficiency.readiness_level.value,
                "blocking_gate": None if sufficiency.blocking_gate is None else sufficiency.blocking_gate.value,
                "failure_reasons": sufficiency.failure_reasons,
            },
            "overall_verdict": self._overall_verdict(
                category_failures=category_failures,
                category_not_proven=category_not_proven,
            ),
            "failure_classification": {
                "failed_categories": category_failures,
                "not_proven_categories": category_not_proven,
            },
            "economic_quality_rubric": economic_quality,
            "decision_grade": {
                "verdict": decision_grade_verdict,
                "missing_evidence": quality_missing_evidence,
            },
            "fixture_case_coverage": fixture_case_coverage,
            "evaluation_cycle_policy": {
                "max_cycles": bounded_max_cycles,
            },
        }
        retry_ledger = self._build_retry_ledger(scorecard=scorecard, max_cycles=bounded_max_cycles)
        return {
            "scorecard": scorecard,
            "vertical_economic_output": vertical_output,
            "read_model_audit_output": read_model_output,
            "retry_ledger": retry_ledger,
            "selected_package_payload": package_payload,
            "decision_grade_verdict": decision_grade_verdict,
        }

    def build_endpoint_read_model(
        self,
        *,
        matrix_input: MatrixInput,
        package_id: str,
        source_family: str,
        run_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evaluation = self.evaluate(
            matrix_input=matrix_input,
            preferred_package_id=package_id,
        )
        package = PolicyEvidencePackage.model_validate(evaluation["selected_package_payload"])
        scorecard = evaluation["scorecard"]
        vertical = evaluation["vertical_economic_output"]
        handoff = evaluation["read_model_audit_output"]["analysis_handoff"]
        taxonomy = scorecard["taxonomy"]
        sufficiency = scorecard["sufficiency_result"]
        decision_grade = scorecard["decision_grade"]
        quality_verdict = scorecard["economic_quality_rubric"]["verdict"]
        rubric = scorecard["economic_quality_rubric"]["dimensions"]
        selected_payload = evaluation["selected_package_payload"]
        runtime = self._extract_runtime_evidence(matrix_input.payload or {})
        orchestration_proof = runtime.get("orchestration_proof")
        if not isinstance(orchestration_proof, dict):
            orchestration_proof = {}
        if not orchestration_proof:
            package_payload = runtime.get("vertical_package_payload")
            if isinstance(package_payload, dict):
                run_context = package_payload.get("run_context")
                if isinstance(run_context, dict):
                    orchestration_proof = {
                        "windmill_flow_path": run_context.get("windmill_flow_path"),
                        "windmill_workspace": run_context.get("windmill_workspace"),
                        "windmill_run_id": run_context.get("windmill_run_id"),
                        "windmill_job_id": run_context.get("windmill_job_id"),
                        "windmill_platform_job_id": run_context.get("windmill_platform_job_id")
                        or run_context.get("windmill_job_id_platform"),
                        "source": "vertical_package_payload.run_context",
                    }
        llm_proof = handoff.get("llm_narrative_proof", {})
        runtime_llm_proof = runtime.get("llm_narrative_proof")
        if isinstance(runtime_llm_proof, dict):
            llm_proof = {**llm_proof, **runtime_llm_proof}
        reader_provenance = self._derive_reader_provenance_evidence(
            package=package,
            runtime_evidence=runtime,
            storage_gate_status=taxonomy["storage/read-back"]["status"],
        )

        storage_refs = [
            {
                "storage_system": ref.storage_system.value,
                "truth_role": ref.truth_role.value,
                "reference_id": ref.reference_id,
                "uri": ref.uri,
                "content_hash": ref.content_hash,
            }
            for ref in package.storage_refs
        ]
        windmill_refs: list[dict[str, Any]] = []
        for key in ("windmill_flow_path", "windmill_workspace", "windmill_run_id", "source"):
            value = orchestration_proof.get(key)
            if value:
                windmill_refs.append({"key": key, "value": value})
        platform_job_id = orchestration_proof.get("windmill_platform_job_id")
        scope_job_id = orchestration_proof.get("windmill_job_id")
        if platform_job_id:
            windmill_refs.append({"key": "windmill_platform_job_id", "value": platform_job_id})
        if scope_job_id:
            scope_key = (
                "windmill_scope_job_id"
                if self._is_probably_scope_job_id(str(scope_job_id))
                else "windmill_job_id"
            )
            windmill_refs.append({"key": scope_key, "value": scope_job_id})
        llm_refs: list[dict[str, Any]] = []
        for key in (
            "canonical_pipeline_run_id",
            "canonical_pipeline_step_id",
            "analysis_step_executed",
            "analysis_payload_present",
            "source",
        ):
            value = llm_proof.get(key)
            if value:
                llm_refs.append({"key": key, "value": value})

        readiness_level = sufficiency["readiness_level"]
        blocking_gate = sufficiency["blocking_gate"]
        if readiness_level == PackageReadinessLevel.FAIL_CLOSED.value:
            readiness_status = "fail"
            readiness_reason = f"fail_closed at {blocking_gate or 'unknown'}"
        elif readiness_level == PackageReadinessLevel.ECONOMIC_HANDOFF_READY.value:
            readiness_status = "pass"
            readiness_reason = "economic handoff is quantified-ready"
        else:
            readiness_status = "not_proven"
            readiness_reason = f"readiness={readiness_level}"

        backend_run_id = self._extract_backend_run_id(
            selected_payload=selected_payload,
            run_context=run_context or {},
        )
        overall_verdict = scorecard["overall_verdict"]
        evidence_package_status = (
            "pass"
            if overall_verdict == "pass"
            else "fail" if overall_verdict == "fail" else "not_proven"
        )
        required_evidence_gaps = self._extract_evidence_gap_categories(
            missing_evidence=decision_grade["missing_evidence"]
        )
        canonical_analysis_binding = self._derive_canonical_analysis_binding(
            package=package,
            llm_proof=llm_proof,
            run_context=run_context or {},
        )
        analysis_status = self._derive_analysis_status(
            readiness_level=readiness_level,
            decision_grade_verdict=decision_grade["verdict"],
            required_evidence_gaps=required_evidence_gaps,
        )
        conclusion_supported = (
            vertical["quantified"]
            and decision_grade["verdict"] == "decision_grade"
            and analysis_status["status"] == "decision_grade"
        )

        if conclusion_supported:
            economic_output = {
                "status": "ready",
                "decision_grade_verdict": "decision_grade",
                "mechanism_type": vertical["mechanism_type"],
                "sensitivity_range": vertical["sensitivity_range"],
                "user_facing_conclusion": vertical["user_facing_conclusion"],
                "unsupported_claim_rejection": vertical["unsupported_claim_rejection"],
            }
        else:
            economic_output = {
                "status": "not_proven",
                "decision_grade_verdict": "not_decision_grade",
                "reason": (
                    "economic quality rubric not decision-grade"
                    if quality_verdict != "decision_grade"
                    else readiness_reason
                ),
                "missing_evidence": decision_grade["missing_evidence"],
                "unsupported_claim_rejection": vertical["unsupported_claim_rejection"],
                "user_facing_conclusion": None,
            }
        secondary_research = self._build_secondary_research_contract(
            package=package,
            analysis_status=analysis_status,
            required_evidence_gaps=required_evidence_gaps,
            sufficiency=sufficiency,
            canonical_binding=canonical_analysis_binding,
        )
        mechanism_candidates = self._build_mechanism_candidates(
            package=package,
            vertical=vertical,
            rubric=rubric,
        )
        parameter_inventory = self._build_parameter_inventory(package=package)
        missing_parameters = parameter_inventory["missing_parameters"]
        assumption_needs = self._build_assumption_needs(
            package=package,
            mechanism_type=str(vertical.get("mechanism_type") or "direct"),
        )
        unsupported_claim_risks = self._build_unsupported_claim_risks(
            package=package,
            vertical=vertical,
        )
        secondary_research_needs = self._build_secondary_research_needs(
            secondary_research=secondary_research,
            required_evidence_gaps=required_evidence_gaps,
            canonical_binding=canonical_analysis_binding,
            assumption_needs=assumption_needs,
            analysis_status=analysis_status,
            unsupported_claim_risks=unsupported_claim_risks,
        )
        source_quality_metrics = self._extract_source_quality_metrics(
            selected_payload=selected_payload
        )
        source_reconciliation = self._extract_source_reconciliation(
            selected_payload=selected_payload
        )
        economic_handoff_quality = self._build_economic_handoff_quality(
            analysis_status=analysis_status,
            decision_grade_verdict=decision_grade["verdict"],
            readiness_level=readiness_level,
            blocking_gate=blocking_gate,
            canonical_binding_status=canonical_analysis_binding["status"],
            mechanism_type=str(vertical.get("mechanism_type") or "direct"),
            direct_fee_model_card=vertical.get("direct_fee_model_card") or {},
            missing_parameters=missing_parameters,
            assumption_needs=assumption_needs,
            secondary_research_needs=secondary_research_needs,
            unsupported_claim_risks=unsupported_claim_risks,
            source_quality_metrics=source_quality_metrics,
            source_reconciliation=source_reconciliation,
        )
        data_moat_status = self._build_data_moat_status(
            evidence_package_status=evidence_package_status,
            decision_grade_verdict=decision_grade["verdict"],
            required_evidence_gaps=required_evidence_gaps,
            readiness_level=readiness_level,
            taxonomy=taxonomy,
            canonical_binding_status=canonical_analysis_binding["status"],
            economic_handoff_quality=economic_handoff_quality,
            source_quality_metrics=source_quality_metrics,
            source_reconciliation=source_reconciliation,
        )
        recommended_next_action = self._recommend_next_action(
            analysis_status=analysis_status,
            taxonomy=taxonomy,
            secondary_research=secondary_research,
            canonical_binding=canonical_analysis_binding,
            economic_handoff_quality=economic_handoff_quality,
            unsupported_claim_risks=unsupported_claim_risks,
            data_moat_status=data_moat_status,
        )
        data_moat_status["recommended_next_action"] = recommended_next_action
        economic_handoff_quality.update(
            {
                "decision_grade_verdict": decision_grade["verdict"],
                "readiness_level": readiness_level,
                "analysis_status": analysis_status["status"],
                "canonical_binding_status": canonical_analysis_binding["status"],
                "mechanism_candidates": mechanism_candidates,
                "parameter_inventory": parameter_inventory,
                "missing_parameters": missing_parameters,
                "assumption_needs": assumption_needs,
                "secondary_research_needs": secondary_research_needs,
                "unsupported_claim_risks": unsupported_claim_risks,
                "recommended_next_action": recommended_next_action,
            }
        )
        quant_model_payload = [
            {
                "model_id": card.id,
                "mechanism_family": card.mechanism_family.value,
                "formula_id": card.formula_id,
                "quantification_eligible": card.quantification_eligible,
                "arithmetic_valid": card.arithmetic_valid,
                "unit_validation_status": card.unit_validation_status.value,
                "input_parameter_ids": card.input_parameter_ids,
                "assumption_ids": card.assumption_ids,
                "scenario_bounds": (
                    None
                    if card.scenario_bounds is None
                    else {
                        "low": card.scenario_bounds.conservative,
                        "base": card.scenario_bounds.central,
                        "high": card.scenario_bounds.aggressive,
                    }
                ),
            }
            for card in package.model_cards
        ]
        assumption_payload = [
            {
                "assumption_id": card.id,
                "family": card.family.value,
                "low": card.low,
                "central": card.central,
                "high": card.high,
                "unit": card.unit,
                "source_url": str(card.source_url),
                "source_excerpt": card.source_excerpt,
                "applicability_tags": card.applicability_tags,
                "stale_after_days": card.stale_after_days,
                "version": card.version,
            }
            for card in package.assumption_cards
        ]

        return {
            "package_id": package.package_id,
            "backend_run_id": backend_run_id,
            "jurisdiction": package.jurisdiction,
            "source_family": source_family,
            "evidence_package_status": evidence_package_status,
            "data_moat_status": data_moat_status,
            "decision_grade_verdict": decision_grade["verdict"],
            "sufficiency_readiness_level": readiness_level,
            "economic_analysis_status": {
                **analysis_status,
                "required_evidence_gaps": required_evidence_gaps,
            },
            "run_context": run_context or {},
            "provenance": {
                "canonical_document_key": package.canonical_document_key,
                "policy_identifier": package.policy_identifier,
                "source_lanes": [lane.value for lane in package.source_lanes],
                "scraped_sources": [
                    {
                        "search_provider": source.search_provider.value,
                        "query_family": source.query_family,
                        "search_snapshot_id": source.search_snapshot_id,
                        "selected_candidate_url": str(source.selected_candidate_url),
                        "reader_artifact_url": (
                            str(source.reader_artifact_url)
                            if source.reader_artifact_url is not None
                            else None
                        ),
                        "reader_substance_passed": reader_provenance["per_source"][index]["effective_passed"],
                        "reader_substance_observed": source.reader_substance_passed,
                        "reader_provenance_hydrated": reader_provenance["per_source"][index][
                            "hydrated_by_storage_proof"
                        ],
                    }
                    for index, source in enumerate(package.scraped_sources)
                ],
                "structured_sources": [
                    {
                        "source_family": source.source_family,
                        "access_method": source.access_method,
                        "endpoint_or_file_url": str(source.endpoint_or_file_url),
                        "provider_run_id": source.provider_run_id,
                        "field_count": source.field_count,
                    }
                    for source in package.structured_sources
                ],
            },
            "gates": {
                "scraped/search": {
                    "status": taxonomy["scraped/search"]["status"],
                    "reason": taxonomy["scraped/search"]["details"],
                    "refs": [],
                },
                "storage/read-back": {
                    "status": taxonomy["storage/read-back"]["status"],
                    "reason": taxonomy["storage/read-back"]["details"],
                    "refs": storage_refs,
                    "proof_mode": taxonomy["storage/read-back"].get("proof_mode"),
                    "direct_probe_available": taxonomy["storage/read-back"].get(
                        "direct_probe_available"
                    ),
                },
                "Windmill/orchestration": {
                    "status": taxonomy["Windmill/orchestration"]["status"],
                    "reason": taxonomy["Windmill/orchestration"]["details"],
                    "refs": windmill_refs,
                },
                "LLM narrative": {
                    "status": taxonomy["LLM narrative"]["status"],
                    "reason": taxonomy["LLM narrative"]["details"],
                    "refs": llm_refs,
                },
                "economic_analysis_readiness": {
                    "status": readiness_status,
                    "reason": readiness_reason,
                    "refs": (
                        [{"key": "blocking_gate", "value": blocking_gate}]
                        if blocking_gate
                        else []
                    ),
                },
            },
            "economic_readiness": {
                "mechanism_readiness": {
                    "status": rubric["mechanism_graph_validity"]["status"],
                    "reason": rubric["mechanism_graph_validity"]["details"],
                },
                "evidence_readiness": {
                    "status": "pass" if package.evidence_cards else "fail",
                    "reason": (
                        f"evidence_cards={len(package.evidence_cards)}"
                        if package.evidence_cards
                        else "No evidence cards present."
                    ),
                },
                "parameter_readiness": {
                    "status": rubric["parameter_provenance"]["status"],
                    "reason": rubric["parameter_provenance"]["details"],
                },
                "assumption_readiness": {
                    "status": rubric["assumption_governance"]["status"],
                    "reason": rubric["assumption_governance"]["details"],
                },
                "model_readiness": {
                    "status": rubric["arithmetic_integrity"]["status"],
                    "reason": rubric["arithmetic_integrity"]["details"],
                },
                "direct_model_card_readiness": {
                    "status": str(
                        (vertical.get("direct_fee_model_card") or {}).get("status")
                        or "not_proven"
                    ),
                    "reason": str(
                        (vertical.get("direct_fee_model_card") or {}).get("reason")
                        or "direct fee model card unavailable"
                    ),
                },
                "uncertainty_readiness": {
                    "status": rubric["uncertainty_sensitivity"]["status"],
                    "reason": rubric["uncertainty_sensitivity"]["details"],
                },
                "unsupported_claim_rejection": vertical["unsupported_claim_rejection"],
            },
            "economic_trace": {
                "mechanism_type": vertical["mechanism_type"],
                "direct_indirect_classification": vertical["direct_indirect_classification"],
                "mechanism_graph": vertical["mechanism_graph"],
                "parameter_table": vertical["parameter_table"],
                "diagnostic_parameter_table": vertical.get("diagnostic_parameter_table", []),
                "direct_fee_model_card": vertical.get("direct_fee_model_card"),
                "assumption_cards": assumption_payload,
                "model_cards": quant_model_payload,
                "arithmetic_integrity": {
                    "status": rubric["arithmetic_integrity"]["status"],
                    "reason": rubric["arithmetic_integrity"]["details"],
                },
                "sensitivity_range": vertical["sensitivity_range"],
                "uncertainty_notes": vertical["uncertainty_notes"],
            },
            "secondary_research": secondary_research,
            "economic_handoff_quality": economic_handoff_quality,
            "mechanism_candidates": mechanism_candidates,
            "parameter_inventory": parameter_inventory,
            "missing_parameters": missing_parameters,
            "assumption_needs": assumption_needs,
            "secondary_research_needs": secondary_research_needs,
            "unsupported_claim_risks": unsupported_claim_risks,
            "recommended_next_action": recommended_next_action,
            "manual_audit_scaffold": self._build_manual_audit_scaffold(
                package=package,
                taxonomy=taxonomy,
                analysis_status=analysis_status,
                canonical_binding=canonical_analysis_binding,
                secondary_research=secondary_research,
            ),
            "canonical_analysis_binding": canonical_analysis_binding,
            "economic_output": economic_output,
        }

    @staticmethod
    def _extract_backend_run_id(
        *,
        selected_payload: dict[str, Any],
        run_context: dict[str, Any],
    ) -> str | None:
        payload_context = selected_payload.get("run_context")
        if isinstance(payload_context, dict):
            backend_run_id = payload_context.get("backend_run_id")
            if backend_run_id:
                return str(backend_run_id)
        run_context_run_id = run_context.get("run_id")
        if run_context_run_id:
            return str(run_context_run_id)
        return None

    @staticmethod
    def _extract_evidence_gap_categories(*, missing_evidence: list[str]) -> list[str]:
        categories: list[str] = []
        for item in missing_evidence:
            text = str(item or "").strip()
            if not text:
                continue
            category = text.split(":", 1)[0].strip().lower()
            if category and category not in categories:
                categories.append(category)
        return categories

    @staticmethod
    def _derive_analysis_status(
        *,
        readiness_level: str,
        decision_grade_verdict: str,
        required_evidence_gaps: list[str],
    ) -> dict[str, str]:
        if readiness_level == PackageReadinessLevel.FAIL_CLOSED.value:
            return {
                "status": "fail_closed",
                "reason": "fail_closed package cannot produce quantitative conclusion",
            }
        if decision_grade_verdict == "decision_grade":
            return {
                "status": "decision_grade",
                "reason": "all quality gates are decision-grade complete",
            }
        if required_evidence_gaps:
            return {
                "status": "secondary_research_needed",
                "reason": "additional evidence is required before quantitative conclusion",
            }
        return {
            "status": "qualitative_only",
            "reason": "package supports qualitative reasoning only",
        }

    @staticmethod
    def _derive_canonical_analysis_binding(
        *,
        package: PolicyEvidencePackage,
        llm_proof: dict[str, Any],
        run_context: dict[str, Any],
    ) -> dict[str, Any]:
        package_run_id = package.gate_projection.canonical_pipeline_run_id
        package_step_id = package.gate_projection.canonical_pipeline_step_id
        observed_run_id = llm_proof.get("canonical_pipeline_run_id")
        observed_step_id = llm_proof.get("canonical_pipeline_step_id")
        blocker = str(llm_proof.get("blocker") or "canonical_llm_run_id_missing")
        proof_status = str(llm_proof.get("proof_status") or "not_proven")
        route_run_id = str(run_context.get("run_id") or "").strip() or None
        source_artifact_refs = [
            {
                "evidence_card_id": card.id,
                "source_url": str(card.source_url),
                "artifact_id": card.artifact_id,
                "content_hash": card.content_hash,
            }
            for card in package.evidence_cards
        ]
        projection_matches_route = bool(
            package_run_id
            and package_step_id
            and observed_run_id == package_run_id
            and observed_step_id == package_step_id
            and (route_run_id is None or route_run_id == package_run_id)
        )
        if (proof_status == "pass" and observed_run_id) or projection_matches_route:
            return {
                "status": "bound",
                "reason": "canonical analysis run/step ids are linked to this package",
                "package_projection": {
                    "canonical_pipeline_run_id": package_run_id,
                    "canonical_pipeline_step_id": package_step_id,
                },
                "observed": {
                    "canonical_pipeline_run_id": observed_run_id,
                    "canonical_pipeline_step_id": observed_step_id,
                    "source": llm_proof.get("source"),
                },
                "route_run_id": route_run_id,
                "source_artifact_refs": source_artifact_refs,
            }
        return {
            "status": "not_proven",
            "reason": (
                "canonical analysis binding missing; package can be evaluated but not "
                "claimed as canonical LLM narrative output"
            ),
            "blocker": blocker,
            "missing_code_path": "analysis_history/package_id linkage in canonical AnalysisPipeline persistence path",
            "package_projection": {
                "canonical_pipeline_run_id": package_run_id,
                "canonical_pipeline_step_id": package_step_id,
            },
            "observed": {
                "canonical_pipeline_run_id": observed_run_id,
                "canonical_pipeline_step_id": observed_step_id,
                "source": llm_proof.get("source"),
            },
            "route_run_id": route_run_id,
            "source_artifact_refs": source_artifact_refs,
        }

    def _build_secondary_research_contract(
        self,
        *,
        package: PolicyEvidencePackage,
        analysis_status: dict[str, str],
        required_evidence_gaps: list[str],
        sufficiency: dict[str, Any],
        canonical_binding: dict[str, Any],
    ) -> dict[str, Any]:
        blocking_gate = str(sufficiency.get("blocking_gate") or "").strip() or None
        readiness_level = str(sufficiency.get("readiness_level") or "").strip()
        requires_secondary = analysis_status.get("status") == "secondary_research_needed"
        mechanism_families = sorted({model.mechanism_family.value for model in package.model_cards})
        unresolved_parameters = [
            {
                "parameter_id": card.id,
                "name": card.parameter_name,
                "unit": card.unit,
                "state": card.state.value,
                "resolution_hint": card.ambiguity_reason,
            }
            for card in package.parameter_cards
            if card.state.value != "resolved"
        ]
        evidence_inputs = [
            {
                "evidence_card_id": card.id,
                "source_url": str(card.source_url),
                "source_type": card.source_type.value,
                "content_hash": card.content_hash,
            }
            for card in package.evidence_cards
        ]
        request_id = f"sec-research::{package.package_id}"
        request_contract = {
            "request_id": request_id,
            "package_id": package.package_id,
            "jurisdiction": package.jurisdiction,
            "canonical_document_key": package.canonical_document_key,
            "policy_identifier": package.policy_identifier,
            "mechanism_families": mechanism_families,
            "blocking_gate": blocking_gate,
            "required_evidence_gaps": required_evidence_gaps,
            "target_parameters": unresolved_parameters,
            "source_artifact_refs": evidence_inputs,
        }
        if not requires_secondary:
            return {
                "status": "not_required",
                "reason": "package is already decision-grade or qualitative-only without secondary trigger",
                "request_contract": None,
                "output_contract": None,
            }
        return {
            "status": "required",
            "reason": (
                "indirect or under-parameterized analysis path requires auditable secondary research package"
            ),
            "request_contract": request_contract,
            "output_contract": {
                "request_id": request_id,
                "must_link_package_id": package.package_id,
                "must_include_source_artifacts": True,
                "must_include_parameter_provenance": True,
                "must_include_assumption_updates": True,
                "must_include_model_card_updates": True,
                "must_emit_fail_closed_if_missing": True,
                "canonical_analysis_binding_required": canonical_binding["status"] == "bound",
                "readiness_target": PackageReadinessLevel.ECONOMIC_HANDOFF_READY.value,
                "current_readiness": readiness_level,
            },
        }

    @staticmethod
    def _build_mechanism_candidates(
        *,
        package: PolicyEvidencePackage,
        vertical: dict[str, Any],
        rubric: dict[str, Any],
    ) -> list[dict[str, Any]]:
        mechanism_type = str(vertical.get("mechanism_type") or "direct")
        direct_fee_model_card = vertical.get("direct_fee_model_card") or {}
        household_impact_readiness = (
            direct_fee_model_card.get("household_impact_readiness")
            if isinstance(direct_fee_model_card, dict)
            else None
        )
        direct_status = (
            "pass"
            if mechanism_type == "direct"
            and str((direct_fee_model_card.get("status") or "")) == "pass"
            else "not_proven"
        )
        indirect_assumptions = [
            card
            for card in package.assumption_cards
            if card.family in {MechanismFamily.FEE_OR_TAX_PASS_THROUGH, MechanismFamily.ADOPTION_TAKE_UP}
        ]
        indirect_status = "pass" if indirect_assumptions else "not_proven"
        return [
            {
                "mechanism_type": "direct",
                "status": direct_status,
                "reason": str(
                    (direct_fee_model_card.get("reason") or "direct model card not proven")
                ),
                "supported_model_card_ids": [
                    card.id for card in package.model_cards if card.mechanism_family == MechanismFamily.DIRECT_FISCAL
                ],
                "direct_fee_model_candidate": {
                    "status": str(direct_fee_model_card.get("status") or "not_proven"),
                    "scope": str(direct_fee_model_card.get("scope") or "direct_developer_fee"),
                    "formula": str(direct_fee_model_card.get("formula") or ""),
                },
                "household_pass_through_need": (
                    {
                        "status": str(household_impact_readiness.get("status") or "not_proven"),
                        "reason": str(
                            household_impact_readiness.get("reason")
                            or "household pass-through/incidence assumptions missing"
                        ),
                    }
                    if isinstance(household_impact_readiness, dict)
                    else {
                        "status": "not_proven",
                        "reason": "household pass-through/incidence assumptions missing",
                    }
                ),
            },
            {
                "mechanism_type": "indirect",
                "status": indirect_status,
                "reason": (
                    "source-bound pass-through/adoption assumptions present"
                    if indirect_status == "pass"
                    else "pass-through/adoption assumptions missing"
                ),
                "supported_assumption_ids": [card.id for card in indirect_assumptions],
            },
            {
                "mechanism_type": mechanism_type,
                "status": str(rubric.get("mechanism_graph_validity", {}).get("status") or "not_proven"),
                "reason": str(rubric.get("mechanism_graph_validity", {}).get("details") or "mechanism graph not proven"),
            },
        ]

    @staticmethod
    def _build_parameter_inventory(*, package: PolicyEvidencePackage) -> dict[str, Any]:
        resolved: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        for card in package.parameter_cards:
            payload = {
                "parameter_id": card.id,
                "name": card.parameter_name,
                "state": card.state.value,
                "unit": card.unit,
                "source_url": None if card.source_url is None else str(card.source_url),
                "evidence_card_id": card.evidence_card_id,
                "ambiguity_reason": card.ambiguity_reason,
            }
            if card.state.value == "resolved":
                resolved.append(payload)
            else:
                missing.append(payload)
        return {
            "resolved_count": len(resolved),
            "missing_count": len(missing),
            "resolved_parameters": resolved,
            "missing_parameters": missing,
        }

    @staticmethod
    def _build_assumption_needs(*, package: PolicyEvidencePackage, mechanism_type: str) -> dict[str, Any]:
        required_families = [MechanismFamily.FEE_OR_TAX_PASS_THROUGH, MechanismFamily.ADOPTION_TAKE_UP]
        assumption_by_family = {card.family: card for card in package.assumption_cards}
        missing_families = [
            family.value for family in required_families if family not in assumption_by_family
        ]
        direct_scope_status = (
            "not_required"
            if mechanism_type == "direct"
            else ("pass" if not missing_families else "not_proven")
        )
        household_scope_status = "pass" if not missing_families else "not_proven"
        return {
            "status": "pass" if not missing_families else "not_proven",
            "required_families": [family.value for family in required_families],
            "missing_families": missing_families,
            "assumption_count": len(package.assumption_cards),
            "assumption_ids": [card.id for card in package.assumption_cards],
            "direct_project_fee_scope": {
                "status": direct_scope_status,
                "reason": (
                    "direct project-fee arithmetic does not require household incidence assumptions"
                    if mechanism_type == "direct"
                    else (
                        "source-bound assumptions present"
                        if direct_scope_status == "pass"
                        else "indirect mechanism still requires source-bound assumptions"
                    )
                ),
            },
            "household_cost_of_living_scope": {
                "status": household_scope_status,
                "reason": (
                    "source-bound pass-through/incidence assumptions present"
                    if household_scope_status == "pass"
                    else "pass-through/incidence assumptions missing"
                ),
                "missing_families": missing_families,
            },
        }

    @staticmethod
    def _build_secondary_research_needs(
        *,
        secondary_research: dict[str, Any],
        required_evidence_gaps: list[str],
        canonical_binding: dict[str, Any],
        assumption_needs: dict[str, Any],
        analysis_status: dict[str, str],
        unsupported_claim_risks: dict[str, Any],
    ) -> dict[str, Any]:
        status = str(secondary_research.get("status") or "not_required")
        request_contract = secondary_research.get("request_contract")
        request_target_parameters = []
        if isinstance(request_contract, dict):
            targets = request_contract.get("target_parameters")
            if isinstance(targets, list):
                request_target_parameters = [
                    str(item.get("name") or item.get("parameter_id") or "").strip()
                    for item in targets
                    if isinstance(item, dict)
                    and str(item.get("name") or item.get("parameter_id") or "").strip()
                ]
        assumption_missing = [
            str(family).strip()
            for family in assumption_needs.get("missing_families", [])
            if str(family).strip()
        ]
        needs_household_incidence = bool(
            set(assumption_missing)
            & {
                MechanismFamily.FEE_OR_TAX_PASS_THROUGH.value,
                MechanismFamily.ADOPTION_TAKE_UP.value,
            }
        )
        analysis_state = str(analysis_status.get("status") or "")
        unsupported_fail_closed = (
            analysis_state == "fail_closed"
            and str(unsupported_claim_risks.get("risk_level") or "") == "high"
        )
        effective_required = status == "required" or (
            needs_household_incidence and not unsupported_fail_closed
        )
        reason_code = "not_required"
        if effective_required and needs_household_incidence:
            reason_code = "pass_through_incidence_assumptions_missing"
        elif effective_required:
            reason_code = "secondary_research_contract_required"
        return {
            "status": "required" if effective_required else "not_required",
            "reason": str(secondary_research.get("reason") or "secondary research not required"),
            "reason_code": reason_code,
            "required_evidence_gaps": required_evidence_gaps,
            "request_contract_id": (
                request_contract.get("request_id")
                if isinstance(request_contract, dict)
                else None
            ),
            "request_target_parameters": request_target_parameters,
            "household_incidence_assumptions_missing": needs_household_incidence,
            "canonical_binding_required": canonical_binding.get("status") == "bound",
            "must_fail_closed_without_secondary_package": effective_required,
        }

    @staticmethod
    def _build_unsupported_claim_risks(
        *,
        package: PolicyEvidencePackage,
        vertical: dict[str, Any],
    ) -> dict[str, Any]:
        unsupported = vertical.get("unsupported_claim_rejection") or {}
        status = str(unsupported.get("status") or "none")
        risk_level = "high" if status == "rejected" else "low"
        return {
            "status": status,
            "risk_level": risk_level,
            "reason": str(unsupported.get("reason") or "none"),
            "unsupported_claim_count": package.gate_report.unsupported_claim_count,
        }

    @staticmethod
    def _derive_source_identity_status(
        *,
        source_quality_metrics: dict[str, Any],
        source_reconciliation: dict[str, Any],
    ) -> dict[str, Any]:
        policy_identity_ready_raw = source_quality_metrics.get("policy_identity_ready")
        jurisdiction_identity_ready_raw = source_quality_metrics.get("jurisdiction_identity_ready")
        policy_identity_ready = (
            bool(policy_identity_ready_raw) if isinstance(policy_identity_ready_raw, bool) else True
        )
        jurisdiction_identity_ready = (
            bool(jurisdiction_identity_ready_raw)
            if isinstance(jurisdiction_identity_ready_raw, bool)
            else True
        )
        identity_signals_present = isinstance(policy_identity_ready_raw, bool) or isinstance(
            jurisdiction_identity_ready_raw, bool
        )
        identity_blocker_code = str(
            source_quality_metrics.get("identity_blocker_code")
            or source_reconciliation.get("identity_blocker_code")
            or ""
        ).strip()
        identity_blocker_reason = str(
            source_quality_metrics.get("identity_blocker_reason")
            or source_reconciliation.get("identity_blocker_reason")
            or ""
        ).strip()
        if not identity_blocker_code:
            if not jurisdiction_identity_ready:
                identity_blocker_code = "jurisdiction_identity_mismatch"
            elif not policy_identity_ready:
                identity_blocker_code = "policy_identity_mismatch"

        identity_ready = policy_identity_ready and jurisdiction_identity_ready and not identity_blocker_code
        if identity_blocker_code == "policy_identity_mismatch":
            identity_recommended_action = "improve_policy_identity_matching"
        elif identity_blocker_code:
            identity_recommended_action = "repair_source_identity"
        else:
            identity_recommended_action = None

        return {
            "policy_identity_ready": policy_identity_ready,
            "jurisdiction_identity_ready": jurisdiction_identity_ready,
            "identity_signals_present": identity_signals_present,
            "identity_ready": identity_ready,
            "identity_blocker_code": identity_blocker_code,
            "identity_blocker_reason": identity_blocker_reason,
            "identity_recommended_action": identity_recommended_action,
        }

    @staticmethod
    def _build_economic_handoff_quality(
        *,
        analysis_status: dict[str, str],
        decision_grade_verdict: str,
        readiness_level: str,
        blocking_gate: str | None,
        canonical_binding_status: str,
        mechanism_type: str,
        direct_fee_model_card: dict[str, Any],
        missing_parameters: list[dict[str, Any]],
        assumption_needs: dict[str, Any],
        secondary_research_needs: dict[str, Any],
        unsupported_claim_risks: dict[str, Any],
        source_quality_metrics: dict[str, Any],
        source_reconciliation: dict[str, Any],
    ) -> dict[str, Any]:
        identity_status = PolicyEvidenceQualitySpineEconomicsService._derive_source_identity_status(
            source_quality_metrics=source_quality_metrics,
            source_reconciliation=source_reconciliation,
        )
        identity_blocker_code = str(identity_status.get("identity_blocker_code") or "")
        identity_blocker_reason = str(identity_status.get("identity_blocker_reason") or "")
        identity_blocked = bool(identity_blocker_code)

        direct_fee_ready = mechanism_type == "direct" and str(direct_fee_model_card.get("status") or "") == "pass"
        household_impact = direct_fee_model_card.get("household_impact_readiness")
        household_impact_status = (
            str(household_impact.get("status") or "").strip()
            if isinstance(household_impact, dict)
            else ""
        )
        household_incidence_missing = bool(
            secondary_research_needs.get("household_incidence_assumptions_missing")
        )

        direct_scope_status = "not_analysis_ready"
        direct_scope_reason = "source-bound direct project-fee path not established"
        if identity_blocked:
            direct_scope_reason = (
                identity_blocker_reason
                or "source identity mismatch blocks direct project-fee exposure analysis"
            )
        elif direct_fee_ready:
            direct_scope_status = "analysis_ready"
            direct_scope_reason = "source-bound direct fee rows support project-fee exposure analysis"

        household_scope_status = "not_analysis_ready"
        household_scope_reason = "household cost-of-living incidence path is not source-bound"
        if identity_blocked:
            household_scope_reason = (
                identity_blocker_reason
                or "source identity mismatch blocks household cost-of-living analysis"
            )
        elif (
            decision_grade_verdict == "decision_grade"
            and analysis_status.get("status") == "decision_grade"
            and canonical_binding_status == "bound"
        ):
            household_scope_status = "analysis_ready"
            household_scope_reason = "household path is decision-grade and canonically bound"
        elif household_impact_status == "pass" and not household_incidence_missing:
            household_scope_status = "analysis_ready_with_gaps"
            household_scope_reason = (
                "household assumptions are present, but package still has unresolved non-decision-grade gates"
            )

        if household_scope_status != "analysis_ready":
            household_scope_status = "not_analysis_ready"

        status = "not_analysis_ready"
        reason_code = "insufficient_source_grounding"
        analysis_state = str(analysis_status.get("status") or "")
        if identity_blocked:
            status = "not_analysis_ready"
            reason_code = identity_blocker_code
        elif (
            decision_grade_verdict == "decision_grade"
            and analysis_state == "decision_grade"
            and canonical_binding_status == "bound"
        ):
            status = "analysis_ready"
            reason_code = "decision_grade_bound"
        elif direct_scope_status == "analysis_ready":
            status = "analysis_ready_with_gaps"
            reason_code = "direct_project_fee_ready_household_incidence_gap"
        elif analysis_state == "qualitative_only":
            status = "not_analysis_ready"
            reason_code = "qualitative_only"
        elif analysis_state == "fail_closed":
            status = "not_analysis_ready"
            reason_code = (
                f"fail_closed_{blocking_gate}_blocking_gate" if blocking_gate else "fail_closed"
            )
        elif secondary_research_needs.get("status") == "required":
            status = "not_analysis_ready"
            reason_code = str(secondary_research_needs.get("reason_code") or "secondary_research_required")

        if (
            not identity_blocked
            and unsupported_claim_risks.get("risk_level") == "high"
            and status != "analysis_ready"
        ):
            status = "not_analysis_ready"
            reason_code = "unsupported_claim_risk_high"

        return {
            "status": status,
            "legacy_status": "ready" if status == "analysis_ready" else "not_ready",
            "reason_code": reason_code,
            "quantification_paths": {
                "direct_project_fee_exposure": {
                    "status": direct_scope_status,
                    "reason": direct_scope_reason,
                },
                "household_cost_of_living": {
                    "status": household_scope_status,
                    "reason": household_scope_reason,
                },
            },
            "can_quantify_now": [path for path, value in {
                "direct_project_fee_exposure": direct_scope_status,
                "household_cost_of_living": household_scope_status,
            }.items() if value == "analysis_ready"],
            "missing_parameters_count": len(missing_parameters),
            "missing_assumption_families": assumption_needs.get("missing_families", []),
            "secondary_research_required": secondary_research_needs.get("status") == "required",
            "fail_closed_specific": analysis_state == "fail_closed",
            "fail_closed_blocking_gate": blocking_gate,
            "analysis_state": analysis_state,
            "readiness_level": readiness_level,
            "source_identity_blocker": identity_blocked,
            "source_identity_blocker_code": identity_blocker_code or None,
            "source_identity_blocker_reason": identity_blocker_reason or None,
        }

    @staticmethod
    def _build_data_moat_status(
        *,
        evidence_package_status: str,
        decision_grade_verdict: str,
        required_evidence_gaps: list[str],
        readiness_level: str,
        taxonomy: dict[str, dict[str, str]],
        canonical_binding_status: str,
        economic_handoff_quality: dict[str, Any],
        source_quality_metrics: dict[str, Any],
        source_reconciliation: dict[str, Any],
    ) -> dict[str, Any]:
        identity_status = PolicyEvidenceQualitySpineEconomicsService._derive_source_identity_status(
            source_quality_metrics=source_quality_metrics,
            source_reconciliation=source_reconciliation,
        )
        policy_identity_ready = bool(identity_status.get("policy_identity_ready"))
        jurisdiction_identity_ready = bool(identity_status.get("jurisdiction_identity_ready"))
        identity_signals_present = bool(identity_status.get("identity_signals_present"))
        identity_ready = bool(identity_status.get("identity_ready"))
        identity_blocker_code = str(identity_status.get("identity_blocker_code") or "")
        identity_blocker_reason = str(identity_status.get("identity_blocker_reason") or "")
        identity_recommended_action = identity_status.get("identity_recommended_action")

        selected_family = str(
            source_quality_metrics.get("selected_artifact_family")
            or (
                source_quality_metrics.get("selected_candidate", {})
                if isinstance(source_quality_metrics.get("selected_candidate"), dict)
                else {}
            ).get("artifact_family")
            or ""
        ).strip()
        top_n_artifact_recall_count = int(
            source_quality_metrics.get("top_n_artifact_recall_count") or 0
        )
        selection_reason = "selected_candidate_quality_unknown"
        source_selection_blocker = False
        if identity_blocker_code:
            selection_reason = identity_blocker_code
            source_selection_blocker = True
        elif selected_family == "artifact":
            selection_reason = "selected_artifact_grade_candidate"
        elif (
            selected_family == "official_page"
            and top_n_artifact_recall_count > 0
            and not (identity_signals_present and identity_ready)
        ):
            selection_reason = "official_page_selected_while_artifact_candidates_exist"
            source_selection_blocker = True
        elif selected_family:
            selection_reason = f"selected_{selected_family}_candidate"

        true_structured_row_count = int(source_reconciliation.get("true_structured_row_count") or 0)
        missing_true_structured_corroboration_count = int(
            source_reconciliation.get("missing_true_structured_corroboration_count") or 0
        )
        structured_depth_ready = (
            true_structured_row_count > 0
            and missing_true_structured_corroboration_count == 0
        )
        runtime_ready = (
            taxonomy.get("storage/read-back", {}).get("status") == "pass"
            and taxonomy.get("Windmill/orchestration", {}).get("status") == "pass"
            and taxonomy.get("LLM narrative", {}).get("status") == "pass"
            and canonical_binding_status == "bound"
        )
        source_quality_ready = (
            taxonomy.get("scraped/search", {}).get("status") == "pass"
            and not source_selection_blocker
            and identity_ready
        )
        economic_handoff_ready = (
            str(economic_handoff_quality.get("status") or "") == "analysis_ready"
            and not source_selection_blocker
            and identity_ready
        )
        data_moat_component_ready = (
            runtime_ready
            and source_quality_ready
            and structured_depth_ready
            and economic_handoff_ready
        )

        moat_blockers: list[dict[str, str]] = []
        if identity_blocker_code:
            moat_blockers.append(
                {
                    "code": identity_blocker_code,
                    "reason": (
                        identity_blocker_reason
                        or (
                            "Selected source identity does not match requested jurisdiction."
                            if identity_blocker_code == "jurisdiction_identity_mismatch"
                            else "Selected source identity does not match requested policy."
                        )
                    ),
                }
            )
        if selection_reason == "official_page_selected_while_artifact_candidates_exist":
            moat_blockers.append(
                {
                    "code": "official_page_selected_while_artifact_candidates_exist",
                    "reason": "Selected source is official page while artifact candidates exist.",
                }
            )
        if true_structured_row_count == 0:
            moat_blockers.append(
                {
                    "code": "true_structured_rows_missing",
                    "reason": "No true structured economic rows are available.",
                }
            )
        if missing_true_structured_corroboration_count > 0:
            moat_blockers.append(
                {
                    "code": "missing_true_structured_corroboration",
                    "reason": (
                        "Primary official rows are missing corroboration from true structured sources."
                    ),
                }
            )

        if decision_grade_verdict == "decision_grade":
            status = "decision_grade_data_moat"
            reason = "all D0-D11 quality gates resolved for this package"
        elif data_moat_component_ready:
            status = "evidence_ready_with_gaps"
            reason = "runtime and source depth requirements are met with non-decision-grade economic gaps"
        elif evidence_package_status == "fail" or moat_blockers:
            status = "fail"
            if moat_blockers:
                reason = "package failed explicit data moat blockers despite runtime readiness"
            else:
                reason = "package evidence quality failed one or more blocking gates"
        else:
            status = "evidence_ready_with_gaps"
            reason = "package is usable but still has named missing evidence or readiness gaps"
        return {
            "status": status,
            "overall_ready": status == "decision_grade_data_moat",
            "runtime_ready": runtime_ready,
            "source_quality_ready": source_quality_ready,
            "structured_depth_ready": structured_depth_ready,
            "economic_handoff_ready": economic_handoff_ready,
            "evidence_package_status": evidence_package_status,
            "decision_grade_verdict": decision_grade_verdict,
            "readiness_level": readiness_level,
            "named_gaps": required_evidence_gaps,
            "named_gap_count": len(required_evidence_gaps),
            "source_selection_blocker": source_selection_blocker,
            "source_selection_reason": selection_reason,
            "selected_artifact_family": selected_family or "unknown",
            "top_n_artifact_recall_count": top_n_artifact_recall_count,
            "policy_identity_ready": policy_identity_ready,
            "jurisdiction_identity_ready": jurisdiction_identity_ready,
            "identity_signals_present": identity_signals_present,
            "identity_ready": identity_ready,
            "identity_blocker_code": identity_blocker_code or None,
            "identity_blocker_reason": identity_blocker_reason or None,
            "identity_recommended_action": identity_recommended_action,
            "true_structured_row_count": true_structured_row_count,
            "missing_true_structured_corroboration_count": missing_true_structured_corroboration_count,
            "blockers": moat_blockers,
            "reason": reason,
        }

    @staticmethod
    def _recommend_next_action(
        *,
        analysis_status: dict[str, str],
        taxonomy: dict[str, dict[str, str]],
        secondary_research: dict[str, Any],
        canonical_binding: dict[str, Any],
        economic_handoff_quality: dict[str, Any],
        unsupported_claim_risks: dict[str, Any],
        data_moat_status: dict[str, Any],
    ) -> str:
        handoff_status = str(economic_handoff_quality.get("status") or "not_analysis_ready")
        runtime_ready = bool(data_moat_status.get("runtime_ready"))
        source_quality_ready = bool(data_moat_status.get("source_quality_ready"))
        structured_depth_ready = bool(data_moat_status.get("structured_depth_ready"))
        true_structured_row_count = int(data_moat_status.get("true_structured_row_count") or 0)
        missing_true_structured_corroboration_count = int(
            data_moat_status.get("missing_true_structured_corroboration_count") or 0
        )
        source_selection_blocker = bool(data_moat_status.get("source_selection_blocker"))
        identity_recommended_action = str(data_moat_status.get("identity_recommended_action") or "").strip()

        if identity_recommended_action:
            return identity_recommended_action

        if runtime_ready and (not source_quality_ready or not structured_depth_ready):
            if (
                true_structured_row_count == 0
                or missing_true_structured_corroboration_count > 0
            ):
                return "ingest_official_attachments"
            if source_selection_blocker:
                return "improve_data_moat_sources"
        if (
            unsupported_claim_risks.get("risk_level") == "high"
            and handoff_status != "analysis_ready"
        ):
            return "reject"
        if handoff_status == "analysis_ready":
            return "run_direct_analysis"
        if bool(economic_handoff_quality.get("secondary_research_required")):
            return "run_secondary_research"
        if secondary_research.get("status") == "required":
            return "run_secondary_research"
        if analysis_status.get("status") == "qualitative_only":
            return "qualitative_summary_only"
        if taxonomy.get("storage/read-back", {}).get("status") != "pass":
            return "reject"
        if taxonomy.get("Windmill/orchestration", {}).get("status") != "pass":
            return "reject"
        if canonical_binding.get("status") != "bound":
            return "reject"
        if handoff_status == "analysis_ready_with_gaps":
            return "run_secondary_research"
        return "reject"

    @staticmethod
    def _extract_source_quality_metrics(*, selected_payload: dict[str, Any]) -> dict[str, Any]:
        direct = selected_payload.get("source_quality_metrics")
        if isinstance(direct, dict) and direct:
            return direct
        run_context = selected_payload.get("run_context")
        if isinstance(run_context, dict):
            nested = run_context.get("source_quality_metrics")
            if isinstance(nested, dict) and nested:
                return nested
        return {}

    @staticmethod
    def _extract_source_reconciliation(*, selected_payload: dict[str, Any]) -> dict[str, Any]:
        direct = selected_payload.get("source_reconciliation")
        if isinstance(direct, dict) and direct:
            return direct
        run_context = selected_payload.get("run_context")
        if isinstance(run_context, dict):
            nested = run_context.get("source_reconciliation")
            if isinstance(nested, dict) and nested:
                return nested
        return {}

    @staticmethod
    def _build_manual_audit_scaffold(
        *,
        package: PolicyEvidencePackage,
        taxonomy: dict[str, dict[str, str]],
        analysis_status: dict[str, str],
        canonical_binding: dict[str, Any],
        secondary_research: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "status": "required",
            "checklist": [
                {
                    "id": "audit_identity_and_provenance",
                    "description": "Verify canonical_document_key and every evidence/parameter card trace to source artifacts or rows.",
                    "gate": "D6",
                },
                {
                    "id": "audit_storage_readback_replay",
                    "description": "Verify Postgres row, MinIO readback, pgvector refs, and replay/idempotent proof mode.",
                    "gate": "D7",
                },
                {
                    "id": "audit_windmill_binding",
                    "description": "Verify current windmill run/job ids are linked to package and backend run state.",
                    "gate": "D9",
                },
                {
                    "id": "audit_economic_handoff_contract",
                    "description": "Verify mechanism candidates, parameter inventory, assumptions, unsupported-claim risks, and next action are machine-actionable.",
                    "gate": "D11",
                },
            ],
            "current_gate_status": {
                "D6": taxonomy.get("identity/dedupe", {}).get("status"),
                "D7": taxonomy.get("storage/read-back", {}).get("status"),
                "D9": taxonomy.get("Windmill/orchestration", {}).get("status"),
                "D11": analysis_status.get("status"),
            },
            "canonical_binding_status": canonical_binding.get("status"),
            "secondary_research_status": secondary_research.get("status"),
            "evidence_refs": [
                {
                    "evidence_card_id": card.id,
                    "source_url": str(card.source_url),
                    "artifact_id": card.artifact_id,
                }
                for card in package.evidence_cards
            ],
        }

    @staticmethod
    def _is_probably_scope_job_id(job_id: str) -> bool:
        text = str(job_id).strip()
        return text.startswith("run_scope_pipeline:") or text.startswith("scope:")

    @classmethod
    def _derive_reader_provenance_evidence(
        cls,
        *,
        package: PolicyEvidencePackage,
        runtime_evidence: dict[str, Any],
        storage_gate_status: str,
    ) -> dict[str, Any]:
        if not package.scraped_sources:
            return {"all_effective_passed": False, "per_source": []}

        storage_proven = storage_gate_status == "pass"
        package_payload = runtime_evidence.get("vertical_package_payload")
        run_context = {}
        if isinstance(package_payload, dict):
            candidate = package_payload.get("run_context")
            if isinstance(candidate, dict):
                run_context = candidate
        run_context_reader_ref = str(run_context.get("reader_artifact_uri") or "").strip()
        has_reader_storage_ref = any(
            (
                ref.storage_system == StorageSystem.MINIO
                and (
                    "reader" in ref.reference_id.lower()
                    or "reader" in str(ref.uri or "").lower()
                    or "reader" in str(ref.notes or "").lower()
                )
            )
            for ref in package.storage_refs
        )
        inferred_reader_ref = bool(run_context_reader_ref or has_reader_storage_ref)

        per_source: list[dict[str, Any]] = []
        for source in package.scraped_sources:
            explicit_reader_ref = source.reader_artifact_url is not None
            hydrated_by_storage = bool(
                not source.reader_substance_passed
                and storage_proven
                and (explicit_reader_ref or inferred_reader_ref)
            )
            effective_passed = bool(source.reader_substance_passed or hydrated_by_storage)
            per_source.append(
                {
                    "effective_passed": effective_passed,
                    "hydrated_by_storage_proof": hydrated_by_storage,
                    "explicit_reader_ref": explicit_reader_ref,
                    "inferred_reader_ref": inferred_reader_ref,
                }
            )

        return {
            "all_effective_passed": all(item["effective_passed"] for item in per_source),
            "per_source": per_source,
        }

    def render_markdown_report(self, *, evaluation: dict[str, Any]) -> str:
        scorecard = evaluation["scorecard"]
        vertical = evaluation["vertical_economic_output"]
        audit = evaluation["read_model_audit_output"]
        lines = [
            "# Policy Evidence Quality Spine Economic Report",
            "",
            f"- feature_key: `{scorecard['feature_key']}`",
            f"- report_version: `{scorecard['report_version']}`",
            f"- generated_at: `{scorecard['generated_at']}`",
            f"- matrix_mode: `{scorecard['matrix_source']['mode']}`",
            f"- matrix_path: `{scorecard['matrix_source']['path']}`",
            f"- overall_verdict: `{scorecard['overall_verdict']}`",
            f"- decision_grade_verdict: `{scorecard['decision_grade']['verdict']}`",
            f"- vertical_package_id: `{scorecard['vertical_package']['package_id']}`",
            f"- sufficiency_readiness: `{scorecard['sufficiency_result']['readiness_level']}`",
            "",
            "## Failure taxonomy",
            "",
            "| Category | Status | Evidence |",
            "| --- | --- | --- |",
        ]
        for category in QUALITY_BUCKETS:
            item = scorecard["taxonomy"][category]
            lines.append(f"| {category} | {item['status']} | {item['details']} |")

        lines.extend(
            [
                "",
                "## Economic quality rubric",
                "",
                "| Dimension | Status | Evidence |",
                "| --- | --- | --- |",
            ]
        )
        rubric = scorecard["economic_quality_rubric"]
        for dimension in ECONOMIC_QUALITY_DIMENSIONS:
            item = rubric["dimensions"][dimension]
            lines.append(f"| {dimension} | {item['status']} | {item['details']} |")

        missing = scorecard["decision_grade"]["missing_evidence"]
        lines.extend(
            [
                "",
                "### Missing evidence for decision grade",
                "",
                *(f"- {item}" for item in missing),
            ]
        )

        lines.extend(
            [
                "",
                "## Vertical economic output",
                "",
                f"- mechanism_type: `{vertical['mechanism_type']}`",
                f"- quantified: `{vertical['quantified']}`",
                f"- unsupported_claim_rejection: "
                f"`{vertical['unsupported_claim_rejection']['status']}`",
                "",
                "### User-facing conclusion",
                "",
                vertical["user_facing_conclusion"],
                "",
                "## Read-model/admin audit output",
                "",
                f"- frontend_requires_recomputation: "
                f"`{audit['frontend_contract']['requires_recomputation']}`",
                f"- admin_requires_recomputation: "
                f"`{audit['admin_contract']['requires_recomputation']}`",
                f"- canonical_analysis_adapter: `{audit['analysis_handoff']['adapter_mode']}`",
                f"- llm_narrative_proof_status: "
                f"`{audit['analysis_handoff']['llm_narrative_proof']['proof_status']}`",
                f"- llm_narrative_proof_blocker: "
                f"`{audit['analysis_handoff']['llm_narrative_proof']['blocker']}`",
            ]
        )
        return "\n".join(lines) + "\n"

    def _extract_package_candidates(self, payload: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        candidates: dict[str, dict[str, Any]] = {}
        stack: list[Any] = [payload]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if self._looks_like_package(node):
                    package_id = str(node.get("package_id") or f"pkg-{len(candidates)+1}")
                    candidates[package_id] = node
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
        return list(candidates.values())

    @staticmethod
    def _looks_like_package(payload: dict[str, Any]) -> bool:
        required = {
            "package_id",
            "canonical_document_key",
            "policy_identifier",
            "source_lanes",
            "evidence_cards",
            "gate_report",
            "gate_projection",
        }
        return required.issubset(payload.keys())

    def _fallback_vertical_package(self) -> dict[str, Any]:
        bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
        for case in bundle["cases"]:
            if case["case_id"] == "indirect_pass_through_case":
                return case["primary_package"]
        raise RuntimeError("fallback package not found")

    def _select_vertical_candidate(
        self,
        packages: list[dict[str, Any]],
        *,
        preferred_package_id: str | None = None,
    ) -> dict[str, Any]:
        if preferred_package_id:
            for package in packages:
                if str(package.get("package_id") or "") == preferred_package_id:
                    return package
            raise ValueError(f"preferred package_id={preferred_package_id} not found")
        best = None
        for package in packages:
            lanes = set(package.get("source_lanes", []))
            score = 0
            if package.get("economic_handoff_ready") is True:
                score += 3
            if "scraped" in lanes:
                score += 1
            if "structured" in lanes:
                score += 1
            if best is None or score > best[0]:
                best = (score, package)
        if best is None:
            raise RuntimeError("no package candidate available")
        return best[1]

    def _persist_for_readback(self, package_payload: dict[str, Any]) -> dict[str, Any]:
        known_uris = {f"minio://policy-evidence/packages/{package_payload['package_id']}.json"}
        for ref in package_payload.get("storage_refs", []):
            if ref.get("storage_system") != "minio":
                continue
            uri = ref.get("uri") or ref.get("reference_id")
            if uri:
                known_uris.add(uri)
        store = InMemoryPolicyEvidencePackageStore()
        storage = PolicyEvidencePackageStorageService(
            store=store,
            artifact_writer=InMemoryArtifactWriter(),
            artifact_probe=InMemoryArtifactProbe(known_uris=known_uris),
        )
        idempotency_key = f"quality-spine::{package_payload['package_id']}"
        storage_result = storage.persist(
            package_payload=package_payload,
            idempotency_key=idempotency_key,
        )
        record = store.get_by_idempotency(idempotency_key=idempotency_key)
        if record is None:
            raise RuntimeError("storage persist failed for quality spine evaluation")
        return {"storage_result": storage_result, "record": record}

    def _build_taxonomy(
        self,
        *,
        package: PolicyEvidencePackage,
        matrix_payload: dict[str, Any],
        matrix_source_mode: str,
        storage_eval: dict[str, Any],
        sufficiency: Any,
    ) -> dict[str, dict[str, str]]:
        storage_result = storage_eval["storage_result"]
        verdict = package.gate_report.verdict
        runtime_evidence = self._extract_runtime_evidence(matrix_payload)
        orchestration_eval = self._evaluate_orchestration_proof(runtime_evidence)
        llm_eval = self._evaluate_llm_narrative_proof(
            package=package,
            runtime_evidence=runtime_evidence,
            matrix_source_mode=matrix_source_mode,
        )
        scraped_eval = self._evaluate_scraped_search_proof(
            package=package,
            matrix_payload=matrix_payload,
        )
        storage_proof_eval = self._evaluate_storage_readback_proof(
            runtime_evidence=runtime_evidence,
            storage_result=storage_result,
        )
        reader_eval = self._derive_reader_provenance_evidence(
            package=package,
            runtime_evidence=runtime_evidence,
            storage_gate_status=storage_proof_eval["status"],
        )
        all_tags = set()
        for assumption in package.assumption_cards:
            all_tags.update(assumption.applicability_tags)

        frontend_ready = (
            package.gate_projection.canonical_pipeline_run_id is not None
            or matrix_source_mode == "fallback_fixture"
        )
        frontend_status = "pass" if frontend_ready else "not_proven"
        frontend_detail = (
            "Read-model payload is display-only and does not recompute economic truth."
            if frontend_ready
            else "No canonical pipeline run id yet; frontend display link not proven."
        )

        taxonomy = {
            "scraped/search": {
                "status": scraped_eval["status"],
                "details": scraped_eval["details"],
            },
            "reader": {
                "status": "pass" if reader_eval["all_effective_passed"] else "fail",
                "details": (
                    "Reader provenance is proven by reader refs and/or storage readback hydration."
                    if reader_eval["all_effective_passed"]
                    else "Missing reader_substance_passed=true or reader artifact references."
                ),
            },
            "structured-source": {
                "status": "pass" if package.structured_sources else "fail",
                "details": (
                    "Structured source provenance attached."
                    if package.structured_sources
                    else "No structured source provenance attached."
                ),
            },
            "identity/dedupe": {
                "status": "pass" if package.canonical_document_key else "fail",
                "details": (
                    "Canonical document key present for dedupe/identity join."
                    if package.canonical_document_key
                    else "Missing canonical_document_key."
                ),
            },
            "storage/read-back": {
                "status": storage_proof_eval["status"],
                "details": storage_proof_eval["details"],
                "proof_mode": storage_proof_eval.get("proof_mode", "unknown"),
                "direct_probe_available": storage_proof_eval.get(
                    "direct_probe_available", False
                ),
            },
            "Windmill/orchestration": {
                "status": orchestration_eval["status"],
                "details": orchestration_eval["details"],
            },
            "sufficiency gate": {
                "status": "pass" if sufficiency.readiness_level != PackageReadinessLevel.FAIL_CLOSED else "fail",
                "details": (
                    f"readiness={sufficiency.readiness_level.value}"
                    if sufficiency.readiness_level != PackageReadinessLevel.FAIL_CLOSED
                    else f"fail_closed at {sufficiency.blocking_gate.value if sufficiency.blocking_gate else 'unknown'}"
                ),
            },
            "economic reasoning": {
                "status": (
                    "pass"
                    if package.model_cards
                    and (
                        any(card.quantification_eligible for card in package.model_cards)
                        or verdict in {GateVerdict.QUALITATIVE_ONLY, GateVerdict.FAIL_CLOSED}
                    )
                    else "fail"
                ),
                "details": (
                    "Mechanism model cards and source-bound parameter/assumption inputs are present."
                    if package.model_cards
                    else "No model cards found."
                ),
            },
            "LLM narrative": {"status": llm_eval["status"], "details": llm_eval["details"]},
            "frontend/read-model auditability": {
                "status": frontend_status,
                "details": frontend_detail,
            },
        }

        if not all_tags and package.assumption_cards:
            taxonomy["economic reasoning"] = {
                "status": "fail",
                "details": "Assumption cards exist without applicability tags.",
            }
        return taxonomy

    def _build_economic_quality_rubric(
        self,
        *,
        package: PolicyEvidencePackage,
        sufficiency: Any,
        vertical_output: dict[str, Any],
    ) -> dict[str, Any]:
        dimensions: dict[str, dict[str, str]] = {}
        mechanism_type = str(vertical_output.get("mechanism_type") or "direct")

        graph = vertical_output.get("mechanism_graph") or {}
        nodes = graph.get("nodes") or []
        edges = graph.get("edges") or []
        graph_ok = bool(nodes) and bool(edges) and len(edges) >= 2
        dimensions["mechanism_graph_validity"] = {
            "status": "pass" if graph_ok else "fail",
            "details": (
                f"nodes={len(nodes)} edges={len(edges)}"
                if graph_ok
                else "Mechanism graph is missing nodes/edges required for causal traceability."
            ),
        }

        resolved_cards = [card for card in package.parameter_cards if card.state.value == "resolved"]
        economic_resolved_cards: list[Any] = []
        diagnostic_resolved_cards: list[Any] = []
        for card in resolved_cards:
            is_economic, _ = self._is_economically_meaningful_parameter(card=card)
            if is_economic:
                economic_resolved_cards.append(card)
            else:
                diagnostic_resolved_cards.append(card)
        parameter_provenance_ok = bool(economic_resolved_cards) and all(
            card.source_url is not None and bool(card.source_excerpt) and bool(card.evidence_card_id)
            for card in economic_resolved_cards
        )
        dimensions["parameter_provenance"] = {
            "status": "pass" if parameter_provenance_ok else "fail",
            "details": (
                (
                    f"economic_resolved_parameters={len(economic_resolved_cards)} "
                    f"(diagnostic_excluded={len(diagnostic_resolved_cards)}) with source-bound provenance."
                )
                if parameter_provenance_ok
                else (
                    "No economically meaningful resolved parameters with source-bound provenance; "
                    f"diagnostic_resolved_parameters_excluded={len(diagnostic_resolved_cards)}."
                )
            ),
        }

        assumption_usage = {item.assumption_id: item for item in package.assumption_usage}
        assumptions_ok = True
        assumption_detail = "No assumption cards required by this package."
        if package.assumption_cards:
            assumptions_ok = all(
                bool(card.applicability_tags)
                and card.source_url is not None
                and assumption_usage.get(card.id) is not None
                and bool(assumption_usage[card.id].applicable)
                and not bool(assumption_usage[card.id].stale)
                for card in package.assumption_cards
            )
            assumption_detail = (
                "Assumption cards include applicability tags, provenance, and non-stale usage records."
                if assumptions_ok
                else "Assumption governance incomplete: missing applicability/provenance/usage validity."
            )
            if assumptions_ok and mechanism_type == "indirect":
                indirect_assumptions = [
                    card
                    for card in package.assumption_cards
                    if card.family
                    in {
                        MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
                        MechanismFamily.ADOPTION_TAKE_UP,
                    }
                ]
                assumptions_ok = bool(indirect_assumptions) and all(
                    not self._looks_placeholder_assumption_text(card.source_excerpt)
                    for card in indirect_assumptions
                )
                if not assumptions_ok:
                    assumption_detail = (
                        "Indirect mechanism requires source-bound pass-through/incidence assumptions; "
                        "placeholder assumptions are not admissible."
                    )
        dimensions["assumption_governance"] = {
            "status": "pass" if assumptions_ok else "fail",
            "details": assumption_detail,
        }

        direct_fee_model_card = vertical_output.get("direct_fee_model_card") or {}
        direct_fee_model_ready = (
            mechanism_type == "direct" and direct_fee_model_card.get("status") == "pass"
        )
        quant_models = [model for model in package.model_cards if model.quantification_eligible]
        arithmetic_ok = bool(quant_models) and all(
            model.arithmetic_valid and model.unit_validation_status.value == "valid"
            for model in quant_models
        )
        if arithmetic_ok:
            for model in quant_models:
                if model.scenario_bounds is None:
                    arithmetic_ok = False
                    break
                bounds = model.scenario_bounds
                if not (bounds.conservative <= bounds.central <= bounds.aggressive):
                    arithmetic_ok = False
                    break
        if not arithmetic_ok and direct_fee_model_ready:
            totals = (
                direct_fee_model_card.get("arithmetic", {})
                .get("total_direct_fee_usd", {})
            )
            arithmetic_ok = (
                isinstance(totals, dict)
                and all(isinstance(totals.get(k), (int, float)) for k in ("low", "base", "high"))
                and totals["low"] <= totals["base"] <= totals["high"]
            )
        dimensions["arithmetic_integrity"] = {
            "status": "pass" if arithmetic_ok else "fail",
            "details": (
                (
                    "Direct fee model-card arithmetic is valid with ordered sensitivity range."
                    if direct_fee_model_ready
                    else "Quantified model arithmetic/unit checks are valid with ordered scenario bounds."
                )
                if arithmetic_ok
                else "Quantified model cards are missing arithmetic/unit validity or ordered scenario bounds."
            ),
        }

        sensitivity = vertical_output.get("sensitivity_range")
        notes = vertical_output.get("uncertainty_notes") or []
        sensitivity_ok = (
            isinstance(sensitivity, dict)
            and all(k in sensitivity for k in ("low", "base", "high"))
            and sensitivity["low"] <= sensitivity["base"] <= sensitivity["high"]
            and len(notes) >= 2
        )
        dimensions["uncertainty_sensitivity"] = {
            "status": "pass" if sensitivity_ok else "fail",
            "details": (
                "Sensitivity range is ordered and uncertainty notes are present."
                if sensitivity_ok
                else "Missing/invalid sensitivity range or uncertainty notes."
            ),
        }

        unsupported = vertical_output.get("unsupported_claim_rejection") or {}
        unsupported_count = int(package.gate_report.unsupported_claim_count or 0)
        unsupported_ok = (
            unsupported.get("status") == "rejected"
            if unsupported_count > 0
            else unsupported.get("status") == "none"
        )
        dimensions["unsupported_claim_rejection"] = {
            "status": "pass" if unsupported_ok else "fail",
            "details": (
                "Unsupported quantified claims are fail-closed."
                if unsupported_ok
                else "Unsupported-claim governance is inconsistent with gate evidence."
            ),
        }

        conclusion = str(vertical_output.get("user_facing_conclusion") or "").strip()
        expected_phrase = (
            "source-bound and auditable"
            if vertical_output.get("quantified")
            else "not quantified-ready"
        )
        conclusion_ok = bool(conclusion) and expected_phrase in conclusion.lower()
        dimensions["user_facing_conclusion_quality"] = {
            "status": "pass" if conclusion_ok else "fail",
            "details": (
                "Conclusion is explicit, bounded, and consistent with quantification eligibility."
                if conclusion_ok
                else "Conclusion is missing or does not clearly state bounded decision quality."
            ),
        }

        failing_dimensions = [
            name for name, result in dimensions.items() if result["status"] != "pass"
        ]
        verdict = (
            "decision_grade"
            if (
                not failing_dimensions
                and sufficiency.readiness_level == PackageReadinessLevel.ECONOMIC_HANDOFF_READY
            )
            else "not_decision_grade"
        )
        return {
            "verdict": verdict,
            "dimensions": dimensions,
            "failing_dimensions": failing_dimensions,
        }

    @classmethod
    def _looks_placeholder_assumption_text(cls, source_excerpt: str | None) -> bool:
        excerpt = str(source_excerpt or "").strip().lower()
        if not excerpt:
            return True
        for pattern in ASSUMPTION_PLACEHOLDER_PATTERNS:
            if re.search(pattern, excerpt):
                return True
        return False

    @classmethod
    def _is_economically_meaningful_parameter(cls, *, card: Any) -> tuple[bool, str]:
        name = str(getattr(card, "parameter_name", "") or "").strip().lower()
        unit = str(getattr(card, "unit", "") or "").strip().lower()
        excerpt = str(getattr(card, "source_excerpt", "") or "").strip().lower()
        value = getattr(card, "value", None)

        if value is None:
            return False, "missing_numeric_value"
        if not name:
            return False, "missing_parameter_name"
        if any(token in name for token in DIAGNOSTIC_PARAMETER_NAME_HINTS):
            if not any(token in name for token in ECONOMIC_PARAMETER_NAME_HINTS):
                return False, "diagnostic_name_pattern"
        if unit in {"id", "identifier"}:
            return False, "diagnostic_unit_identifier"
        has_economic_name_hint = any(token in name for token in ECONOMIC_PARAMETER_NAME_HINTS)
        has_economic_unit_hint = any(token in unit for token in ECONOMIC_PARAMETER_UNIT_HINTS)
        has_economic_excerpt_hint = any(
            token in excerpt for token in ("cost", "fee", "tax", "rent", "price", "income", "benefit", "burden")
        )
        has_economic_signal = has_economic_name_hint or has_economic_unit_hint or has_economic_excerpt_hint
        if "structured fact" in excerpt and "resolved from source payload" in excerpt and not has_economic_signal:
            return False, "diagnostic_structured_fact_excerpt"
        if unit == "count" and not (has_economic_name_hint or has_economic_excerpt_hint):
            return False, "non_economic_count_metric"
        if not has_economic_signal:
            return False, "missing_economic_semantic_signal"
        return True, "economically_meaningful"

    @classmethod
    def _extract_parameter_metadata(cls, *, card: Any) -> dict[str, Any]:
        name = str(getattr(card, "parameter_name", "") or "").strip().lower()
        excerpt = str(getattr(card, "source_excerpt", "") or "").strip().lower()
        time_horizon = getattr(card, "time_horizon", None)
        category = next((hint for hint in FEE_CATEGORY_HINTS if hint in name or hint in excerpt), None)

        effective_date = None
        date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", excerpt)
        if date_match:
            effective_date = date_match.group(1)

        payment_timing = next(
            (pattern for pattern in PAYMENT_TIMING_PATTERNS if pattern in excerpt),
            None,
        )
        return {
            "category": category,
            "effective_date": effective_date,
            "payment_timing": payment_timing,
            "time_horizon": time_horizon,
        }

    def _build_fixture_case_coverage(self) -> dict[str, Any]:
        bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
        required = {
            "direct_cost_case": "direct",
            "indirect_pass_through_case": "indirect",
            "secondary_research_required_case": "secondary_research",
        }
        coverage: list[dict[str, Any]] = []
        for case_id, case_type in required.items():
            matched = next((case for case in bundle["cases"] if case["case_id"] == case_id), None)
            if matched is None:
                coverage.append(
                    {
                        "case_id": case_id,
                        "case_type": case_type,
                        "status": "missing",
                        "details": "Required fixture case not found.",
                    }
                )
                continue
            package = matched.get("primary_package") or {}
            has_parameters = bool(package.get("parameter_cards"))
            has_gate_report = bool(package.get("gate_report"))
            has_projection = bool(package.get("gate_projection"))
            plausible = bool(matched.get("quantification_plausible"))
            status = (
                "pass"
                if has_parameters and has_gate_report and has_projection and plausible
                else "fail"
            )
            details = (
                "Fixture contains source-bound parameters, gates, and quantification plausibility."
                if status == "pass"
                else "Fixture is missing source-bound parameterization/gate metadata."
            )
            coverage.append(
                {
                    "case_id": case_id,
                    "case_type": case_type,
                    "status": status,
                    "details": details,
                }
            )
        return {
            "required_case_count": len(required),
            "covered_case_count": sum(1 for item in coverage if item["status"] == "pass"),
            "cases": coverage,
        }

    @staticmethod
    def _build_missing_evidence(
        *,
        taxonomy: dict[str, dict[str, str]],
        economic_quality: dict[str, Any],
        readiness_level: str,
        blocking_gate: str | None,
    ) -> list[str]:
        missing: list[str] = []
        for bucket in QUALITY_BUCKETS:
            bucket_result = taxonomy.get(bucket, {})
            if bucket_result.get("status") != "pass":
                details = str(bucket_result.get("details") or "no details")
                missing.append(f"{bucket}: {details}")
        for dimension in ECONOMIC_QUALITY_DIMENSIONS:
            dimension_result = economic_quality.get("dimensions", {}).get(dimension, {})
            if dimension_result.get("status") != "pass":
                details = str(dimension_result.get("details") or "no details")
                missing.append(f"rubric/{dimension}: {details}")
        if readiness_level != PackageReadinessLevel.ECONOMIC_HANDOFF_READY.value:
            reason = (
                f"blocking_gate={blocking_gate}"
                if blocking_gate
                else f"readiness_level={readiness_level}"
            )
            missing.append(f"sufficiency_readiness: {reason}")
        # Preserve stable ordering while deduplicating.
        seen: set[str] = set()
        deduped: list[str] = []
        for item in missing:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    @staticmethod
    def _evaluate_storage_readback_proof(
        *,
        runtime_evidence: dict[str, Any],
        storage_result: Any,
    ) -> dict[str, str]:
        readback_status = str(storage_result.artifact_readback_status or "unknown")
        if readback_status != "proven":
            return {
                "status": "fail",
                "details": f"artifact_readback_status={readback_status}",
                "proof_mode": "storage_service",
                "direct_probe_available": False,
            }

        storage_proof = runtime_evidence.get("storage_proof")
        if not isinstance(storage_proof, dict) or not storage_proof:
            return {
                "status": "not_proven",
                "details": (
                    "Deterministic in-memory readback is proven, but non-memory "
                    "Postgres/MinIO storage proof is not provided."
                ),
                "proof_mode": "in_memory",
                "direct_probe_available": False,
            }

        proof_status = str(storage_proof.get("proof_status") or "not_proven")
        proof_mode = str(storage_proof.get("proof_mode") or "unknown")
        store_backend = str(storage_proof.get("store_backend") or "unknown")
        artifact_backend = str(storage_proof.get("artifact_probe_backend") or "unknown")
        blocker = str(storage_proof.get("blocker") or "storage_proof_missing")
        record_id = str(storage_proof.get("persisted_record_id") or "").strip()
        minio_readback = bool(storage_proof.get("minio_readback_proven"))
        direct_probe_available = bool(storage_proof.get("direct_probe_available"))
        non_memory_backend = store_backend not in {"in_memory", "unknown"}
        non_memory_probe = artifact_backend not in {"in_memory", "unknown"}

        if proof_status == "fail":
            return {
                "status": "fail",
                "details": f"Storage proof failed: {blocker}.",
                "proof_mode": proof_mode,
                "direct_probe_available": direct_probe_available,
            }

        if (
            proof_status == "pass"
            and non_memory_backend
            and non_memory_probe
            and record_id
            and minio_readback
        ):
            return {
                "status": "pass",
                "details": (
                    "Backend storage-service proof present with persisted row id and MinIO "
                    f"readback (mode={proof_mode}, record_id={record_id}, "
                    f"direct_probe_available={str(direct_probe_available).lower()})."
                ),
                "proof_mode": proof_mode,
                "direct_probe_available": direct_probe_available,
            }

        return {
            "status": "not_proven",
            "details": (
                "Readback exists but non-memory storage proof is incomplete "
                f"(mode={proof_mode}, blocker={blocker})."
            ),
            "proof_mode": proof_mode,
            "direct_probe_available": direct_probe_available,
        }

    @staticmethod
    def _evaluate_scraped_search_proof(
        *,
        package: PolicyEvidencePackage,
        matrix_payload: dict[str, Any],
    ) -> dict[str, str]:
        if not package.scraped_sources:
            return {"status": "fail", "details": "No scraped provenance found."}

        runtime_evidence = PolicyEvidenceQualitySpineEconomicsService._extract_runtime_evidence(
            matrix_payload
        )
        package_payload = runtime_evidence.get("vertical_package_payload")
        source_identity_status: dict[str, Any] = {}
        if isinstance(package_payload, dict):
            source_identity_status = (
                PolicyEvidenceQualitySpineEconomicsService._derive_source_identity_status(
                    source_quality_metrics=PolicyEvidenceQualitySpineEconomicsService._extract_source_quality_metrics(
                        selected_payload=package_payload
                    ),
                    source_reconciliation=PolicyEvidenceQualitySpineEconomicsService._extract_source_reconciliation(
                        selected_payload=package_payload
                    ),
                )
            )
        identity_blocker_code = str(
            source_identity_status.get("identity_blocker_code") or ""
        ).strip()
        identity_blocker_reason = str(
            source_identity_status.get("identity_blocker_reason") or ""
        ).strip()
        if identity_blocker_code:
            return {
                "status": "fail",
                "details": identity_blocker_reason
                or f"Selected scraped source failed source identity gate ({identity_blocker_code}).",
            }

        rows = matrix_payload.get("rows")
        if not isinstance(rows, list) or not rows:
            return {
                "status": "not_proven",
                "details": (
                    "Scraped provenance exists, but no selected-artifact provider-quality "
                    "metrics were provided."
                ),
            }

        selected_metrics = None
        for row in rows:
            if not isinstance(row, dict):
                continue
            selected_candidate = row.get("selected_candidate")
            provider_results = row.get("provider_results")
            if not isinstance(selected_candidate, dict) or not isinstance(provider_results, dict):
                continue

            selected_url = str(selected_candidate.get("url") or "").strip()
            selected_provider = str(selected_candidate.get("provider") or "").strip()
            selected_rank = selected_candidate.get("rank")
            selection_reason = str(selected_candidate.get("selection_reason") or "").strip()
            if not selected_url or not selected_provider:
                continue

            provider_entry = provider_results.get(selected_provider)
            if selected_provider == "tavily":
                provider_entry = provider_entry or provider_results.get("tavily_fallback")
            if not isinstance(provider_entry, dict):
                selected_metrics = {
                    "status": "not_proven",
                    "details": (
                        f"Selected provider={selected_provider} is missing provider_results entry."
                    ),
                }
                continue

            provider_status = str(provider_entry.get("status") or "")
            reason_code = str(provider_entry.get("reason_code") or "")
            candidates = provider_entry.get("candidates")
            artifact_grade = False
            official_domain = False
            if isinstance(candidates, list):
                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue
                    same_url = str(candidate.get("url") or "").strip() == selected_url
                    same_rank = selected_rank is not None and candidate.get("rank") == selected_rank
                    if same_url or same_rank:
                        artifact_grade = bool(candidate.get("artifact_grade"))
                        official_domain = bool(candidate.get("official_domain"))
                        break

            if artifact_grade and official_domain:
                return {
                    "status": "pass",
                    "details": (
                        "Selected artifact has provider-quality support "
                        f"(provider={selected_provider}, status={provider_status or 'unknown'}, "
                        f"reason={reason_code or selection_reason or 'none'})."
                    ),
                }

            low_quality_reason = (
                f"artifact_grade={artifact_grade}, official_domain={official_domain}, "
                f"provider={selected_provider}, status={provider_status or 'unknown'}"
            )
            selected_metrics = {
                "status": "fail" if artifact_grade is False else "not_proven",
                "details": (
                    "Selected candidate did not meet artifact-quality threshold "
                    f"({low_quality_reason})."
                ),
            }

        if selected_metrics is not None:
            return selected_metrics

        return {
            "status": "not_proven",
            "details": (
                "Scraped provenance exists, but selected-artifact provider-quality metrics "
                "are missing for the evaluated package."
            ),
        }

    @staticmethod
    def _extract_runtime_evidence(payload: dict[str, Any]) -> dict[str, Any]:
        runtime = payload.get("agent_a_runtime_evidence")
        if isinstance(runtime, dict):
            return runtime
        return {}

    @staticmethod
    def _evaluate_orchestration_proof(runtime_evidence: dict[str, Any]) -> dict[str, str]:
        proof = runtime_evidence.get("orchestration_proof")
        if not isinstance(proof, dict):
            proof = {}
        if not proof:
            package_payload = runtime_evidence.get("vertical_package_payload")
            run_context = {}
            if isinstance(package_payload, dict):
                candidate = package_payload.get("run_context")
                if isinstance(candidate, dict):
                    run_context = candidate
            context_run_id = run_context.get("windmill_run_id")
            context_scope_job_id = run_context.get("windmill_job_id")
            context_platform_job_id = (
                run_context.get("windmill_platform_job_id")
                or run_context.get("windmill_job_id_platform")
            )
            if context_run_id or context_scope_job_id or context_platform_job_id:
                proof = {
                    "proof_status": "not_proven",
                    "proof_mode": "package_run_context",
                    "linked_to_current_vertical_package": True,
                    "windmill_run_id": context_run_id,
                    "windmill_job_id": context_scope_job_id,
                    "windmill_platform_job_id": context_platform_job_id,
                    "source": "vertical_package_payload.run_context",
                    "blocker": None,
                }
            else:
                return {
                    "status": "not_proven",
                    "details": "No orchestration proof payload found in runtime evidence.",
                }

        proof_status = str(proof.get("proof_status") or "not_proven")
        proof_mode = str(proof.get("proof_mode") or "unknown")
        linked = bool(proof.get("linked_to_current_vertical_package"))
        blocker = proof.get("blocker")
        run_id = proof.get("windmill_run_id")
        scope_job_id = proof.get("windmill_job_id")
        platform_job_id = proof.get("windmill_platform_job_id")
        has_run_id = bool(isinstance(run_id, str) and run_id.strip())
        has_scope_job_id = bool(isinstance(scope_job_id, str) and scope_job_id.strip())
        has_platform_job_id = bool(
            isinstance(platform_job_id, str) and str(platform_job_id).strip()
        )
        has_any_job_id = has_scope_job_id or has_platform_job_id

        if proof_mode == "historical_stub_flow_proof":
            details = (
                "Historical Windmill stub proof exists but is not valid for current vertical package."
                if not linked
                else "Historical Windmill stub proof is linked but does not count as current-run proof."
            )
            return {"status": "not_proven", "details": details}

        if linked and has_run_id and has_any_job_id and proof_status in {"pass", "not_proven"}:
            if has_platform_job_id:
                return {
                    "status": "pass",
                    "details": (
                        "Current-run Windmill ids present "
                        f"(run_id={run_id}, platform_job_id={platform_job_id})."
                    ),
                }
            if has_scope_job_id:
                return {
                    "status": "pass",
                    "details": (
                        "Current-run Windmill run id present with backend scope job id only "
                        f"(run_id={run_id}, scope_job_id={scope_job_id})."
                    ),
                }

        if proof_status == "pass" and linked and has_run_id and has_any_job_id:
            return {
                "status": "pass",
                "details": (
                    "Current-run Windmill ids present "
                    f"(run_id={run_id}, job_id={platform_job_id or scope_job_id})."
                ),
            }

        blocker_text = str(blocker or "windmill_current_run_proof_missing")
        if proof_status == "blocked":
            return {
                "status": "not_proven",
                "details": f"Windmill proof blocked: {blocker_text}.",
            }
        return {
            "status": "not_proven",
            "details": f"Windmill proof not proven for current run ({blocker_text}).",
        }

    @staticmethod
    def _evaluate_llm_narrative_proof(
        *,
        package: PolicyEvidencePackage,
        runtime_evidence: dict[str, Any],
        matrix_source_mode: str,
    ) -> dict[str, str]:
        proof = runtime_evidence.get("llm_narrative_proof")
        if not isinstance(proof, dict):
            proof = {
                "proof_status": "not_proven",
                "blocker": "canonical_llm_run_id_missing",
                "source": "quality_spine_deterministic_lane",
                "canonical_pipeline_run_id": package.gate_projection.canonical_pipeline_run_id,
                "canonical_pipeline_step_id": package.gate_projection.canonical_pipeline_step_id,
            }

        proof_run_id = proof.get("canonical_pipeline_run_id")
        proof_step_id = proof.get("canonical_pipeline_step_id")
        run_id = proof_run_id or package.gate_projection.canonical_pipeline_run_id
        step_id = proof_step_id or package.gate_projection.canonical_pipeline_step_id
        source = str(proof.get("source") or "quality_spine_deterministic_lane")
        blocker = str(proof.get("blocker") or "canonical_llm_run_id_missing")
        proof_status = str(proof.get("proof_status") or "not_proven")
        analysis_step_executed = bool(proof.get("analysis_step_executed"))
        analysis_payload_present = bool(proof.get("analysis_payload_present"))
        proof_matches_package_projection = bool(
            proof_run_id
            and proof_step_id
            and package.gate_projection.canonical_pipeline_run_id
            and proof_run_id == package.gate_projection.canonical_pipeline_run_id
            and proof_step_id == package.gate_projection.canonical_pipeline_step_id
        )

        if matrix_source_mode != "fallback_fixture" and (
            (proof_status == "pass" and run_id) or proof_matches_package_projection
        ):
            return {
                "status": "pass",
                "details": (
                    "Canonical LLM narrative run evidence present "
                    f"(run_id={run_id}, step_id={step_id or 'none'}, source={source})."
                ),
            }
        if (
            blocker == "analysis_step_succeeded_but_no_canonical_analysis_history"
            or analysis_step_executed
            or analysis_payload_present
        ):
            return {
                "status": "not_proven",
                "details": (
                    "LLM analysis step appears to have succeeded, but canonical analysis history "
                    f"is missing (blocker={blocker}; source={source})."
                ),
            }
        return {
            "status": "not_proven",
            "details": f"LLM narrative not proven ({blocker}; source={source}).",
        }

    def _build_vertical_economic_output(
        self, *, package: PolicyEvidencePackage, sufficiency: Any
    ) -> dict[str, Any]:
        parameter_table: list[dict[str, Any]] = []
        diagnostic_parameter_table: list[dict[str, Any]] = []
        for card in package.parameter_cards:
            if card.state.value != "resolved":
                continue
            parameter_payload = {
                "parameter_id": card.id,
                "name": card.parameter_name,
                "value": card.value,
                "unit": card.unit,
                "source_url": None if card.source_url is None else str(card.source_url),
                "source_excerpt": card.source_excerpt,
                "evidence_card_id": card.evidence_card_id,
                "metadata": self._extract_parameter_metadata(card=card),
            }
            is_economic, reason = self._is_economically_meaningful_parameter(card=card)
            if is_economic:
                parameter_table.append(parameter_payload)
                continue
            diagnostic_parameter_table.append(
                {
                    **parameter_payload,
                    "excluded_from_economic_support": True,
                    "exclusion_reason": reason,
                }
            )
        mechanism_family = package.model_cards[0].mechanism_family if package.model_cards else None
        mechanism_type = self._classify_mechanism_type(package=package, mechanism_family=mechanism_family)
        direct_fee_model_card = self._build_direct_fee_model_card(
            package=package,
            parameter_table=parameter_table,
            mechanism_type=mechanism_type,
        )

        graph_nodes = [
            {"id": "policy_change", "label": package.policy_identifier},
            {"id": "economic_mechanism", "label": mechanism_family.value if mechanism_family else "unknown"},
            {"id": "household_cost_of_living", "label": "Household cost-of-living"},
        ]
        graph_edges = [
            {"from": "policy_change", "to": "economic_mechanism", "evidence_refs": [item.id for item in package.evidence_cards]},
            {"from": "economic_mechanism", "to": "household_cost_of_living", "evidence_refs": [item["parameter_id"] for item in parameter_table]},
        ]

        scenario = None
        quant_models = [model for model in package.model_cards if model.quantification_eligible]
        if quant_models:
            bounds = quant_models[0].scenario_bounds
            if bounds is not None:
                scenario = {
                    "low": bounds.conservative,
                    "base": bounds.central,
                    "high": bounds.aggressive,
                    "unit": "usd_per_household_per_year",
                }

        unsupported = {
            "status": "none",
            "reason": None,
        }
        if package.gate_report.unsupported_claim_count > 0 or package.gate_report.verdict in {
            GateVerdict.FAIL_CLOSED,
            GateVerdict.QUALITATIVE_ONLY_DUE_TO_UNSUPPORTED_CLAIMS,
            GateVerdict.FAIL_CLOSED_QUALITATIVE_ONLY,
        }:
            unsupported = {
                "status": "rejected",
                "reason": (
                    "Unsupported quantitative claim blocked by gate_report verdict "
                    f"{package.gate_report.verdict.value}."
                ),
            }

        quantified = (
            sufficiency.readiness_level == PackageReadinessLevel.ECONOMIC_HANDOFF_READY
            and scenario is not None
        )
        conclusion = (
            "Package is quantified-ready for canonical economic analysis handoff; "
            "the low/base/high range is source-bound and auditable."
            if quantified
            else "Package is not quantified-ready; output should remain qualitative or fail-closed."
        )

        return {
            "package_id": package.package_id,
            "mechanism_type": mechanism_type,
            "mechanism_graph": {"nodes": graph_nodes, "edges": graph_edges},
            "direct_indirect_classification": mechanism_type,
            "parameter_table": parameter_table,
            "diagnostic_parameter_table": diagnostic_parameter_table,
            "direct_fee_model_card": direct_fee_model_card,
            "source_bound_assumptions": [
                {
                    "assumption_id": card.id,
                    "family": card.family.value,
                    "low": card.low,
                    "central": card.central,
                    "high": card.high,
                    "unit": card.unit,
                    "source_url": str(card.source_url),
                    "applicability_tags": card.applicability_tags,
                    "stale_after_days": card.stale_after_days,
                }
                for card in package.assumption_cards
            ],
            "sensitivity_range": scenario,
            "uncertainty_notes": [
                "Range depends on parameter resolution quality and evidence recency.",
                "Assumption transferability must remain within applicability tags.",
            ],
            "unsupported_claim_rejection": unsupported,
            "quantified": quantified,
            "user_facing_conclusion": conclusion,
            "sufficiency_state": package.gate_projection.runtime_sufficiency_state.value,
            "sufficiency_readiness_level": sufficiency.readiness_level.value,
        }

    @staticmethod
    def _classify_mechanism_type(
        *, package: PolicyEvidencePackage, mechanism_family: MechanismFamily | None
    ) -> str:
        if mechanism_family in {
            MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
            MechanismFamily.ADOPTION_TAKE_UP,
        }:
            return "indirect"
        if mechanism_family in {MechanismFamily.DIRECT_FISCAL, MechanismFamily.COMPLIANCE_COST}:
            return "direct"
        for assumption in package.assumption_cards:
            if assumption.family in {
                MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
                MechanismFamily.ADOPTION_TAKE_UP,
            }:
                return "indirect"
        for parameter in package.parameter_cards:
            name = str(parameter.parameter_name or "").lower()
            if any(token in name for token in ("pass_through", "incidence", "take_up", "adoption")):
                return "indirect"
        return "direct"

    def _build_direct_fee_model_card(
        self,
        *,
        package: PolicyEvidencePackage,
        parameter_table: list[dict[str, Any]],
        mechanism_type: str,
    ) -> dict[str, Any]:
        if mechanism_type != "direct":
            return {
                "status": "not_applicable",
                "reason": "mechanism_type is not direct",
            }

        sqft_parameters = [
            row
            for row in parameter_table
            if str(row.get("unit") or "").strip().lower() in SQFT_UNIT_ALIASES
            and isinstance(row.get("value"), (int, float))
        ]
        if not sqft_parameters:
            return {
                "status": "not_proven",
                "reason": "no source-bound direct fee/tax parameters with sqft units",
            }

        scenario_bounds = {"low": 75000.0, "base": 100000.0, "high": 125000.0}
        scenario_assumptions = {
            "project_size_source": "defaulted_for_model_card",
            "project_size_unit": "sqft",
            "bounds": scenario_bounds,
            "note": (
                "Project size not supplied by package run context; "
                "used deterministic conservative/base/aggressive defaults."
            ),
        }
        rate_values = [float(row["value"]) for row in sqft_parameters]
        min_rate = min(rate_values)
        max_rate = max(rate_values)
        avg_rate = sum(rate_values) / len(rate_values)
        total_low = scenario_bounds["low"] * min_rate
        total_base = scenario_bounds["base"] * avg_rate
        total_high = scenario_bounds["high"] * max_rate
        per_parameter_base = [
            {
                "parameter_id": row["parameter_id"],
                "name": row["name"],
                "rate_per_sqft": float(row["value"]),
                "project_size_sqft": scenario_bounds["base"],
                "estimated_direct_fee_usd": scenario_bounds["base"] * float(row["value"]),
                "unit": "usd",
                "source_url": row.get("source_url"),
                "evidence_card_id": row.get("evidence_card_id"),
            }
            for row in sqft_parameters
        ]
        source_refs = [
            {
                "parameter_id": row["parameter_id"],
                "source_url": row.get("source_url"),
                "source_excerpt": row.get("source_excerpt"),
                "evidence_card_id": row.get("evidence_card_id"),
            }
            for row in sqft_parameters
        ]

        has_pass_through_assumption = any(
            card.family
            in {MechanismFamily.FEE_OR_TAX_PASS_THROUGH, MechanismFamily.ADOPTION_TAKE_UP}
            and not self._looks_placeholder_assumption_text(card.source_excerpt)
            for card in package.assumption_cards
        )
        household_readiness = {
            "status": "not_proven" if not has_pass_through_assumption else "pass",
            "reason": (
                "household cost-of-living incidence is not decision-grade without "
                "source-bound pass-through/incidence assumptions"
                if not has_pass_through_assumption
                else "source-bound pass-through/incidence assumptions present"
            ),
        }

        return {
            "status": "pass",
            "reason": "source-bound per-square-foot fee parameters available for direct model card",
            "scope": "direct_developer_fee",
            "formula": "direct_fee_usd = project_size_sqft * fee_rate_usd_per_sqft",
            "inputs": {
                "project_size_sqft": scenario_bounds,
                "fee_rate_usd_per_sqft": {
                    "low": min_rate,
                    "base": avg_rate,
                    "high": max_rate,
                },
            },
            "assumptions": scenario_assumptions,
            "arithmetic": {
                "per_parameter_base_project": per_parameter_base,
                "total_direct_fee_usd": {
                    "low": total_low,
                    "base": total_base,
                    "high": total_high,
                },
                "units": {
                    "project_size": "sqft",
                    "rate": "usd_per_sqft",
                    "output": "usd",
                },
            },
            "sensitivity_range": {
                "low": total_low,
                "base": total_base,
                "high": total_high,
                "reason": "multiple rate rows and bounded project-size assumptions",
            },
            "source_refs": source_refs,
            "household_impact_readiness": household_readiness,
        }

    def _build_read_model_output(
        self,
        *,
        package: PolicyEvidencePackage,
        sufficiency: Any,
        vertical_output: dict[str, Any],
        taxonomy: dict[str, dict[str, str]],
        economic_quality: dict[str, Any],
    ) -> dict[str, Any]:
        blocking_gate = None if sufficiency.blocking_gate is None else sufficiency.blocking_gate.value
        frontend_payload = {
            "package_id": package.package_id,
            "canonical_document_key": package.canonical_document_key,
            "jurisdiction": package.jurisdiction,
            "policy_identifier": package.policy_identifier,
            "sufficiency_readiness_level": sufficiency.readiness_level.value,
            "blocking_gate": blocking_gate,
            "taxonomy": taxonomy,
            "economic_quality_rubric": economic_quality,
            "user_facing_conclusion": vertical_output["user_facing_conclusion"],
            "unsupported_claim_rejection": vertical_output["unsupported_claim_rejection"],
            "requires_recomputation": False,
        }
        admin_payload = {
            "pipeline_status": {
                "runtime_sufficiency_state": package.gate_projection.runtime_sufficiency_state.value,
                "economic_handoff_ready": package.economic_handoff_ready,
                "canonical_pipeline_run_id": package.gate_projection.canonical_pipeline_run_id,
                "canonical_pipeline_step_id": package.gate_projection.canonical_pipeline_step_id,
            },
            "storage_refs": [ref.model_dump(mode="json") for ref in package.storage_refs],
            "evidence_card_ids": [card.id for card in package.evidence_cards],
            "parameter_card_ids": [card.id for card in package.parameter_cards],
            "assumption_card_ids": [card.id for card in package.assumption_cards],
            "model_card_ids": [card.id for card in package.model_cards],
            "requires_recomputation": False,
        }
        return {
            "frontend_contract": frontend_payload,
            "admin_contract": admin_payload,
            "analysis_handoff": {
                "adapter_mode": "policy_package_projection_into_canonical_analysis",
                "canonical_engine": "AnalysisPipeline + LegislationResearchService",
                "parallel_engine_created": False,
                "llm_narrative_proof": {
                    "proof_status": (
                        "pass" if taxonomy["LLM narrative"]["status"] == "pass" else "not_proven"
                    ),
                    "canonical_pipeline_run_id": package.gate_projection.canonical_pipeline_run_id,
                    "canonical_pipeline_step_id": package.gate_projection.canonical_pipeline_step_id,
                    "blocker": (
                        None
                        if taxonomy["LLM narrative"]["status"] == "pass"
                        else "canonical_llm_run_id_missing_or_not_executed"
                    ),
                    "source": "policy_evidence_quality_spine_economics",
                },
            },
        }

    def _build_retry_ledger(self, *, scorecard: dict[str, Any], max_cycles: int) -> dict[str, Any]:
        failed = scorecard["failure_classification"]["failed_categories"]
        not_proven = scorecard["failure_classification"]["not_proven_categories"]
        proposed_tweaks = self._proposed_tweaks(failed=failed, not_proven=not_proven)
        matrix_attempt = scorecard.get("matrix_attempt", {})
        current_round = int(matrix_attempt.get("retry_round") or 0)
        current_tweak = str(matrix_attempt.get("targeted_tweak") or "baseline_no_tweak")
        current_round = max(0, min(current_round, max_cycles - 1))
        known_attempts = {
            0: {
                "attempt_id": "baseline",
                "result_verdict": "fail",
                "failed_categories": ["economic reasoning"],
                "not_proven_categories": ["Windmill/orchestration", "LLM narrative"],
                "tweaks_applied": [],
                "result_note": "Initial integrated run lacked source-bound model cards on the vertical package.",
            },
            1: {
                "attempt_id": "retry_1",
                "result_verdict": "partial",
                "failed_categories": [],
                "not_proven_categories": ["Windmill/orchestration", "LLM narrative"],
                "tweaks_applied": ["source_bound_model_card_projection"],
                "result_note": "Source-bound model card projection cleared the economic reasoning failure.",
            },
            2: {
                "attempt_id": "retry_2",
                "result_verdict": "partial",
                "failed_categories": [],
                "not_proven_categories": ["Windmill/orchestration", "LLM narrative"],
                "tweaks_applied": ["windmill_orchestration_evidence_capture"],
                "result_note": "Historical Windmill stub proof captured but not counted as current-run proof.",
            },
        }
        attempts = []
        for index in range(0, max_cycles):
            attempt_id = "baseline" if index == 0 else f"retry_{index}"
            if index < current_round:
                known = known_attempts.get(index)
                if known is not None:
                    attempts.append(
                        {
                            **known,
                            "status": "completed_superseded",
                            "score_delta": None,
                        }
                    )
                    continue
                attempts.append(
                    {
                        "attempt_id": attempt_id,
                        "status": "completed_superseded",
                        "result_verdict": None,
                        "failed_categories": [],
                        "not_proven_categories": [],
                        "tweaks_applied": [],
                        "result_note": "Historical cycle metadata unavailable in deterministic ledger.",
                        "score_delta": None,
                    }
                )
                continue
            if index == current_round:
                attempts.append(
                    {
                        "attempt_id": attempt_id,
                        "status": "completed",
                        "result_verdict": scorecard["overall_verdict"],
                        "failed_categories": failed,
                        "not_proven_categories": not_proven,
                        "tweaks_applied": [] if index == 0 else [current_tweak],
                        "result_note": (
                            "Strict proof fields captured; storage/Windmill/LLM remain not_proven until live current-run proof is present."
                            if not_proven
                            else None
                        ),
                        "score_delta": {
                            "before_score": matrix_attempt.get("before_score"),
                            "after_score": matrix_attempt.get("after_score"),
                        },
                    }
                )
                continue
            attempts.append(
                {
                    "attempt_id": attempt_id,
                    "status": "not_executed",
                    "result_verdict": None,
                    "failed_categories": [],
                    "not_proven_categories": [],
                    "tweaks_applied": proposed_tweaks,
                    "result_note": None,
                    "score_delta": None,
                }
            )
        return {
            "feature_key": "bd-3wefe.13",
            "max_retry_rounds": max_cycles,
            "attempts": attempts,
            "retry_policy": {
                "diagnosis_source": "quality_spine_scorecard.taxonomy",
                "allowed_tweaks_only": True,
                "strategic_hitl_required_for_boundary_changes": True,
            },
        }

    @staticmethod
    def _matrix_attempt_metadata(payload: dict[str, Any]) -> dict[str, Any]:
        metadata = payload.get("attempt_metadata")
        if isinstance(metadata, dict):
            return dict(metadata)
        return {
            "attempt_id": "baseline",
            "retry_round": 0,
            "targeted_tweak": "baseline_no_tweak",
        }

    @staticmethod
    def _previous_failure_for_tweak(tweak: str) -> list[str]:
        if tweak == "source_bound_model_card_projection":
            return ["economic reasoning"]
        if tweak == "windmill_orchestration_evidence_capture":
            return []
        return []

    @staticmethod
    def _proposed_tweaks(*, failed: list[str], not_proven: list[str]) -> list[str]:
        mapping = {
            "scraped/search": "Adjust query-family templates and ranker boosts for artifact URLs.",
            "reader": "Tighten portal skip + reader substance floor before package admission.",
            "structured-source": "Attach at least one additional structured-source provenance row.",
            "identity/dedupe": "Normalize canonical_document_key and enforce dedupe on policy identifier.",
            "storage/read-back": "Repair MinIO probe/readback and content-hash linkage.",
            "Windmill/orchestration": "Capture windmill job/run identifiers in matrix artifact.",
            "sufficiency gate": "Address blocking gate with source-bound parameter/assumption evidence.",
            "economic reasoning": "Add source-bound model card or assumption applicability evidence.",
            "LLM narrative": "Run canonical analysis narrative step and record run ids.",
            "frontend/read-model auditability": "Add admin/frontend payload refs for display-only rendering.",
        }
        ordered = failed + [item for item in not_proven if item not in failed]
        return [mapping[item] for item in ordered if item in mapping]

    @staticmethod
    def _overall_verdict(*, category_failures: list[str], category_not_proven: list[str]) -> str:
        if category_failures:
            return "fail"
        if category_not_proven:
            return "partial"
        return "pass"
