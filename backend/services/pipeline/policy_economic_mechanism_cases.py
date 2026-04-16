"""Deterministic economic mechanism case generator for bd-3wefe.6.

This module generates auditable POC cases that consume PolicyEvidencePackage
contracts without calling live search/read/LLM systems.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from schemas.analysis import (
    FailureCode,
    ScenarioBounds,
    SourceHierarchyStatus,
    SourceTier,
    SufficiencyState,
)
from schemas.economic_evidence import (
    AssumptionCard,
    EvidenceCard,
    EvidenceSourceType,
    GateReport,
    GateStageResult,
    GateVerdict,
    MechanismFamily,
    ModelCard,
    ParameterCard,
    ParameterState,
    QualityGateStage,
    UnitValidationStatus,
)
from schemas.policy_evidence_package import (
    AssumptionUsageStatus,
    FreshnessStatus,
    GateProjection,
    PackageFailureReason,
    PolicyEvidencePackage,
    ScrapedSourceProvenance,
    SearchProvider,
    SourceLane,
    StorageRef,
    StorageSystem,
    StorageTruthRole,
    StructuredSourceProvenance,
)


class PolicyEconomicMechanismCaseService:
    """Generate deterministic mechanism test cases for package-to-analysis handoff."""

    def build_case_bundle(self) -> dict[str, Any]:
        direct = self._build_direct_case()
        indirect = self._build_indirect_case()
        secondary = self._build_secondary_case()
        control = self._build_unsupported_control_case()
        cases = [direct, indirect, secondary, control]
        return {
            "feature_key": "bd-3wefe.6",
            "generated_at": "2026-04-15T00:00:00+00:00",
            "report_version": "2026-04-15.policy-economic-mechanism-cases.v1",
            "cases": cases,
            "architecture_readiness": self._build_readiness_summary(cases),
            "sufficiency_integration_hook": {
                "status": "pending_parallel_worker",
                "expected_input": "case-level package_id + sufficiency_target_state + blocking_reasons",
                "expected_consumer": "bd-3wefe.5 package sufficiency verifier",
            },
        }

    def _build_readiness_summary(self, cases: list[dict[str, Any]]) -> dict[str, Any]:
        direct_ready = self._case_by_id(cases, "direct_cost_case")["quantification_plausible"]
        indirect_ready = self._case_by_id(cases, "indirect_pass_through_case")["quantification_plausible"]
        secondary_ready = self._case_by_id(cases, "secondary_research_required_case")["quantification_plausible"]
        control_blocked = self._case_by_id(cases, "unsupported_fail_closed_control")[
            "unsupported_claim_rejection"
        ]
        return {
            "can_represent_direct_quant_inputs": bool(direct_ready),
            "can_represent_indirect_quant_inputs": bool(indirect_ready),
            "can_represent_secondary_package_handoff": bool(secondary_ready),
            "unsupported_claims_fail_closed": bool(control_blocked),
            "note": (
                "POC confirms representational readiness for direct/indirect/secondary "
                "inputs with explicit fail-closed controls; it does not claim production "
                "LLM narrative quality."
            ),
        }

    @staticmethod
    def _case_by_id(cases: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
        for case in cases:
            if case["case_id"] == case_id:
                return case
        raise RuntimeError(f"missing case_id={case_id}")

    def _build_direct_case(self) -> dict[str, Any]:
        evidence = self._evidence_card(
            card_id="ev-direct-1",
            url="https://records.sanjoseca.gov/agenda/parking-standard-update",
            excerpt=(
                "Staff fiscal impact memo estimates additional per-unit construction "
                "cost from one required parking space."
            ),
            source_type=EvidenceSourceType.STAFF_REPORT,
        )
        parameter_cost = self._resolved_parameter(
            parameter_id="param-direct-cost",
            name="parking_space_cost_per_unit",
            value=45000.0,
            unit="usd_per_unit",
            url=str(evidence.source_url),
            excerpt="Estimated incremental structured parking build cost per dwelling unit.",
            evidence_card_id=evidence.id,
        )
        parameter_units = self._resolved_parameter(
            parameter_id="param-direct-units",
            name="new_units_subject_to_rule",
            value=1200.0,
            unit="units_per_year",
            url=str(evidence.source_url),
            excerpt="Annual housing production expected under current permitting pipeline.",
            evidence_card_id=evidence.id,
        )
        model = ModelCard(
            id="model-direct-1",
            mechanism_family=MechanismFamily.COMPLIANCE_COST,
            formula_id="direct_compliance_cost_per_household.v1",
            input_parameter_ids=[parameter_cost.id, parameter_units.id],
            assumption_ids=[],
            scenario_bounds=ScenarioBounds(
                conservative=1800.0,
                central=2400.0,
                aggressive=3100.0,
            ),
            arithmetic_valid=True,
            unit_validation_status=UnitValidationStatus.VALID,
            quantification_eligible=True,
        )
        package = self._package(
            package_id="pkg-direct-cost-001",
            jurisdiction="san_jose_ca",
            policy_identifier="SJ-PARKING-REQ-POC",
            source_lanes=[SourceLane.SCRAPED, SourceLane.STRUCTURED],
            evidence_cards=[evidence],
            parameter_cards=[parameter_cost, parameter_units],
            assumption_cards=[],
            assumption_usage=[],
            model_cards=[model],
            gate_report=self._passing_gate_report(
                case_id="direct_cost_case",
                provider="private_searxng",
            ),
            gate_projection=self._quantified_projection(),
            insufficiency_reasons=[],
            economic_handoff_ready=True,
            scraped_query_text="san jose parking requirement residential development cost burden",
            scraped_selected_candidate_url=str(evidence.source_url),
            scraped_reader_artifact_url=(
                "https://minio.local/artifacts/pkg-direct-cost-001/reader-output.txt"
            ),
        )
        return {
            "case_id": "direct_cost_case",
            "case_type": "direct",
            "quantification_plausible": True,
            "primary_package": package.model_dump(mode="json"),
            "secondary_package": None,
            "mechanism_graph": {
                "nodes": [
                    "required_parking_space_per_unit",
                    "incremental_construction_cost",
                    "developer_unit_cost",
                    "sale_or_rent_price_pressure",
                    "household_cost_of_living",
                ],
                "edges": [
                    {
                        "from": "required_parking_space_per_unit",
                        "to": "incremental_construction_cost",
                        "evidence_refs": [evidence.id],
                    },
                    {
                        "from": "incremental_construction_cost",
                        "to": "developer_unit_cost",
                        "evidence_refs": [parameter_cost.id],
                    },
                    {
                        "from": "developer_unit_cost",
                        "to": "sale_or_rent_price_pressure",
                        "evidence_refs": [model.id],
                    },
                    {
                        "from": "sale_or_rent_price_pressure",
                        "to": "household_cost_of_living",
                        "evidence_refs": [model.id],
                    },
                ],
            },
            "parameter_table": self._parameter_rows([parameter_cost, parameter_units]),
            "source_bound_evidence_refs": [self._evidence_ref(evidence)],
            "assumption_cards": [],
            "scenario_range": self._scenario_payload(model.scenario_bounds, "usd_per_household_per_year"),
            "uncertainty_notes": [
                "Cost variability across parcel geometry and parking type.",
                "Transmission to household prices depends on local supply constraints.",
            ],
            "unsupported_claim_rejection": None,
            "deterministic_conclusion": (
                "[Deterministic POC] Direct compliance-cost inputs are sufficient to "
                "construct low/base/high household burden ranges without adding "
                "unsupported external facts."
            ),
            "sufficiency_hook": {
                "case_package_ids": [package.package_id],
                "expected_state": SufficiencyState.QUANTIFIED.value,
                "blocking_reasons": [],
            },
        }

    def _build_indirect_case(self) -> dict[str, Any]:
        evidence = self._evidence_card(
            card_id="ev-indirect-1",
            url="https://records.sanjoseca.gov/agenda/development-impact-fee",
            excerpt="Agenda packet records proposed multifamily fee increase schedule.",
            source_type=EvidenceSourceType.AGENDA_PACKET,
        )
        fee_parameter = self._resolved_parameter(
            parameter_id="param-fee-delta",
            name="fee_increase_per_unit",
            value=12000.0,
            unit="usd_per_unit",
            url=str(evidence.source_url),
            excerpt="Proposed fee delta for newly permitted multifamily housing units.",
            evidence_card_id=evidence.id,
        )
        pass_through_assumption = AssumptionCard(
            id="assump-pass-through-housing-v1",
            family=MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
            low=0.50,
            central=0.68,
            high=0.89,
            unit="share",
            source_url="https://www.philadelphiafed.org/-/media/frbp/assets/consumer-finance/discussion-papers/dp24-01.pdf",
            source_excerpt=(
                "Property tax and fee burdens are partially transmitted to renter prices, "
                "with market-dependent variation."
            ),
            applicability_tags=["housing", "rental_market", "local_tax_or_fee"],
            external_validity_notes=(
                "Applicable to rental incidence contexts; avoid non-housing or owner-only markets."
            ),
            confidence=0.76,
            version="2026-04-14",
            stale_after_days=365,
        )
        model = ModelCard(
            id="model-indirect-1",
            mechanism_family=MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
            formula_id="fee_pass_through_to_rent.v1",
            input_parameter_ids=[fee_parameter.id],
            assumption_ids=[pass_through_assumption.id],
            scenario_bounds=ScenarioBounds(
                conservative=420.0,
                central=570.0,
                aggressive=740.0,
            ),
            arithmetic_valid=True,
            unit_validation_status=UnitValidationStatus.VALID,
            quantification_eligible=True,
        )
        package = self._package(
            package_id="pkg-indirect-pass-through-001",
            jurisdiction="san_jose_ca",
            policy_identifier="SJ-FEE-PASS-THROUGH-POC",
            source_lanes=[SourceLane.SCRAPED, SourceLane.STRUCTURED],
            evidence_cards=[evidence],
            parameter_cards=[fee_parameter],
            assumption_cards=[pass_through_assumption],
            assumption_usage=[
                AssumptionUsageStatus(
                    assumption_id=pass_through_assumption.id,
                    used_for_quantitative_claim=True,
                    applicable=True,
                    stale=False,
                )
            ],
            model_cards=[model],
            gate_report=self._passing_gate_report(
                case_id="indirect_pass_through_case",
                provider="private_searxng",
            ),
            gate_projection=self._quantified_projection(),
            insufficiency_reasons=[],
            economic_handoff_ready=True,
            scraped_query_text="san jose multifamily fee increase rent pass-through",
            scraped_selected_candidate_url=str(evidence.source_url),
            scraped_reader_artifact_url=(
                "https://minio.local/artifacts/pkg-indirect-pass-through-001/reader-output.txt"
            ),
        )
        return {
            "case_id": "indirect_pass_through_case",
            "case_type": "indirect",
            "quantification_plausible": True,
            "primary_package": package.model_dump(mode="json"),
            "secondary_package": None,
            "mechanism_graph": {
                "nodes": [
                    "development_fee_increase",
                    "project_total_cost",
                    "pass_through_share_to_rents",
                    "monthly_rent_change",
                    "household_cost_of_living",
                ],
                "edges": [
                    {
                        "from": "development_fee_increase",
                        "to": "project_total_cost",
                        "evidence_refs": [fee_parameter.id],
                    },
                    {
                        "from": "project_total_cost",
                        "to": "pass_through_share_to_rents",
                        "evidence_refs": [pass_through_assumption.id],
                    },
                    {
                        "from": "pass_through_share_to_rents",
                        "to": "monthly_rent_change",
                        "evidence_refs": [model.id],
                    },
                    {
                        "from": "monthly_rent_change",
                        "to": "household_cost_of_living",
                        "evidence_refs": [model.id],
                    },
                ],
            },
            "parameter_table": self._parameter_rows([fee_parameter]),
            "source_bound_evidence_refs": [self._evidence_ref(evidence)],
            "assumption_cards": [pass_through_assumption.model_dump(mode="json")],
            "scenario_range": self._scenario_payload(model.scenario_bounds, "usd_per_household_per_year"),
            "uncertainty_notes": [
                "Pass-through differs by housing submarket tightness and lease turnover.",
                "Observed effects can lag fee adoption due to development cycle delays.",
            ],
            "unsupported_claim_rejection": None,
            "deterministic_conclusion": (
                "[Deterministic POC] Indirect pass-through can be quantified only when a "
                "source-bound assumption card is present and applicability-constrained."
            ),
            "sufficiency_hook": {
                "case_package_ids": [package.package_id],
                "expected_state": SufficiencyState.QUANTIFIED.value,
                "blocking_reasons": [],
            },
        }

    def _build_secondary_case(self) -> dict[str, Any]:
        primary_evidence = self._evidence_card(
            card_id="ev-secondary-primary-1",
            url="https://records.sanjoseca.gov/agenda/transit-assistance-program",
            excerpt="Policy text introduces a means-tested transit subsidy but no expected take-up range.",
            source_type=EvidenceSourceType.ORDINANCE_TEXT,
        )
        primary_parameter = ParameterCard(
            id="param-takeup-missing",
            parameter_name="expected_take_up_rate",
            state=ParameterState.MISSING,
            ambiguity_reason="Program enrollment response is not quantified in primary artifacts.",
        )
        primary_package = self._package(
            package_id="pkg-secondary-primary-001",
            jurisdiction="san_jose_ca",
            policy_identifier="SJ-TRANSIT-SUBSIDY-POC",
            source_lanes=[SourceLane.STRUCTURED],
            evidence_cards=[primary_evidence],
            parameter_cards=[primary_parameter],
            assumption_cards=[],
            assumption_usage=[],
            model_cards=[],
            gate_report=GateReport(
                case_id="secondary_research_required_case",
                provider="legistar",
                verdict=GateVerdict.QUALITATIVE_ONLY_DUE_TO_UNSUPPORTED_CLAIMS,
                stage_results=[
                    GateStageResult(stage=QualityGateStage.PARAMETERIZATION, passed=False, failure_codes=[FailureCode.PARAMETER_MISSING]),
                    GateStageResult(stage=QualityGateStage.ASSUMPTION_SELECTION, passed=False, failure_codes=[FailureCode.PARAMETER_UNVERIFIABLE]),
                ],
                blocking_gate=QualityGateStage.PARAMETERIZATION,
                failure_codes=[FailureCode.PARAMETER_MISSING, FailureCode.PARAMETER_UNVERIFIABLE],
                unsupported_claim_count=1,
            ),
            gate_projection=GateProjection(
                runtime_sufficiency_state=SufficiencyState.QUALITATIVE_ONLY,
                runtime_insufficiency_reason="Secondary research package required for take-up rate.",
                runtime_failure_codes=[FailureCode.PARAMETER_MISSING, FailureCode.PARAMETER_UNVERIFIABLE],
            ),
            insufficiency_reasons=[
                PackageFailureReason.BLOCKING_GATE_PRESENT,
                PackageFailureReason.NO_QUANT_SUPPORT_PATH,
            ],
            economic_handoff_ready=False,
        )

        secondary_evidence = self._evidence_card(
            card_id="ev-secondary-research-1",
            url="https://www.urban.org/urban-wire/automatic-enrollment-discounted-transit-fare-programs-can-support-higher-participation",
            excerpt=(
                "Enrollment friction reduces participation; automatic enrollment policies "
                "increase take-up materially in means-tested transport programs."
            ),
            source_type=EvidenceSourceType.ACADEMIC_LITERATURE,
            source_tier=SourceTier.TIER_B,
        )
        take_up_assumption = AssumptionCard(
            id="assump-adoption-takeup-v1",
            family=MechanismFamily.ADOPTION_TAKE_UP,
            low=0.30,
            central=0.45,
            high=0.65,
            unit="share",
            source_url=str(secondary_evidence.source_url),
            source_excerpt=secondary_evidence.excerpt,
            applicability_tags=["means_tested_program", "enrollment_friction", "household_benefit"],
            external_validity_notes="Secondary package applies to subsidy enrollment contexts with non-automatic uptake.",
            confidence=0.67,
            version="2026-04-14",
            stale_after_days=365,
        )
        take_up_parameter = self._resolved_parameter(
            parameter_id="param-secondary-takeup",
            name="estimated_take_up_rate",
            value=0.45,
            unit="share",
            url=str(secondary_evidence.source_url),
            excerpt="Central take-up estimate from secondary literature package.",
            evidence_card_id=secondary_evidence.id,
        )
        model = ModelCard(
            id="model-secondary-1",
            mechanism_family=MechanismFamily.ADOPTION_TAKE_UP,
            formula_id="benefit_takeup_net_household_effect.v1",
            input_parameter_ids=[take_up_parameter.id],
            assumption_ids=[take_up_assumption.id],
            scenario_bounds=ScenarioBounds(
                conservative=95.0,
                central=160.0,
                aggressive=240.0,
            ),
            arithmetic_valid=True,
            unit_validation_status=UnitValidationStatus.VALID,
            quantification_eligible=True,
        )
        secondary_package = self._package(
            package_id="pkg-secondary-research-001",
            jurisdiction="san_jose_ca",
            policy_identifier="SJ-TRANSIT-SUBSIDY-POC:SECONDARY",
            source_lanes=[SourceLane.SCRAPED],
            evidence_cards=[secondary_evidence],
            parameter_cards=[take_up_parameter],
            assumption_cards=[take_up_assumption],
            assumption_usage=[
                AssumptionUsageStatus(
                    assumption_id=take_up_assumption.id,
                    used_for_quantitative_claim=True,
                    applicable=True,
                    stale=False,
                )
            ],
            model_cards=[model],
            gate_report=self._passing_gate_report(
                case_id="secondary_research_required_case:secondary",
                provider="tavily",
            ),
            gate_projection=self._quantified_projection(),
            insufficiency_reasons=[],
            economic_handoff_ready=True,
            search_provider=SearchProvider.TAVILY,
            scraped_query_family="secondary_research_probe",
            scraped_query_text="means tested transit subsidy enrollment take-up elasticity evidence",
            scraped_selected_candidate_url=str(secondary_evidence.source_url),
            scraped_reader_artifact_url=(
                "https://minio.local/artifacts/pkg-secondary-research-001/reader-output.txt"
            ),
        )
        return {
            "case_id": "secondary_research_required_case",
            "case_type": "secondary_research",
            "quantification_plausible": True,
            "primary_package": primary_package.model_dump(mode="json"),
            "secondary_package": secondary_package.model_dump(mode="json"),
            "mechanism_graph": {
                "nodes": [
                    "subsidy_policy",
                    "eligible_households",
                    "take_up_rate",
                    "effective_household_benefit",
                    "household_cost_of_living",
                ],
                "edges": [
                    {
                        "from": "subsidy_policy",
                        "to": "eligible_households",
                        "evidence_refs": [primary_evidence.id],
                    },
                    {
                        "from": "eligible_households",
                        "to": "take_up_rate",
                        "evidence_refs": [take_up_assumption.id],
                    },
                    {
                        "from": "take_up_rate",
                        "to": "effective_household_benefit",
                        "evidence_refs": [take_up_parameter.id],
                    },
                    {
                        "from": "effective_household_benefit",
                        "to": "household_cost_of_living",
                        "evidence_refs": [model.id],
                    },
                ],
            },
            "parameter_table": self._parameter_rows([take_up_parameter]),
            "source_bound_evidence_refs": [
                self._evidence_ref(primary_evidence),
                self._evidence_ref(secondary_evidence),
            ],
            "assumption_cards": [take_up_assumption.model_dump(mode="json")],
            "scenario_range": self._scenario_payload(model.scenario_bounds, "usd_per_household_per_month"),
            "uncertainty_notes": [
                "Take-up remains sensitive to enrollment design and outreach.",
                "Observed household savings may vary by transit usage baseline.",
            ],
            "unsupported_claim_rejection": None,
            "deterministic_conclusion": (
                "[Deterministic POC] Primary package alone remains qualitative-only; "
                "a separate secondary-research package can restore quantified eligibility "
                "with explicit provenance."
            ),
            "sufficiency_hook": {
                "case_package_ids": [primary_package.package_id, secondary_package.package_id],
                "expected_state": SufficiencyState.QUANTIFIED.value,
                "blocking_reasons": ["primary_missing_take_up_parameter"],
            },
        }

    def _build_unsupported_control_case(self) -> dict[str, Any]:
        evidence = self._evidence_card(
            card_id="ev-control-1",
            url="https://records.sanjoseca.gov/agenda/study-session-overview",
            excerpt="Agenda header mentions discussion topic but provides no fiscal or incidence estimates.",
            source_type=EvidenceSourceType.MINUTES,
            source_tier=SourceTier.TIER_C,
        )
        unsupported_parameter = ParameterCard(
            id="param-control-unsupported",
            parameter_name="consumer_price_change",
            state=ParameterState.UNSUPPORTED,
            ambiguity_reason="No source-bound quantitative evidence supports this claim.",
        )
        package = self._package(
            package_id="pkg-unsupported-control-001",
            jurisdiction="san_jose_ca",
            policy_identifier="SJ-CONTROL-UNSUPPORTED-POC",
            source_lanes=[SourceLane.SCRAPED],
            evidence_cards=[evidence],
            parameter_cards=[unsupported_parameter],
            assumption_cards=[],
            assumption_usage=[],
            model_cards=[],
            gate_report=GateReport(
                case_id="unsupported_fail_closed_control",
                provider="private_searxng",
                verdict=GateVerdict.FAIL_CLOSED,
                stage_results=[
                    GateStageResult(
                        stage=QualityGateStage.EVIDENCE_EXTRACTION,
                        passed=False,
                        failure_codes=[FailureCode.EXCERPT_VALIDATION_FAILED],
                    ),
                    GateStageResult(
                        stage=QualityGateStage.PARAMETERIZATION,
                        passed=False,
                        failure_codes=[FailureCode.PARAMETER_UNVERIFIABLE],
                    ),
                ],
                blocking_gate=QualityGateStage.PARAMETERIZATION,
                failure_codes=[FailureCode.EXCERPT_VALIDATION_FAILED, FailureCode.PARAMETER_UNVERIFIABLE],
                unsupported_claim_count=1,
            ),
            gate_projection=GateProjection(
                runtime_sufficiency_state=SufficiencyState.INSUFFICIENT_EVIDENCE,
                runtime_insufficiency_reason="Unsupported quantitative claim rejected by deterministic gates.",
                runtime_failure_codes=[FailureCode.PARAMETER_UNVERIFIABLE],
            ),
            insufficiency_reasons=[
                PackageFailureReason.BLOCKING_GATE_PRESENT,
                PackageFailureReason.NO_QUANT_SUPPORT_PATH,
            ],
            economic_handoff_ready=False,
            scraped_query_text="san jose study session overview household cost claim",
            scraped_selected_candidate_url=str(evidence.source_url),
            scraped_reader_artifact_url=(
                "https://minio.local/artifacts/pkg-unsupported-control-001/reader-output.txt"
            ),
        )
        return {
            "case_id": "unsupported_fail_closed_control",
            "case_type": "fail_closed_control",
            "quantification_plausible": False,
            "primary_package": package.model_dump(mode="json"),
            "secondary_package": None,
            "mechanism_graph": {
                "nodes": ["policy_claim", "missing_evidence", "rejected_quantification"],
                "edges": [
                    {
                        "from": "policy_claim",
                        "to": "missing_evidence",
                        "evidence_refs": [evidence.id],
                    },
                    {
                        "from": "missing_evidence",
                        "to": "rejected_quantification",
                        "evidence_refs": [unsupported_parameter.id],
                    },
                ],
            },
            "parameter_table": self._parameter_rows([unsupported_parameter]),
            "source_bound_evidence_refs": [self._evidence_ref(evidence)],
            "assumption_cards": [],
            "scenario_range": None,
            "uncertainty_notes": [
                "Evidence is too weak to support a numeric estimate.",
                "Case intentionally demonstrates unsupported-claim rejection.",
            ],
            "unsupported_claim_rejection": {
                "failure_code": FailureCode.PARAMETER_UNVERIFIABLE.value,
                "reason": (
                    "Quantitative claim rejected because parameterization lacks source-bound "
                    "evidence and no admissible assumption card applies."
                ),
            },
            "deterministic_conclusion": (
                "[Deterministic POC] The architecture correctly fails closed for unsupported "
                "quantitative claims."
            ),
            "sufficiency_hook": {
                "case_package_ids": [package.package_id],
                "expected_state": SufficiencyState.INSUFFICIENT_EVIDENCE.value,
                "blocking_reasons": ["unsupported_quantitative_claim"],
            },
        }

    def _package(
        self,
        *,
        package_id: str,
        jurisdiction: str,
        policy_identifier: str,
        source_lanes: list[SourceLane],
        evidence_cards: list[EvidenceCard],
        parameter_cards: list[ParameterCard],
        assumption_cards: list[AssumptionCard],
        assumption_usage: list[AssumptionUsageStatus],
        model_cards: list[ModelCard],
        gate_report: GateReport,
        gate_projection: GateProjection,
        insufficiency_reasons: list[PackageFailureReason],
        economic_handoff_ready: bool,
        search_provider: SearchProvider = SearchProvider.PRIVATE_SEARXNG,
        scraped_query_family: str = "economic_mechanism_probe",
        scraped_query_text: str | None = None,
        scraped_selected_candidate_url: str | None = None,
        scraped_reader_artifact_url: str | None = None,
        scraped_candidate_rank: int = 1,
    ) -> PolicyEvidencePackage:
        created = datetime(2026, 4, 15, tzinfo=UTC)
        return PolicyEvidencePackage(
            package_id=package_id,
            jurisdiction=jurisdiction,
            canonical_document_key=f"{jurisdiction}::{policy_identifier}",
            policy_identifier=policy_identifier,
            created_at=created,
            source_lanes=source_lanes,
            scraped_sources=(
                [
                    ScrapedSourceProvenance(
                        search_provider=search_provider,
                        provider_run_id=f"run::{package_id}",
                        query_family=scraped_query_family,
                        query_text=(
                            scraped_query_text
                            or f"{jurisdiction} {policy_identifier} cost-of-living mechanism"
                        ),
                        search_snapshot_id=f"snapshot::{package_id}",
                        candidate_rank=scraped_candidate_rank,
                        selected_candidate_url=(
                            scraped_selected_candidate_url
                            or "https://records.sanjoseca.gov/agenda"
                        ),
                        reader_artifact_url=(
                            scraped_reader_artifact_url
                            or f"https://minio.local/artifacts/{package_id}/reader-output.txt"
                        ),
                        reader_substance_passed=True,
                    )
                ]
                if SourceLane.SCRAPED in source_lanes
                else []
            ),
            structured_sources=(
                [
                    StructuredSourceProvenance(
                        source_family="legistar",
                        access_method="rest_api",
                        endpoint_or_file_url="https://records.sanjoseca.gov/api/v1/events/123",
                        provider_run_id=f"run::{package_id}",
                        field_count=6,
                    )
                ]
                if SourceLane.STRUCTURED in source_lanes
                else []
            ),
            evidence_cards=evidence_cards,
            parameter_cards=parameter_cards,
            assumption_cards=assumption_cards,
            assumption_usage=assumption_usage,
            model_cards=model_cards,
            gate_report=gate_report,
            gate_projection=gate_projection,
            storage_refs=[
                StorageRef(
                    storage_system=StorageSystem.POSTGRES,
                    truth_role=StorageTruthRole.SOURCE_OF_TRUTH,
                    reference_id=f"policy_evidence_packages:{package_id}",
                ),
                StorageRef(
                    storage_system=StorageSystem.MINIO,
                    truth_role=StorageTruthRole.ARTIFACT_OF_RECORD,
                    reference_id=f"minio://policy-evidence/packages/{package_id}.json",
                ),
                StorageRef(
                    storage_system=StorageSystem.PGVECTOR,
                    truth_role=StorageTruthRole.DERIVED_INDEX,
                    reference_id=f"chunk:{package_id}",
                ),
            ],
            freshness_status=FreshnessStatus.FRESH,
            insufficiency_reasons=insufficiency_reasons,
            economic_handoff_ready=economic_handoff_ready,
        )

    @staticmethod
    def _passing_gate_report(case_id: str, provider: str) -> GateReport:
        return GateReport(
            case_id=case_id,
            provider=provider,
            verdict=GateVerdict.QUANTIFIED_PASS,
            stage_results=[
                GateStageResult(stage=QualityGateStage.EVIDENCE_CARDS, passed=True),
                GateStageResult(stage=QualityGateStage.PARAMETERIZATION, passed=True),
                GateStageResult(stage=QualityGateStage.ASSUMPTION_SELECTION, passed=True),
                GateStageResult(stage=QualityGateStage.QUANTIFICATION, passed=True),
            ],
            blocking_gate=None,
            failure_codes=[],
            artifact_counts={"evidence_cards": 1},
            unsupported_claim_count=0,
        )

    @staticmethod
    def _quantified_projection() -> GateProjection:
        return GateProjection(
            runtime_sufficiency_state=SufficiencyState.QUANTIFIED,
            runtime_failure_codes=[],
            canonical_breakdown_ref="sufficiency_breakdown::deterministic_poc",
            canonical_pipeline_run_id="pipeline_run::deterministic_poc",
            canonical_pipeline_step_id="pipeline_step::quantification",
        )

    @staticmethod
    def _evidence_card(
        *,
        card_id: str,
        url: str,
        excerpt: str,
        source_type: EvidenceSourceType,
        source_tier: SourceTier = SourceTier.TIER_A,
    ) -> EvidenceCard:
        return EvidenceCard(
            id=card_id,
            source_url=url,
            source_type=source_type,
            content_hash=f"hash-{card_id}-00112233",
            excerpt=excerpt,
            retrieved_at=datetime(2026, 4, 15, tzinfo=UTC),
            source_tier=source_tier,
            provenance_label="deterministic_poc_fixture",
            artifact_id=f"artifact::{card_id}",
            reader_run_id=f"reader::{card_id}",
        )

    @staticmethod
    def _resolved_parameter(
        *,
        parameter_id: str,
        name: str,
        value: float,
        unit: str,
        url: str,
        excerpt: str,
        evidence_card_id: str,
    ) -> ParameterCard:
        return ParameterCard(
            id=parameter_id,
            parameter_name=name,
            state=ParameterState.RESOLVED,
            value=value,
            unit=unit,
            source_url=url,
            source_excerpt=excerpt,
            source_hierarchy_status=SourceHierarchyStatus.FISCAL_OR_REG_IMPACT_ANALYSIS,
            evidence_card_id=evidence_card_id,
        )

    @staticmethod
    def _parameter_rows(cards: list[ParameterCard]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for card in cards:
            rows.append(
                {
                    "parameter_id": card.id,
                    "name": card.parameter_name,
                    "state": card.state.value,
                    "value": card.value,
                    "unit": card.unit,
                    "source_url": str(card.source_url) if card.source_url else None,
                    "source_excerpt": card.source_excerpt,
                    "source_hierarchy_status": card.source_hierarchy_status.value,
                    "evidence_card_id": card.evidence_card_id,
                    "ambiguity_reason": card.ambiguity_reason,
                }
            )
        return rows

    @staticmethod
    def _evidence_ref(card: EvidenceCard) -> dict[str, str]:
        return {
            "evidence_card_id": card.id,
            "source_url": str(card.source_url),
            "provenance_label": card.provenance_label,
        }

    @staticmethod
    def _scenario_payload(bounds: ScenarioBounds | None, unit: str) -> dict[str, Any] | None:
        if bounds is None:
            return None
        return {
            "low": bounds.conservative,
            "base": bounds.central,
            "high": bounds.aggressive,
            "unit": unit,
        }
