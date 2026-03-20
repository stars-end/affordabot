"""Persistence adapter from EvidenceEnvelope to Affordabot impact evidence.

Preserves required provenance fields: id, kind, url, excerpt, content_hash,
derived_from, tool_name, tool_args, confidence.

Feature-Key: bd-tytc.2
"""

from __future__ import annotations

from typing import List

from schemas.analysis import ImpactEvidence, PersistedEvidence, SourceTier


TIER_A_DOMAINS = {
    ".gov",
    ".ca.gov",
    ".leginfo.ca.gov",
    ".senate.ca.gov",
    ".assembly.ca.gov",
    ".lao.ca.gov",
    ".ebudget.ca.gov",
    ".cbo.gov",
    ".gao.gov",
    ".bls.gov",
    ".census.gov",
}

TIER_B_DOMAINS = {
    ".org",
    ".edu",
}


def _classify_tier(url: str) -> SourceTier | None:
    if not url:
        return None
    lower = url.lower()
    for domain in TIER_A_DOMAINS:
        if domain in lower:
            return SourceTier.TIER_A
    for domain in TIER_B_DOMAINS:
        if domain in lower:
            return SourceTier.TIER_B
    return SourceTier.TIER_C


def envelope_to_persisted_evidence(envelope_data: dict) -> List[PersistedEvidence]:
    """Convert an EvidenceEnvelope-compatible dict to a list of PersistedEvidence.

    The input is expected to have the shape of an EvidenceEnvelope serialized
    via model_dump(), with an 'evidence' key containing a list of evidence dicts.

    Each evidence dict should have the fields from llm_common.agents.provenance.Evidence.
    """
    evidence_list = envelope_data.get("evidence", [])
    if isinstance(evidence_list, dict):
        evidence_list = [evidence_list]

    results: List[PersistedEvidence] = []
    for item in evidence_list:
        if not isinstance(item, dict):
            continue
        results.append(
            PersistedEvidence(
                id=item.get("id", ""),
                kind=item.get("kind", ""),
                url=item.get("url", ""),
                excerpt=item.get("excerpt"),
                content_hash=item.get("content_hash"),
                derived_from=item.get("derived_from", []),
                tool_name=item.get("tool_name"),
                tool_args=item.get("tool_args"),
                confidence=item.get("confidence"),
                source_name=item.get("label", item.get("source_name", "")),
                label=item.get("label"),
            )
        )
    return results


def persisted_to_impact_evidence(
    persisted: PersistedEvidence,
) -> ImpactEvidence:
    """Convert a PersistedEvidence back to an ImpactEvidence for the analysis schema."""
    return ImpactEvidence(
        source_name=persisted.source_name or persisted.label or "",
        url=persisted.url or "",
        excerpt=persisted.excerpt or "",
        source_tier=_classify_tier(persisted.url),
        persisted_evidence_id=persisted.id or None,
        persisted_evidence_kind=persisted.kind or None,
    )


def envelope_to_impact_evidence(envelope_data: dict) -> List[ImpactEvidence]:
    """Full pipeline: EvidenceEnvelope dict -> PersistedEvidence -> ImpactEvidence."""
    persisted_list = envelope_to_persisted_evidence(envelope_data)
    return [persisted_to_impact_evidence(p) for p in persisted_list]


def research_data_to_evidence_items(
    research_data: List[dict],
) -> List[ImpactEvidence]:
    """Convert legacy research_data dicts to ImpactEvidence items.

    This handles the current output from _research_step() which returns
    loosely-structured dicts from ResearchAgent. Each dict may have
    'url', 'title', 'snippet', 'content', 'source' keys.
    """
    results: List[ImpactEvidence] = []
    for item in research_data:
        if not isinstance(item, dict):
            continue
        url = item.get("url", "") or item.get("source", "")
        name = (
            item.get("title", "")
            or item.get("source_name", "")
            or item.get("domain", "")
            or ""
        )
        excerpt = (
            item.get("snippet", "")
            or item.get("excerpt", "")
            or item.get("content", "")[:500]
            or ""
        )
        results.append(
            ImpactEvidence(
                source_name=name,
                url=url,
                excerpt=excerpt,
                source_tier=_classify_tier(url),
            )
        )
    return results
