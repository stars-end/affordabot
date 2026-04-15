"""Deterministic sufficiency gate over persisted policy evidence packages.

bd-3wefe.5 consumes persisted/read-back storage rows and decides whether a
package is ready for canonical economic analysis handoff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pydantic import ValidationError

from schemas.analysis import SourceHierarchyStatus, SufficiencyState
from schemas.economic_evidence import GateVerdict, ParameterState
from schemas.policy_evidence_package import PolicyEvidencePackage
from services.pipeline.policy_evidence_package_storage import PersistedPackageRecord


class PackageReadinessLevel(str, Enum):
    ECONOMIC_HANDOFF_READY = "economic_handoff_ready"
    QUALITATIVE_ONLY = "qualitative_only"
    FAIL_CLOSED = "fail_closed"


class SufficiencyBlockingGate(str, Enum):
    SCHEMA_VALIDATION = "schema_validation"
    STORAGE_READBACK = "storage_readback"
    PACKAGE_COMPLETENESS = "package_completeness"
    GATE_PROJECTION = "gate_projection"
    PARAMETER_READINESS = "parameter_readiness"
    SOURCE_SUPPORT = "source_support"
    ASSUMPTION_APPLICABILITY = "assumption_applicability"
    ASSUMPTION_STALENESS = "assumption_staleness"
    UNCERTAINTY_SENSITIVITY = "uncertainty_sensitivity"
    UNSUPPORTED_CLAIMS = "unsupported_claims"


@dataclass(frozen=True)
class PackageSufficiencyResult:
    passed: bool
    blocking_gate: SufficiencyBlockingGate | None
    readiness_level: PackageReadinessLevel
    failure_reasons: list[str] = field(default_factory=list)
    recommendations_for_bd_3wefe_6: list[str] = field(default_factory=list)


class PolicyEvidencePackageSufficiencyService:
    """Evaluate persisted package rows for economic-analysis handoff readiness."""

    def evaluate(self, *, record: PersistedPackageRecord) -> PackageSufficiencyResult:
        package, schema_error = self._validate_package(record=record)
        if schema_error is not None:
            return self._fail_closed(
                gate=SufficiencyBlockingGate.SCHEMA_VALIDATION,
                reason=schema_error,
            )
        assert package is not None

        storage_failure = self._check_storage(record=record)
        if storage_failure is not None:
            return self._fail_closed(
                gate=SufficiencyBlockingGate.STORAGE_READBACK,
                reason=storage_failure,
            )

        completeness_failure = self._check_completeness(package=package)
        if completeness_failure is not None:
            return self._fail_closed(
                gate=SufficiencyBlockingGate.PACKAGE_COMPLETENESS,
                reason=completeness_failure,
            )

        projection_failure = self._check_gate_projection(package=package)
        if projection_failure is not None:
            return self._fail_closed(
                gate=SufficiencyBlockingGate.GATE_PROJECTION,
                reason=projection_failure,
            )

        assumption_failure = self._check_assumption_usage(package=package)
        if assumption_failure is not None:
            return self._fail_closed(
                gate=assumption_failure[0],
                reason=assumption_failure[1],
            )

        unsupported_claim_failure = self._check_unsupported_claims(package=package)
        if unsupported_claim_failure is not None:
            return self._fail_closed(
                gate=SufficiencyBlockingGate.UNSUPPORTED_CLAIMS,
                reason=unsupported_claim_failure,
            )

        parameter_failure = self._check_parameter_support(package=package)
        if parameter_failure is not None:
            runtime_is_qualitative = (
                package.gate_projection.runtime_sufficiency_state
                == SufficiencyState.QUALITATIVE_ONLY
            )
            if runtime_is_qualitative:
                return PackageSufficiencyResult(
                    passed=True,
                    blocking_gate=SufficiencyBlockingGate.PARAMETER_READINESS,
                    readiness_level=PackageReadinessLevel.QUALITATIVE_ONLY,
                    failure_reasons=[parameter_failure],
                    recommendations_for_bd_3wefe_6=[
                        "Treat this package as qualitative-only in canonical analysis.",
                        "Resolve missing parameters before enabling quantified paths.",
                    ],
                )
            return self._fail_closed(
                gate=SufficiencyBlockingGate.PARAMETER_READINESS,
                reason=parameter_failure,
            )

        source_support_failure = self._check_source_support(package=package)
        if source_support_failure is not None:
            return self._fail_closed(
                gate=SufficiencyBlockingGate.SOURCE_SUPPORT,
                reason=source_support_failure,
            )

        uncertainty_failure = self._check_uncertainty_support(package=package)
        if uncertainty_failure is not None:
            return self._fail_closed(
                gate=SufficiencyBlockingGate.UNCERTAINTY_SENSITIVITY,
                reason=uncertainty_failure,
            )

        if package.economic_handoff_ready:
            return PackageSufficiencyResult(
                passed=True,
                blocking_gate=None,
                readiness_level=PackageReadinessLevel.ECONOMIC_HANDOFF_READY,
                failure_reasons=[],
                recommendations_for_bd_3wefe_6=[
                    "Use this package as the quantitative handoff input for direct and indirect mechanism cases.",
                    "Record assumption ids and parameter ids used in final analysis output for audit traceability.",
                ],
            )

        return PackageSufficiencyResult(
            passed=True,
            blocking_gate=None,
            readiness_level=PackageReadinessLevel.QUALITATIVE_ONLY,
            failure_reasons=[
                "Package does not satisfy quantitative handoff prerequisites but remains qualitative-usable."
            ],
            recommendations_for_bd_3wefe_6=[
                "Run canonical analysis in qualitative-only mode and surface insufficiency reason to users.",
                "Backfill parameter and assumption evidence before rerunning quantified mode.",
            ],
        )

    def _validate_package(
        self, *, record: PersistedPackageRecord
    ) -> tuple[PolicyEvidencePackage | None, str | None]:
        try:
            package = PolicyEvidencePackage.model_validate(record.package_payload)
        except ValidationError as exc:
            return None, f"Persisted payload schema validation failed: {exc.errors()[0]['type']}"
        return package, None

    def _check_storage(self, *, record: PersistedPackageRecord) -> str | None:
        if not record.record_id:
            return "Persisted record is missing record_id."
        if record.artifact_readback_status != "proven":
            return (
                "Artifact readback is not proven "
                f"(artifact_readback_status={record.artifact_readback_status})."
            )
        return None

    def _check_completeness(self, *, package: PolicyEvidencePackage) -> str | None:
        if not package.source_lanes:
            return "Package has no source lanes."
        if not package.evidence_cards:
            return "Package has no evidence cards."
        if not package.gate_projection:
            return "Package has no gate projection."
        if not package.gate_report.stage_results:
            return "Package has no gate stage results."
        return None

    def _check_gate_projection(self, *, package: PolicyEvidencePackage) -> str | None:
        if package.gate_report.blocking_gate is not None and package.economic_handoff_ready:
            return "economic_handoff_ready=true with gate_report.blocking_gate present."
        if (
            package.economic_handoff_ready
            and package.gate_projection.runtime_sufficiency_state != SufficiencyState.QUANTIFIED
        ):
            return "economic_handoff_ready=true requires runtime sufficiency state quantified."
        return None

    def _check_parameter_support(self, *, package: PolicyEvidencePackage) -> str | None:
        has_resolved_parameters = any(
            card.state == ParameterState.RESOLVED for card in package.parameter_cards
        )
        has_quant_model_support = any(
            card.quantification_eligible
            and bool(card.input_parameter_ids)
            and bool(card.assumption_ids)
            for card in package.model_cards
        )
        if not has_resolved_parameters and not has_quant_model_support:
            return "No resolved parameters or quantification-eligible model support path."
        return None

    def _check_source_support(self, *, package: PolicyEvidencePackage) -> str | None:
        for card in package.parameter_cards:
            if card.state != ParameterState.RESOLVED:
                continue
            if card.source_hierarchy_status == SourceHierarchyStatus.FAILED_CLOSED:
                return (
                    f"Resolved parameter {card.id} has failed_closed source hierarchy status."
                )
        return None

    def _check_assumption_usage(
        self, *, package: PolicyEvidencePackage
    ) -> tuple[SufficiencyBlockingGate, str] | None:
        assumption_by_id = {item.id: item for item in package.assumption_cards}
        for usage in package.assumption_usage:
            if not usage.used_for_quantitative_claim:
                continue
            if package.freshness_status.value == "stale_blocked":
                return (
                    SufficiencyBlockingGate.ASSUMPTION_STALENESS,
                    "Package freshness is stale_blocked for quantitative assumption usage.",
                )
            assumption = assumption_by_id.get(usage.assumption_id)
            if assumption is None:
                return (
                    SufficiencyBlockingGate.ASSUMPTION_APPLICABILITY,
                    f"assumption_usage references missing assumption_id={usage.assumption_id}.",
                )
            if usage.stale:
                return (
                    SufficiencyBlockingGate.ASSUMPTION_STALENESS,
                    f"Assumption {usage.assumption_id} is stale for quantitative use.",
                )
            if not usage.applicable:
                return (
                    SufficiencyBlockingGate.ASSUMPTION_APPLICABILITY,
                    f"Assumption {usage.assumption_id} marked inapplicable for quantitative use.",
                )
            if assumption.stale_after_days is None:
                return (
                    SufficiencyBlockingGate.ASSUMPTION_STALENESS,
                    f"Assumption {usage.assumption_id} missing staleness policy.",
                )
            if not assumption.applicability_tags:
                return (
                    SufficiencyBlockingGate.ASSUMPTION_APPLICABILITY,
                    f"Assumption {usage.assumption_id} missing applicability tags.",
                )
        return None

    def _check_uncertainty_support(self, *, package: PolicyEvidencePackage) -> str | None:
        quant_models = [card for card in package.model_cards if card.quantification_eligible]
        if not quant_models:
            return None
        for model in quant_models:
            if model.scenario_bounds is None:
                return f"Quant model {model.id} missing scenario_bounds."
        return None

    def _check_unsupported_claims(self, *, package: PolicyEvidencePackage) -> str | None:
        if package.gate_report.unsupported_claim_count <= 0:
            return None
        qualitative_verdicts = {
            GateVerdict.QUALITATIVE_ONLY,
            GateVerdict.QUALITATIVE_ONLY_DUE_TO_UNSUPPORTED_CLAIMS,
            GateVerdict.FAIL_CLOSED_QUALITATIVE_ONLY,
        }
        if package.gate_report.verdict not in qualitative_verdicts:
            return (
                "Unsupported claims present but gate verdict is not qualitative/fail-closed."
            )
        return None

    def _fail_closed(
        self, *, gate: SufficiencyBlockingGate, reason: str
    ) -> PackageSufficiencyResult:
        return PackageSufficiencyResult(
            passed=False,
            blocking_gate=gate,
            readiness_level=PackageReadinessLevel.FAIL_CLOSED,
            failure_reasons=[reason],
            recommendations_for_bd_3wefe_6=[
                "Keep canonical analysis fail-closed until this gate is resolved.",
                "Propagate insufficiency reason into admin/frontend read models.",
            ],
        )
