"""Template-driven non-fee policy fact extraction for data-moat packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Any


@dataclass(frozen=True)
class NonFeeExtractionTemplate:
    template_id: str
    policy_family: str
    evidence_use: str
    economic_relevance: str
    action_type: str
    applicability: str
    moat_value_reason: str
    patterns: tuple[str, ...]
    example_text: str
    example_source_locator: str


_TEMPLATES: tuple[NonFeeExtractionTemplate, ...] = (
    NonFeeExtractionTemplate(
        template_id="tmpl-zoning-land-use-v1",
        policy_family="zoning_land_use",
        evidence_use="policy_lineage_source",
        economic_relevance="indirect",
        action_type="zoning_or_land_use_change",
        applicability="district_or_overlay_specific",
        moat_value_reason=(
            "policy_lineage_source:zoning_land_use:captures enforceable land-use lineage that is reusable even "
            "before quantitative calibration."
        ),
        patterns=(
            r"\bzoning\b",
            r"\bland\s+use\b",
            r"\brezon(?:e|ing)\b",
            r"\boverlay\s+district\b",
            r"\bgeneral\s+plan\b",
        ),
        example_text="Council adopted rezoning and overlay district updates for mixed-use parcels.",
        example_source_locator="structured_template:zoning_land_use",
    ),
    NonFeeExtractionTemplate(
        template_id="tmpl-parking-tdm-v1",
        policy_family="parking_policy",
        evidence_use="compliance_rule_source",
        economic_relevance="indirect",
        action_type="parking_or_tdm_standard_update",
        applicability="project_type_and_location_specific",
        moat_value_reason=(
            "compliance_rule_source:parking_policy:preserves parking/TDM requirements that affect project design, "
            "cost burden assumptions, and policy lineage."
        ),
        patterns=(
            r"\bparking\b",
            r"\bminimum\s+parking\b",
            r"\bparking\s+ratio\b",
            r"\btdm\b",
            r"\btransportation\s+demand\s+management\b",
        ),
        example_text="Transportation demand management ordinance reduces parking minimums downtown.",
        example_source_locator="structured_template:parking_policy",
    ),
    NonFeeExtractionTemplate(
        template_id="tmpl-business-compliance-v1",
        policy_family="business_compliance",
        evidence_use="compliance_rule_source",
        economic_relevance="indirect",
        action_type="business_license_or_inspection_rule",
        applicability="business_activity_or_sector_specific",
        moat_value_reason=(
            "compliance_rule_source:business_compliance:records licensing and inspection obligations that remain "
            "valuable even when direct economic quantification is deferred."
        ),
        patterns=(
            r"\bbusiness\s+license\b",
            r"\blicensing\b",
            r"\binspection\b",
            r"\bcode\s+enforcement\b",
            r"\bcompliance\b",
        ),
        example_text="Business licensing compliance schedule updated with annual inspection requirements.",
        example_source_locator="structured_template:business_compliance",
    ),
    NonFeeExtractionTemplate(
        template_id="tmpl-meeting-action-lineage-v1",
        policy_family="meeting_action",
        evidence_use="meeting_record",
        economic_relevance="contextual",
        action_type="council_or_committee_action_lineage",
        applicability="jurisdiction_wide_governance_record",
        moat_value_reason=(
            "meeting_record:meeting_action:preserves action lineage, adoption timing, and provenance for durable "
            "policy history even without immediate economic handoff."
        ),
        patterns=(
            r"\bmeeting\b",
            r"\bagenda\b",
            r"\bminutes\b",
            r"\bcouncil\b",
            r"\bresolution\b",
            r"\bordinance\b",
            r"\badopt(?:ed|ion)\b",
        ),
        example_text="Council meeting minutes show ordinance adoption and final vote action.",
        example_source_locator="structured_template:meeting_action",
    ),
)


def non_fee_extraction_templates() -> list[dict[str, Any]]:
    """Return machine-readable extraction template definitions."""
    rows: list[dict[str, Any]] = []
    for template in _TEMPLATES:
        rows.append(
            {
                "template_id": template.template_id,
                "policy_family": template.policy_family,
                "evidence_use": template.evidence_use,
                "economic_relevance": template.economic_relevance,
                "action_type": template.action_type,
                "applicability": template.applicability,
                "moat_value_reason": template.moat_value_reason,
                "patterns": list(template.patterns),
                "example": {
                    "text": template.example_text,
                    "source_locator": template.example_source_locator,
                },
            }
        )
    return rows


def _clip_source_excerpt(*, text: str, pattern: str, window: int = 180) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        collapsed = " ".join(text.split())
        return collapsed[:window].strip()
    start = max(0, match.start() - int(window / 3))
    end = min(len(text), match.end() + int(window / 2))
    return " ".join(text[start:end].split()).strip()


def extract_non_fee_policy_facts(
    *,
    text: str,
    source_url: str,
    source_family: str,
    jurisdiction: str,
    retrieved_at: str | None = None,
    source_locator_prefix: str = "structured_template",
    geography: str = "jurisdiction_wide",
) -> list[dict[str, Any]]:
    """Extract structured non-fee policy facts from lightweight text context."""
    normalized_text = str(text or "").strip()
    if not normalized_text:
        return []

    retrieved = str(retrieved_at or "").strip() or datetime.now(UTC).isoformat()
    facts: list[dict[str, Any]] = []
    seen_templates: set[str] = set()
    for template in _TEMPLATES:
        if template.template_id in seen_templates:
            continue
        if not any(re.search(pattern, normalized_text, flags=re.IGNORECASE) for pattern in template.patterns):
            continue
        seen_templates.add(template.template_id)
        facts.append(
            {
                "field": "non_fee_policy_signal",
                "value": 1.0,
                "unit": "count",
                "policy_family": template.policy_family,
                "evidence_use": template.evidence_use,
                "economic_relevance": template.economic_relevance,
                "jurisdiction": jurisdiction,
                "geography": geography,
                "applicability": template.applicability,
                "action_type": template.action_type,
                "source_url": source_url,
                "source_family": source_family,
                "source_locator": f"{source_locator_prefix}:{template.template_id}",
                "source_excerpt": _clip_source_excerpt(
                    text=normalized_text,
                    pattern=template.patterns[0],
                ),
                "effective_date": "unknown",
                "adoption_date": "unknown",
                "retrieved_at": retrieved,
                "moat_value_reason": template.moat_value_reason,
                "template_id": template.template_id,
            }
        )
    return facts
