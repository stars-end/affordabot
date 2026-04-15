"""Policy evidence package builder for bd-3wefe.4.

Builds schema-valid PolicyEvidencePackage payloads from scraped and structured
inputs while keeping fail-closed semantics.
"""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any

from services.revision_identity import normalize_canonical_url
from schemas.analysis import FailureCode, SourceHierarchyStatus, SourceTier, SufficiencyState
from schemas.economic_evidence import (
    AssumptionCard,
    EvidenceCard,
    EvidenceSourceType,
    GateReport,
    GateStageResult,
    GateVerdict,
    MechanismFamily,
    ParameterCard,
    ParameterState,
    QualityGateStage,
)
from schemas.policy_evidence_package import (
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

_INSUFFICIENT_REASONS = {
    "reader_output_insufficient_substance",
    "empty_reader_output",
    "content_too_short",
    "low_substantive_signal",
    "navigation_heavy",
    "agenda_header_logistics_only",
}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _content_hash(candidate: dict[str, Any]) -> str:
    value = str(candidate.get("content_hash", "")).strip()
    if value:
        return value
    fallback = str(candidate.get("canonical_document_key", "")).strip() or str(
        candidate.get("artifact_url", "")
    ).strip()
    if fallback:
        return f"missing_hash::{fallback}"
    return "missing_hash::unknown"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "unknown"


def _build_canonical_key(candidate: dict[str, Any]) -> str:
    jurisdiction_slug = _slug(str(candidate.get("jurisdiction", "unknown")))
    source_family_slug = _slug(str(candidate.get("source_family") or candidate.get("source_lane") or "unknown"))
    document_type = _slug(str(candidate.get("artifact_type") or "unknown")).replace("-", "_")
    canonical_url = normalize_canonical_url(str(candidate.get("artifact_url") or ""))
    if canonical_url:
        return (
            f"v2|jurisdiction={jurisdiction_slug}|family={source_family_slug}"
            f"|doctype={document_type}|url={canonical_url}"
        )
    title = re.sub(r"\s+", " ", str(candidate.get("title") or "untitled")).strip().lower()
    date_hint = str(candidate.get("published_date") or candidate.get("retrieved_at") or "unknown")
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", date_hint)
    normalized_date = date_match.group(0) if date_match else "unknown"
    return (
        f"v2|jurisdiction={jurisdiction_slug}|family={source_family_slug}"
        f"|doctype={document_type}|title={title}|date={normalized_date}"
    )


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def _map_source_lane(value: str) -> SourceLane:
    if value == "structured":
        return SourceLane.STRUCTURED
    return SourceLane.SCRAPED


def _map_search_provider(value: str) -> SearchProvider:
    mapping = {
        "private_searxng": SearchProvider.PRIVATE_SEARXNG,
        "tavily": SearchProvider.TAVILY,
        "exa": SearchProvider.EXA,
        "zai_search": SearchProvider.ZAI_SEARCH,
    }
    return mapping.get(value, SearchProvider.OTHER)


def _map_source_tier(value: str) -> SourceTier:
    mapping = {
        "tier_a": SourceTier.TIER_A,
        "tier_b": SourceTier.TIER_B,
        "tier_c": SourceTier.TIER_C,
    }
    return mapping.get(value, SourceTier.TIER_C)


def _map_evidence_source_type(candidate: dict[str, Any]) -> EvidenceSourceType:
    raw = str(candidate.get("evidence_source_type") or candidate.get("artifact_type") or "other").strip().lower()
    mapping = {
        "bill_text": EvidenceSourceType.BILL_TEXT,
        "fiscal_note": EvidenceSourceType.FISCAL_NOTE,
        "committee_analysis": EvidenceSourceType.COMMITTEE_ANALYSIS,
        "staff_report": EvidenceSourceType.STAFF_REPORT,
        "agenda_packet": EvidenceSourceType.AGENDA_PACKET,
        "minutes": EvidenceSourceType.MINUTES,
        "meeting_minutes": EvidenceSourceType.MINUTES,
        "ordinance_text": EvidenceSourceType.ORDINANCE_TEXT,
        "budget_document": EvidenceSourceType.BUDGET_DOCUMENT,
        "academic_literature": EvidenceSourceType.ACADEMIC_LITERATURE,
    }
    return mapping.get(raw, EvidenceSourceType.OTHER)


def _map_mechanism_family(value: str | None) -> MechanismFamily | None:
    mapping = {
        "direct_fiscal": MechanismFamily.DIRECT_FISCAL,
        "compliance_cost": MechanismFamily.COMPLIANCE_COST,
        "fee_or_tax_pass_through": MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
        "adoption_take_up": MechanismFamily.ADOPTION_TAKE_UP,
    }
    if not value:
        return None
    return mapping.get(value)


def _candidate_identity(candidate: dict[str, Any]) -> str:
    explicit = str(candidate.get("canonical_document_key", "")).strip()
    if explicit:
        return explicit
    return _build_canonical_key(candidate)


def _normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(candidate)
    normalized["canonical_document_key"] = _candidate_identity(candidate)
    normalized["content_hash"] = _content_hash(candidate)
    normalized["source_lane"] = str(candidate.get("source_lane") or "unknown")
    normalized["provider"] = str(candidate.get("provider") or "unknown")
    normalized["source_family"] = str(
        candidate.get("source_family") or candidate.get("provider") or normalized["source_lane"]
    )
    normalized["jurisdiction"] = str(candidate.get("jurisdiction") or "unknown")
    normalized["artifact_url"] = str(candidate.get("artifact_url") or "")
    normalized["artifact_type"] = str(candidate.get("artifact_type") or "unknown")
    normalized["source_tier"] = str(candidate.get("source_tier") or "tier_c")
    normalized["retrieved_at"] = str(candidate.get("retrieved_at") or "")
    normalized["linked_artifact_refs"] = _as_list(candidate.get("linked_artifact_refs"))
    normalized["reader_artifact_refs"] = _as_list(candidate.get("reader_artifact_refs"))
    normalized["structured_policy_facts"] = _as_list(candidate.get("structured_policy_facts"))
    normalized["alerts"] = [str(item) for item in _as_list(candidate.get("alerts")) if str(item).strip()]
    return normalized


def _classify_candidate(candidate: dict[str, Any]) -> tuple[bool, list[str]]:
    fail_reasons: list[str] = []
    source_lane = str(candidate.get("source_lane", ""))
    has_structured_facts = bool(candidate.get("structured_policy_facts"))
    has_reader_artifact = bool(candidate.get("reader_artifact_refs"))
    has_identity = bool(candidate.get("canonical_document_key")) and bool(candidate.get("artifact_url"))

    prefetch_skip_reason = str(candidate.get("prefetch_skip_reason") or "").strip()
    if prefetch_skip_reason:
        fail_reasons.append("prefetch_skipped_low_value_portal")

    reader_substance_reason = str(candidate.get("reader_substance_reason") or "").strip()
    if reader_substance_reason in _INSUFFICIENT_REASONS:
        fail_reasons.append(reader_substance_reason)

    if str(candidate.get("evidence_readiness", "")).strip() == "insufficient":
        fail_reasons.append("upstream_marked_insufficient")

    if not has_identity:
        fail_reasons.append("missing_identity")

    if source_lane == "scrape_search" and not has_reader_artifact and not has_structured_facts:
        fail_reasons.append("reader_required_for_scraped_source")
    return (len(fail_reasons) == 0, sorted(set(fail_reasons)))


def _build_evidence_card(candidate: dict[str, Any], index: int) -> EvidenceCard:
    url = candidate["artifact_url"] or "https://example.org/unknown"
    excerpt = (
        str(candidate.get("excerpt") or "").strip()
        or f"Evidence extracted from {candidate['source_family']} artifact for economic analysis."
    )
    if len(excerpt) < 16:
        excerpt = f"{excerpt} Source material supports policy impact extraction."
    return EvidenceCard(
        id=f"ev-{index}",
        source_url=url,
        source_type=_map_evidence_source_type(candidate),
        content_hash=candidate["content_hash"],
        excerpt=excerpt,
        retrieved_at=_parse_datetime(candidate.get("retrieved_at")),
        source_tier=_map_source_tier(candidate["source_tier"]),
        provenance_label=f"{candidate['provider']}_{candidate['source_family']}",
        artifact_id=candidate["canonical_document_key"],
        reader_run_id=None,
    )


def _build_parameter_cards(candidate: dict[str, Any], evidence_id: str) -> list[ParameterCard]:
    cards: list[ParameterCard] = []
    for fact in candidate.get("structured_policy_facts", []):
        value = fact.get("value")
        if not isinstance(value, (int, float)):
            continue
        name = str(fact.get("field") or "").strip() or "unknown_parameter"
        cards.append(
            ParameterCard(
                id=f"param-{len(cards)+1}-{_slug(name)}",
                parameter_name=name,
                state=ParameterState.RESOLVED,
                value=float(value),
                unit=str(fact.get("unit") or "unitless"),
                source_url=candidate["artifact_url"] or "https://example.org/unknown",
                source_excerpt=f"Structured fact {name} resolved from source payload.",
                source_hierarchy_status=SourceHierarchyStatus.FISCAL_OR_REG_IMPACT_ANALYSIS,
                evidence_card_id=evidence_id,
            )
        )
    return cards


def _build_storage_refs(storage_refs: dict[str, Any] | None) -> list[StorageRef]:
    refs = storage_refs or {}
    postgres_ref = str(refs.get("postgres_package_row") or "pipeline_packages:pending")
    minio_ref = str(
        refs.get("reader_artifact")
        or refs.get("raw_provider_response")
        or "minio://policy-evidence/unproven/pending"
    )
    pgvector_ref = str(refs.get("pgvector_chunk_ref") or "chunk:pending")
    return [
        StorageRef(
            storage_system=StorageSystem.POSTGRES,
            truth_role=StorageTruthRole.SOURCE_OF_TRUTH,
            reference_id=postgres_ref,
        ),
        StorageRef(
            storage_system=StorageSystem.MINIO,
            truth_role=StorageTruthRole.ARTIFACT_OF_RECORD,
            reference_id=minio_ref,
            uri=minio_ref,
            notes="readback proof pending bd-3wefe.10",
        ),
        StorageRef(
            storage_system=StorageSystem.PGVECTOR,
            truth_role=StorageTruthRole.DERIVED_INDEX,
            reference_id=pgvector_ref,
            notes="derived index only",
        ),
    ]


class PolicyEvidencePackageBuilder:
    """Assemble schema-valid policy evidence packages from mixed source lanes."""

    def build(
        self,
        *,
        package_id: str,
        jurisdiction: str,
        scraped_candidates: list[dict[str, Any]] | None = None,
        structured_candidates: list[dict[str, Any]] | None = None,
        freshness_gate: dict[str, Any] | None = None,
        economic_hints: dict[str, Any] | None = None,
        storage_refs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        all_candidates = []
        all_candidates.extend(scraped_candidates or [])
        all_candidates.extend(structured_candidates or [])

        evidence_cards: list[EvidenceCard] = []
        parameter_cards: list[ParameterCard] = []
        assumption_cards: list[AssumptionCard] = []
        scraped_sources: list[ScrapedSourceProvenance] = []
        structured_sources: list[StructuredSourceProvenance] = []
        source_lanes: set[SourceLane] = set()
        insufficiency_reasons: set[PackageFailureReason] = set()
        reader_substance_passed = True

        for idx, raw in enumerate(all_candidates, start=1):
            normalized = _normalize_candidate(raw)
            source_lane = _map_source_lane(normalized["source_lane"])
            source_lanes.add(source_lane)
            is_usable, fail_reasons = _classify_candidate(normalized)

            if source_lane == SourceLane.SCRAPED:
                search_provider = _map_search_provider(normalized["provider"])
                if search_provider == SearchProvider.OTHER:
                    insufficiency_reasons.add(PackageFailureReason.SCRAPED_PROVIDER_IDENTITY_MISSING)
                reader_url = None
                if normalized["reader_artifact_refs"]:
                    ref = str(normalized["reader_artifact_refs"][0])
                    if ref.startswith("http://") or ref.startswith("https://"):
                        reader_url = ref
                reader_passed = bool(normalized["reader_artifact_refs"]) and is_usable
                reader_substance_passed = reader_substance_passed and reader_passed
                scraped_sources.append(
                    ScrapedSourceProvenance(
                        search_provider=search_provider,
                        provider_run_id=str(normalized.get("provider_run_id") or "") or None,
                        query_family=str(normalized.get("source_family") or "unknown"),
                        query_text=str(normalized.get("query_text") or normalized.get("artifact_url") or "unknown query"),
                        search_snapshot_id=str(normalized.get("search_snapshot_id") or f"{package_id}-snapshot"),
                        candidate_rank=int(normalized.get("candidate_rank") or 1),
                        selected_candidate_url=normalized["artifact_url"] or "https://example.org/unknown",
                        reader_artifact_url=reader_url,
                        reader_substance_passed=reader_passed,
                    )
                )
            else:
                structured_sources.append(
                    StructuredSourceProvenance(
                        source_family=normalized["source_family"],
                        access_method=str(normalized.get("access_method") or "api_or_file"),
                        endpoint_or_file_url=normalized["artifact_url"] or "https://example.org/unknown",
                        provider_run_id=str(normalized.get("provider_run_id") or "") or None,
                        field_count=len(normalized.get("structured_policy_facts", [])),
                    )
                )

            evidence = _build_evidence_card(normalized, idx)
            evidence_cards.append(evidence)
            parameter_cards.extend(_build_parameter_cards(normalized, evidence.id))
            mechanism = _map_mechanism_family(str(normalized.get("mechanism_family") or ""))
            if mechanism and normalized.get("selected_impact_mode") != "qualitative_only":
                assumption_cards.append(
                    AssumptionCard(
                        id=f"assump-{idx}-{mechanism.value}",
                        family=mechanism,
                        low=0.5,
                        central=0.65,
                        high=0.8,
                        unit="share",
                        source_url=normalized["artifact_url"] or "https://example.org/unknown",
                        source_excerpt="Mapped mechanism assumption from source evidence and policy context.",
                        applicability_tags=[jurisdiction, normalized["source_family"]],
                        external_validity_notes="POC placeholder assumption; validate with literature in bd-3wefe.5/.6.",
                        confidence=0.5,
                        version="v1",
                        stale_after_days=365,
                    )
                )

            for reason in fail_reasons:
                if reason in _INSUFFICIENT_REASONS:
                    insufficiency_reasons.add(PackageFailureReason.BLOCKING_GATE_PRESENT)
                if reason == "reader_required_for_scraped_source":
                    insufficiency_reasons.add(PackageFailureReason.BLOCKING_GATE_PRESENT)
                if reason == "missing_identity":
                    insufficiency_reasons.add(PackageFailureReason.NO_EVIDENCE_CARDS)

        if not source_lanes:
            insufficiency_reasons.add(PackageFailureReason.NO_SOURCE_LANES)
        if not evidence_cards:
            insufficiency_reasons.add(PackageFailureReason.NO_EVIDENCE_CARDS)

        has_resolved_parameters = any(card.state == ParameterState.RESOLVED for card in parameter_cards)
        has_blocking_gate = bool(insufficiency_reasons) or (not has_resolved_parameters)
        if not has_resolved_parameters:
            insufficiency_reasons.add(PackageFailureReason.NO_QUANT_SUPPORT_PATH)
        if has_blocking_gate:
            insufficiency_reasons.add(PackageFailureReason.BLOCKING_GATE_PRESENT)

        stage_results = [
            GateStageResult(stage=QualityGateStage.SEARCH_RECALL, passed=bool(evidence_cards)),
            GateStageResult(
                stage=QualityGateStage.READER_SUBSTANCE,
                passed=reader_substance_passed if SourceLane.SCRAPED in source_lanes else True,
                failure_codes=[FailureCode.EXCERPT_VALIDATION_FAILED]
                if (SourceLane.SCRAPED in source_lanes and not reader_substance_passed)
                else [],
            ),
            GateStageResult(
                stage=QualityGateStage.PARAMETERIZATION,
                passed=has_resolved_parameters,
                failure_codes=[] if has_resolved_parameters else [FailureCode.PARAMETER_MISSING],
            ),
            GateStageResult(
                stage=QualityGateStage.QUANTIFICATION,
                passed=has_resolved_parameters and not has_blocking_gate,
                failure_codes=[] if (has_resolved_parameters and not has_blocking_gate) else [FailureCode.PARAMETER_UNVERIFIABLE],
            ),
        ]
        blocking_gate = None
        if SourceLane.SCRAPED in source_lanes and not reader_substance_passed:
            blocking_gate = QualityGateStage.READER_SUBSTANCE
        elif not has_resolved_parameters:
            blocking_gate = QualityGateStage.PARAMETERIZATION

        gate_report = GateReport(
            case_id=f"{package_id}-gate",
            provider=str((scraped_candidates or [{}])[0].get("provider") or "structured_only"),
            verdict=GateVerdict.QUANTIFIED_PASS if not has_blocking_gate else GateVerdict.FAIL_CLOSED,
            stage_results=stage_results,
            blocking_gate=blocking_gate,
            failure_codes=[] if not has_blocking_gate else [FailureCode.PARAMETER_MISSING],
            artifact_counts={"evidence_cards": len(evidence_cards)},
            unsupported_claim_count=0 if has_resolved_parameters else 1,
            manual_audit_notes="Builder POC payload; full durability/orchestration gates in bd-3wefe.10/.12.",
        )

        freshness_raw = str((freshness_gate or {}).get("freshness_status") or "unknown")
        freshness_map = {
            "fresh": FreshnessStatus.FRESH,
            "stale_usable": FreshnessStatus.STALE_USABLE,
            "stale_blocked": FreshnessStatus.STALE_BLOCKED,
            "unknown": FreshnessStatus.UNKNOWN,
        }
        runtime_state = (
            SufficiencyState.QUANTIFIED if not has_blocking_gate else SufficiencyState.QUALITATIVE_ONLY
        )

        primary = _normalize_candidate(all_candidates[0]) if all_candidates else {
            "canonical_document_key": f"{jurisdiction}::unknown",
            "dedupe_group": "unknown",
        }
        policy_identifier = str(primary.get("dedupe_group") or primary["canonical_document_key"])

        created_at = _parse_datetime(str((economic_hints or {}).get("created_at") or ""))

        package = PolicyEvidencePackage(
            package_id=package_id,
            jurisdiction=jurisdiction,
            canonical_document_key=primary["canonical_document_key"],
            policy_identifier=policy_identifier,
            created_at=created_at,
            source_lanes=sorted(source_lanes, key=lambda lane: lane.value),
            scraped_sources=scraped_sources,
            structured_sources=structured_sources,
            evidence_cards=evidence_cards,
            parameter_cards=parameter_cards,
            assumption_cards=assumption_cards,
            model_cards=[],
            gate_report=gate_report,
            gate_projection=GateProjection(
                runtime_sufficiency_state=runtime_state,
                runtime_insufficiency_reason=(
                    "blocking gate present or missing quantitative support"
                    if has_blocking_gate
                    else None
                ),
                runtime_failure_codes=[] if not has_blocking_gate else [FailureCode.PARAMETER_MISSING],
                canonical_breakdown_ref=str((economic_hints or {}).get("canonical_breakdown_ref") or ""),
                canonical_pipeline_run_id=str((economic_hints or {}).get("canonical_pipeline_run_id") or ""),
                canonical_pipeline_step_id=str((economic_hints or {}).get("canonical_pipeline_step_id") or ""),
            ),
            assumption_usage=[],
            storage_refs=_build_storage_refs(storage_refs),
            freshness_status=freshness_map.get(freshness_raw, FreshnessStatus.UNKNOWN),
            economic_handoff_ready=(not has_blocking_gate),
            insufficiency_reasons=sorted(insufficiency_reasons, key=lambda reason: reason.value),
        )
        return package.model_dump(mode="json")
