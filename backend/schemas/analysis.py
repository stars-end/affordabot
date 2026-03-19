from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class SufficiencyState(str, Enum):
    RESEARCH_INCOMPLETE = "research_incomplete"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    QUALITATIVE_ONLY = "qualitative_only"
    QUANTIFIED = "quantified"


class SourceTier(str, Enum):
    TIER_A = "tier_a"
    TIER_B = "tier_b"
    TIER_C = "tier_c"


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

    p10: Optional[float] = Field(
        default=None, description="10th percentile cost impact"
    )
    p25: Optional[float] = Field(
        default=None, description="25th percentile cost impact"
    )
    p50: Optional[float] = Field(
        default=None, description="50th percentile cost impact (median)"
    )
    p75: Optional[float] = Field(
        default=None, description="75th percentile cost impact"
    )
    p90: Optional[float] = Field(
        default=None, description="90th percentile cost impact"
    )

    numeric_basis: Optional[str] = Field(
        default=None, description="Description of numeric basis used"
    )
    estimate_method: Optional[str] = Field(
        default=None, description="Estimation method"
    )
    assumptions: Optional[str] = Field(default=None, description="Key assumptions")

    @property
    def is_quantified(self) -> bool:
        return self.p50 is not None


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
    total_impact_p50: Optional[float] = Field(
        default=None, description="Sum of median impacts (None if not quantified)"
    )
    analysis_timestamp: str
    model_used: str


class SufficiencyBreakdown(BaseModel):
    """Deterministic sufficiency assessment for a bill."""

    bill_text_present: bool = False
    bill_text_is_placeholder: bool = False
    rag_chunks_retrieved: int = 0
    web_research_sources_found: int = 0
    tier_a_sources_found: int = 0
    fiscal_notes_detected: bool = False
    has_verifiable_url: bool = False
    source_text_present: bool = False
    sufficiency_state: SufficiencyState = SufficiencyState.RESEARCH_INCOMPLETE
    insufficiency_reasons: List[str] = Field(default_factory=list)
    quantification_eligible: bool = False


class ReviewCritique(BaseModel):
    """Review output."""

    passed: bool
    critique: str
    missing_impacts: List[str] = Field(default_factory=list)
    factual_errors: List[str] = Field(default_factory=list)
