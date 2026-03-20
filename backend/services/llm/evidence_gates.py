"""Deterministic evidence sufficiency gates.

Runs BEFORE generation to decide whether quantified output is permitted.
All checks are programmatic — no LLM involvement.

Feature-Key: bd-tytc.2
"""

from __future__ import annotations

import re
from typing import List

from schemas.analysis import (
    ImpactEvidence,
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


def assess_sufficiency(
    bill_text: str,
    evidence_list: List[ImpactEvidence],
    rag_chunks_retrieved: int = 0,
    web_research_count: int = 0,
) -> SufficiencyBreakdown:
    """Run deterministic sufficiency gates.

    Returns a SufficiencyBreakdown with the final state and reasons.
    """
    reasons: List[str] = []
    bill_text_present = bool(bill_text and bill_text.strip())
    bill_text_is_placeholder = (
        _is_placeholder_text(bill_text) if bill_text_present else True
    )
    has_url = _has_verifiable_url(evidence_list)
    tier_a_count = _count_tier_a(evidence_list)
    has_fiscal = _detect_fiscal_notes(evidence_list)
    source_text_ok = bill_text_present and not bill_text_is_placeholder

    if not source_text_ok:
        reasons.append("Bill text is absent or placeholder")
    if not evidence_list:
        reasons.append("No evidence items collected")
    if not has_url:
        reasons.append("No evidence items have verifiable HTTP(S) URLs")

    if source_text_ok and has_url and len(evidence_list) > 0 and len(reasons) == 0:
        if tier_a_count > 0 and has_fiscal:
            state = SufficiencyState.QUANTIFIED
            quantification_eligible = True
        elif tier_a_count > 0:
            state = SufficiencyState.QUALITATIVE_ONLY
            reasons.append(
                "Tier A sources found but no fiscal note/official cost estimate detected"
            )
            quantification_eligible = False
        elif has_url:
            state = SufficiencyState.QUALITATIVE_ONLY
            reasons.append(
                "Only Tier B/C sources available; Tier A (official fiscal) source required for quantification"
            )
            quantification_eligible = False
        else:
            state = SufficiencyState.QUALITATIVE_ONLY
            quantification_eligible = False
    elif not source_text_ok:
        state = SufficiencyState.RESEARCH_INCOMPLETE
        quantification_eligible = False
    else:
        state = SufficiencyState.INSUFFICIENT_EVIDENCE
        quantification_eligible = False

    return SufficiencyBreakdown(
        bill_text_present=bill_text_present,
        bill_text_is_placeholder=bill_text_is_placeholder,
        rag_chunks_retrieved=rag_chunks_retrieved,
        web_research_sources_found=web_research_count,
        tier_a_sources_found=tier_a_count,
        fiscal_notes_detected=has_fiscal,
        has_verifiable_url=has_url,
        source_text_present=source_text_ok,
        sufficiency_state=state,
        insufficiency_reasons=reasons,
        quantification_eligible=quantification_eligible,
    )


def strip_quantification(
    impacts: List[dict],
) -> List[dict]:
    """Remove percentile fields from impacts when quantification is not eligible.

    Used as a post-generation safety net to ensure no quantified output
    leaks through even if the LLM ignores the sufficiency instruction.
    """
    cleaned = []
    for imp in impacts:
        imp = dict(imp)
        for key in ("p10", "p25", "p50", "p75", "p90"):
            imp.pop(key, None)
        imp.pop("numeric_basis", None)
        imp.pop("estimate_method", None)
        imp.pop("assumptions", None)
        cleaned.append(imp)
    return cleaned
