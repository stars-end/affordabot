"""Deterministic evidence sufficiency gates.

Runs before generation to decide whether quantified output is permitted.
All checks are programmatic.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from schemas.analysis import (
    ExcerptValidationStatus,
    FailureCode,
    ImpactGateSummary,
    ImpactEvidence,
    ImpactMode,
    ParameterResolutionOutput,
    ParameterValidationOutput,
    RetrievalPrerequisiteStatus,
    SourceHierarchyStatus,
    SourceTier,
    SufficiencyBreakdown,
    SufficiencyState,
)

PLACEHOLDER_PATTERNS = [
    r"^Introduced$",
    r"^Title only",
    r"^placeholder",
    r"^N/A$",
    r"^TBD$",
    r"^unknown",
    r"^no text",
    r"^not available",
    r"^summary only",
]

FISCAL_NOTE_INDICATORS = [
    "fiscal note",
    "fiscal impact",
    "cost estimate",
    "budget analysis",
    "appropriation",
    "fiscal committee",
    "legislative analyst",
]

QUANTIFIED_SUPPORT_INDICATORS = [
    "annual cost",
    "annual savings",
    "monthly cost",
    "monthly savings",
    "per household",
    "general fund",
    "appropriation",
    "reimbursement",
    "estimated at",
]

FISCAL_SUPPORT_KEYWORDS = [
    "fiscal",
    "budget",
    "appropriation",
    "cost",
    "costs",
    "expense",
    "expenses",
    "expenditure",
    "revenue",
    "funding",
    "savings",
    "fee",
    "fees",
    "tax",
    "taxes",
    "estimate",
    "estimated",
    "projection",
    "projected",
    "per year",
    "annual",
    "annually",
]

NUMERIC_SUPPORT_PATTERNS = (
    r"\$\s?\d",
    r"\d[\d,]*(?:\.\d+)?\s*(?:million|billion|thousand|m|k|bn)\b",
    r"\d[\d,]*(?:\.\d+)?\s*%",
    r"\b\d[\d,]*(?:\.\d+)?\b",
)

SUPPORTED_MODES = {
    ImpactMode.DIRECT_FISCAL,
    ImpactMode.COMPLIANCE_COST,
    ImpactMode.PASS_THROUGH_INCIDENCE,
    ImpactMode.ADOPTION_TAKE_UP,
}

WAVE2_LITERATURE_CONFIDENCE_MIN = 0.6


def _is_placeholder_text(text: str) -> bool:
    if not text or not text.strip():
        return True
    lower = text.strip().lower()
    return any(re.match(p, lower, re.IGNORECASE) for p in PLACEHOLDER_PATTERNS)


def _has_verifiable_url(evidence_list: List[ImpactEvidence]) -> bool:
    return any(
        e.url.startswith(("http://", "https://")) and len(e.url) > 15
        for e in evidence_list
        if e.url
    )


def _count_tier_a(evidence_list: List[ImpactEvidence]) -> int:
    from services.llm.evidence_adapter import _classify_tier

    count = sum(1 for e in evidence_list if e.source_tier == SourceTier.TIER_A)
    if count == 0:
        count = sum(
            1 for e in evidence_list if _classify_tier(e.url) == SourceTier.TIER_A
        )
    return count


def _detect_fiscal_notes(evidence_list: List[ImpactEvidence]) -> bool:
    for e in evidence_list:
        lower_excerpt = (e.excerpt or "").lower()
        lower_name = (e.source_name or "").lower()
        combined = f"{lower_excerpt} {lower_name}"
        if any(indicator in combined for indicator in FISCAL_NOTE_INDICATORS):
            return True
    return False


def _normalize_mode(mode: Any) -> ImpactMode:
    try:
        return ImpactMode(mode)
    except Exception:
        return ImpactMode.QUALITATIVE_ONLY


def _normalize_parameter_resolution(
    payload: ParameterResolutionOutput | Dict[str, Any] | None,
) -> ParameterResolutionOutput:
    if isinstance(payload, ParameterResolutionOutput):
        return payload
    if isinstance(payload, dict):
        return ParameterResolutionOutput(**payload)
    return ParameterResolutionOutput()


def _normalize_parameter_validation(
    payload: ParameterValidationOutput | Dict[str, Any] | None,
) -> ParameterValidationOutput:
    if isinstance(payload, ParameterValidationOutput):
        return payload
    if isinstance(payload, dict):
        return ParameterValidationOutput(**payload)
    return ParameterValidationOutput()


def _resolve_frequency_hierarchy(
    resolution: ParameterResolutionOutput,
) -> SourceHierarchyStatus:
    frequency_status = resolution.source_hierarchy_status.get("frequency")
    if frequency_status in (
        SourceHierarchyStatus.BILL_OR_REG_TEXT,
        SourceHierarchyStatus.FISCAL_OR_REG_IMPACT_ANALYSIS,
    ):
        return frequency_status
    return SourceHierarchyStatus.FAILED_CLOSED


def _wave2_literature_confidence_valid(
    mode: ImpactMode, resolution: ParameterResolutionOutput
) -> bool:
    if mode == ImpactMode.PASS_THROUGH_INCIDENCE:
        value = resolution.literature_confidence.get("pass_through_rate")
    elif mode == ImpactMode.ADOPTION_TAKE_UP:
        value = resolution.literature_confidence.get("take_up_rate")
    else:
        return True
    if value is None:
        return False
    try:
        return float(value) >= WAVE2_LITERATURE_CONFIDENCE_MIN
    except (TypeError, ValueError):
        return False


def _derive_retrieval_status(
    bill_text: str,
    evidence_list: List[ImpactEvidence],
    rag_chunks_retrieved: int,
    web_research_count: int,
) -> RetrievalPrerequisiteStatus:
    _ = web_research_count  # Explicitly tracked for audit surfaces upstream.
    return RetrievalPrerequisiteStatus(
        source_text_present=bool(bill_text and bill_text.strip())
        and not _is_placeholder_text(bill_text),
        rag_chunks_retrieved=rag_chunks_retrieved,
        web_research_sources_found=web_research_count,
        has_verifiable_url=_has_verifiable_url(evidence_list),
    )


def assess_impact_sufficiency(
    impact_id: str,
    selected_mode: ImpactMode | str,
    parameter_resolution: ParameterResolutionOutput | Dict[str, Any] | None,
    parameter_validation: ParameterValidationOutput | Dict[str, Any] | None,
    retrieval_prerequisite_status: RetrievalPrerequisiteStatus | Dict[str, Any] | None,
) -> ImpactGateSummary:
    """Evaluate deterministic sufficiency for a single impact."""
    failures: List[FailureCode] = []
    mode = _normalize_mode(selected_mode)
    resolution = _normalize_parameter_resolution(parameter_resolution)
    validation = _normalize_parameter_validation(parameter_validation)

    retrieval_status = (
        retrieval_prerequisite_status
        if isinstance(retrieval_prerequisite_status, RetrievalPrerequisiteStatus)
        else RetrievalPrerequisiteStatus(**(retrieval_prerequisite_status or {}))
    )
    if (
        not retrieval_status.source_text_present
        or retrieval_status.rag_chunks_retrieved <= 0
        or not retrieval_status.has_verifiable_url
    ):
        failures.append(FailureCode.IMPACT_DISCOVERY_FAILED)

    if mode not in SUPPORTED_MODES:
        if mode != ImpactMode.QUALITATIVE_ONLY:
            failures.append(FailureCode.MODE_SELECTION_FAILED)
        return ImpactGateSummary(
            impact_id=impact_id,
            selected_mode=ImpactMode.QUALITATIVE_ONLY,
            quantification_eligible=False,
            sufficiency_state=SufficiencyState.QUALITATIVE_ONLY,
            gate_failures=failures,
            parameter_validation_summary=validation,
            retrieval_prerequisite_status=retrieval_status,
        )

    if resolution.missing_parameters:
        failures.append(FailureCode.PARAMETER_MISSING)

    for status in resolution.source_hierarchy_status.values():
        if status == SourceHierarchyStatus.FAILED_CLOSED:
            failures.append(FailureCode.SOURCE_HIERARCHY_FAILED)
            break

    for status in resolution.excerpt_validation_status.values():
        if status == ExcerptValidationStatus.FAIL:
            failures.append(FailureCode.EXCERPT_VALIDATION_FAILED)
            failures.append(FailureCode.PARAMETER_UNVERIFIABLE)
            break

    # Wave 1 binding note: literature_confidence is informational only.
    # Do not gate on confidence values in this wave.
    if mode == ImpactMode.COMPLIANCE_COST:
        frequency_status = _resolve_frequency_hierarchy(resolution)
        if frequency_status == SourceHierarchyStatus.FAILED_CLOSED:
            failures.append(FailureCode.SOURCE_HIERARCHY_FAILED)
    elif mode in (
        ImpactMode.PASS_THROUGH_INCIDENCE,
        ImpactMode.ADOPTION_TAKE_UP,
    ):
        if not _wave2_literature_confidence_valid(mode, resolution):
            failures.append(FailureCode.PARAMETER_UNVERIFIABLE)

    if not validation.schema_valid:
        failures.append(FailureCode.VALIDATION_FAILED)
    if not validation.arithmetic_valid:
        failures.append(FailureCode.VALIDATION_FAILED)
    if not validation.bound_construction_valid:
        failures.append(FailureCode.INVALID_SCENARIO_CONSTRUCTION)
    if not validation.claim_support_valid:
        failures.append(FailureCode.PARAMETER_UNVERIFIABLE)

    deduped_failures = list(dict.fromkeys(failures))
    quantification_eligible = len(deduped_failures) == 0

    sufficiency_state = (
        SufficiencyState.QUANTIFIED
        if quantification_eligible
        else (
            SufficiencyState.RESEARCH_INCOMPLETE
            if FailureCode.IMPACT_DISCOVERY_FAILED in deduped_failures
            else SufficiencyState.QUALITATIVE_ONLY
        )
    )

    return ImpactGateSummary(
        impact_id=impact_id,
        selected_mode=mode,
        quantification_eligible=quantification_eligible,
        sufficiency_state=sufficiency_state,
        gate_failures=deduped_failures,
        parameter_validation_summary=validation,
        retrieval_prerequisite_status=retrieval_status,
    )


def supports_quantified_evidence(
    excerpt: str,
    source_name: str = "",
    numeric_basis: str | None = None,
) -> bool:
    """Return true when evidence contains materially supportive numeric fiscal basis."""
    combined = " ".join(
        part for part in [excerpt or "", source_name or "", numeric_basis or ""] if part
    ).lower()
    has_numeric_signal = bool(
        re.search(
            r"\$\s?\d|\b\d+(?:\.\d+)?\s*(?:million|billion|thousand|m|k|%)\b|\bper (?:month|year|household)\b",
            combined,
        )
    )
    has_fiscal_signal = any(
        indicator in combined
        for indicator in FISCAL_NOTE_INDICATORS + QUANTIFIED_SUPPORT_INDICATORS
    )
    return has_numeric_signal and has_fiscal_signal


def has_material_fiscal_numeric_support(excerpt: str, source_name: str = "") -> bool:
    """Return True only when excerpt carries concrete fiscal/numeric support."""
    normalized = re.sub(r"\s+", " ", excerpt or "").strip()
    if len(normalized) < 80:
        return False

    combined = f"{normalized.lower()} {(source_name or '').lower()}"
    has_fiscal_context = any(keyword in combined for keyword in FISCAL_SUPPORT_KEYWORDS)
    has_numeric_signal = any(
        re.search(pattern, normalized.lower()) for pattern in NUMERIC_SUPPORT_PATTERNS
    )
    return has_fiscal_context and has_numeric_signal


def assess_sufficiency(
    bill_text: str,
    evidence_list: List[ImpactEvidence],
    candidate_impacts: List[Dict[str, Any]] | None = None,
    rag_chunks_retrieved: int = 0,
    web_research_count: int = 0,
) -> SufficiencyBreakdown:
    """Derive bill-level sufficiency from per-impact gate evaluations."""
    candidate_impacts = candidate_impacts or []
    bill_level_failures: List[FailureCode] = []
    retrieval_status = _derive_retrieval_status(
        bill_text=bill_text,
        evidence_list=evidence_list,
        rag_chunks_retrieved=rag_chunks_retrieved,
        web_research_count=web_research_count,
    )

    if not candidate_impacts:
        bill_level_failures.append(FailureCode.IMPACT_DISCOVERY_FAILED)

    impact_gate_summaries = []
    for idx, impact in enumerate(candidate_impacts, start=1):
        summary = assess_impact_sufficiency(
            impact_id=str(impact.get("impact_id") or f"impact-{idx}"),
            selected_mode=impact.get("selected_mode", ImpactMode.QUALITATIVE_ONLY),
            parameter_resolution=impact.get("parameter_resolution"),
            parameter_validation=impact.get("parameter_validation"),
            retrieval_prerequisite_status=impact.get(
                "retrieval_prerequisite_status", retrieval_status.model_dump()
            ),
        )
        impact_gate_summaries.append(summary)

    overall_quantification_eligible = any(
        item.quantification_eligible for item in impact_gate_summaries
    )
    if not retrieval_status.source_text_present:
        overall_sufficiency_state = SufficiencyState.RESEARCH_INCOMPLETE
    elif not retrieval_status.has_verifiable_url or retrieval_status.rag_chunks_retrieved <= 0:
        overall_sufficiency_state = SufficiencyState.INSUFFICIENT_EVIDENCE
    elif overall_quantification_eligible:
        overall_sufficiency_state = SufficiencyState.QUANTIFIED
    else:
        overall_sufficiency_state = SufficiencyState.QUALITATIVE_ONLY

    for summary in impact_gate_summaries:
        bill_level_failures.extend(summary.gate_failures)

    return SufficiencyBreakdown(
        overall_quantification_eligible=overall_quantification_eligible,
        overall_sufficiency_state=overall_sufficiency_state,
        impact_gate_summaries=impact_gate_summaries,
        bill_level_failures=list(dict.fromkeys(bill_level_failures)),
    )


def strip_quantification(
    impacts: List[dict],
) -> List[dict]:
    """Strip quantitative payloads when an impact must degrade to qualitative_only."""
    cleaned = []
    for imp in impacts:
        imp = dict(imp)
        imp["impact_mode"] = ImpactMode.QUALITATIVE_ONLY.value
        imp.pop("modeled_parameters", None)
        imp.pop("component_breakdown", None)
        imp.pop("scenario_bounds", None)
        imp.pop("aggregate_scenario_bounds", None)
        cleaned.append(imp)
    return cleaned
