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
                "status": storage_proof_eval["status"],
                "details": storage_proof_eval["details"],
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
            }

        storage_proof = runtime_evidence.get("storage_proof")
        if not isinstance(storage_proof, dict) or not storage_proof:
            return {
                "status": "not_proven",
                "details": (
                    "Deterministic in-memory readback is proven, but non-memory "
                    "Postgres/MinIO storage proof is not provided."
                ),
            }

        proof_status = str(storage_proof.get("proof_status") or "not_proven")
        proof_mode = str(storage_proof.get("proof_mode") or "unknown")
        store_backend = str(storage_proof.get("store_backend") or "unknown")
        artifact_backend = str(storage_proof.get("artifact_probe_backend") or "unknown")
        blocker = str(storage_proof.get("blocker") or "storage_proof_missing")
        record_id = str(storage_proof.get("persisted_record_id") or "").strip()
        minio_readback = bool(storage_proof.get("minio_readback_proven"))
        non_memory_backend = store_backend not in {"in_memory", "unknown"}
        non_memory_probe = artifact_backend not in {"in_memory", "unknown"}

        if proof_status == "fail":
            return {
                "status": "fail",
                "details": f"Storage proof failed: {blocker}.",
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
                    "Non-memory storage proof present with persisted row id and MinIO readback "
                    f"(mode={proof_mode}, record_id={record_id})."
                ),
            }

        return {
            "status": "not_proven",
            "details": (
                "Readback exists but non-memory storage proof is incomplete "
                f"(mode={proof_mode}, blocker={blocker})."
            ),
        }

    @staticmethod
    def _evaluate_scraped_search_proof(
        *,
        package: PolicyEvidencePackage,
        matrix_payload: dict[str, Any],
    ) -> dict[str, str]:
        if not package.scraped_sources:
            return {"status": "fail", "details": "No scraped provenance found."}

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
            return {
                "status": "not_proven",
                "details": "No orchestration proof payload found in runtime evidence.",
            }

        proof_status = str(proof.get("proof_status") or "not_proven")
        proof_mode = str(proof.get("proof_mode") or "unknown")
        linked = bool(proof.get("linked_to_current_vertical_package"))
        blocker = proof.get("blocker")
        run_id = proof.get("windmill_run_id")
        job_id = proof.get("windmill_job_id")
        has_live_ids = bool(isinstance(run_id, str) and run_id.strip()) and bool(
            isinstance(job_id, str) and job_id.strip()
        )

        if proof_mode == "historical_stub_flow_proof":
            details = (
                "Historical Windmill stub proof exists but is not valid for current vertical package."
                if not linked
                else "Historical Windmill stub proof is linked but does not count as current-run proof."
            )
            return {"status": "not_proven", "details": details}

        if proof_status == "pass" and linked and has_live_ids:
            return {
                "status": "pass",
                "details": f"Current-run Windmill ids present (run_id={run_id}, job_id={job_id}).",
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

        run_id = proof.get("canonical_pipeline_run_id") or package.gate_projection.canonical_pipeline_run_id
        step_id = proof.get("canonical_pipeline_step_id") or package.gate_projection.canonical_pipeline_step_id
        source = str(proof.get("source") or "quality_spine_deterministic_lane")
        blocker = str(proof.get("blocker") or "canonical_llm_run_id_missing")
        proof_status = str(proof.get("proof_status") or "not_proven")

        if matrix_source_mode != "fallback_fixture" and proof_status == "pass" and run_id:
            return {
                "status": "pass",
                "details": (
                    "Canonical LLM narrative run evidence present "
                    f"(run_id={run_id}, step_id={step_id or 'none'}, source={source})."
                ),
            }
        return {
            "status": "not_proven",
            "details": f"LLM narrative not proven ({blocker}; source={source}).",
        }

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

    def _build_retry_ledger(self, *, scorecard: dict[str, Any]) -> dict[str, Any]:
        failed = scorecard["failure_classification"]["failed_categories"]
        not_proven = scorecard["failure_classification"]["not_proven_categories"]
        proposed_tweaks = self._proposed_tweaks(failed=failed, not_proven=not_proven)
        matrix_attempt = scorecard.get("matrix_attempt", {})
        current_round = int(matrix_attempt.get("retry_round") or 0)
        current_tweak = str(matrix_attempt.get("targeted_tweak") or "baseline_no_tweak")
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
        for index in range(0, min(current_round, 3)):
            known = known_attempts[index]
            attempts.append(
                {
                    **known,
                    "status": "completed_superseded",
                    "score_delta": None,
                }
            )
        if current_round == 0:
            attempts.append(
                {
                    "attempt_id": "baseline",
                    "status": "completed",
                    "result_verdict": scorecard["overall_verdict"],
                    "failed_categories": failed,
                    "not_proven_categories": not_proven,
                    "tweaks_applied": [],
                    "result_note": None,
                    "score_delta": {
                        "before_score": matrix_attempt.get("before_score"),
                        "after_score": matrix_attempt.get("after_score"),
                    },
                }
            )
        for index in range(1, 6):
            executed = index == current_round
            if index < current_round and index in known_attempts:
                continue
            attempts.append(
                {
                    "attempt_id": f"retry_{index}",
                    "status": "completed" if executed else "not_executed",
                    "result_verdict": scorecard["overall_verdict"] if executed else None,
                    "failed_categories": failed if executed else [],
                    "not_proven_categories": not_proven if executed else [],
                    "tweaks_applied": [current_tweak] if executed else proposed_tweaks,
                    "result_note": (
                        "Strict proof fields captured; storage/Windmill/LLM remain not_proven until live current-run proof is present."
                        if executed and not_proven
                        else None
                    ),
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
