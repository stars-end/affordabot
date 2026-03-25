from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class SufficiencyState(str, Enum):
    RESEARCH_INCOMPLETE = "research_incomplete"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    QUALITATIVE_ONLY = "qualitative_only"
    QUANTIFIED = "quantified"


class SourceTier(str, Enum):
    TIER_A = "tier_a"
    TIER_B = "tier_b"
    TIER_C = "tier_c"


class ImpactMode(str, Enum):
    DIRECT_FISCAL = "direct_fiscal"
    COMPLIANCE_COST = "compliance_cost"
    PASS_THROUGH_INCIDENCE = "pass_through_incidence"
    ADOPTION_TAKE_UP = "adoption_take_up"
    QUALITATIVE_ONLY = "qualitative_only"


class FailureCode(str, Enum):
    IMPACT_DISCOVERY_FAILED = "impact_discovery_failed"
    MODE_SELECTION_FAILED = "mode_selection_failed"
    PARAMETER_MISSING = "parameter_missing"
    PARAMETER_UNVERIFIABLE = "parameter_unverifiable"
    SOURCE_HIERARCHY_FAILED = "source_hierarchy_failed"
    EXCERPT_VALIDATION_FAILED = "excerpt_validation_failed"
    INVALID_SCENARIO_CONSTRUCTION = "invalid_scenario_construction"
    VALIDATION_FAILED = "validation_failed"
    FIXTURE_INVALID = "fixture_invalid"


class SourceHierarchyStatus(str, Enum):
    BILL_OR_REG_TEXT = "bill_or_reg_text"
    FISCAL_OR_REG_IMPACT_ANALYSIS = "fiscal_or_reg_impact_analysis"
    FAILED_CLOSED = "failed_closed"


class ExcerptValidationStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class AmbiguityStatus(str, Enum):
    CLEAR = "clear"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


class ModeSelectionOutput(BaseModel):
    candidate_modes: List[ImpactMode] = Field(default_factory=list)
    selected_mode: ImpactMode = ImpactMode.QUALITATIVE_ONLY
    rejected_modes: List[ImpactMode] = Field(default_factory=list)
    selection_rationale: str = ""
    ambiguity_status: AmbiguityStatus = AmbiguityStatus.CLEAR
    composition_candidate: bool = False

    @model_validator(mode="after")
    def enforce_wave1_no_composition(self) -> "ModeSelectionOutput":
        if self.composition_candidate:
            raise ValueError(
                "Wave 1 requires composition_candidate=false; composition is deferred."
            )
        return self


class ModeledParameter(BaseModel):
    name: str
    value: float
    unit: Optional[str] = None
    source_url: str = ""
    source_excerpt: str = ""


class ParameterResolutionOutput(BaseModel):
    required_parameters: List[str] = Field(default_factory=list)
    resolved_parameters: Dict[str, ModeledParameter] = Field(default_factory=dict)
    missing_parameters: List[str] = Field(default_factory=list)
    source_hierarchy_status: Dict[str, SourceHierarchyStatus] = Field(
        default_factory=dict
    )
    excerpt_validation_status: Dict[str, ExcerptValidationStatus] = Field(
        default_factory=dict
    )
    literature_confidence: Dict[str, float] = Field(default_factory=dict)
    dominant_uncertainty_parameters: List[str] = Field(default_factory=list)


class ParameterValidationOutput(BaseModel):
    schema_valid: bool = False
    arithmetic_valid: bool = False
    bound_construction_valid: bool = False
    claim_support_valid: bool = False
    validation_failures: List[FailureCode] = Field(default_factory=list)


class ComponentBreakdown(BaseModel):
    component_name: str
    base: float
    low: float
    high: float
    unit: Optional[str] = None
    formula: Optional[str] = None


class ScenarioBounds(BaseModel):
    conservative: float
    central: float
    aggressive: float

    @model_validator(mode="after")
    def ensure_monotonic(self) -> "ScenarioBounds":
        if not (self.conservative <= self.central <= self.aggressive):
            raise ValueError(
                "Invalid scenario construction: conservative <= central <= aggressive is required."
            )
        return self


class PersistedEvidence(BaseModel):
    """Evidence persisted from an EvidenceEnvelope, preserving provenance fields."""

    id: str = ""
    kind: str = ""
    url: str = ""
    excerpt: Optional[str] = None
    content_hash: Optional[str] = None
    derived_from: List[str] = Field(default_factory=list)
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source_name: str = ""
    label: Optional[str] = None


class ImpactEvidence(BaseModel):
    """Evidence supporting a cost of living impact."""

    source_name: str = Field(
        default="", description="Name of source (e.g., 'NREL Study 2024')"
    )
    url: str = Field(default="", description="URL to original source")
    excerpt: str = Field(default="", description="Relevant excerpt from source")
    source_tier: Optional[SourceTier] = Field(
        default=None, description="Evidence source tier"
    )
    persisted_evidence_id: Optional[str] = Field(
        default=None, description="Upstream EvidenceEnvelope.id"
    )
    persisted_evidence_kind: Optional[str] = Field(
        default=None, description="Upstream EvidenceEnvelope.kind"
    )

    @field_validator("url")
    @classmethod
    def url_must_not_be_placeholder(cls, v: str) -> str:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError(f"Evidence URL must be HTTP(S), got: {v}")
        return v


class LegislationImpact(BaseModel):
    """Single impact analysis for a piece of legislation."""

    impact_number: int = Field(ge=1, description="Impact sequence number")
    relevant_clause: str = Field(default="", description="Exact text from legislation")
    legal_interpretation: str = Field(
        default="", description="Interpretation of the legal mechanism (LAW)"
    )
    impact_description: str = Field(
        default="", description="Description of cost of living impact (FACT)"
    )
    evidence: List[ImpactEvidence] = Field(
        default_factory=list, description="Evidence list"
    )
    chain_of_causality: str = Field(default="", description="Step-by-step reasoning")
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence in this specific impact assessment (0.0-1.0)",
    )
    impact_mode: ImpactMode = Field(default=ImpactMode.QUALITATIVE_ONLY)
    mode_selection: Optional[ModeSelectionOutput] = None
    parameter_resolution: Optional[ParameterResolutionOutput] = None
    parameter_validation: Optional[ParameterValidationOutput] = None
    modeled_parameters: Dict[str, ModeledParameter] = Field(default_factory=dict)
    component_breakdown: List[ComponentBreakdown] = Field(default_factory=list)
    scenario_bounds: Optional[ScenarioBounds] = None
    composition_note: Optional[str] = None
    failure_codes: List[FailureCode] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def upgrade_legacy_quantiles(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if data.get("scenario_bounds") is not None:
            return data
        p50 = data.get("p50")
        if p50 is None:
            return data
        upgraded = dict(data)
        upgraded["scenario_bounds"] = {
            "conservative": upgraded.get("p10", p50),
            "central": p50,
            "aggressive": upgraded.get("p90", p50),
        }
        return upgraded

    @property
    def is_quantified(self) -> bool:
        return self.scenario_bounds is not None

    @property
    def p10(self) -> Optional[float]:
        return (
            self.scenario_bounds.conservative if self.scenario_bounds is not None else None
        )

    @property
    def p50(self) -> Optional[float]:
        return self.scenario_bounds.central if self.scenario_bounds is not None else None

    @property
    def p90(self) -> Optional[float]:
        return self.scenario_bounds.aggressive if self.scenario_bounds is not None else None


class LegislationAnalysisResponse(BaseModel):
    """Complete analysis of a single bill/regulation."""

    bill_number: str
    title: str = Field(default="", description="Title of the legislation")
    jurisdiction: str = Field(default="", description="Jurisdiction of the legislation")
    status: str = Field(default="", description="Current status of the legislation")
    sufficiency_state: SufficiencyState = Field(
        default=SufficiencyState.RESEARCH_INCOMPLETE,
        description="Evidence sufficiency state for this analysis",
    )
    insufficiency_reason: Optional[str] = Field(
        default=None, description="Human-readable reason if not quantified"
    )
    quantification_eligible: bool = Field(
        default=False,
        description="Whether quantified output is permitted for this analysis",
    )
    impacts: List[LegislationImpact] = Field(default_factory=list)
    aggregate_scenario_bounds: Optional[ScenarioBounds] = None
    analysis_timestamp: str
    model_used: str

    @model_validator(mode="before")
    @classmethod
    def upgrade_legacy_total_impact(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if data.get("aggregate_scenario_bounds") is not None:
            return data
        total_impact_p50 = data.get("total_impact_p50")
        if total_impact_p50 is None:
            return data
        upgraded = dict(data)
        upgraded["aggregate_scenario_bounds"] = {
            "conservative": total_impact_p50,
            "central": total_impact_p50,
            "aggressive": total_impact_p50,
        }
        return upgraded

    @property
    def total_impact_p50(self) -> Optional[float]:
        if self.aggregate_scenario_bounds is not None:
            return self.aggregate_scenario_bounds.central
        quantified = [
            impact.scenario_bounds.central
            for impact in self.impacts
            if impact.scenario_bounds is not None
        ]
        return sum(quantified) if quantified else None


class RetrievalPrerequisiteStatus(BaseModel):
    source_text_present: bool = False
    rag_chunks_retrieved: int = 0
    web_research_sources_found: int = 0
    has_verifiable_url: bool = False


class ImpactGateSummary(BaseModel):
    impact_id: str
    selected_mode: ImpactMode = ImpactMode.QUALITATIVE_ONLY
    quantification_eligible: bool = False
    sufficiency_state: SufficiencyState = SufficiencyState.QUALITATIVE_ONLY
    gate_failures: List[FailureCode] = Field(default_factory=list)
    parameter_validation_summary: ParameterValidationOutput = Field(
        default_factory=ParameterValidationOutput
    )
    retrieval_prerequisite_status: RetrievalPrerequisiteStatus = Field(
        default_factory=RetrievalPrerequisiteStatus
    )


class SufficiencyBreakdown(BaseModel):
    """Bill-level deterministic sufficiency derived after per-impact gating."""

    overall_quantification_eligible: bool = False
    overall_sufficiency_state: SufficiencyState = SufficiencyState.RESEARCH_INCOMPLETE
    impact_gate_summaries: List[ImpactGateSummary] = Field(default_factory=list)
    bill_level_failures: List[FailureCode] = Field(default_factory=list)


class ReviewCritique(BaseModel):
    """Review output."""

    passed: bool
    critique: str
    missing_impacts: List[str] = Field(default_factory=list)
    factual_errors: List[str] = Field(default_factory=list)
