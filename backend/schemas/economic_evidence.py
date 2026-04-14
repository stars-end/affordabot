from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator

from schemas.analysis import FailureCode, ScenarioBounds, SourceHierarchyStatus, SourceTier


class EvidenceSourceType(str, Enum):
    BILL_TEXT = "bill_text"
    FISCAL_NOTE = "fiscal_note"
    COMMITTEE_ANALYSIS = "committee_analysis"
    STAFF_REPORT = "staff_report"
    AGENDA_PACKET = "agenda_packet"
    MINUTES = "minutes"
    ORDINANCE_TEXT = "ordinance_text"
    BUDGET_DOCUMENT = "budget_document"
    ACADEMIC_LITERATURE = "academic_literature"
    OTHER = "other"


class MechanismFamily(str, Enum):
    DIRECT_FISCAL = "direct_fiscal"
    COMPLIANCE_COST = "compliance_cost"
    FEE_OR_TAX_PASS_THROUGH = "fee_or_tax_pass_through"
    ADOPTION_TAKE_UP = "adoption_take_up"


class ParameterState(str, Enum):
    RESOLVED = "resolved"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


class UnitValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNVERIFIED = "unverified"


class QualityGateStage(str, Enum):
    SEARCH_RECALL = "search_recall"
    READER_SUBSTANCE = "reader_substance"
    ARTIFACT_CLASSIFICATION = "artifact_classification"
    EVIDENCE_EXTRACTION = "evidence_extraction"
    PARAMETERIZATION = "parameterization"
    ASSUMPTION_SELECTION = "assumption_selection"
    QUANTIFICATION = "quantification"
    LLM_EXPLANATION = "llm_explanation"


class GateVerdict(str, Enum):
    PASS = "pass"
    FAIL_CLOSED = "fail_closed"
    QUALITATIVE_ONLY = "qualitative_only"


class EvidenceCard(BaseModel):
    id: str = Field(min_length=1)
    source_url: HttpUrl
    source_type: EvidenceSourceType
    content_hash: str = Field(min_length=8)
    excerpt: str = Field(min_length=16)
    retrieved_at: datetime
    source_tier: SourceTier
    provenance_label: str = Field(
        min_length=1,
        description="Short provenance label such as legistar_primary or curated_literature.",
    )
    artifact_id: Optional[str] = None
    reader_run_id: Optional[str] = None


class ParameterCard(BaseModel):
    id: str = Field(min_length=1)
    parameter_name: str = Field(min_length=1)
    state: ParameterState = ParameterState.RESOLVED
    value: Optional[float] = None
    unit: Optional[str] = None
    time_horizon: Optional[str] = None
    source_url: Optional[HttpUrl] = None
    source_excerpt: Optional[str] = None
    source_hierarchy_status: SourceHierarchyStatus = SourceHierarchyStatus.FAILED_CLOSED
    ambiguity_reason: Optional[str] = None
    evidence_card_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_state_requirements(self) -> "ParameterCard":
        if self.state == ParameterState.RESOLVED:
            if self.value is None:
                raise ValueError("Resolved parameter requires numeric value.")
            if self.source_url is None:
                raise ValueError("Resolved parameter requires source_url.")
            if not self.source_excerpt:
                raise ValueError("Resolved parameter requires source_excerpt.")
        else:
            if self.value is not None:
                raise ValueError("Non-resolved parameter must not include numeric value.")
            if not self.ambiguity_reason:
                raise ValueError("Non-resolved parameter requires ambiguity_reason.")
        return self


class AssumptionCard(BaseModel):
    id: str = Field(min_length=1)
    family: MechanismFamily
    low: float
    central: float
    high: float
    unit: str = Field(min_length=1)
    source_url: HttpUrl
    source_excerpt: str = Field(min_length=16)
    applicability_tags: List[str] = Field(min_length=1)
    external_validity_notes: str = Field(min_length=8)
    confidence: float = Field(ge=0.0, le=1.0)
    version: str = Field(min_length=1)
    stale_after_days: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> "AssumptionCard":
        if not (self.low <= self.central <= self.high):
            raise ValueError("Assumption bounds must satisfy low <= central <= high.")
        return self


class ModelCard(BaseModel):
    id: str = Field(min_length=1)
    mechanism_family: MechanismFamily
    formula_id: str = Field(min_length=1)
    input_parameter_ids: List[str] = Field(min_length=1)
    assumption_ids: List[str] = Field(default_factory=list)
    scenario_bounds: Optional[ScenarioBounds] = None
    arithmetic_valid: bool = False
    unit_validation_status: UnitValidationStatus = UnitValidationStatus.UNVERIFIED
    quantification_eligible: bool = False
    failure_codes: List[FailureCode] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_quantification_flags(self) -> "ModelCard":
        if self.quantification_eligible:
            if self.scenario_bounds is None:
                raise ValueError(
                    "Quantification-eligible model requires scenario_bounds."
                )
            if not self.arithmetic_valid:
                raise ValueError(
                    "Quantification-eligible model requires arithmetic_valid=true."
                )
            if self.unit_validation_status != UnitValidationStatus.VALID:
                raise ValueError(
                    "Quantification-eligible model requires valid unit checks."
                )
        return self


class GateStageResult(BaseModel):
    stage: QualityGateStage
    passed: bool
    failure_codes: List[FailureCode] = Field(default_factory=list)
    note: Optional[str] = None


class GateReport(BaseModel):
    case_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    verdict: GateVerdict
    stage_results: List[GateStageResult] = Field(min_length=1)
    blocking_gate: Optional[QualityGateStage] = None
    failure_codes: List[FailureCode] = Field(default_factory=list)
    artifact_counts: Dict[str, int] = Field(default_factory=dict)
    unsupported_claim_count: int = Field(default=0, ge=0)
    manual_audit_notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_blocking_gate_alignment(self) -> "GateReport":
        if self.blocking_gate is not None:
            matched = any(
                stage_result.stage == self.blocking_gate and not stage_result.passed
                for stage_result in self.stage_results
            )
            if not matched:
                raise ValueError(
                    "blocking_gate must correspond to a failed stage result."
                )
        return self
