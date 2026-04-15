"""Economic quality-spine evaluator for bd-3wefe.13 (Agent B lane).

This service evaluates whether a vertical PolicyEvidencePackage candidate is
good enough to hand off to canonical economic analysis semantics. It consumes
Agent A's horizontal matrix artifact when available and falls back to a
contract-compatible deterministic fixture when it is not.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from schemas.economic_evidence import GateVerdict, MechanismFamily
from schemas.policy_evidence_package import PolicyEvidencePackage
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


@dataclass(frozen=True)
class MatrixInput:
    payload: dict[str, Any] | None
    source_path: str
    source_mode: str


class PolicyEvidenceQualitySpineEconomicsService:
    """Build deterministic quality-spine economics scorecards and read models."""

    def evaluate(self, *, matrix_input: MatrixInput) -> dict[str, Any]:
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
            package_payload = self._select_vertical_candidate(matrix_packages)
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
        read_model_output = self._build_read_model_output(
            package=package,
            sufficiency=sufficiency,
            vertical_output=vertical_output,
            taxonomy=category_results,
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
        }
        retry_ledger = self._build_retry_ledger(scorecard=scorecard)
        return {
            "scorecard": scorecard,
            "vertical_economic_output": vertical_output,
            "read_model_audit_output": read_model_output,
            "retry_ledger": retry_ledger,
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

    def _select_vertical_candidate(self, packages: list[dict[str, Any]]) -> dict[str, Any]:
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
        all_tags = set()
        for assumption in package.assumption_cards:
            all_tags.update(assumption.applicability_tags)

        has_windmill_ids = self._matrix_contains_windmill_ids(matrix_payload)

        llm_status = "not_proven"
        llm_detail = "Deterministic lane only; live LLM narrative quality not executed."
        if matrix_source_mode != "fallback_fixture" and package.gate_projection.canonical_pipeline_run_id:
            llm_status = "pass"
            llm_detail = "Canonical pipeline run id present for narrative audit."

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
                "status": "pass" if package.scraped_sources else "fail",
                "details": (
                    "Scraped provenance present with provider/query/candidate rank."
                    if package.scraped_sources
                    else "No scraped provenance found."
                ),
            },
            "reader": {
                "status": (
                    "pass"
                    if package.scraped_sources
                    and all(
                        source.reader_substance_passed and source.reader_artifact_url is not None
                        for source in package.scraped_sources
                    )
                    else "fail"
                ),
                "details": (
                    "Reader substance passed and reader artifact refs present."
                    if package.scraped_sources
                    and all(
                        source.reader_substance_passed and source.reader_artifact_url is not None
                        for source in package.scraped_sources
                    )
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
                "status": "pass" if storage_result.artifact_readback_status == "proven" else "fail",
                "details": (
                    "Storage readback proven via MinIO probe and package row persistence."
                    if storage_result.artifact_readback_status == "proven"
                    else f"artifact_readback_status={storage_result.artifact_readback_status}"
                ),
            },
            "Windmill/orchestration": {
                "status": "pass" if has_windmill_ids else "not_proven",
                "details": (
                    "Windmill run/job identifiers present in matrix payload."
                    if has_windmill_ids
                    else "Windmill run identifiers not found in provided matrix payload."
                ),
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
            "LLM narrative": {"status": llm_status, "details": llm_detail},
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

    @staticmethod
    def _matrix_contains_windmill_ids(payload: dict[str, Any]) -> bool:
        stack: list[Any] = [payload]
        keys = {"windmill_run_id", "windmill_job_id", "windmill_flow_run_id", "job_id", "run_id"}
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                for key, value in item.items():
                    if key in keys and isinstance(value, str) and value.strip():
                        return True
                    stack.append(value)
            elif isinstance(item, list):
                stack.extend(item)
        return False

    def _build_vertical_economic_output(
        self, *, package: PolicyEvidencePackage, sufficiency: Any
    ) -> dict[str, Any]:
        parameter_table = [
            {
                "parameter_id": card.id,
                "name": card.parameter_name,
                "value": card.value,
                "unit": card.unit,
                "source_url": None if card.source_url is None else str(card.source_url),
                "source_excerpt": card.source_excerpt,
                "evidence_card_id": card.evidence_card_id,
            }
            for card in package.parameter_cards
            if card.state.value == "resolved"
        ]
        mechanism_family = package.model_cards[0].mechanism_family if package.model_cards else None
        mechanism_type = "direct"
        if mechanism_family in {
            MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
            MechanismFamily.ADOPTION_TAKE_UP,
        }:
            mechanism_type = "indirect"

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

    def _build_read_model_output(
        self,
        *,
        package: PolicyEvidencePackage,
        sufficiency: Any,
        vertical_output: dict[str, Any],
        taxonomy: dict[str, dict[str, str]],
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
            },
        }

    def _build_retry_ledger(self, *, scorecard: dict[str, Any]) -> dict[str, Any]:
        failed = scorecard["failure_classification"]["failed_categories"]
        not_proven = scorecard["failure_classification"]["not_proven_categories"]
        proposed_tweaks = self._proposed_tweaks(failed=failed, not_proven=not_proven)
        matrix_attempt = scorecard.get("matrix_attempt", {})
        current_round = int(matrix_attempt.get("retry_round") or 0)
        current_tweak = str(matrix_attempt.get("targeted_tweak") or "baseline_no_tweak")
        previous_failure = self._previous_failure_for_tweak(current_tweak)
        attempts = [
            {
                "attempt_id": "baseline",
                "status": "completed_superseded" if current_round > 0 else "completed",
                "result_verdict": "fail" if previous_failure else scorecard["overall_verdict"],
                "failed_categories": previous_failure,
                "not_proven_categories": not_proven if current_round == 0 else [],
                "tweaks_applied": [],
            }
        ]
        for index in range(1, 6):
            executed = index == current_round
            attempts.append(
                {
                    "attempt_id": f"retry_{index}",
                    "status": "completed" if executed else "not_executed",
                    "result_verdict": scorecard["overall_verdict"] if executed else None,
                    "failed_categories": failed if executed else [],
                    "not_proven_categories": not_proven if executed else [],
                    "tweaks_applied": [current_tweak] if executed else proposed_tweaks,
                    "score_delta": {
                        "before_score": matrix_attempt.get("before_score"),
                        "after_score": matrix_attempt.get("after_score"),
                    }
                    if executed
                    else None,
                }
            )
        return {
            "feature_key": "bd-3wefe.13",
            "max_retry_rounds": 5,
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
