#!/usr/bin/env python3
"""Scrape + structured source integration verifier (bd-2agbe.11).

Deterministic replay verifier for one merged backend-owned artifact/evidence
envelope contract across:
1) structured source lane (Legistar/LegInfo/CKAN/ArcGIS)
2) scrape/search lane (private SearXNG + Tavily fallback + Exa eval-only)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FEATURE_KEY = "bd-2agbe.11"
POC_VERSION = "2026-04-14.scrape-structured-integration.v1"

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
OUT_JSON = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "source-integration"
    / "artifacts"
    / "scrape_structured_integration_report.json"
)
OUT_MD = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "source-integration"
    / "artifacts"
    / "scrape_structured_integration_report.md"
)

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SCHEMA_IMPORT_ERROR: str | None = None
HAS_SCHEMA_VALIDATION = False

try:
    from schemas.analysis import ImpactMode, SourceTier
    from schemas.economic_evidence import EvidenceCard, EvidenceSourceType, MechanismFamily

    HAS_SCHEMA_VALIDATION = True
except Exception as exc:  # pragma: no cover - fallback path for import issues
    SCHEMA_IMPORT_ERROR = f"{exc.__class__.__name__}: {exc}"
    ImpactMode = None  # type: ignore[assignment]
    SourceTier = None  # type: ignore[assignment]
    EvidenceCard = None  # type: ignore[assignment]
    EvidenceSourceType = None  # type: ignore[assignment]
    MechanismFamily = None  # type: ignore[assignment]


@dataclass(frozen=True)
class VerifierConfig:
    mode: str
    out_json: Path
    out_md: Path
    self_check: bool


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _impact_mode_mapping() -> list[dict[str, Any]]:
    return [
        {
            "impact_mode": "direct_fiscal",
            "mechanism_family": "direct_fiscal",
            "supports_quantified_handoff": True,
            "note": "Direct appropriations/tax spend flows map 1:1.",
        },
        {
            "impact_mode": "compliance_cost",
            "mechanism_family": "compliance_cost",
            "supports_quantified_handoff": True,
            "note": "Regulatory/admin burden costs map 1:1.",
        },
        {
            "impact_mode": "pass_through_incidence",
            "mechanism_family": "fee_or_tax_pass_through",
            "supports_quantified_handoff": True,
            "note": "Explicit normalization required due enum label mismatch.",
        },
        {
            "impact_mode": "adoption_take_up",
            "mechanism_family": "adoption_take_up",
            "supports_quantified_handoff": True,
            "note": "Program participation/uptake mechanics map 1:1.",
        },
        {
            "impact_mode": "qualitative_only",
            "mechanism_family": None,
            "supports_quantified_handoff": False,
            "note": "No economic_evidence mechanism family exists for qualitative-only.",
        },
    ]


def _mapping_lookup() -> dict[str, str | None]:
    return {item["impact_mode"]: item["mechanism_family"] for item in _impact_mode_mapping()}


def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fixture_candidates() -> list[dict[str, Any]]:
    return [
        {
            "source_lane": "structured",
            "provider": "legistar",
            "jurisdiction": "san_jose_ca",
            "artifact_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=13000001&GUID=A-1",
            "artifact_type": "staff_report",
            "source_tier": "tier_a",
            "retrieved_at": "2026-04-14T08:00:00+00:00",
            "selected_impact_mode": "direct_fiscal",
            "structured_policy_facts": [
                {"field": "annual_cost_usd", "value": 2400000.0, "unit": "usd_per_year"},
                {"field": "affected_households", "value": 8000, "unit": "households"},
            ],
            "linked_artifact_refs": [
                "https://sanjose.legistar.com/View.ashx?M=A&ID=13000001&GUID=A-1"
            ],
            "reader_artifact_refs": [],
            "dedupe_group": "sj-13000001-program-cost",
        },
        {
            "source_lane": "scrape_search",
            "provider": "private_searxng",
            "jurisdiction": "san_jose_ca",
            "artifact_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=13000001&GUID=A-1",
            "artifact_type": "staff_report",
            "source_tier": "tier_a",
            "retrieved_at": "2026-04-14T08:05:00+00:00",
            "selected_impact_mode": "direct_fiscal",
            "structured_policy_facts": [],
            "linked_artifact_refs": [],
            "reader_artifact_refs": [
                "https://backend.artifacts/scrape/sj-13000001-program-cost-reader.txt"
            ],
            "dedupe_group": "sj-13000001-program-cost",
        },
        {
            "source_lane": "scrape_search",
            "provider": "tavily",
            "jurisdiction": "san_jose_ca",
            "artifact_url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=13000001&GUID=A-1",
            "artifact_type": "meeting_detail",
            "source_tier": "tier_b",
            "retrieved_at": "2026-04-14T08:06:00+00:00",
            "selected_impact_mode": "compliance_cost",
            "structured_policy_facts": [],
            "linked_artifact_refs": [
                "https://sanjose.legistar.com/View.ashx?M=A&ID=13000001&GUID=A-1"
            ],
            "reader_artifact_refs": [],
            "dedupe_group": "sj-13000001-program-cost",
        },
        {
            "source_lane": "scrape_search",
            "provider": "exa",
            "jurisdiction": "san_jose_ca",
            "artifact_url": "https://example.org/blog/sanjose-housing-opinion",
            "artifact_type": "other",
            "source_tier": "tier_c",
            "retrieved_at": "2026-04-14T08:09:00+00:00",
            "selected_impact_mode": "qualitative_only",
            "structured_policy_facts": [],
            "linked_artifact_refs": [],
            "reader_artifact_refs": [],
            "dedupe_group": "sj-opinion-eval-only",
        },
        {
            "source_lane": "structured",
            "provider": "leginfo",
            "jurisdiction": "california_state",
            "artifact_url": "https://downloads.leginfo.legislature.ca.gov/pubinfo_daily_Mon.zip",
            "artifact_type": "bill_text",
            "source_tier": "tier_a",
            "retrieved_at": "2026-04-14T07:55:00+00:00",
            "selected_impact_mode": "compliance_cost",
            "structured_policy_facts": [
                {"field": "bill_id", "value": "AB-1234", "unit": None},
                {"field": "requires_reporting", "value": True, "unit": "boolean"},
            ],
            "linked_artifact_refs": [
                "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260AB1234"
            ],
            "reader_artifact_refs": [
                "https://backend.artifacts/scrape/ab-1234-analysis.txt"
            ],
            "dedupe_group": "ca-ab-1234-reporting",
        },
        {
            "source_lane": "structured",
            "provider": "ckan",
            "jurisdiction": "california_state",
            "artifact_url": "https://data.ca.gov/api/3/action/package_show?id=state-housing-permits",
            "artifact_type": "budget_document",
            "source_tier": "tier_b",
            "retrieved_at": "2026-04-14T07:57:00+00:00",
            "selected_impact_mode": "adoption_take_up",
            "structured_policy_facts": [
                {"field": "permit_volume_delta_pct", "value": 0.08, "unit": "ratio"},
                {"field": "baseline_permits", "value": 26000, "unit": "units_per_year"},
            ],
            "linked_artifact_refs": [
                "https://data.ca.gov/dataset/state-housing-permits"
            ],
            "reader_artifact_refs": [],
            "dedupe_group": "ca-housing-permits-delta",
        },
        {
            "source_lane": "structured",
            "provider": "arcgis",
            "jurisdiction": "santa_clara_county_ca",
            "artifact_url": "https://services2.arcgis.com/9KdAx8qBsHiGXOEw/arcgis/rest/services/NFHL_Flood_Hazard_Zones_Dissolve/FeatureServer/0/query",
            "artifact_type": "other",
            "source_tier": "tier_c",
            "retrieved_at": "2026-04-14T08:04:00+00:00",
            "selected_impact_mode": "qualitative_only",
            "structured_policy_facts": [
                {"field": "flood_hazard_flag", "value": True, "unit": "boolean"}
            ],
            "linked_artifact_refs": [],
            "reader_artifact_refs": [],
            "dedupe_group": "sc-flood-hazard-context",
        },
        {
            "source_lane": "scrape_search",
            "provider": "private_searxng",
            "jurisdiction": "san_jose_ca",
            "artifact_url": "https://www.sanjoseca.gov/your-government/departments-offices/planning-building-code-enforcement/planning-division/planning-fees",
            "artifact_type": "staff_report",
            "source_tier": "tier_b",
            "retrieved_at": "2026-04-14T08:10:00+00:00",
            "selected_impact_mode": "pass_through_incidence",
            "structured_policy_facts": [],
            "linked_artifact_refs": [],
            "reader_artifact_refs": [
                "https://backend.artifacts/scrape/sj-planning-fees-reader.txt"
            ],
            "dedupe_group": "sj-planning-fees-pass-through",
        },
    ]


def _evidence_readiness(candidate: dict[str, Any]) -> str:
    mode = str(candidate["selected_impact_mode"])
    facts = candidate["structured_policy_facts"]
    linked = candidate["linked_artifact_refs"]
    reader = candidate["reader_artifact_refs"]
    tier = candidate["source_tier"]
    has_quant_mode = mode in {
        "direct_fiscal",
        "compliance_cost",
        "pass_through_incidence",
        "adoption_take_up",
    }
    if mode == "qualitative_only":
        return "insufficient"
    if facts and has_quant_mode and tier in {"tier_a", "tier_b"}:
        return "evidence_card_ready"
    if reader or linked:
        return "reader_required"
    return "insufficient"


def _source_type_from_artifact_type(artifact_type: str) -> str:
    mapping = {
        "bill_text": "bill_text",
        "staff_report": "staff_report",
        "budget_document": "budget_document",
        "meeting_detail": "minutes",
        "other": "other",
    }
    return mapping.get(artifact_type, "other")


def _to_envelope(candidate: dict[str, Any], mode_map: dict[str, str | None]) -> dict[str, Any]:
    canonical_document_key = f"{candidate['jurisdiction']}::{candidate['dedupe_group']}"
    artifact_url = str(candidate["artifact_url"])
    content_hash = _stable_hash(f"{canonical_document_key}::{artifact_url}")
    readiness = _evidence_readiness(candidate)
    selected_mode = str(candidate["selected_impact_mode"])
    mech_family = mode_map.get(selected_mode)
    economic_handoff_ready = readiness == "evidence_card_ready" and mech_family is not None
    return {
        "source_lane": candidate["source_lane"],
        "provider": candidate["provider"],
        "canonical_document_key": canonical_document_key,
        "jurisdiction": candidate["jurisdiction"],
        "artifact_url": artifact_url,
        "artifact_type": candidate["artifact_type"],
        "source_tier": candidate["source_tier"],
        "content_hash": content_hash,
        "retrieved_at": candidate["retrieved_at"],
        "structured_policy_facts": candidate["structured_policy_facts"],
        "linked_artifact_refs": candidate["linked_artifact_refs"],
        "reader_artifact_refs": candidate["reader_artifact_refs"],
        "dedupe_group": candidate["dedupe_group"],
        "selected_impact_mode": selected_mode,
        "mechanism_family": mech_family,
        "evidence_source_type": _source_type_from_artifact_type(candidate["artifact_type"]),
        "evidence_readiness": readiness,
        "economic_handoff_ready": economic_handoff_ready,
    }


def _validate_envelope_shape(envelope: dict[str, Any]) -> list[str]:
    required_keys = (
        "source_lane",
        "provider",
        "canonical_document_key",
        "jurisdiction",
        "artifact_url",
        "artifact_type",
        "source_tier",
        "content_hash",
        "retrieved_at",
        "structured_policy_facts",
        "linked_artifact_refs",
        "reader_artifact_refs",
        "dedupe_group",
        "evidence_readiness",
        "economic_handoff_ready",
    )
    errors: list[str] = []
    for key in required_keys:
        if key not in envelope:
            errors.append(f"missing_key:{key}")
    if envelope.get("source_lane") not in {"structured", "scrape_search"}:
        errors.append("invalid_source_lane")
    if envelope.get("provider") not in {
        "legistar",
        "leginfo",
        "ckan",
        "arcgis",
        "private_searxng",
        "tavily",
        "exa",
    }:
        errors.append("invalid_provider")
    if envelope.get("evidence_readiness") not in {
        "evidence_card_ready",
        "reader_required",
        "insufficient",
    }:
        errors.append("invalid_evidence_readiness")
    return errors


def _schema_validate_ready_envelopes(envelopes: list[dict[str, Any]]) -> dict[str, Any]:
    fallback_errors: list[str] = []
    validated = 0
    skipped_non_ready = 0
    schema_errors: list[str] = []

    for envelope in envelopes:
        if envelope["evidence_readiness"] != "evidence_card_ready":
            skipped_non_ready += 1
            continue
        if not HAS_SCHEMA_VALIDATION:
            fallback_errors.append("schema_models_unavailable")
            continue
        try:
            source_tier = SourceTier(envelope["source_tier"])
            source_type = EvidenceSourceType(envelope["evidence_source_type"])
            EvidenceCard(
                id=f"ec-{envelope['provider']}-{validated + 1}",
                source_url=envelope["artifact_url"],
                source_type=source_type,
                content_hash=envelope["content_hash"],
                excerpt=json.dumps(envelope["structured_policy_facts"], separators=(",", ":"))[:300]
                or "reader-backed evidence",
                retrieved_at=envelope["retrieved_at"],
                source_tier=source_tier,
                provenance_label=f"{envelope['source_lane']}.{envelope['provider']}",
                artifact_id=envelope["canonical_document_key"],
            )
            validated += 1
        except Exception as exc:
            schema_errors.append(
                f"{envelope['provider']}::{envelope['dedupe_group']}::{exc.__class__.__name__}:{exc}"
            )

    return {
        "schema_validation_mode": "pydantic_economic_evidence" if HAS_SCHEMA_VALIDATION else "local_contract_only",
        "validated_ready_evidence_count": validated,
        "skipped_non_ready_count": skipped_non_ready,
        "schema_errors": schema_errors,
        "schema_import_error": SCHEMA_IMPORT_ERROR,
        "local_contract_errors": fallback_errors,
    }


def _provider_role_recommendation() -> dict[str, Any]:
    return {
        "structured_first_policy": True,
        "lane_roles": [
            {
                "provider": "private_searxng",
                "role": "primary_scrape_search_lane",
                "reason": "Low cost + broad official-domain discovery for linked artifacts.",
            },
            {
                "provider": "tavily",
                "role": "hot_fallback",
                "reason": "Fallback when SearXNG recall/ranking misses official artifacts.",
            },
            {
                "provider": "exa",
                "role": "bakeoff_eval_only",
                "reason": "Constrain quota spend to eval/research experiments.",
            },
            {
                "provider": "legistar|leginfo|ckan|arcgis",
                "role": "structured_primary_when_available",
                "reason": "Prefer structured facts + canonical linked refs before scrape-only interpretation.",
            },
        ],
    }


def _summary(envelopes: list[dict[str, Any]], schema_check: dict[str, Any]) -> dict[str, Any]:
    total = len(envelopes)
    ready = [e for e in envelopes if e["evidence_readiness"] == "evidence_card_ready"]
    reader_required = [e for e in envelopes if e["evidence_readiness"] == "reader_required"]
    insufficient = [e for e in envelopes if e["evidence_readiness"] == "insufficient"]
    handoff_ready = [e for e in envelopes if e["economic_handoff_ready"]]
    dedupe_groups = {}
    for item in envelopes:
        dedupe_groups.setdefault(item["dedupe_group"], set()).add(item["source_lane"])
    integrated_groups = [
        key for key, lanes in dedupe_groups.items() if "structured" in lanes and "scrape_search" in lanes
    ]
    quantified_ready = [
        e for e in handoff_ready if e["selected_impact_mode"] != "qualitative_only"
    ]
    return {
        "total_envelopes": total,
        "ready_count": len(ready),
        "reader_required_count": len(reader_required),
        "insufficient_count": len(insufficient),
        "economic_handoff_ready_count": len(handoff_ready),
        "quantified_handoff_ready_count": len(quantified_ready),
        "integrated_dedupe_groups_count": len(integrated_groups),
        "integrated_dedupe_groups": sorted(integrated_groups),
        "provider_counts": {
            provider: len([e for e in envelopes if e["provider"] == provider])
            for provider in sorted({e["provider"] for e in envelopes})
        },
        "schema_validation_mode": schema_check["schema_validation_mode"],
        "schema_errors_count": len(schema_check["schema_errors"]),
        "evidence_quality_assessment": (
            "sufficient_for_quantified_handoff_in_subset"
            if len(quantified_ready) >= 3 and len(schema_check["schema_errors"]) == 0
            else "qualitative_or_fail_closed_only"
        ),
        "evidence_quality_note": (
            "Merged contract is suitable for backend economic handoff in a subset; "
            "items marked reader_required/insufficient remain fail-closed or qualitative."
        ),
    }


def _unified_package_proof(
    envelopes: list[dict[str, Any]],
) -> dict[str, Any]:
    lane_values = {str(item.get("source_lane", "")) for item in envelopes}
    has_scraped_lane = "scrape_search" in lane_values
    has_structured_lane = "structured" in lane_values
    structured_families = sorted(
        {
            str(item.get("provider", ""))
            for item in envelopes
            if item.get("source_lane") == "structured"
        }
    )
    has_multiple_structured_families = len(structured_families) >= 2
    provenance_required = (
        "provider",
        "canonical_document_key",
        "artifact_url",
        "content_hash",
        "retrieved_at",
        "source_tier",
    )
    missing_provenance_rows: list[int] = []
    deterministic_identity_failures: list[str] = []
    lanes_by_doc: dict[str, set[str]] = {}
    for index, envelope in enumerate(envelopes):
        if any(not envelope.get(key) for key in provenance_required):
            missing_provenance_rows.append(index)
        canonical_document_key = str(envelope.get("canonical_document_key", ""))
        source_lane = str(envelope.get("source_lane", ""))
        if canonical_document_key:
            lanes_by_doc.setdefault(canonical_document_key, set()).add(source_lane)
        artifact_url = str(envelope.get("artifact_url", ""))
        content_hash = str(envelope.get("content_hash", ""))
        expected_hash = _stable_hash(f"{canonical_document_key}::{artifact_url}")
        if canonical_document_key and artifact_url and content_hash and content_hash != expected_hash:
            deterministic_identity_failures.append(canonical_document_key)
    cross_lane_document_keys = sorted(
        [key for key, lanes in lanes_by_doc.items() if {"structured", "scrape_search"}.issubset(lanes)]
    )
    has_cross_lane_identity_overlap = len(cross_lane_document_keys) >= 1
    reasons: list[str] = []
    if not has_scraped_lane:
        reasons.append("missing_scraped_lane")
    if not has_structured_lane:
        reasons.append("missing_structured_lane")
    if not has_multiple_structured_families:
        reasons.append("insufficient_structured_source_families")
    if not has_cross_lane_identity_overlap:
        reasons.append("no_cross_lane_canonical_document_overlap")
    if missing_provenance_rows:
        reasons.append("missing_source_level_provenance")
    if deterministic_identity_failures:
        reasons.append("deterministic_identity_hash_mismatch")
    passed = len(reasons) == 0
    return {
        "passed": passed,
        "has_scraped_lane": has_scraped_lane,
        "has_structured_lane": has_structured_lane,
        "structured_source_family_count": len(structured_families),
        "structured_source_families": structured_families,
        "cross_lane_canonical_document_keys": cross_lane_document_keys,
        "missing_provenance_rows": missing_provenance_rows,
        "deterministic_identity_hash_failures": sorted(set(deterministic_identity_failures)),
        "reasons": reasons,
    }


def _economic_analysis_handoff_assessment(
    *,
    envelopes: list[dict[str, Any]],
    summary: dict[str, Any],
    schema_check: dict[str, Any],
    unified_package_proof: dict[str, Any],
) -> dict[str, Any]:
    quantified_ready_count = int(summary.get("quantified_handoff_ready_count", 0))
    reader_required_count = int(summary.get("reader_required_count", 0))
    insufficient_count = int(summary.get("insufficient_count", 0))
    schema_errors_count = len(schema_check.get("schema_errors", []))
    conditions = {
        "unified_package_passed": bool(unified_package_proof.get("passed")),
        "quantified_ready_count_ge_2": quantified_ready_count >= 2,
        "schema_errors_zero": schema_errors_count == 0,
    }
    sufficient_for_handoff = all(conditions.values())
    reasons: list[str] = []
    if not conditions["unified_package_passed"]:
        reasons.append("unified_package_contract_not_proven")
    if not conditions["quantified_ready_count_ge_2"]:
        reasons.append("insufficient_quantified_ready_evidence_cards")
    if not conditions["schema_errors_zero"]:
        reasons.append("schema_validation_errors_present")
    production_blockers: list[str] = []
    if reader_required_count > 0:
        production_blockers.append("reader_required_rows_remain")
    if insufficient_count > 0:
        production_blockers.append("insufficient_rows_remain")
    return {
        "sufficient_for_economic_analysis_handoff": sufficient_for_handoff,
        "handoff_decision": (
            "sufficient_for_controlled_backend_handoff"
            if sufficient_for_handoff
            else "not_sufficient_for_handoff"
        ),
        "conditions": conditions,
        "why_or_why_not": reasons or ["quantified_subset_ready_with_proven_unified_package"],
        "production_decision_grade_ready": False,
        "production_blockers": production_blockers,
    }


def _validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    envelopes = report.get("envelopes")
    if not isinstance(envelopes, list) or not envelopes:
        errors.append("missing_or_empty_envelopes")
        return errors
    for idx, envelope in enumerate(envelopes):
        if not isinstance(envelope, dict):
            errors.append(f"invalid_envelope:{idx}")
            continue
        for err in _validate_envelope_shape(envelope):
            errors.append(f"envelope[{idx}]::{err}")
    mapping = report.get("impact_to_mechanism_mapping")
    required_modes = {
        "direct_fiscal",
        "compliance_cost",
        "pass_through_incidence",
        "adoption_take_up",
        "qualitative_only",
    }
    if not isinstance(mapping, list):
        errors.append("missing_impact_mapping")
    else:
        got = {m.get("impact_mode") for m in mapping if isinstance(m, dict)}
        missing = sorted(required_modes - got)
        if missing:
            errors.append(f"missing_mapping_modes:{','.join(missing)}")
    summary = report.get("summary", {})
    if summary.get("integrated_dedupe_groups_count", 0) < 1:
        errors.append("integration_not_proven_no_cross_lane_dedupe_group")
    unified = report.get("unified_package_proof")
    if not isinstance(unified, dict):
        errors.append("missing_unified_package_proof")
    else:
        if not bool(unified.get("has_scraped_lane")):
            errors.append("unified_proof_missing_scraped_lane")
        if not bool(unified.get("has_structured_lane")):
            errors.append("unified_proof_missing_structured_lane")
        if int(unified.get("structured_source_family_count", 0)) < 2:
            errors.append("unified_proof_insufficient_structured_source_families")
    handoff = report.get("economic_analysis_handoff_assessment")
    if not isinstance(handoff, dict):
        errors.append("missing_economic_analysis_handoff_assessment")
    elif "sufficient_for_economic_analysis_handoff" not in handoff:
        errors.append("missing_handoff_sufficiency_answer")
    return errors


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    schema = report["schema_validation"]
    unified = report["unified_package_proof"]
    handoff = report["economic_analysis_handoff_assessment"]
    return f"""
# Scrape + Structured Source Integration POC

Date: {report["generated_at"]}
Feature key: `{report["feature_key"]}`
Mode: `{report["mode"]}`

## Objective

Prove one backend-owned merged artifact/evidence contract across:

- structured lane (`legistar`, `leginfo`, `ckan`, `arcgis`)
- scrape/search lane (`private_searxng`, `tavily`, `exa`)

## Contract Outcome

- total envelopes: `{summary["total_envelopes"]}`
- integrated cross-lane dedupe groups: `{summary["integrated_dedupe_groups_count"]}`
- evidence_card_ready: `{summary["ready_count"]}`
- reader_required: `{summary["reader_required_count"]}`
- insufficient: `{summary["insufficient_count"]}`
- economic_handoff_ready: `{summary["economic_handoff_ready_count"]}`
- quantified-ready subset: `{summary["quantified_handoff_ready_count"]}`
- quality assessment: `{summary["evidence_quality_assessment"]}`

## Unified Package Proof

- unified package passed: `{unified["passed"]}`
- has scraped lane: `{unified["has_scraped_lane"]}`
- has structured lane: `{unified["has_structured_lane"]}`
- structured source family count: `{unified["structured_source_family_count"]}`
- cross-lane canonical-document overlap count: `{len(unified["cross_lane_canonical_document_keys"])}`
- proof blockers: `{', '.join(unified["reasons"]) if unified["reasons"] else 'none'}`

## Provider Role Recommendation

- `private_searxng`: primary scrape/search lane
- `tavily`: hot fallback
- `exa`: bakeoff/eval only
- structured providers first when available (`legistar`, `leginfo`, `ckan`, `arcgis`)

## ImpactMode -> MechanismFamily Mapping

{json.dumps(report["impact_to_mechanism_mapping"], indent=2)}

## Schema Validation

- mode: `{schema["schema_validation_mode"]}`
- validated ready evidence count: `{schema["validated_ready_evidence_count"]}`
- schema errors count: `{len(schema["schema_errors"])}`
- schema import error: `{schema["schema_import_error"]}`

## Evidence Quality Note

{summary["evidence_quality_note"]}

## Economic Analysis Handoff Answer

- sufficient for economic analysis handoff: `{handoff["sufficient_for_economic_analysis_handoff"]}`
- handoff decision: `{handoff["handoff_decision"]}`
- why/why not: `{', '.join(handoff["why_or_why_not"])}`
- production decision-grade ready: `{handoff["production_decision_grade_ready"]}`
- production blockers: `{', '.join(handoff["production_blockers"]) if handoff["production_blockers"] else 'none'}`
"""


def _run(config: VerifierConfig) -> dict[str, Any]:
    mode_map = _mapping_lookup()
    candidates = _fixture_candidates()
    envelopes = [_to_envelope(candidate, mode_map) for candidate in candidates]
    schema_check = _schema_validate_ready_envelopes(envelopes)
    summary = _summary(envelopes, schema_check)
    unified_package_proof = _unified_package_proof(envelopes)
    handoff_assessment = _economic_analysis_handoff_assessment(
        envelopes=envelopes,
        summary=summary,
        schema_check=schema_check,
        unified_package_proof=unified_package_proof,
    )
    report = {
        "feature_key": FEATURE_KEY,
        "poc_version": POC_VERSION,
        "mode": config.mode,
        "generated_at": _now_iso(),
        "impact_to_mechanism_mapping": _impact_mode_mapping(),
        "provider_role_recommendation": _provider_role_recommendation(),
        "envelopes": envelopes,
        "schema_validation": schema_check,
        "summary": summary,
        "unified_package_proof": unified_package_proof,
        "economic_analysis_handoff_assessment": handoff_assessment,
    }
    return report


def _parse_args(argv: list[str]) -> VerifierConfig:
    parser = argparse.ArgumentParser(description="Scrape + structured integration verifier.")
    parser.add_argument("--mode", choices=("replay",), default="replay")
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=OUT_MD)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)
    return VerifierConfig(
        mode=args.mode,
        out_json=args.out_json,
        out_md=args.out_md,
        self_check=args.self_check,
    )


def main(argv: list[str] | None = None) -> int:
    config = _parse_args(argv or sys.argv[1:])
    report = _run(config)
    _write_json(config.out_json, report)
    _write_markdown(config.out_md, _render_markdown(report))
    if config.self_check:
        errors = _validate_report(report)
        if errors:
            print("SELF_CHECK_FAILED")
            for err in errors:
                print(err)
            return 1
        print("SELF_CHECK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
