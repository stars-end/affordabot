from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator

from schemas.analysis import FailureCode, SufficiencyState
from schemas.economic_evidence import (
    AssumptionCard,
    EvidenceCard,
    GateReport,
    ModelCard,
    ParameterCard,
    ParameterState,
)


class PackageSchemaVersion(str, Enum):
    V1 = "1.0.0"


class SourceLane(str, Enum):
    SCRAPED = "scraped"
    STRUCTURED = "structured"


class PackageFailureReason(str, Enum):
    NO_SOURCE_LANES = "no_source_lanes"
    NO_EVIDENCE_CARDS = "no_evidence_cards"
    BLOCKING_GATE_PRESENT = "blocking_gate_present"
    NO_QUANT_SUPPORT_PATH = "no_quant_support_path"
    STALE_ASSUMPTION_FOR_QUANT_CLAIM = "stale_assumption_for_quant_claim"
    MISSING_ASSUMPTION_STALENESS = "missing_assumption_staleness"
    UNSUPPORTED_ASSUMPTION_FOR_QUANT_CLAIM = "unsupported_assumption_for_quant_claim"
    PGVECTOR_MARKED_SOURCE_OF_TRUTH = "pgvector_marked_source_of_truth"
    SCRAPED_PROVIDER_IDENTITY_MISSING = "scraped_provider_identity_missing"


class SearchProvider(str, Enum):
    PRIVATE_SEARXNG = "private_searxng"
    TAVILY = "tavily"
    EXA = "exa"
    ZAI_SEARCH = "zai_search"
    OTHER = "other"


class StorageSystem(str, Enum):
    POSTGRES = "postgres"
    MINIO = "minio"
    PGVECTOR = "pgvector"


class StorageTruthRole(str, Enum):
    SOURCE_OF_TRUTH = "source_of_truth"
    ARTIFACT_OF_RECORD = "artifact_of_record"
    DERIVED_INDEX = "derived_index"


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE_USABLE = "stale_usable"
    STALE_BLOCKED = "stale_blocked"
    UNKNOWN = "unknown"


class ScrapedSourceProvenance(BaseModel):
    search_provider: SearchProvider
    provider_run_id: Optional[str] = None
    query_family: str = Field(min_length=1)
    query_text: str = Field(min_length=1)
    search_snapshot_id: str = Field(min_length=1)
    candidate_rank: int = Field(ge=1)
    selected_candidate_url: HttpUrl
    reader_artifact_url: Optional[HttpUrl] = None
    reader_substance_passed: bool = False


class StructuredSourceProvenance(BaseModel):
    source_family: str = Field(min_length=1)
    access_method: str = Field(min_length=1)
    endpoint_or_file_url: HttpUrl
    provider_run_id: Optional[str] = None
    field_count: int = Field(default=0, ge=0)


class StorageRef(BaseModel):
    storage_system: StorageSystem
    truth_role: StorageTruthRole
    reference_id: str = Field(min_length=1)
    content_hash: Optional[str] = None
    uri: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_pgvector_truth_role(self) -> "StorageRef":
        if (
            self.storage_system == StorageSystem.PGVECTOR
            and self.truth_role == StorageTruthRole.SOURCE_OF_TRUTH
        ):
            raise ValueError(
                PackageFailureReason.PGVECTOR_MARKED_SOURCE_OF_TRUTH.value
            )
        return self


class GateProjection(BaseModel):
    runtime_sufficiency_state: SufficiencyState
    runtime_insufficiency_reason: Optional[str] = None
    runtime_failure_codes: List[FailureCode] = Field(default_factory=list)
    canonical_breakdown_ref: Optional[str] = None
    canonical_pipeline_run_id: Optional[str] = None
    canonical_pipeline_step_id: Optional[str] = None


class AssumptionUsageStatus(BaseModel):
    assumption_id: str = Field(min_length=1)
    used_for_quantitative_claim: bool = False
    applicable: bool = True
    stale: bool = False
    stale_reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_stale_reason(self) -> "AssumptionUsageStatus":
        if self.stale and not self.stale_reason:
            raise ValueError("stale_reason is required when stale=true.")
        return self


class PolicyEvidencePackage(BaseModel):
    schema_version: PackageSchemaVersion = PackageSchemaVersion.V1
    package_id: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    canonical_document_key: str = Field(min_length=1)
    policy_identifier: str = Field(min_length=1)
    created_at: datetime
    source_lanes: List[SourceLane] = Field(min_length=1)

    scraped_sources: List[ScrapedSourceProvenance] = Field(default_factory=list)
    structured_sources: List[StructuredSourceProvenance] = Field(default_factory=list)

    evidence_cards: List[EvidenceCard] = Field(min_length=1)
    parameter_cards: List[ParameterCard] = Field(default_factory=list)
    assumption_cards: List[AssumptionCard] = Field(default_factory=list)
    model_cards: List[ModelCard] = Field(default_factory=list)

    gate_report: GateReport
    gate_projection: GateProjection
    assumption_usage: List[AssumptionUsageStatus] = Field(default_factory=list)

    storage_refs: List[StorageRef] = Field(default_factory=list)
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN
    economic_handoff_ready: bool = False
    insufficiency_reasons: List[PackageFailureReason] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lane_provenance(self) -> "PolicyEvidencePackage":
        if not self.source_lanes:
            raise ValueError(PackageFailureReason.NO_SOURCE_LANES.value)
        if not self.evidence_cards:
            raise ValueError(PackageFailureReason.NO_EVIDENCE_CARDS.value)

        lanes = set(self.source_lanes)
        if SourceLane.SCRAPED in lanes and not self.scraped_sources:
            raise ValueError(PackageFailureReason.SCRAPED_PROVIDER_IDENTITY_MISSING.value)
        if SourceLane.STRUCTURED in lanes and not self.structured_sources:
            raise ValueError("structured source lane requires structured_sources.")
        return self

    @model_validator(mode="after")
    def validate_quantitative_assumption_requirements(self) -> "PolicyEvidencePackage":
        assumptions_by_id = {card.id: card for card in self.assumption_cards}

        for usage in self.assumption_usage:
            if not usage.used_for_quantitative_claim:
                continue
            card = assumptions_by_id.get(usage.assumption_id)
            if card is None:
                raise ValueError(
                    f"assumption_usage references unknown assumption_id={usage.assumption_id}"
                )
            if card.stale_after_days is None:
                raise ValueError(PackageFailureReason.MISSING_ASSUMPTION_STALENESS.value)
            if not card.applicability_tags:
                raise ValueError(
                    PackageFailureReason.UNSUPPORTED_ASSUMPTION_FOR_QUANT_CLAIM.value
                )
            if usage.stale:
                raise ValueError(
                    PackageFailureReason.STALE_ASSUMPTION_FOR_QUANT_CLAIM.value
                )
            if not usage.applicable:
                raise ValueError(
                    PackageFailureReason.UNSUPPORTED_ASSUMPTION_FOR_QUANT_CLAIM.value
                )
        return self

    @model_validator(mode="after")
    def validate_handoff_readiness(self) -> "PolicyEvidencePackage":
        if not self.economic_handoff_ready:
            return self

        if self.gate_report.blocking_gate is not None:
            raise ValueError(PackageFailureReason.BLOCKING_GATE_PRESENT.value)
        if self.gate_projection.runtime_sufficiency_state != SufficiencyState.QUANTIFIED:
            raise ValueError(
                "economic_handoff_ready=true requires runtime sufficiency_state=quantified."
            )

        has_resolved_parameter = any(
            param.state == ParameterState.RESOLVED for param in self.parameter_cards
        )
        has_quant_model_support = any(
            model.quantification_eligible
            and bool(model.input_parameter_ids)
            and bool(model.assumption_ids)
            for model in self.model_cards
        )
        if not has_resolved_parameter and not has_quant_model_support:
            raise ValueError(PackageFailureReason.NO_QUANT_SUPPORT_PATH.value)
        return self
