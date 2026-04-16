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

_DIAGNOSTIC_PARAMETER_FIELDS = {
    "event_attachment_hint_count",
    "ckan_dataset_count",
    "provider_result_count",
}

_ECONOMIC_PARAMETER_SIGNALS = {
    "affected_household",
    "baseline_permit",
    "cost",
    "fee",
    "household",
    "permit_volume",
    "price",
    "rate",
    "rent",
    "tax",
    "usd",
    "wage",
}


def _source_tier_rank(value: str) -> int:
    mapping = {"tier_a": 0, "tier_b": 1, "tier_c": 2}
    return mapping.get(str(value or "").strip().lower(), 3)


def _source_lane_rank(value: str) -> int:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("structured"):
        return 0
    if normalized == "scrape_search":
        return 1
    return 2


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


def _is_economic_parameter_name(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized or normalized in _DIAGNOSTIC_PARAMETER_FIELDS:
        return False
    return any(signal in normalized for signal in _ECONOMIC_PARAMETER_SIGNALS)


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
    normalized = str(value or "").strip().lower()
    if normalized in {"structured", "structured_primary"}:
        return SourceLane.STRUCTURED
    if normalized.startswith("structured_"):
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
    raw_lane = str(candidate.get("source_lane") or "").strip().lower()
    default_true_structured = not raw_lane.startswith("structured_secondary")
    normalized["true_structured"] = bool(candidate.get("true_structured", default_true_structured))
    normalized["policy_match_key"] = str(candidate.get("policy_match_key") or "").strip()
    normalized["policy_match_confidence"] = candidate.get("policy_match_confidence")
    normalized["reconciliation_status"] = str(candidate.get("reconciliation_status") or "").strip()
    lineage = candidate.get("lineage_metadata")
    normalized["lineage_metadata"] = lineage if isinstance(lineage, dict) else {}
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
    if source_lane.startswith("structured_secondary"):
        fail_reasons.append("secondary_search_not_true_structured")
    return (len(fail_reasons) == 0, sorted(set(fail_reasons)))


def _policy_match_key(candidate: dict[str, Any]) -> str:
    explicit = str(candidate.get("policy_match_key") or "").strip()
    if explicit:
        return explicit
    dedupe_group = str(candidate.get("dedupe_group") or "").strip()
    if dedupe_group:
        return dedupe_group
    return str(candidate.get("canonical_document_key") or "").strip()


def _reconciles_with_primary(*, primary_keys: set[str], candidate: dict[str, Any]) -> bool:
    if not primary_keys:
        return True
    candidate_keys = {
        _policy_match_key(candidate),
        str(candidate.get("canonical_document_key") or "").strip(),
        str(candidate.get("dedupe_group") or "").strip(),
        str(candidate.get("artifact_url") or "").strip(),
    }
    candidate_keys = {key for key in candidate_keys if key}
    return bool(primary_keys.intersection(candidate_keys))


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
        raw_value = fact.get("normalized_value", fact.get("value"))
        value: float | None = None
        if isinstance(raw_value, (int, float)):
            value = float(raw_value)
        elif isinstance(raw_value, str):
            cleaned = raw_value.replace(",", "").strip()
            try:
                value = float(cleaned)
            except ValueError:
                value = None
        name = str(fact.get("field") or "").strip() or "unknown_parameter"
        if not _is_economic_parameter_name(name):
            continue
        source_url = str(fact.get("source_url") or candidate["artifact_url"] or "https://example.org/unknown")
        excerpt_base = (
            str(fact.get("source_excerpt") or "").strip()
            or f"Structured fact {name} resolved from source payload."
        )
        raw_token = str(fact.get("raw_value") or "").strip()
        unit = str(fact.get("unit") or "unitless")
        denominator = str(fact.get("denominator") or "").strip()
        category = str(fact.get("category") or "").strip()
        effective_date = str(fact.get("effective_date") or "").strip()
        confidence = fact.get("confidence")
        citation_parts: list[str] = []
        if raw_token:
            citation_parts.append(f"raw={raw_token}")
        if value is not None:
            citation_parts.append(f"normalized={value}")
        if unit:
            citation_parts.append(f"unit={unit}")
        if denominator:
            citation_parts.append(f"denominator={denominator}")
        if category:
            citation_parts.append(f"category={category}")
        if effective_date:
            citation_parts.append(f"effective_date={effective_date}")
        if isinstance(confidence, (int, float)):
            citation_parts.append(f"confidence={float(confidence):.2f}")
        source_excerpt = excerpt_base
        if citation_parts:
            source_excerpt = f"{excerpt_base} [{' ; '.join(citation_parts)}]"
        hierarchy_raw = str(fact.get("source_hierarchy_status") or "").strip()
        hierarchy = (
            SourceHierarchyStatus.BILL_OR_REG_TEXT
            if hierarchy_raw == SourceHierarchyStatus.BILL_OR_REG_TEXT.value
            else SourceHierarchyStatus.FISCAL_OR_REG_IMPACT_ANALYSIS
        )
        ambiguity_flag = bool(fact.get("ambiguity_flag"))
        currency_sanity = str(fact.get("currency_sanity") or "").strip().lower()
        unit_sanity = str(fact.get("unit_sanity") or "").strip().lower()
        ambiguity_reason = str(fact.get("ambiguity_reason") or "").strip()
        if not ambiguity_reason and (
            value is None or ambiguity_flag or currency_sanity == "invalid" or unit_sanity == "invalid"
        ):
            ambiguity_reason = "parameter_requires_manual_reconciliation"
        state = ParameterState.RESOLVED if value is not None and not ambiguity_reason else ParameterState.AMBIGUOUS
        cards.append(
            ParameterCard(
                id=f"param-{len(cards)+1}-{_slug(name)}",
                parameter_name=name,
                state=state,
                value=value if state == ParameterState.RESOLVED else None,
                unit=unit,
                time_horizon=effective_date or None,
                source_url=source_url,
                source_excerpt=source_excerpt,
                source_hierarchy_status=hierarchy,
                ambiguity_reason=ambiguity_reason or None,
                evidence_card_id=evidence_id,
            )
        )
    return cards


def _build_storage_refs(
    storage_refs: dict[str, Any] | None,
    *,
    canonical_candidates: list[dict[str, Any]],
) -> list[StorageRef]:
    refs = storage_refs or {}
    canonical_hash = ""
    for candidate in canonical_candidates:
        candidate_hash = str(candidate.get("content_hash") or "").strip()
        if candidate_hash and not candidate_hash.startswith("missing_hash::"):
            canonical_hash = candidate_hash
            break
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
            content_hash=canonical_hash or None,
        ),
        StorageRef(
            storage_system=StorageSystem.MINIO,
            truth_role=StorageTruthRole.ARTIFACT_OF_RECORD,
            reference_id=minio_ref,
            uri=minio_ref,
            content_hash=canonical_hash or None,
            notes="readback proof pending bd-3wefe.10",
        ),
        StorageRef(
            storage_system=StorageSystem.PGVECTOR,
            truth_role=StorageTruthRole.DERIVED_INDEX,
            reference_id=pgvector_ref,
            content_hash=canonical_hash or None,
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
        primary_scraped = [
            _normalize_candidate(item)
            for item in (scraped_candidates or [])
        ]
        primary_policy_keys = {
            _policy_match_key(item)
            for item in primary_scraped
            if _policy_match_key(item)
        }
        primary_policy_keys.update(
            str(item.get("canonical_document_key") or "").strip()
            for item in primary_scraped
            if str(item.get("canonical_document_key") or "").strip()
        )

        evidence_cards: list[EvidenceCard] = []
        parameter_cards: list[ParameterCard] = []
        assumption_cards: list[AssumptionCard] = []
        scraped_sources: list[ScrapedSourceProvenance] = []
        structured_sources: list[StructuredSourceProvenance] = []
        source_lanes: set[SourceLane] = set()
        insufficiency_reasons: set[PackageFailureReason] = set()
        reader_substance_passed = True
        normalized_candidates = [_normalize_candidate(candidate) for candidate in all_candidates]

        canonical_by_dedupe: dict[tuple[str, str, str], dict[str, Any]] = {}
        duplicate_count = 0
        for normalized in normalized_candidates:
            dedupe_key = (
                str(normalized.get("canonical_document_key") or "").strip(),
                str(normalized.get("content_hash") or "").strip(),
                str(normalized.get("source_lane") or "").strip(),
            )
            if not dedupe_key[0]:
                dedupe_key = (f"missing_identity:{duplicate_count}", dedupe_key[1], dedupe_key[2])
            existing = canonical_by_dedupe.get(dedupe_key)
            if existing is None:
                canonical_by_dedupe[dedupe_key] = normalized
                continue
            duplicate_count += 1
            existing_usable, _ = _classify_candidate(existing)
            candidate_usable, _ = _classify_candidate(normalized)
            existing_rank = (
                0 if existing_usable else 1,
                _source_tier_rank(str(existing.get("source_tier") or "")),
                _source_lane_rank(str(existing.get("source_lane") or "")),
            )
            candidate_rank = (
                0 if candidate_usable else 1,
                _source_tier_rank(str(normalized.get("source_tier") or "")),
                _source_lane_rank(str(normalized.get("source_lane") or "")),
            )
            if candidate_rank < existing_rank:
                canonical_by_dedupe[dedupe_key] = normalized

        canonical_candidates = list(canonical_by_dedupe.values())
        true_structured_resolved_parameters = False
        structured_depth_blocked = False

        for idx, normalized in enumerate(canonical_candidates, start=1):
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
                reconciled = _reconciles_with_primary(primary_keys=primary_policy_keys, candidate=normalized)
                reconciliation_status = (
                    str(normalized.get("reconciliation_status") or "").strip()
                    or ("confirmed" if reconciled else "conflict_unresolved")
                )
                if not reconciled and primary_policy_keys:
                    insufficiency_reasons.add(PackageFailureReason.BLOCKING_GATE_PRESENT)
                structured_sources.append(
                    StructuredSourceProvenance(
                        source_family=normalized["source_family"],
                        access_method=str(normalized.get("access_method") or "api_or_file"),
                        endpoint_or_file_url=normalized["artifact_url"] or "https://example.org/unknown",
                        provider_run_id=str(normalized.get("provider_run_id") or "") or None,
                        field_count=len(normalized.get("structured_policy_facts", [])),
                        true_structured=bool(normalized.get("true_structured", True)),
                        policy_match_key=_policy_match_key(normalized) or None,
                        policy_match_confidence=(
                            float(normalized["policy_match_confidence"])
                            if isinstance(normalized.get("policy_match_confidence"), (int, float))
                            else None
                        ),
                        reconciliation_status=reconciliation_status,
                        event_date=str(normalized.get("lineage_metadata", {}).get("event_date") or "") or None,
                        event_body_id=str(normalized.get("lineage_metadata", {}).get("event_body_id") or "") or None,
                        matter_id=str(normalized.get("lineage_metadata", {}).get("matter_id") or "") or None,
                    )
                )

            evidence = _build_evidence_card(normalized, idx)
            evidence_cards.append(evidence)
            candidate_parameter_cards = _build_parameter_cards(normalized, evidence.id)
            parameter_cards.extend(candidate_parameter_cards)
            if (
                source_lane == SourceLane.STRUCTURED
                and bool(normalized.get("true_structured", True))
                and any(
                    card.state == ParameterState.RESOLVED
                    and _is_economic_parameter_name(card.parameter_name)
                    for card in candidate_parameter_cards
                )
            ):
                true_structured_resolved_parameters = True
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
                if reason == "secondary_search_not_true_structured":
                    pass

        if not source_lanes:
            insufficiency_reasons.add(PackageFailureReason.NO_SOURCE_LANES)
        if not evidence_cards:
            insufficiency_reasons.add(PackageFailureReason.NO_EVIDENCE_CARDS)

        has_resolved_parameters = any(card.state == ParameterState.RESOLVED for card in parameter_cards)
        has_resolved_economic_parameters = any(
            card.state == ParameterState.RESOLVED and _is_economic_parameter_name(card.parameter_name)
            for card in parameter_cards
        )
        true_structured_sources = [
            source
            for source in structured_sources
            if source.true_structured
        ]
        if SourceLane.STRUCTURED in source_lanes and not true_structured_sources:
            structured_depth_blocked = True
            insufficiency_reasons.add(PackageFailureReason.BLOCKING_GATE_PRESENT)
        if SourceLane.STRUCTURED in source_lanes and true_structured_sources:
            has_structured_provenance_depth = any(
                source.policy_match_key and source.reconciliation_status in {"confirmed", "contextual_metadata_linked_to_policy_query"}
                for source in true_structured_sources
            )
            if not has_structured_provenance_depth or not true_structured_resolved_parameters:
                structured_depth_blocked = True
                insufficiency_reasons.add(PackageFailureReason.BLOCKING_GATE_PRESENT)
        reader_gate_blocked = SourceLane.SCRAPED in source_lanes and not reader_substance_passed
        if reader_gate_blocked:
            insufficiency_reasons.add(PackageFailureReason.BLOCKING_GATE_PRESENT)
        if not has_resolved_economic_parameters:
            insufficiency_reasons.add(PackageFailureReason.NO_QUANT_SUPPORT_PATH)
        has_blocking_gate = bool(insufficiency_reasons)
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
                passed=has_resolved_economic_parameters and not structured_depth_blocked,
                failure_codes=[]
                if (has_resolved_economic_parameters and not structured_depth_blocked)
                else [FailureCode.PARAMETER_MISSING],
            ),
            GateStageResult(
                stage=QualityGateStage.QUANTIFICATION,
                passed=has_resolved_economic_parameters and not has_blocking_gate,
                failure_codes=[] if (has_resolved_economic_parameters and not has_blocking_gate) else [FailureCode.PARAMETER_UNVERIFIABLE],
            ),
        ]
        blocking_gate = None
        if SourceLane.SCRAPED in source_lanes and not reader_substance_passed:
            blocking_gate = QualityGateStage.READER_SUBSTANCE
        elif not has_resolved_economic_parameters:
            blocking_gate = QualityGateStage.PARAMETERIZATION
        elif has_blocking_gate:
            blocking_gate = QualityGateStage.PARAMETERIZATION

        gate_report = GateReport(
            case_id=f"{package_id}-gate",
            provider=str((scraped_candidates or [{}])[0].get("provider") or "structured_only"),
            verdict=GateVerdict.QUANTIFIED_PASS if not has_blocking_gate else GateVerdict.FAIL_CLOSED,
            stage_results=stage_results,
            blocking_gate=blocking_gate,
            failure_codes=[] if not has_blocking_gate else [FailureCode.PARAMETER_MISSING],
            artifact_counts={"evidence_cards": len(evidence_cards)},
            unsupported_claim_count=0 if not has_blocking_gate else 1,
            manual_audit_notes=(
                "Builder payload with canonical identity dedupe and provenance linkage; "
                f"deduped_candidates={duplicate_count}. Full durability/orchestration gates in bd-3wefe.10/.12."
            ),
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

        primary = canonical_candidates[0] if canonical_candidates else {
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
            storage_refs=_build_storage_refs(
                storage_refs,
                canonical_candidates=canonical_candidates,
            ),
            freshness_status=freshness_map.get(freshness_raw, FreshnessStatus.UNKNOWN),
            economic_handoff_ready=(not has_blocking_gate),
            insufficiency_reasons=sorted(insufficiency_reasons, key=lambda reason: reason.value),
        )
        return package.model_dump(mode="json")
