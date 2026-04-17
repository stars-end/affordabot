"""Corpus matrix + scorecard spine for local_government_data_moat_benchmark_v0."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
from typing import Any

CORPUS_GATE_IDS = [f"C{index}" for index in range(0, 15)]
PACKAGE_GATE_IDS = [f"D{index}" for index in range(0, 12)]
ECONOMIC_GATE_IDS = [f"E{index}" for index in range(1, 6)]

EXTERNAL_SOURCE_OFFICIALNESS = {
    "external_advocacy",
    "news_media",
    "vendor",
}
SECONDARY_SEARCH_FAMILIES = {
    "secondary_search_tavily",
    "secondary_search_exa",
}
LIVE_ORCHESTRATION_MODES = {"windmill_live", "mixed"}
ORCHESTRATION_INTENT_MODE = "orchestration_intent"
ORCHESTRATION_MODES = LIVE_ORCHESTRATION_MODES | {
    "cli_only",
    ORCHESTRATION_INTENT_MODE,
}
LEGISTAR_LIKE_FAMILIES = {
    "agenda_meeting_api",
}
NON_FEE_POLICY_FAMILIES = {
    "housing_permits",
    "zoning_land_use",
    "parking_policy",
    "transportation_demand_management",
    "business_licensing_compliance",
    "utilities_energy_building_standard",
    "air_quality_electrification",
    "short_term_rental",
    "affordable_housing_mandate",
    "code_enforcement",
    "procurement_contract",
    "public_safety",
    "meeting_action",
    "general_governance",
}
REQUIRED_MANUAL_AUDIT_FIELDS = {
    "selected_primary_source_checked",
    "source_officialness_checked",
    "source_family_checked",
    "structured_contribution_checked",
    "package_identity_checked",
    "storage_readback_checked",
    "data_moat_classification_checked",
    "economic_handoff_checked",
    "dominant_failure_class",
}
LIVE_STRUCTURED_PROOF_STATUSES = {"live_proven", "proven"}


class DataMoatPackageClassification(StrEnum):
    ECONOMIC_ANALYSIS_READY = "economic_analysis_ready"
    ECONOMIC_HANDOFF_CANDIDATE = "economic_handoff_candidate"
    SECONDARY_RESEARCH_NEEDED = "secondary_research_needed"
    QUALITATIVE_ONLY = "qualitative_only"
    STORED_NOT_ECONOMIC = "stored_not_economic"
    NOT_POLICY_EVIDENCE = "not_policy_evidence"
    FAIL = "fail"


C3_D11_ALLOWED_QUALITIES: dict[DataMoatPackageClassification, set[str]] = {
    DataMoatPackageClassification.ECONOMIC_ANALYSIS_READY: {"analysis_ready"},
    DataMoatPackageClassification.ECONOMIC_HANDOFF_CANDIDATE: {
        "analysis_ready",
        "analysis_ready_with_gaps",
    },
    DataMoatPackageClassification.SECONDARY_RESEARCH_NEEDED: {
        "analysis_ready_with_gaps"
    },
    DataMoatPackageClassification.QUALITATIVE_ONLY: {"not_analysis_ready"},
    DataMoatPackageClassification.STORED_NOT_ECONOMIC: {"not_analysis_ready"},
    DataMoatPackageClassification.NOT_POLICY_EVIDENCE: {"not_analysis_ready"},
    DataMoatPackageClassification.FAIL: {"not_analysis_ready"},
}


@dataclass(frozen=True)
class GateResult:
    status: str
    reason: str
    metrics: dict[str, Any]
    blockers: list[str]

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "metrics": self.metrics,
            "blockers": self.blockers,
        }


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _default_package_gate_status(
    *,
    d11_handoff_quality: str,
    has_true_structured: bool,
    orchestration_mode: str,
    manual_audit_sampled: bool,
) -> dict[str, str]:
    d11_status = (
        "pass"
        if d11_handoff_quality in {"analysis_ready", "analysis_ready_with_gaps"}
        else "not_proven"
    )
    return {
        "D0": "pass",
        "D1": "pass",
        "D2": "pass",
        "D3": "pass" if has_true_structured else "not_proven",
        "D4": "pass",
        "D5": "pass",
        "D6": "pass",
        "D7": "pass",
        "D8": "pass",
        "D9": "pass"
        if orchestration_mode in LIVE_ORCHESTRATION_MODES
        else "not_proven",
        "D10": "pass" if manual_audit_sampled else "not_proven",
        "D11": d11_status,
        "E1": "not_proven",
        "E2": "not_proven",
        "E3": "not_proven",
        "E4": "not_proven",
        "E5": "not_proven",
    }


def _template_id_for_policy_family(policy_family: str) -> str:
    return f"non_fee_template::{policy_family}"


def _is_non_fee_policy_family(policy_family: str) -> bool:
    return policy_family in NON_FEE_POLICY_FAMILIES


def _structured_observation_is_live_proven(observation: dict[str, Any]) -> bool:
    proof_status = str(observation.get("proof_status") or "")
    if proof_status:
        return proof_status in LIVE_STRUCTURED_PROOF_STATUSES
    return bool(observation.get("live_proven"))


def _with_structured_proof_defaults(
    observations: list[dict[str, Any]],
    *,
    default_proof_source: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for observation in observations:
        item = dict(observation)
        if item.get("true_structured"):
            if _structured_observation_is_live_proven(item):
                item.setdefault("live_proven", True)
                item.setdefault("proof_status", "live_proven")
            else:
                item["live_proven"] = False
                item.setdefault("proof_status", "cataloged_intent")
            item.setdefault("proof_source", default_proof_source)
        else:
            item["live_proven"] = False
            item.setdefault("proof_status", "metadata_only")
            item.setdefault("proof_source", default_proof_source)
        normalized.append(item)
    return normalized


def _as_cataloged_structured_intent(
    observations: list[dict[str, Any]],
    *,
    proof_source: str,
) -> list[dict[str, Any]]:
    cataloged: list[dict[str, Any]] = []
    for observation in observations:
        item = dict(observation)
        item["live_proven"] = False
        item["proof_status"] = "cataloged_intent"
        item["proof_source"] = proof_source
        cataloged.append(item)
    return cataloged


def _make_seed_row(
    *,
    corpus_row_id: str,
    jurisdiction_id: str,
    jurisdiction_name: str,
    jurisdiction_type: str,
    state: str,
    policy_family: str,
    mechanism_family: str,
    query_families: list[str],
    expected_official_source_families: list[str],
    expected_structured_source_families: list[str],
    selected_primary_source_family: str,
    selected_primary_source_url: str,
    source_officialness: str,
    source_of_truth_role: str,
    evaluation_split: str,
    blind_seed: bool,
    known_policy_reference_id: str,
    data_moat_package_classification: str,
    d11_handoff_quality: str,
    d11_reason: str,
    structured_observations: list[dict[str, Any]],
    source_infrastructure_status: str,
    orchestration_mode: str,
    manual_audit_priority: str,
    manual_audit_sampled: bool,
    deep_dive_type: str | None = None,
    model_card_reuse_count: int = 0,
    primary_provider: str = "private_searxng",
    tavily_primary_selected: bool = False,
    exa_primary_selected: bool = False,
    external_source_promotion_rule_id: str | None = None,
) -> dict[str, Any]:
    structured_observations = _with_structured_proof_defaults(
        structured_observations,
        default_proof_source="local_government_corpus_seed_matrix",
    )
    has_true_structured = any(
        bool(item.get("true_structured")) for item in structured_observations
    )
    manual_audit: dict[str, Any] = {"sampled": manual_audit_sampled}
    if manual_audit_sampled:
        manual_audit.update(
            {
                "audit_id": f"audit::{corpus_row_id}",
                "selected_primary_source_checked": True,
                "source_officialness_checked": True,
                "source_family_checked": True,
                "structured_contribution_checked": True,
                "package_identity_checked": True,
                "storage_readback_checked": True,
                "data_moat_classification_checked": True,
                "economic_handoff_checked": True,
                "dominant_failure_class": "none",
            }
        )

    planned_orchestration_mode = orchestration_mode
    effective_orchestration_mode = (
        ORCHESTRATION_INTENT_MODE
        if orchestration_mode in LIVE_ORCHESTRATION_MODES
        else orchestration_mode
    )

    windmill_refs: dict[str, Any] | None = None
    if (
        planned_orchestration_mode in LIVE_ORCHESTRATION_MODES
        or effective_orchestration_mode == ORCHESTRATION_INTENT_MODE
    ):
        windmill_refs = {
            "flow_id": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
            "run_id": f"wm::{corpus_row_id}",
            "job_id": f"wm-job::{corpus_row_id}",
            "proof_status": "seeded_not_live_proven",
            "proof_source": "local_government_corpus_seed_matrix",
            "planned_orchestration_mode": planned_orchestration_mode,
        }

    package_gate_status = _default_package_gate_status(
        d11_handoff_quality=d11_handoff_quality,
        has_true_structured=has_true_structured,
        orchestration_mode=effective_orchestration_mode,
        manual_audit_sampled=manual_audit_sampled,
    )

    row: dict[str, Any] = {
        "row_type": "corpus_package",
        "corpus_row_id": corpus_row_id,
        "package_id": f"pkg::{corpus_row_id}",
        "jurisdiction": {
            "id": jurisdiction_id,
            "name": jurisdiction_name,
            "type": jurisdiction_type,
            "state": state,
            "region": "us",
        },
        "policy_family": policy_family,
        "mechanism_family": mechanism_family,
        "query_families": query_families,
        "expected_official_source_families": expected_official_source_families,
        "expected_structured_source_families": expected_structured_source_families,
        "expected_structured_depth_targets": [
            {
                "source_family": str(observation.get("source_family") or ""),
                "depth": str(observation.get("depth") or ""),
                "proof_status": str(observation.get("proof_status") or ""),
            }
            for observation in structured_observations
            if observation.get("true_structured")
        ],
        "known_official_domains": [
            f"{jurisdiction_id.replace('_', '')}.gov",
            "legistar.com",
        ],
        "evaluation_split": evaluation_split,
        "blind_seed": blind_seed,
        "known_policy_reference_id": known_policy_reference_id,
        "required_package_verdict_floor": "stored_not_economic",
        "manual_audit_priority": manual_audit_priority,
        "golden_regression_expectation": {
            "stable_query_input": query_families[0],
            "expected_jurisdiction_id": jurisdiction_id,
            "expected_policy_family": policy_family,
            "selected_source_url": selected_primary_source_url,
            "package_id": f"pkg::{corpus_row_id}",
            "verdict": "corpus_ready_with_gaps",
            "failure_class": "none",
        },
        "selected_primary_source": {
            "source_family": selected_primary_source_family,
            "source_url": selected_primary_source_url,
            "source_officialness": source_officialness,
            "source_of_truth_role": source_of_truth_role,
            "jurisdiction_match": True,
            "policy_family_match": True,
            "external_context_allowed": source_officialness
            in EXTERNAL_SOURCE_OFFICIALNESS,
            "primary_evidence_allowed": source_officialness == "official_primary",
        },
        "provider_usage": {
            "primary_discovery_provider": primary_provider,
            "tavily_primary_selected": tavily_primary_selected,
            "exa_primary_selected": exa_primary_selected,
        },
        "structured_source_observations": structured_observations,
        "structured_cell_status": "covered"
        if has_true_structured
        else "cataloged_absent",
        "source_infrastructure_status": source_infrastructure_status,
        "infrastructure_status": {
            "source_lane_status": source_infrastructure_status,
            "orchestration_mode": effective_orchestration_mode,
            "planned_orchestration_mode": planned_orchestration_mode,
            "windmill_refs": windmill_refs,
        },
        "economic_handoff_plausibility": {
            "classification_target": data_moat_package_classification,
            "deep_dive_type": deep_dive_type,
            "deep_dive_performed": deep_dive_type is not None,
            "model_card_reuse_count": model_card_reuse_count,
        },
        "classification": {
            "data_moat_package_classification": data_moat_package_classification,
            "d11_handoff_quality": d11_handoff_quality,
            "d11_reason": d11_reason,
        },
        "package_gate_status": package_gate_status,
        "manual_audit": manual_audit,
        "freshness": {
            "expected_update_interval_days": 30,
            "retrieved_at": "2026-04-16T00:00:00+00:00",
            "source_published_at": "2026-03-31T00:00:00+00:00",
            "date_not_found": False,
            "last_successful_refresh_at": "2026-04-16T00:00:00+00:00",
            "source_shape_fingerprint": f"shape::{corpus_row_id}",
            "source_shape_changed": False,
            "update_cadence_drift": False,
            "stale_for_policy_use": False,
            "next_refresh_recommendation": "refresh_within_30_days",
        },
        "identity": {
            "canonical_policy_key": f"policy::{jurisdiction_id}::{policy_family}",
            "canonical_source_key": f"source::{selected_primary_source_family}::{jurisdiction_id}",
            "canonical_document_key": f"doc::{corpus_row_id}",
            "canonical_attachment_key": f"attachment::{corpus_row_id}",
            "dedupe_cluster_id": f"cluster::{jurisdiction_id}::{policy_family}",
            "version_state": "active",
        },
        "normalization": {
            "currency_normalized": True,
            "percent_normalized": True,
            "count_normalized": True,
            "date_normalized": True,
            "unit_normalized": True,
            "geography_fields": ["jurisdiction", "state"],
            "export_ready": True,
        },
        "licensing": {
            "license_posture": "public_record_or_open_data",
            "robots_tos_posture": "allowed_with_rate_limit",
            "rate_limit_notes": "respect source published limits",
            "attribution_notes": "retain source URL attribution",
            "allowed_storage_export_posture": "internal_plus_customer_export",
        },
        "schema_contract": {
            "package_schema_version": "policy_evidence_package_v1",
            "taxonomy_version": "corpus_taxonomy_v1",
            "gate_version": "data_moat_c0_c14_v1",
        },
        "extraction_depth": {
            "template_id": _template_id_for_policy_family(policy_family),
            "live_exercised": _is_non_fee_policy_family(policy_family),
            "applicability_present": _is_non_fee_policy_family(policy_family),
            "effective_date_or_unknown_present": True,
            "jurisdiction_geography_present": True,
            "source_locator_present": True,
            "policy_action_type_present": True,
        },
    }
    if external_source_promotion_rule_id:
        row["external_source_promotion"] = {
            "rule_id": external_source_promotion_rule_id,
            "reason": "explicit_source_of_truth_exception",
            "review_status": "approved",
        }
    return row


def _build_seed_rows() -> list[dict[str, Any]]:
    return [
        _make_seed_row(
            corpus_row_id="lgm-001",
            jurisdiction_id="san_jose_ca",
            jurisdiction_name="San Jose",
            jurisdiction_type="city",
            state="CA",
            policy_family="commercial_linkage_fee",
            mechanism_family="direct_fee_or_tax",
            query_families=["san jose commercial linkage fee ordinance adopted rate"],
            expected_official_source_families=["official_pdf_html_attachment"],
            expected_structured_source_families=["agenda_meeting_api", "socrata_api"],
            selected_primary_source_family="official_pdf_html_attachment",
            selected_primary_source_url="https://www.sanjoseca.gov/housing/commercial-linkage-fee.pdf",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="tuning",
            blind_seed=False,
            known_policy_reference_id="kp-sj-clf-001",
            data_moat_package_classification="economic_handoff_candidate",
            d11_handoff_quality="analysis_ready_with_gaps",
            d11_reason="parameter inventory present with bounded assumptions",
            structured_observations=[
                {
                    "source_family": "agenda_meeting_api",
                    "true_structured": False,
                    "depth": "metadata",
                    "live_proven": True,
                },
                {
                    "source_family": "socrata_api",
                    "true_structured": True,
                    "depth": "economic_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="windmill_live",
            manual_audit_priority="P0",
            manual_audit_sampled=True,
            deep_dive_type="direct",
            model_card_reuse_count=2,
        ),
        _make_seed_row(
            corpus_row_id="lgm-002",
            jurisdiction_id="san_jose_ca",
            jurisdiction_name="San Jose",
            jurisdiction_type="city",
            state="CA",
            policy_family="parking_policy",
            mechanism_family="direct_compliance_cost",
            query_families=["san jose multifamily parking minimum amendment"],
            expected_official_source_families=[
                "official_pdf_html_attachment",
                "official_clerk_or_code_portal",
            ],
            expected_structured_source_families=["agenda_meeting_api", "arcgis_rest"],
            selected_primary_source_family="official_pdf_html_attachment",
            selected_primary_source_url="https://sanjose.legistar.com/View.ashx?M=F&ID=13050001",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="tuning",
            blind_seed=False,
            known_policy_reference_id="kp-sj-parking-001",
            data_moat_package_classification="economic_handoff_candidate",
            d11_handoff_quality="analysis_ready_with_gaps",
            d11_reason="structured facts include permit and cost proxies",
            structured_observations=[
                {
                    "source_family": "agenda_meeting_api",
                    "true_structured": False,
                    "depth": "metadata",
                    "live_proven": True,
                },
                {
                    "source_family": "arcgis_rest",
                    "true_structured": True,
                    "depth": "geospatial_policy_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="windmill_live",
            manual_audit_priority="P0",
            manual_audit_sampled=True,
            deep_dive_type="direct",
            model_card_reuse_count=1,
        ),
        _make_seed_row(
            corpus_row_id="lgm-003",
            jurisdiction_id="san_jose_ca",
            jurisdiction_name="San Jose",
            jurisdiction_type="city",
            state="CA",
            policy_family="short_term_rental",
            mechanism_family="direct_compliance_cost",
            query_families=["san jose short term rental permit ordinance"],
            expected_official_source_families=["official_clerk_or_code_portal"],
            expected_structured_source_families=["ckan_api"],
            selected_primary_source_family="official_clerk_or_code_portal",
            selected_primary_source_url="https://library.municode.com/ca/san_jose/codes/code_of_ordinances",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="blind_evaluation",
            blind_seed=True,
            known_policy_reference_id="kp-sj-str-001",
            data_moat_package_classification="qualitative_only",
            d11_handoff_quality="not_analysis_ready",
            d11_reason="qualitative context only no source-bound unitized parameters",
            structured_observations=[
                {
                    "source_family": "ckan_api",
                    "true_structured": True,
                    "depth": "permit_status_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="mixed",
            manual_audit_priority="P1",
            manual_audit_sampled=True,
        ),
        _make_seed_row(
            corpus_row_id="lgm-004",
            jurisdiction_id="los_angeles_ca",
            jurisdiction_name="Los Angeles",
            jurisdiction_type="city",
            state="CA",
            policy_family="affordable_housing_mandate",
            mechanism_family="indirect_housing_cost_pass_through",
            query_families=["los angeles inclusionary housing ordinance affordability"],
            expected_official_source_families=[
                "official_pdf_html_attachment",
                "official_clerk_or_code_portal",
            ],
            expected_structured_source_families=["socrata_api"],
            selected_primary_source_family="official_pdf_html_attachment",
            selected_primary_source_url="https://planning.lacity.gov/ordinances/inclusionary-housing.pdf",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="tuning",
            blind_seed=False,
            known_policy_reference_id="kp-la-ih-001",
            data_moat_package_classification="secondary_research_needed",
            d11_handoff_quality="analysis_ready_with_gaps",
            d11_reason="indirect mechanism requires secondary incidence assumptions",
            structured_observations=[
                {
                    "source_family": "socrata_api",
                    "true_structured": True,
                    "depth": "affordability_units",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="windmill_live",
            manual_audit_priority="P0",
            manual_audit_sampled=True,
            deep_dive_type="indirect",
            model_card_reuse_count=1,
        ),
        _make_seed_row(
            corpus_row_id="lgm-005",
            jurisdiction_id="los_angeles_ca",
            jurisdiction_name="Los Angeles",
            jurisdiction_type="city",
            state="CA",
            policy_family="zoning_land_use",
            mechanism_family="indirect_supply_constraint",
            query_families=["los angeles zoning ordinance floor area ratio update"],
            expected_official_source_families=["official_clerk_or_code_portal"],
            expected_structured_source_families=["arcgis_rest"],
            selected_primary_source_family="official_clerk_or_code_portal",
            selected_primary_source_url="https://planning.lacity.gov/odocument/zoning-code",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="blind_evaluation",
            blind_seed=True,
            known_policy_reference_id="kp-la-zoning-001",
            data_moat_package_classification="stored_not_economic",
            d11_handoff_quality="not_analysis_ready",
            d11_reason="non-economic planning context preserved for downstream joins",
            structured_observations=[
                {
                    "source_family": "arcgis_rest",
                    "true_structured": True,
                    "depth": "zoning_parcel_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="mixed",
            manual_audit_priority="P1",
            manual_audit_sampled=False,
        ),
        _make_seed_row(
            corpus_row_id="lgm-006",
            jurisdiction_id="oakland_ca",
            jurisdiction_name="Oakland",
            jurisdiction_type="city",
            state="CA",
            policy_family="code_enforcement",
            mechanism_family="direct_compliance_cost",
            query_families=["oakland code enforcement penalty schedule housing"],
            expected_official_source_families=["official_pdf_html_attachment"],
            expected_structured_source_families=["socrata_api"],
            selected_primary_source_family="official_pdf_html_attachment",
            selected_primary_source_url="https://cao-94612.s3.amazonaws.com/documents/code-enforcement-fees.pdf",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="tuning",
            blind_seed=False,
            known_policy_reference_id="kp-oak-code-001",
            data_moat_package_classification="economic_handoff_candidate",
            d11_handoff_quality="analysis_ready_with_gaps",
            d11_reason="policy penalties and applicability extracted with caveats",
            structured_observations=[
                {
                    "source_family": "socrata_api",
                    "true_structured": True,
                    "depth": "citation_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="windmill_live",
            manual_audit_priority="P1",
            manual_audit_sampled=True,
            deep_dive_type="direct",
            model_card_reuse_count=1,
        ),
        _make_seed_row(
            corpus_row_id="lgm-007",
            jurisdiction_id="oakland_ca",
            jurisdiction_name="Oakland",
            jurisdiction_type="city",
            state="CA",
            policy_family="business_licensing_compliance",
            mechanism_family="direct_compliance_cost",
            query_families=["oakland business licensing compliance ordinance fees"],
            expected_official_source_families=["official_clerk_or_code_portal"],
            expected_structured_source_families=["ckan_api"],
            selected_primary_source_family="official_clerk_or_code_portal",
            selected_primary_source_url="https://library.municode.com/ca/oakland/codes/code_of_ordinances",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="tuning",
            blind_seed=False,
            known_policy_reference_id="kp-oak-biz-001",
            data_moat_package_classification="stored_not_economic",
            d11_handoff_quality="not_analysis_ready",
            d11_reason="non-economic licensing evidence preserved for filtering",
            structured_observations=[
                {
                    "source_family": "ckan_api",
                    "true_structured": True,
                    "depth": "license_classes",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="cli_only",
            manual_audit_priority="P2",
            manual_audit_sampled=False,
        ),
        _make_seed_row(
            corpus_row_id="lgm-008",
            jurisdiction_id="santa_clara_county_ca",
            jurisdiction_name="Santa Clara County",
            jurisdiction_type="county",
            state="CA",
            policy_family="housing_permits",
            mechanism_family="indirect_supply_constraint",
            query_families=["santa clara county permit timeline housing"],
            expected_official_source_families=[
                "official_pdf_html_attachment",
                "official_clerk_or_code_portal",
            ],
            expected_structured_source_families=["opendatasoft_api", "ckan_api"],
            selected_primary_source_family="official_clerk_or_code_portal",
            selected_primary_source_url="https://plandev.sccgov.org/permit-center",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="blind_evaluation",
            blind_seed=True,
            known_policy_reference_id="kp-scc-permit-001",
            data_moat_package_classification="economic_handoff_candidate",
            d11_handoff_quality="analysis_ready_with_gaps",
            d11_reason="permit duration data supports indirect lag modeling",
            structured_observations=[
                {
                    "source_family": "opendatasoft_api",
                    "true_structured": True,
                    "depth": "permit_duration_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="mixed",
            manual_audit_priority="P1",
            manual_audit_sampled=True,
            deep_dive_type="indirect",
            model_card_reuse_count=1,
        ),
        _make_seed_row(
            corpus_row_id="lgm-009",
            jurisdiction_id="santa_clara_county_ca",
            jurisdiction_name="Santa Clara County",
            jurisdiction_type="county",
            state="CA",
            policy_family="local_tax_fee",
            mechanism_family="direct_fee_or_tax",
            query_families=["santa clara county documentary transfer tax ordinance"],
            expected_official_source_families=["official_pdf_html_attachment"],
            expected_structured_source_families=["state_legislation_api_or_raw"],
            selected_primary_source_family="official_pdf_html_attachment",
            selected_primary_source_url="https://board.sccgov.org/sites/g/files/exjcpb956/files/doc-transfer-tax.pdf",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="tuning",
            blind_seed=False,
            known_policy_reference_id="kp-scc-tax-001",
            data_moat_package_classification="economic_analysis_ready",
            d11_handoff_quality="analysis_ready",
            d11_reason="direct tax schedule and units fully source-grounded",
            structured_observations=[
                {
                    "source_family": "state_legislation_api_or_raw",
                    "true_structured": True,
                    "depth": "tax_rate_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="windmill_live",
            manual_audit_priority="P0",
            manual_audit_sampled=True,
            deep_dive_type="direct",
            model_card_reuse_count=2,
        ),
        _make_seed_row(
            corpus_row_id="lgm-010",
            jurisdiction_id="california_state",
            jurisdiction_name="California",
            jurisdiction_type="state",
            state="CA",
            policy_family="utilities_energy_building_standard",
            mechanism_family="indirect_energy_or_utility_cost",
            query_families=["california building electrification code update title 24"],
            expected_official_source_families=["state_legislation_api_or_raw"],
            expected_structured_source_families=["state_legislation_api_or_raw"],
            selected_primary_source_family="state_legislation_api_or_raw",
            selected_primary_source_url="https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260SB49",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="tuning",
            blind_seed=False,
            known_policy_reference_id="kp-ca-energy-001",
            data_moat_package_classification="secondary_research_needed",
            d11_handoff_quality="analysis_ready_with_gaps",
            d11_reason="statewide effects require localized incidence adjustments",
            structured_observations=[
                {
                    "source_family": "state_legislation_api_or_raw",
                    "true_structured": True,
                    "depth": "section_text_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="windmill_live",
            manual_audit_priority="P1",
            manual_audit_sampled=False,
            deep_dive_type="secondary",
            model_card_reuse_count=1,
        ),
        _make_seed_row(
            corpus_row_id="lgm-011",
            jurisdiction_id="california_state",
            jurisdiction_name="California",
            jurisdiction_type="state",
            state="CA",
            policy_family="air_quality_electrification",
            mechanism_family="indirect_energy_or_utility_cost",
            query_families=[
                "california air resources board electrification rule local compliance"
            ],
            expected_official_source_families=[
                "state_legislation_api_or_raw",
                "official_pdf_html_attachment",
            ],
            expected_structured_source_families=["state_legislation_api_or_raw"],
            selected_primary_source_family="official_pdf_html_attachment",
            selected_primary_source_url="https://ww2.arb.ca.gov/sites/default/files/2026-01/electrification-rule.pdf",
            source_officialness="official_primary",
            source_of_truth_role="implementation_guidance",
            evaluation_split="blind_evaluation",
            blind_seed=True,
            known_policy_reference_id="kp-ca-air-001",
            data_moat_package_classification="economic_handoff_candidate",
            d11_handoff_quality="analysis_ready_with_gaps",
            d11_reason="source-grounded compliance timetable with partial cost ranges",
            structured_observations=[
                {
                    "source_family": "state_legislation_api_or_raw",
                    "true_structured": True,
                    "depth": "compliance_schedule_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="mixed",
            manual_audit_priority="P1",
            manual_audit_sampled=False,
        ),
        _make_seed_row(
            corpus_row_id="lgm-012",
            jurisdiction_id="portland_or",
            jurisdiction_name="Portland",
            jurisdiction_type="city",
            state="OR",
            policy_family="parking_policy",
            mechanism_family="direct_compliance_cost",
            query_families=["portland parking reform code 33.266"],
            expected_official_source_families=["official_clerk_or_code_portal"],
            expected_structured_source_families=["arcgis_rest"],
            selected_primary_source_family="official_clerk_or_code_portal",
            selected_primary_source_url="https://www.portland.gov/code/33/266",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="tuning",
            blind_seed=False,
            known_policy_reference_id="kp-por-parking-001",
            data_moat_package_classification="economic_handoff_candidate",
            d11_handoff_quality="analysis_ready_with_gaps",
            d11_reason="policy text and geospatial applicability available",
            structured_observations=[
                {
                    "source_family": "arcgis_rest",
                    "true_structured": True,
                    "depth": "zone_mapping_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="windmill_live",
            manual_audit_priority="P1",
            manual_audit_sampled=False,
            deep_dive_type="direct",
            model_card_reuse_count=1,
        ),
        _make_seed_row(
            corpus_row_id="lgm-013",
            jurisdiction_id="portland_or",
            jurisdiction_name="Portland",
            jurisdiction_type="city",
            state="OR",
            policy_family="short_term_rental",
            mechanism_family="direct_compliance_cost",
            query_families=["portland short term rental licensing code 33.207"],
            expected_official_source_families=["official_clerk_or_code_portal"],
            expected_structured_source_families=["ckan_api"],
            selected_primary_source_family="official_clerk_or_code_portal",
            selected_primary_source_url="https://www.portland.gov/code/33/207",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="blind_evaluation",
            blind_seed=True,
            known_policy_reference_id="kp-por-str-001",
            data_moat_package_classification="stored_not_economic",
            d11_handoff_quality="not_analysis_ready",
            d11_reason="non-economic value for compliance and risk filters",
            structured_observations=[
                {
                    "source_family": "ckan_api",
                    "true_structured": True,
                    "depth": "permit_registration_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="cli_only",
            manual_audit_priority="P2",
            manual_audit_sampled=False,
        ),
        _make_seed_row(
            corpus_row_id="lgm-014",
            jurisdiction_id="king_county_wa",
            jurisdiction_name="King County",
            jurisdiction_type="county",
            state="WA",
            policy_family="zoning_land_use",
            mechanism_family="indirect_supply_constraint",
            query_families=["king county zoning map amendment multifamily"],
            expected_official_source_families=[
                "official_pdf_html_attachment",
                "official_clerk_or_code_portal",
            ],
            expected_structured_source_families=["arcgis_rest"],
            selected_primary_source_family="official_pdf_html_attachment",
            selected_primary_source_url="https://kingcounty.gov/council/legislation/zoning-amendment-2026.pdf",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="tuning",
            blind_seed=False,
            known_policy_reference_id="kp-king-zoning-001",
            data_moat_package_classification="secondary_research_needed",
            d11_handoff_quality="analysis_ready_with_gaps",
            d11_reason="needs localized conversion assumptions for incidence",
            structured_observations=[
                {
                    "source_family": "arcgis_rest",
                    "true_structured": True,
                    "depth": "parcel_zone_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="mixed",
            manual_audit_priority="P1",
            manual_audit_sampled=False,
            deep_dive_type="indirect",
            model_card_reuse_count=1,
        ),
        _make_seed_row(
            corpus_row_id="lgm-015",
            jurisdiction_id="king_county_wa",
            jurisdiction_name="King County",
            jurisdiction_type="county",
            state="WA",
            policy_family="meeting_action",
            mechanism_family="qualitative_policy_context",
            query_families=["king county council action housing work program"],
            expected_official_source_families=["agenda_meeting_api"],
            expected_structured_source_families=["agenda_meeting_api"],
            selected_primary_source_family="agenda_meeting_api",
            selected_primary_source_url="https://kingcounty.legistar.com/LegislationDetail.aspx?ID=1234567",
            source_officialness="official_primary",
            source_of_truth_role="adoption_action",
            evaluation_split="tuning",
            blind_seed=False,
            known_policy_reference_id="kp-king-meeting-001",
            data_moat_package_classification="qualitative_only",
            d11_handoff_quality="not_analysis_ready",
            d11_reason="qualitative meeting action no quantifiable cost parameters",
            structured_observations=[
                {
                    "source_family": "agenda_meeting_api",
                    "true_structured": False,
                    "depth": "meeting_metadata",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="cataloged_unavailable",
            orchestration_mode="cli_only",
            manual_audit_priority="P2",
            manual_audit_sampled=False,
        ),
        _make_seed_row(
            corpus_row_id="lgm-016",
            jurisdiction_id="austin_tx",
            jurisdiction_name="Austin",
            jurisdiction_type="city",
            state="TX",
            policy_family="affordable_housing_mandate",
            mechanism_family="indirect_housing_cost_pass_through",
            query_families=["austin density bonus affordability ordinance"],
            expected_official_source_families=[
                "official_clerk_or_code_portal",
                "official_pdf_html_attachment",
            ],
            expected_structured_source_families=["socrata_api"],
            selected_primary_source_family="official_pdf_html_attachment",
            selected_primary_source_url="https://www.austintexas.gov/edims/document.cfm?id=456789",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="tuning",
            blind_seed=False,
            known_policy_reference_id="kp-aus-afford-001",
            data_moat_package_classification="economic_handoff_candidate",
            d11_handoff_quality="analysis_ready_with_gaps",
            d11_reason="quantification path exists with incidence uncertainty",
            structured_observations=[
                {
                    "source_family": "socrata_api",
                    "true_structured": True,
                    "depth": "incentive_program_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="windmill_live",
            manual_audit_priority="P1",
            manual_audit_sampled=False,
            deep_dive_type="indirect",
            model_card_reuse_count=1,
        ),
        _make_seed_row(
            corpus_row_id="lgm-017",
            jurisdiction_id="austin_tx",
            jurisdiction_name="Austin",
            jurisdiction_type="city",
            state="TX",
            policy_family="code_enforcement",
            mechanism_family="direct_compliance_cost",
            query_families=["austin code enforcement fee schedule"],
            expected_official_source_families=["official_clerk_or_code_portal"],
            expected_structured_source_families=["ckan_api"],
            selected_primary_source_family="official_clerk_or_code_portal",
            selected_primary_source_url="https://library.municode.com/tx/austin/codes/code_of_ordinances",
            source_officialness="official_primary",
            source_of_truth_role="policy_text",
            evaluation_split="blind_evaluation",
            blind_seed=True,
            known_policy_reference_id="kp-aus-code-001",
            data_moat_package_classification="stored_not_economic",
            d11_handoff_quality="not_analysis_ready",
            d11_reason="non-economic evidence retained for compliance product surface",
            structured_observations=[
                {
                    "source_family": "ckan_api",
                    "true_structured": True,
                    "depth": "inspection_rows",
                    "live_proven": True,
                },
            ],
            source_infrastructure_status="live_integrated",
            orchestration_mode="mixed",
            manual_audit_priority="P2",
            manual_audit_sampled=False,
        ),
        _make_seed_row(
            corpus_row_id="lgm-018",
            jurisdiction_id="austin_tx",
            jurisdiction_name="Austin",
            jurisdiction_type="city",
            state="TX",
            policy_family="procurement_contract",
            mechanism_family="not_economic",
            query_families=["austin council procurement contract local preference"],
            expected_official_source_families=["official_pdf_html_attachment"],
            expected_structured_source_families=["cataloged_unavailable"],
            selected_primary_source_family="official_pdf_html_attachment",
            selected_primary_source_url="https://www.austintexas.gov/edims/document.cfm?id=457890",
            source_officialness="external_advocacy",
            source_of_truth_role="background_only",
            evaluation_split="tuning",
            blind_seed=False,
            known_policy_reference_id="kp-aus-proc-001",
            data_moat_package_classification="not_policy_evidence",
            d11_handoff_quality="not_analysis_ready",
            d11_reason="false-positive off-topic procurement commentary",
            structured_observations=[],
            source_infrastructure_status="cataloged_unavailable",
            orchestration_mode="cli_only",
            manual_audit_priority="P2",
            manual_audit_sampled=False,
        ),
    ]


def _build_cycle_45_expansion_rows() -> list[dict[str, Any]]:
    jurisdictions = [
        {
            "id": "san_diego_ca",
            "name": "San Diego",
            "type": "city",
            "state": "CA",
            "domain": "www.sandiego.gov",
            "slug": "sd",
        },
        {
            "id": "sacramento_ca",
            "name": "Sacramento",
            "type": "city",
            "state": "CA",
            "domain": "www.cityofsacramento.gov",
            "slug": "sac",
        },
        {
            "id": "fresno_ca",
            "name": "Fresno",
            "type": "city",
            "state": "CA",
            "domain": "www.fresno.gov",
            "slug": "fre",
        },
        {
            "id": "portland_or",
            "name": "Portland",
            "type": "city",
            "state": "OR",
            "domain": "www.portland.gov",
            "slug": "por",
        },
        {
            "id": "king_county_wa",
            "name": "King County",
            "type": "county",
            "state": "WA",
            "domain": "kingcounty.gov",
            "slug": "king",
        },
        {
            "id": "austin_tx",
            "name": "Austin",
            "type": "city",
            "state": "TX",
            "domain": "www.austintexas.gov",
            "slug": "aus",
        },
        {
            "id": "denver_co",
            "name": "Denver",
            "type": "city",
            "state": "CO",
            "domain": "www.denvergov.org",
            "slug": "den",
        },
        {
            "id": "phoenix_az",
            "name": "Phoenix",
            "type": "city",
            "state": "AZ",
            "domain": "www.phoenix.gov",
            "slug": "phx",
        },
        {
            "id": "miami_dade_county_fl",
            "name": "Miami-Dade County",
            "type": "county",
            "state": "FL",
            "domain": "www.miamidade.gov",
            "slug": "mdc",
        },
    ]
    policy_templates = [
        {
            "policy_family": "commercial_linkage_fee",
            "policy_code": "commercial-linkage-fee",
            "mechanism_family": "direct_fee_or_tax",
            "query_stub": "commercial linkage fee ordinance rate schedule",
            "expected_official_source_families": ["official_pdf_html_attachment"],
            "expected_structured_source_families": ["socrata_api"],
            "selected_primary_source_family": "official_pdf_html_attachment",
            "source_url_template": "https://{domain}/housing/{policy_code}-2026.pdf",
            "source_of_truth_role": "policy_text",
            "structured_observations": [
                {
                    "source_family": "socrata_api",
                    "true_structured": True,
                    "depth": "fee_schedule_rows",
                    "live_proven": True,
                }
            ],
            "classification": DataMoatPackageClassification.ECONOMIC_HANDOFF_CANDIDATE.value,
            "d11_handoff_quality": "analysis_ready_with_gaps",
            "d11_reason": "parameter inventory present with bounded assumptions",
            "orchestration_mode": "windmill_live",
            "deep_dive_type": "direct",
            "model_card_reuse_count": 2,
        },
        {
            "policy_family": "parking_policy",
            "policy_code": "parking-policy",
            "mechanism_family": "direct_compliance_cost",
            "query_stub": "multifamily parking minimum update",
            "expected_official_source_families": ["official_clerk_or_code_portal"],
            "expected_structured_source_families": ["arcgis_rest"],
            "selected_primary_source_family": "official_clerk_or_code_portal",
            "source_url_template": "https://{domain}/code/{policy_code}",
            "source_of_truth_role": "policy_text",
            "structured_observations": [
                {
                    "source_family": "arcgis_rest",
                    "true_structured": True,
                    "depth": "zone_mapping_rows",
                    "live_proven": True,
                }
            ],
            "classification": DataMoatPackageClassification.ECONOMIC_HANDOFF_CANDIDATE.value,
            "d11_handoff_quality": "analysis_ready_with_gaps",
            "d11_reason": "policy text and geospatial applicability available",
            "orchestration_mode": "windmill_live",
            "deep_dive_type": "direct",
            "model_card_reuse_count": 1,
        },
        {
            "policy_family": "housing_permits",
            "policy_code": "housing-permits",
            "mechanism_family": "indirect_supply_constraint",
            "query_stub": "housing permit timeline dashboard",
            "expected_official_source_families": ["official_clerk_or_code_portal"],
            "expected_structured_source_families": ["opendatasoft_api"],
            "selected_primary_source_family": "official_clerk_or_code_portal",
            "source_url_template": "https://{domain}/permit-center/{policy_code}",
            "source_of_truth_role": "policy_text",
            "structured_observations": [
                {
                    "source_family": "opendatasoft_api",
                    "true_structured": True,
                    "depth": "permit_duration_rows",
                    "live_proven": True,
                }
            ],
            "classification": DataMoatPackageClassification.ECONOMIC_HANDOFF_CANDIDATE.value,
            "d11_handoff_quality": "analysis_ready_with_gaps",
            "d11_reason": "permit duration data supports indirect lag modeling",
            "orchestration_mode": "mixed",
            "deep_dive_type": "indirect",
            "model_card_reuse_count": 1,
        },
        {
            "policy_family": "zoning_land_use",
            "policy_code": "zoning-land-use",
            "mechanism_family": "indirect_supply_constraint",
            "query_stub": "zoning map amendment multifamily",
            "expected_official_source_families": [
                "official_pdf_html_attachment",
                "official_clerk_or_code_portal",
            ],
            "expected_structured_source_families": ["arcgis_rest"],
            "selected_primary_source_family": "official_clerk_or_code_portal",
            "source_url_template": "https://{domain}/planning/{policy_code}",
            "source_of_truth_role": "policy_text",
            "structured_observations": [
                {
                    "source_family": "arcgis_rest",
                    "true_structured": True,
                    "depth": "parcel_zone_rows",
                    "live_proven": True,
                }
            ],
            "classification": DataMoatPackageClassification.SECONDARY_RESEARCH_NEEDED.value,
            "d11_handoff_quality": "analysis_ready_with_gaps",
            "d11_reason": "needs localized conversion assumptions for incidence",
            "orchestration_mode": "mixed",
            "deep_dive_type": "indirect",
            "model_card_reuse_count": 1,
        },
        {
            "policy_family": "code_enforcement",
            "policy_code": "code-enforcement",
            "mechanism_family": "direct_compliance_cost",
            "query_stub": "code enforcement fee schedule",
            "expected_official_source_families": ["official_pdf_html_attachment"],
            "expected_structured_source_families": ["ckan_api"],
            "selected_primary_source_family": "official_pdf_html_attachment",
            "source_url_template": "https://{domain}/documents/{policy_code}-schedule.pdf",
            "source_of_truth_role": "policy_text",
            "structured_observations": [
                {
                    "source_family": "ckan_api",
                    "true_structured": True,
                    "depth": "inspection_rows",
                    "live_proven": True,
                }
            ],
            "classification": DataMoatPackageClassification.STORED_NOT_ECONOMIC.value,
            "d11_handoff_quality": "not_analysis_ready",
            "d11_reason": "non-economic compliance evidence preserved for downstream joins",
            "orchestration_mode": "mixed",
            "deep_dive_type": None,
            "model_card_reuse_count": 0,
        },
        {
            "policy_family": "short_term_rental",
            "policy_code": "short-term-rental",
            "mechanism_family": "direct_compliance_cost",
            "query_stub": "short term rental permit code",
            "expected_official_source_families": ["official_clerk_or_code_portal"],
            "expected_structured_source_families": ["ckan_api"],
            "selected_primary_source_family": "official_clerk_or_code_portal",
            "source_url_template": "https://{domain}/code/{policy_code}",
            "source_of_truth_role": "policy_text",
            "structured_observations": [
                {
                    "source_family": "ckan_api",
                    "true_structured": True,
                    "depth": "permit_registration_rows",
                    "live_proven": True,
                }
            ],
            "classification": DataMoatPackageClassification.QUALITATIVE_ONLY.value,
            "d11_handoff_quality": "not_analysis_ready",
            "d11_reason": "qualitative enforcement context captured without unitized costs",
            "orchestration_mode": "mixed",
            "deep_dive_type": None,
            "model_card_reuse_count": 0,
        },
        {
            "policy_family": "affordable_housing_mandate",
            "policy_code": "affordable-housing-mandate",
            "mechanism_family": "indirect_housing_cost_pass_through",
            "query_stub": "inclusionary housing affordability ordinance",
            "expected_official_source_families": ["official_pdf_html_attachment"],
            "expected_structured_source_families": ["socrata_api"],
            "selected_primary_source_family": "official_pdf_html_attachment",
            "source_url_template": "https://{domain}/housing/{policy_code}.pdf",
            "source_of_truth_role": "policy_text",
            "structured_observations": [
                {
                    "source_family": "socrata_api",
                    "true_structured": True,
                    "depth": "affordability_units",
                    "live_proven": True,
                }
            ],
            "classification": DataMoatPackageClassification.SECONDARY_RESEARCH_NEEDED.value,
            "d11_handoff_quality": "analysis_ready_with_gaps",
            "d11_reason": "incidence assumptions needed for indirect cost conversion",
            "orchestration_mode": "windmill_live",
            "deep_dive_type": "secondary",
            "model_card_reuse_count": 1,
        },
        {
            "policy_family": "local_tax_fee",
            "policy_code": "local-tax-fee",
            "mechanism_family": "direct_fee_or_tax",
            "query_stub": "documentary transfer tax ordinance rate",
            "expected_official_source_families": ["official_pdf_html_attachment"],
            "expected_structured_source_families": ["state_legislation_api_or_raw"],
            "selected_primary_source_family": "official_pdf_html_attachment",
            "source_url_template": "https://{domain}/finance/{policy_code}-rate.pdf",
            "source_of_truth_role": "policy_text",
            "structured_observations": [
                {
                    "source_family": "state_legislation_api_or_raw",
                    "true_structured": True,
                    "depth": "tax_rate_rows",
                    "live_proven": True,
                }
            ],
            "classification": DataMoatPackageClassification.ECONOMIC_ANALYSIS_READY.value,
            "d11_handoff_quality": "analysis_ready",
            "d11_reason": "direct tax schedule and units fully source-grounded",
            "orchestration_mode": "windmill_live",
            "deep_dive_type": "direct",
            "model_card_reuse_count": 2,
        },
    ]

    generated_rows: list[dict[str, Any]] = []
    row_counter = 19
    generated_index = 0
    for jurisdiction_index, jurisdiction in enumerate(jurisdictions):
        for template_index, template in enumerate(policy_templates):
            row_id = f"lgm-{row_counter:03d}"
            row_counter += 1
            evaluation_split = (
                "blind_evaluation"
                if (jurisdiction_index + template_index) % 3 == 0
                else "tuning"
            )
            generated_row = _make_seed_row(
                corpus_row_id=row_id,
                jurisdiction_id=jurisdiction["id"],
                jurisdiction_name=jurisdiction["name"],
                jurisdiction_type=jurisdiction["type"],
                state=jurisdiction["state"],
                policy_family=template["policy_family"],
                mechanism_family=template["mechanism_family"],
                query_families=[
                    f"{jurisdiction['name'].lower()} {template['query_stub']}"
                ],
                expected_official_source_families=template[
                    "expected_official_source_families"
                ],
                expected_structured_source_families=template[
                    "expected_structured_source_families"
                ],
                selected_primary_source_family=template[
                    "selected_primary_source_family"
                ],
                selected_primary_source_url=template["source_url_template"].format(
                    domain=jurisdiction["domain"],
                    policy_code=template["policy_code"],
                ),
                source_officialness="official_primary",
                source_of_truth_role=template["source_of_truth_role"],
                evaluation_split=evaluation_split,
                blind_seed=evaluation_split == "blind_evaluation",
                known_policy_reference_id=(
                    f"kp-{jurisdiction['slug']}-{template['policy_code']}-c45"
                ),
                data_moat_package_classification=template["classification"],
                d11_handoff_quality=template["d11_handoff_quality"],
                d11_reason=template["d11_reason"],
                structured_observations=_as_cataloged_structured_intent(
                    template["structured_observations"],
                    proof_source="generated_expansion_matrix",
                ),
                source_infrastructure_status="cataloged_intent",
                orchestration_mode=template["orchestration_mode"],
                manual_audit_priority="P1",
                manual_audit_sampled=generated_index < 24,
                deep_dive_type=template["deep_dive_type"],
                model_card_reuse_count=template["model_card_reuse_count"],
            )
            extraction_depth = generated_row.get("extraction_depth")
            if isinstance(extraction_depth, dict):
                extraction_depth["live_exercised"] = False
                extraction_depth["proof_status"] = "cataloged_intent"
                extraction_depth["proof_source"] = "generated_expansion_matrix"
            generated_rows.append(generated_row)
            generated_index += 1
    return generated_rows


def build_local_government_corpus_matrix_seed() -> dict[str, Any]:
    rows = _build_seed_rows() + _build_cycle_45_expansion_rows()
    known_policy_references = [
        {
            "known_policy_reference_id": row["known_policy_reference_id"],
            "jurisdiction_id": row["jurisdiction"]["id"],
            "policy_family": row["policy_family"],
            "expected_official_source_family": row["expected_official_source_families"][
                0
            ],
            "expected_structured_source_family": (
                row["expected_structured_source_families"][0]
                if row["expected_structured_source_families"]
                else "cataloged_absent"
            ),
            "expected_structured_depth_target": (
                row["expected_structured_depth_targets"][0]
                if row.get("expected_structured_depth_targets")
                else {
                    "source_family": "cataloged_absent",
                    "depth": "cataloged_absent",
                    "proof_status": "cataloged_absent",
                }
            ),
            "expected_handoff_class": row["classification"][
                "data_moat_package_classification"
            ],
            "evaluation_split": row["evaluation_split"],
        }
        for row in rows
    ]

    matrix: dict[str, Any] = {
        "benchmark_id": "local_government_data_moat_benchmark_v0",
        "feature_key": "bd-3wefe.13.4.1",
        "schema_version": "local_government_corpus_matrix_v1",
        "taxonomy_version": "corpus_taxonomy_v1",
        "gate_version": "data_moat_c0_c14_v1",
        "generated_at": "2026-04-17T00:00:00+00:00",
        "seed_mode": "expanded_generator_cycle_45",
        "target_row_range": {"min": 75, "max": 120},
        "corpus_readiness_target": "corpus_ready_with_gaps",
        "expansion_backlog": [
            {
                "backlog_id": "expand-state-level-policy-families",
                "description": "Add additional state-level rows for non-CA jurisdictions to harden longitudinal coverage.",
                "target_rows": 18,
            },
            {
                "backlog_id": "increase-manual-audit-to-45",
                "description": "Grow sampled manual audits from 31 to 45 rows while keeping stratification guarantees.",
                "target_rows": 14,
            },
            {
                "backlog_id": "raise-windmill-live-share",
                "description": "Increase windmill_live share for policy families that still run in mixed mode.",
                "target_rows": 12,
            },
        ],
        "product_surface": {
            "read_api_endpoint": "/api/policy-evidence/corpus",
            "export_artifact_path": (
                "docs/poc/policy-evidence-quality-spine/artifacts/local_government_corpus_scorecard.json"
            ),
            "schema_fields": [
                "package_id",
                "corpus_row_id",
                "jurisdiction.id",
                "policy_family",
                "selected_primary_source.source_family",
                "classification.data_moat_package_classification",
                "classification.d11_handoff_quality",
                "freshness.retrieved_at",
                "infrastructure_status.orchestration_mode",
            ],
            "access_control": {
                "internal_admin": "required",
                "customer_beta": "planned",
            },
            "query_examples": [
                {"dimension": "jurisdiction", "example": "jurisdiction.id=portland_or"},
                {
                    "dimension": "policy_family",
                    "example": "policy_family=zoning_land_use",
                },
                {
                    "dimension": "source_family",
                    "example": "selected_primary_source.source_family=official_pdf_html_attachment",
                },
                {
                    "dimension": "officialness",
                    "example": "selected_primary_source.source_officialness=official_primary",
                },
                {
                    "dimension": "freshness",
                    "example": "freshness.stale_for_policy_use=false",
                },
                {
                    "dimension": "classification",
                    "example": "classification.data_moat_package_classification=economic_handoff_candidate",
                },
            ],
        },
        "schema_contract": {
            "package_schema_version": "policy_evidence_package_v1",
            "source_taxonomy_version": "corpus_taxonomy_v1",
            "gate_version": "data_moat_c0_c14_v1",
            "migration_backfill_notes": "v1 baseline no backfill yet",
            "field_change_rules": "additive fields only until corpus_v2",
            "unknown_field_handling": "ignore_and_log",
        },
        "non_fee_extraction_templates": [
            {
                "template_id": "non_fee_template::zoning_land_use",
                "policy_family": "zoning_land_use",
            },
            {
                "template_id": "non_fee_template::short_term_rental",
                "policy_family": "short_term_rental",
            },
            {
                "template_id": "non_fee_template::code_enforcement",
                "policy_family": "code_enforcement",
            },
            {
                "template_id": "non_fee_template::housing_permits",
                "policy_family": "housing_permits",
            },
        ],
        "known_policy_references": known_policy_references,
        "rows": rows
        + [
            {
                "row_type": "infrastructure_milestone",
                "corpus_row_id": "infra-001",
                "name": "source-identity-classifier",
                "status": "in_progress",
                "owner": "bd-3wefe.13.2",
            },
            {
                "row_type": "infrastructure_milestone",
                "corpus_row_id": "infra-002",
                "name": "non-san-jose-structured-runtime",
                "status": "in_progress",
                "owner": "bd-3wefe.13.6",
            },
        ],
    }
    return matrix


class LocalGovernmentCorpusBenchmarkService:
    """Evaluate corpus matrix fixtures against C0-C14 gates without live infra."""

    def evaluate(
        self,
        *,
        matrix: dict[str, Any],
        windmill_orchestration_artifact: dict[str, Any] | None = None,
        windmill_row_proof_overlay: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        rows = [
            row
            for row in matrix.get("rows", [])
            if isinstance(row, dict) and row.get("row_type") == "corpus_package"
        ]
        c13_rows = self._build_c13_rows_with_proof_overlay(
            matrix=matrix,
            rows=rows,
            windmill_orchestration_artifact=windmill_orchestration_artifact,
            windmill_row_proof_overlay=windmill_row_proof_overlay,
        )

        gate_results: dict[str, GateResult] = {
            "C0": self._evaluate_c0(matrix=matrix, rows=rows),
            "C1": self._evaluate_c1(rows=rows),
            "C2": self._evaluate_c2(rows=rows),
            "C3": self._evaluate_c3(rows=rows),
            "C4": self._evaluate_c4(rows=rows),
            "C5": self._evaluate_c5(rows=rows),
            "C6": self._evaluate_c6(matrix=matrix, rows=rows),
            "C7": self._evaluate_c7(rows=rows),
            "C8": self._evaluate_c8(rows=rows),
            "C9": self._evaluate_c9(rows=rows),
            "C9a": self._evaluate_c9a(matrix=matrix),
            "C10": self._evaluate_c10(rows=rows),
            "C11": self._evaluate_c11(matrix=matrix, rows=rows),
            "C12": self._evaluate_c12(matrix=matrix, rows=rows),
            "C13": self._evaluate_c13(matrix=matrix, rows=c13_rows),
            "C14": self._evaluate_c14(matrix=matrix, rows=rows),
        }

        core_metrics = self._build_core_metrics(rows=rows, gate_results=gate_results)
        package_gate_projection = self._build_package_gate_projection(rows=rows)
        gate_json = {gate_id: gate.to_json() for gate_id, gate in gate_results.items()}
        corpus_state = self._derive_corpus_state(gates=gate_json)
        next_blocker = self._derive_next_blocker(gates=gate_json)

        scorecard = {
            "benchmark_id": str(
                matrix.get("benchmark_id") or "local_government_data_moat_benchmark_v0"
            ),
            "feature_key": str(matrix.get("feature_key") or "bd-3wefe.13.4.1"),
            "scorecard_schema_version": "local_government_corpus_scorecard_v1",
            "taxonomy_version": str(matrix.get("taxonomy_version") or ""),
            "gate_version": str(matrix.get("gate_version") or ""),
            "generated_at": _iso_now(),
            "matrix_digest": _hash_payload(matrix),
            "matrix_summary": {
                "row_count_total": len(matrix.get("rows", [])),
                "package_row_count": len(rows),
                "milestone_row_count": len(matrix.get("rows", [])) - len(rows),
                "seed_mode": matrix.get("seed_mode"),
                "corpus_readiness_target": matrix.get("corpus_readiness_target"),
            },
            "core_metrics": core_metrics,
            "gates": gate_json,
            "package_gate_projection": package_gate_projection,
            "corpus_state": corpus_state,
            "next_eval_blocker": next_blocker,
            "expansion_backlog": list(matrix.get("expansion_backlog", [])),
        }
        return scorecard

    def render_markdown_report(
        self, *, matrix: dict[str, Any], scorecard: dict[str, Any]
    ) -> str:
        gates = scorecard.get("gates", {})
        non_pass = [
            gate_id for gate_id, gate in gates.items() if gate.get("status") != "pass"
        ]
        blocker = scorecard.get("next_eval_blocker") or {}

        c13_gate = gates.get("C13", {})
        c13_metrics = c13_gate.get("metrics")
        if not isinstance(c13_metrics, dict):
            c13_metrics = {}
        c2_metrics = (gates.get("C2", {}) or {}).get("metrics")
        if not isinstance(c2_metrics, dict):
            c2_metrics = {}
        c14_metrics = (gates.get("C14", {}) or {}).get("metrics")
        if not isinstance(c14_metrics, dict):
            c14_metrics = {}
        c13_live_proven_rows = int(c13_metrics.get("live_proven_rows") or 0)
        c13_seeded_target_rows = int(
            c13_metrics.get("seeded_ref_target_rows")
            or (c13_live_proven_rows + int(c13_metrics.get("seeded_not_live_proven_rows") or 0))
        )
        c13_remaining_seeded_rows = int(
            c13_metrics.get("remaining_seeded_ref_row_count")
            or c13_metrics.get("seeded_not_live_proven_rows")
            or 0
        )
        c13_orchestration_intent_rows = int(
            c13_metrics.get("orchestration_intent_rows") or 0
        )
        c13_mode_counts = c13_metrics.get("mode_counts")
        if not isinstance(c13_mode_counts, dict):
            c13_mode_counts = {}
        c13_coverage_ratio = c13_metrics.get("live_proof_coverage_ratio")
        c13_next_targets = c13_metrics.get("next_seeded_ref_target_rows")
        if not isinstance(c13_next_targets, list):
            c13_next_targets = []
        c13_next_targets_display = ", ".join(
            str(row_id) for row_id in c13_next_targets[:10]
        ) or "none"

        lines = [
            "# Local Government Corpus Report",
            "",
            f"- benchmark_id: `{scorecard.get('benchmark_id')}`",
            f"- feature_key: `{scorecard.get('feature_key')}`",
            f"- corpus_state: `{scorecard.get('corpus_state')}`",
            f"- package_rows: `{scorecard.get('matrix_summary', {}).get('package_row_count')}`",
            f"- seed_mode: `{scorecard.get('matrix_summary', {}).get('seed_mode')}`",
            "",
            "## Gate Status",
            "",
        ]
        for gate_id in [
            "C0",
            "C1",
            "C2",
            "C3",
            "C4",
            "C5",
            "C6",
            "C7",
            "C8",
            "C9",
            "C9a",
            "C10",
            "C11",
            "C12",
            "C13",
            "C14",
        ]:
            gate = gates.get(gate_id, {})
            lines.append(
                f"- {gate_id}: `{gate.get('status', 'unknown')}` - {gate.get('reason', 'n/a')}"
            )

        lines.extend(
            [
                "",
                "## Structured Proof Boundary",
                "",
                f"- C2 live structured coverage ratio: `{c2_metrics.get('live_structured_coverage_ratio')}`",
                f"- C2 live true structured families: `{c2_metrics.get('live_true_structured_family_count')}`",
                f"- C2 cataloged true structured families: `{c2_metrics.get('cataloged_true_structured_family_count')}`",
                f"- C14 live non-fee families: `{c14_metrics.get('live_non_fee_family_count')}`",
                f"- C14 cataloged non-fee families: `{c14_metrics.get('cataloged_non_fee_family_count')}`",
                "",
                "## C13 Burn-down",
                "",
                f"- mode counts: `{json.dumps(c13_mode_counts, sort_keys=True)}`",
                f"- live proof coverage ratio: `{c13_coverage_ratio}`",
                f"- live proof progress: `{c13_live_proven_rows}/{c13_seeded_target_rows}`",
                f"- orchestration-intent rows awaiting live proof: `{c13_orchestration_intent_rows}`",
                f"- remaining seeded ref rows: `{c13_remaining_seeded_rows}`",
                f"- next seeded ref target rows: `{c13_next_targets_display}`",
                "",
                "## Current Gaps",
                "",
                f"- non-pass gate count: `{len(non_pass)}`",
                f"- next blocker gate: `{blocker.get('gate', 'none')}`",
                f"- next blocker reason: {blocker.get('reason', 'none')}",
                "",
                "## Next Eval Blocker",
                "",
                (
                    "- All benchmark gates currently pass; continue with live corpus refresh and drift monitoring."
                    if not blocker.get("gate")
                    else f"- Address {blocker.get('gate')} before next decision-grade assertion."
                ),
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def build_seed_artifacts(self) -> dict[str, Any]:
        matrix = build_local_government_corpus_matrix_seed()
        scorecard = self.evaluate(matrix=matrix)
        report = self.render_markdown_report(matrix=matrix, scorecard=scorecard)
        return {
            "matrix": matrix,
            "scorecard": scorecard,
            "report_markdown": report,
        }

    def _evaluate_c0(
        self, *, matrix: dict[str, Any], rows: list[dict[str, Any]]
    ) -> GateResult:
        jurisdictions: dict[str, int] = {}
        policy_families: set[str] = set()
        source_families: set[str] = set()
        non_ca_jurisdictions: set[str] = set()

        for row in rows:
            jurisdiction = str((row.get("jurisdiction") or {}).get("id") or "")
            if jurisdiction:
                jurisdictions[jurisdiction] = jurisdictions.get(jurisdiction, 0) + 1
            state = str((row.get("jurisdiction") or {}).get("state") or "")
            if state and state != "CA":
                non_ca_jurisdictions.add(jurisdiction)
            policy_family = str(row.get("policy_family") or "")
            if policy_family:
                policy_families.add(policy_family)
            source_family = str(
                (row.get("selected_primary_source") or {}).get("source_family") or ""
            )
            if source_family:
                source_families.add(source_family)
            for structured in row.get("structured_source_observations", []):
                if isinstance(structured, dict):
                    family = str(structured.get("source_family") or "")
                    if family:
                        source_families.add(family)

        package_count = len(rows)
        san_jose_only = set(jurisdictions.keys()) == {"san_jose_ca"}
        california_only = bool(jurisdictions) and len(non_ca_jurisdictions) == 0
        policy_family_count = len(policy_families)
        source_family_count = len(source_families)
        max_jurisdiction_share = (
            max(jurisdictions.values()) / package_count
            if package_count and jurisdictions
            else 0.0
        )
        stored_or_qualitative_count = sum(
            1
            for row in rows
            if str(
                (row.get("classification") or {}).get(
                    "data_moat_package_classification"
                )
                or ""
            )
            in {
                DataMoatPackageClassification.STORED_NOT_ECONOMIC.value,
                DataMoatPackageClassification.QUALITATIVE_ONLY.value,
            }
        )
        non_fee_depth_families = {
            str(row.get("policy_family") or "")
            for row in rows
            if _is_non_fee_policy_family(str(row.get("policy_family") or ""))
            and any(
                isinstance(item, dict) and bool(item.get("true_structured"))
                for item in row.get("structured_source_observations", [])
            )
        }

        metrics = {
            "package_count": package_count,
            "jurisdiction_count": len(jurisdictions),
            "non_ca_jurisdiction_count": len(non_ca_jurisdictions),
            "policy_family_count": policy_family_count,
            "source_family_count": source_family_count,
            "max_jurisdiction_share": round(max_jurisdiction_share, 4),
            "stored_or_qualitative_ratio": round(
                (stored_or_qualitative_count / package_count) if package_count else 0.0,
                4,
            ),
            "non_fee_depth_family_count": len(non_fee_depth_families),
        }

        blockers: list[str] = []
        if san_jose_only:
            blockers.append("san_jose_only")
        if california_only:
            blockers.append("california_only")
        if policy_family_count < 8:
            blockers.append("policy_family_count_below_8")
        if source_family_count < 5:
            blockers.append("source_family_count_below_5")
        if len(non_ca_jurisdictions) < 2:
            blockers.append("non_ca_jurisdictions_below_2")
        if max_jurisdiction_share > 0.4:
            blockers.append("single_jurisdiction_over_40_percent")
        if package_count and (stored_or_qualitative_count / package_count) < 0.1:
            blockers.append("stored_or_qualitative_below_10_percent")
        if len(non_fee_depth_families) < 3:
            blockers.append("non_fee_depth_families_below_3")

        if san_jose_only:
            return GateResult(
                status="fail",
                reason="Corpus is San-Jose-only and fails C0 anti-tokenism scope rule.",
                metrics=metrics,
                blockers=blockers,
            )

        if package_count < 75:
            has_backlog = bool(matrix.get("expansion_backlog"))
            if (
                has_backlog
                and str(matrix.get("corpus_readiness_target") or "")
                == "corpus_ready_with_gaps"
            ):
                return GateResult(
                    status="not_proven",
                    reason="Seed matrix is intentionally below 75 rows with explicit expansion backlog.",
                    metrics=metrics,
                    blockers=blockers + ["package_count_below_75"],
                )
            return GateResult(
                status="fail",
                reason="Corpus package count is below C0 threshold without explicit backlog contract.",
                metrics=metrics,
                blockers=blockers + ["package_count_below_75"],
            )

        if blockers:
            return GateResult(
                status="fail",
                reason="C0 composition requirements are not met.",
                metrics=metrics,
                blockers=blockers,
            )
        return GateResult(
            status="pass",
            reason="Corpus scope and composition satisfy C0.",
            metrics=metrics,
            blockers=[],
        )

    def _evaluate_c1(self, *, rows: list[dict[str, Any]]) -> GateResult:
        primary_rows = [
            row for row in rows if isinstance(row.get("selected_primary_source"), dict)
        ]
        audited_rows = [
            row
            for row in primary_rows
            if bool((row.get("manual_audit") or {}).get("sampled"))
            and str(row.get("manual_audit_priority") or "") in {"P0", "P1"}
        ]

        if not primary_rows:
            return GateResult(
                status="not_proven",
                reason="No primary source rows available for C1 dominance scoring.",
                metrics={"primary_row_count": 0},
                blockers=["primary_rows_missing"],
            )

        official_primary_count = 0
        audited_official_count = 0
        tavily_exa_primary_corpus = 0
        tavily_exa_primary_audited = 0
        unruled_external_primary_rows: list[str] = []
        missing_required_fields: list[str] = []

        for row in primary_rows:
            source = row.get("selected_primary_source") or {}
            officialness = str(source.get("source_officialness") or "")
            if not officialness:
                missing_required_fields.append(
                    str(row.get("corpus_row_id") or "unknown")
                )
                continue

            provider_usage = row.get("provider_usage") or {}
            tavily_primary = bool(provider_usage.get("tavily_primary_selected"))
            exa_primary = bool(provider_usage.get("exa_primary_selected"))
            if tavily_primary or exa_primary:
                tavily_exa_primary_corpus += 1

            if officialness == "official_primary":
                official_primary_count += 1
            elif officialness in EXTERNAL_SOURCE_OFFICIALNESS:
                classification = str(
                    (row.get("classification") or {}).get(
                        "data_moat_package_classification"
                    )
                    or ""
                )
                promotion = row.get("external_source_promotion")
                is_fail_row = classification in {
                    DataMoatPackageClassification.NOT_POLICY_EVIDENCE.value,
                    DataMoatPackageClassification.FAIL.value,
                }
                has_rule = isinstance(promotion, dict) and bool(
                    promotion.get("rule_id")
                )
                if not is_fail_row and not has_rule:
                    unruled_external_primary_rows.append(
                        str(row.get("corpus_row_id") or "unknown")
                    )

            if row in audited_rows:
                if officialness == "official_primary":
                    audited_official_count += 1
                if tavily_primary or exa_primary:
                    tavily_exa_primary_audited += 1

        corpus_official_ratio = official_primary_count / len(primary_rows)
        audited_official_ratio = (
            audited_official_count / len(audited_rows) if audited_rows else 0.0
        )
        tavily_exa_corpus_ratio = tavily_exa_primary_corpus / len(primary_rows)
        tavily_exa_audited_ratio = (
            tavily_exa_primary_audited / len(audited_rows) if audited_rows else 0.0
        )
        metrics = {
            "primary_row_count": len(primary_rows),
            "audited_p0_p1_count": len(audited_rows),
            "corpus_official_primary_ratio": round(corpus_official_ratio, 4),
            "audited_official_primary_ratio": round(audited_official_ratio, 4),
            "tavily_exa_primary_ratio_corpus": round(tavily_exa_corpus_ratio, 4),
            "tavily_exa_primary_ratio_audited": round(tavily_exa_audited_ratio, 4),
        }

        blockers: list[str] = []
        if missing_required_fields:
            blockers.append("source_officialness_missing")
        if not audited_rows:
            blockers.append("audited_p0_p1_rows_missing")
        if unruled_external_primary_rows:
            blockers.append("external_primary_without_rule_or_fail_verdict")
        if tavily_exa_primary_audited > 0:
            blockers.append("tavily_exa_primary_selected_in_audited_sample")
        if tavily_exa_corpus_ratio > 0.05:
            blockers.append("tavily_exa_primary_over_5_percent_corpus_cap")
        if corpus_official_ratio < 0.8 or (
            audited_rows and audited_official_ratio < 0.8
        ):
            blockers.append("official_dominance_below_hard_floor_80_percent")

        if blockers:
            return GateResult(
                status="fail",
                reason="C1 official-source dominance contract violated.",
                metrics=metrics,
                blockers=blockers,
            )

        if corpus_official_ratio >= 0.85 and audited_official_ratio >= 0.9:
            return GateResult(
                status="pass",
                reason="Official-source dominance and Tavily/Exa primary caps satisfy C1.",
                metrics=metrics,
                blockers=[],
            )
        return GateResult(
            status="not_proven",
            reason="Official-source dominance is below pass thresholds but above hard-fail floors.",
            metrics=metrics,
            blockers=["official_dominance_below_pass_threshold"],
        )

    def _evaluate_c2(self, *, rows: list[dict[str, Any]]) -> GateResult:
        source_families: set[str] = set()
        true_structured_families: set[str] = set()
        live_true_structured_families: set[str] = set()
        cataloged_true_structured_families: set[str] = set()
        true_structured_non_legistar = False
        live_true_structured_non_legistar = False
        covered_cells = 0
        live_covered_cells = 0
        uncovered_without_absence = 0
        non_primary_jurisdictions: dict[str, dict[str, bool]] = {}

        for row in rows:
            source_family = str(
                (row.get("selected_primary_source") or {}).get("source_family") or ""
            )
            if source_family:
                source_families.add(source_family)

            jurisdiction_id = str((row.get("jurisdiction") or {}).get("id") or "")
            if jurisdiction_id and jurisdiction_id != "san_jose_ca":
                non_primary_jurisdictions.setdefault(
                    jurisdiction_id,
                    {
                        "has_live_true_structured": False,
                        "has_cataloged_true_structured": False,
                        "has_catalog_absence": False,
                    },
                )

            has_true_structured = False
            has_live_true_structured = False
            for observation in row.get("structured_source_observations", []):
                if not isinstance(observation, dict):
                    continue
                family = str(observation.get("source_family") or "")
                if family:
                    source_families.add(family)

                true_structured = bool(observation.get("true_structured"))
                if true_structured and family not in SECONDARY_SEARCH_FAMILIES:
                    has_true_structured = True
                    true_structured_families.add(family)
                    live_proven = _structured_observation_is_live_proven(observation)
                    if live_proven:
                        has_live_true_structured = True
                        live_true_structured_families.add(family)
                    else:
                        cataloged_true_structured_families.add(family)
                    if family not in LEGISTAR_LIKE_FAMILIES:
                        true_structured_non_legistar = True
                        if live_proven:
                            live_true_structured_non_legistar = True
                    if jurisdiction_id in non_primary_jurisdictions:
                        key = (
                            "has_live_true_structured"
                            if live_proven
                            else "has_cataloged_true_structured"
                        )
                        non_primary_jurisdictions[jurisdiction_id][key] = True

            if has_true_structured:
                covered_cells += 1
            if has_live_true_structured:
                live_covered_cells += 1
            elif not has_true_structured and str(row.get("structured_cell_status") or "") == "cataloged_absent":
                covered_cells += 1
                if jurisdiction_id in non_primary_jurisdictions:
                    non_primary_jurisdictions[jurisdiction_id][
                        "has_catalog_absence"
                    ] = True
            elif not has_true_structured:
                uncovered_without_absence += 1

        row_count = len(rows)
        coverage_ratio = covered_cells / row_count if row_count else 0.0
        live_coverage_ratio = live_covered_cells / row_count if row_count else 0.0
        shallow_legistar_only = bool(
            true_structured_families
        ) and true_structured_families.issubset(LEGISTAR_LIKE_FAMILIES)
        missing_non_primary_structured = [
            jurisdiction
            for jurisdiction, status in non_primary_jurisdictions.items()
            if not status["has_live_true_structured"] and not status["has_catalog_absence"]
        ]
        non_primary_cataloged_only = [
            jurisdiction
            for jurisdiction, status in non_primary_jurisdictions.items()
            if not status["has_live_true_structured"]
            and status["has_cataloged_true_structured"]
        ]
        metrics = {
            "source_family_count": len(source_families),
            "true_structured_family_count": len(true_structured_families),
            "live_true_structured_family_count": len(live_true_structured_families),
            "cataloged_true_structured_family_count": len(
                cataloged_true_structured_families
            ),
            "coverage_ratio": round(coverage_ratio, 4),
            "live_structured_coverage_ratio": round(live_coverage_ratio, 4),
            "non_legistar_true_structured_present": true_structured_non_legistar,
            "live_non_legistar_true_structured_present": (
                live_true_structured_non_legistar
            ),
            "non_primary_jurisdiction_count": len(non_primary_jurisdictions),
            "non_primary_without_structured_or_absence": len(
                missing_non_primary_structured
            ),
            "non_primary_cataloged_only_count": len(non_primary_cataloged_only),
        }

        blockers: list[str] = []
        if len(source_families) < 5:
            blockers.append("source_family_count_below_5")
        if len(live_true_structured_families) < 2:
            blockers.append("live_true_structured_family_count_below_2")
        if not live_true_structured_non_legistar:
            blockers.append("live_non_legistar_true_structured_missing")
        if coverage_ratio < 0.4:
            blockers.append("structured_coverage_below_40_percent")
        if live_coverage_ratio < 0.4:
            blockers.append("live_structured_coverage_below_40_percent")
        if cataloged_true_structured_families:
            blockers.append("structured_sources_cataloged_not_live_proven")
        if uncovered_without_absence > 0:
            blockers.append("uncovered_cells_missing_catalog_absence_evidence")
        if missing_non_primary_structured:
            blockers.append("non_primary_jurisdictions_without_structured_or_absence")
        if non_primary_cataloged_only:
            blockers.append("non_primary_structured_sources_cataloged_not_live_proven")
        if shallow_legistar_only:
            blockers.append("shallow_legistar_only_structured_depth")

        if blockers:
            status = (
                "not_proven"
                if cataloged_true_structured_families
                and not {
                    "source_family_count_below_5",
                    "uncovered_cells_missing_catalog_absence_evidence",
                    "shallow_legistar_only_structured_depth",
                }.intersection(blockers)
                else "fail"
            )
            return GateResult(
                status=status,
                reason="C2 structured-source diversity/depth requirements not met.",
                metrics=metrics,
                blockers=blockers,
            )
        return GateResult(
            status="pass",
            reason="Structured-source diversity/depth satisfies C2.",
            metrics=metrics,
            blockers=[],
        )

    def _evaluate_c3(self, *, rows: list[dict[str, Any]]) -> GateResult:
        mismatches: list[str] = []
        reason_mismatches: list[str] = []
        reconciled = 0
        not_policy_evidence_count = 0

        for row in rows:
            row_id = str(row.get("corpus_row_id") or "unknown")
            classification_payload = row.get("classification") or {}
            class_value = str(
                classification_payload.get("data_moat_package_classification") or ""
            )
            d11_quality = str(classification_payload.get("d11_handoff_quality") or "")
            d11_reason = str(classification_payload.get("d11_reason") or "").lower()

            try:
                class_enum = DataMoatPackageClassification(class_value)
            except ValueError:
                mismatches.append(f"{row_id}:invalid_classification")
                continue

            if class_enum == DataMoatPackageClassification.NOT_POLICY_EVIDENCE:
                not_policy_evidence_count += 1

            allowed = C3_D11_ALLOWED_QUALITIES[class_enum]
            if d11_quality not in allowed:
                mismatches.append(f"{row_id}:d11_quality_mismatch")
                continue

            if (
                class_enum == DataMoatPackageClassification.QUALITATIVE_ONLY
                and "qualitative" not in d11_reason
            ):
                reason_mismatches.append(f"{row_id}:qualitative_reason_missing")
            if (
                class_enum == DataMoatPackageClassification.STORED_NOT_ECONOMIC
                and "non-economic" not in d11_reason
            ):
                reason_mismatches.append(f"{row_id}:non_economic_reason_missing")
            if (
                class_enum == DataMoatPackageClassification.NOT_POLICY_EVIDENCE
                and not any(
                    token in d11_reason
                    for token in {
                        "false-positive",
                        "off-topic",
                        "wrong jurisdiction",
                        "duplicate",
                    }
                )
            ):
                reason_mismatches.append(f"{row_id}:not_policy_reason_missing")

            reconciled += 1

        total = len(rows)
        not_policy_ratio = (not_policy_evidence_count / total) if total else 0.0
        metrics = {
            "row_count": total,
            "handoff_taxonomy_reconciled_count": reconciled,
            "handoff_taxonomy_reconciled_ratio": round(
                (reconciled / total) if total else 0.0, 4
            ),
            "not_policy_evidence_ratio": round(not_policy_ratio, 4),
        }

        blockers: list[str] = []
        if mismatches:
            blockers.append("c3_d11_mapping_mismatch")
        if reason_mismatches:
            blockers.append("c3_reason_quality_missing")
        if not_policy_ratio > 0.15:
            blockers.append("not_policy_evidence_share_above_15_percent_cap")

        if blockers:
            return GateResult(
                status="fail",
                reason="C3 package classification and D11 reconciliation failed.",
                metrics=metrics,
                blockers=blockers,
            )
        return GateResult(
            status="pass",
            reason="C3 package classifications reconcile cleanly with D11 handoff quality.",
            metrics=metrics,
            blockers=[],
        )

    def _evaluate_c4(self, *, rows: list[dict[str, Any]]) -> GateResult:
        plausible_candidates = 0
        deep_dive_rows = []
        direct_count = 0
        indirect_count = 0
        secondary_count = 0
        non_san_jose_deep_dives = 0
        non_clf_deep_dives = 0
        rows_missing_reuse = 0

        for row in rows:
            classification = str(
                (row.get("classification") or {}).get(
                    "data_moat_package_classification"
                )
                or ""
            )
            if classification in {
                DataMoatPackageClassification.ECONOMIC_ANALYSIS_READY.value,
                DataMoatPackageClassification.ECONOMIC_HANDOFF_CANDIDATE.value,
                DataMoatPackageClassification.SECONDARY_RESEARCH_NEEDED.value,
            }:
                plausible_candidates += 1

            handoff = row.get("economic_handoff_plausibility") or {}
            if bool(handoff.get("deep_dive_performed")):
                deep_dive_rows.append(row)
                deep_dive_type = str(handoff.get("deep_dive_type") or "")
                if deep_dive_type == "direct":
                    direct_count += 1
                elif deep_dive_type == "indirect":
                    indirect_count += 1
                elif deep_dive_type == "secondary":
                    secondary_count += 1
                if (
                    str((row.get("jurisdiction") or {}).get("id") or "")
                    != "san_jose_ca"
                ):
                    non_san_jose_deep_dives += 1
                if str(row.get("policy_family") or "") != "commercial_linkage_fee":
                    non_clf_deep_dives += 1
                if int(handoff.get("model_card_reuse_count") or 0) < 1:
                    rows_missing_reuse += 1

        metrics = {
            "plausible_handoff_candidates": plausible_candidates,
            "deep_dive_count": len(deep_dive_rows),
            "direct_deep_dive_count": direct_count,
            "indirect_deep_dive_count": indirect_count,
            "secondary_deep_dive_count": secondary_count,
            "non_san_jose_deep_dive_count": non_san_jose_deep_dives,
            "non_clf_deep_dive_count": non_clf_deep_dives,
            "deep_dive_rows_without_model_reuse": rows_missing_reuse,
        }

        blockers: list[str] = []
        if plausible_candidates < 10:
            blockers.append("plausible_handoff_candidates_below_10")
        if len(deep_dive_rows) < 6:
            blockers.append("deep_dive_count_below_6")
        if direct_count < 3:
            blockers.append("direct_deep_dive_count_below_3")
        if indirect_count < 2:
            blockers.append("indirect_deep_dive_count_below_2")
        if secondary_count < 1:
            blockers.append("secondary_deep_dive_count_below_1")
        if non_san_jose_deep_dives < 1:
            blockers.append("non_san_jose_deep_dive_missing")
        if non_clf_deep_dives < 1:
            blockers.append("non_clf_deep_dive_missing")
        if rows_missing_reuse > 0:
            blockers.append("model_card_reuse_missing")

        if blockers:
            return GateResult(
                status="not_proven",
                reason="C4 economic handoff distribution is partially populated but below pass thresholds.",
                metrics=metrics,
                blockers=blockers,
            )
        return GateResult(
            status="pass",
            reason="C4 economic handoff distribution thresholds are satisfied.",
            metrics=metrics,
            blockers=[],
        )

    def _evaluate_c5(self, *, rows: list[dict[str, Any]]) -> GateResult:
        sampled_rows = [
            row for row in rows if bool((row.get("manual_audit") or {}).get("sampled"))
        ]
        sampled_count = len(sampled_rows)
        required_total = len(rows) if len(rows) < 30 else 30
        missing_fields: list[str] = []

        for row in sampled_rows:
            audit = row.get("manual_audit") or {}
            row_id = str(row.get("corpus_row_id") or "unknown")
            for field in REQUIRED_MANUAL_AUDIT_FIELDS:
                if field not in audit:
                    missing_fields.append(f"{row_id}:{field}")

        per_jurisdiction: dict[str, int] = {}
        per_policy_family: dict[str, int] = {}
        per_source_family: dict[str, int] = {}
        for row in sampled_rows:
            jurisdiction = str((row.get("jurisdiction") or {}).get("id") or "")
            policy_family = str(row.get("policy_family") or "")
            source_family = str(
                (row.get("selected_primary_source") or {}).get("source_family") or ""
            )
            per_jurisdiction[jurisdiction] = per_jurisdiction.get(jurisdiction, 0) + 1
            per_policy_family[policy_family] = (
                per_policy_family.get(policy_family, 0) + 1
            )
            per_source_family[source_family] = (
                per_source_family.get(source_family, 0) + 1
            )

        metrics = {
            "sampled_count": sampled_count,
            "required_sample_count": required_total,
            "sampled_jurisdiction_count": len(per_jurisdiction),
            "sampled_policy_family_count": len(per_policy_family),
            "sampled_source_family_count": len(per_source_family),
        }

        blockers: list[str] = []
        if missing_fields:
            blockers.append("manual_audit_required_fields_missing")
            return GateResult(
                status="fail",
                reason="C5 sampled manual-audit rows are missing required audit fields.",
                metrics=metrics,
                blockers=blockers,
            )

        if sampled_count == 0:
            return GateResult(
                status="not_proven",
                reason="No sampled manual audit rows were provided.",
                metrics=metrics,
                blockers=["manual_audit_sample_missing"],
            )

        if sampled_count < required_total:
            blockers.append("sample_size_below_requirement")

        if per_jurisdiction and max(per_jurisdiction.values()) == sampled_count:
            blockers.append("manual_audit_single_jurisdiction_only")

        if any(count < 2 for count in per_policy_family.values()):
            blockers.append("policy_family_stratification_below_2")
        if any(count < 2 for count in per_source_family.values()):
            blockers.append("source_family_stratification_below_2")

        if blockers:
            return GateResult(
                status="not_proven",
                reason="C5 manual audit exists but is not yet stratified to pass thresholds.",
                metrics=metrics,
                blockers=blockers,
            )
        return GateResult(
            status="pass",
            reason="C5 manual audit sampling is stratified and complete.",
            metrics=metrics,
            blockers=[],
        )

    def _evaluate_c6(
        self, *, matrix: dict[str, Any], rows: list[dict[str, Any]]
    ) -> GateResult:
        required = {
            "stable_query_input",
            "expected_jurisdiction_id",
            "expected_policy_family",
            "selected_source_url",
            "package_id",
            "verdict",
            "failure_class",
        }
        missing_rows = []
        for row in rows:
            expectation = row.get("golden_regression_expectation")
            if not isinstance(expectation, dict):
                missing_rows.append(str(row.get("corpus_row_id") or "unknown"))
                continue
            absent = [field for field in required if field not in expectation]
            if absent:
                missing_rows.append(
                    f"{row.get('corpus_row_id')}:{','.join(sorted(absent))}"
                )

        metrics = {
            "row_count": len(rows),
            "missing_expectation_rows": len(missing_rows),
            "taxonomy_version": matrix.get("taxonomy_version"),
        }
        if missing_rows:
            return GateResult(
                status="fail",
                reason="C6 golden regression expectations are incomplete.",
                metrics=metrics,
                blockers=["golden_expectation_fields_missing"],
            )
        if not matrix.get("taxonomy_version"):
            return GateResult(
                status="fail",
                reason="C6 requires explicit taxonomy_version in matrix metadata.",
                metrics=metrics,
                blockers=["taxonomy_version_missing"],
            )
        return GateResult(
            status="pass",
            reason="C6 golden regression fields are complete and taxonomy-versioned.",
            metrics=metrics,
            blockers=[],
        )

    def _evaluate_c7(self, *, rows: list[dict[str, Any]]) -> GateResult:
        required_fields = {
            "expected_update_interval_days",
            "retrieved_at",
            "last_successful_refresh_at",
            "source_shape_fingerprint",
            "source_shape_changed",
            "update_cadence_drift",
            "stale_for_policy_use",
            "next_refresh_recommendation",
        }
        missing = []
        stale_rows = 0
        drift_rows = 0
        for row in rows:
            freshness = row.get("freshness")
            if not isinstance(freshness, dict):
                missing.append(str(row.get("corpus_row_id") or "unknown"))
                continue
            absent = [field for field in required_fields if field not in freshness]
            if absent:
                missing.append(f"{row.get('corpus_row_id')}:{','.join(sorted(absent))}")
            if bool(freshness.get("stale_for_policy_use")):
                stale_rows += 1
            if bool(freshness.get("source_shape_changed")) or bool(
                freshness.get("update_cadence_drift")
            ):
                drift_rows += 1

        metrics = {
            "row_count": len(rows),
            "missing_freshness_rows": len(missing),
            "stale_row_count": stale_rows,
            "drift_row_count": drift_rows,
        }
        if missing:
            return GateResult(
                status="fail",
                reason="C7 freshness/drift fields are missing.",
                metrics=metrics,
                blockers=["freshness_fields_missing"],
            )
        return GateResult(
            status="pass",
            reason="C7 freshness/drift metadata is complete and visible.",
            metrics=metrics,
            blockers=[],
        )

    def _evaluate_c8(self, *, rows: list[dict[str, Any]]) -> GateResult:
        required_fields = {
            "canonical_policy_key",
            "canonical_source_key",
            "canonical_document_key",
            "canonical_attachment_key",
            "dedupe_cluster_id",
            "version_state",
        }
        missing = []
        for row in rows:
            identity = row.get("identity")
            if not isinstance(identity, dict):
                missing.append(str(row.get("corpus_row_id") or "unknown"))
                continue
            absent = [field for field in required_fields if field not in identity]
            if absent:
                missing.append(f"{row.get('corpus_row_id')}:{','.join(sorted(absent))}")

        metrics = {
            "row_count": len(rows),
            "missing_identity_rows": len(missing),
        }
        if missing:
            return GateResult(
                status="fail",
                reason="C8 identity/dedupe canonical fields are missing.",
                metrics=metrics,
                blockers=["identity_fields_missing"],
            )
        return GateResult(
            status="pass",
            reason="C8 identity/dedupe canonical fields are present.",
            metrics=metrics,
            blockers=[],
        )

    def _evaluate_c9(self, *, rows: list[dict[str, Any]]) -> GateResult:
        required_fields = {
            "currency_normalized",
            "percent_normalized",
            "count_normalized",
            "date_normalized",
            "unit_normalized",
            "geography_fields",
            "export_ready",
        }
        missing = []
        for row in rows:
            normalization = row.get("normalization")
            if not isinstance(normalization, dict):
                missing.append(str(row.get("corpus_row_id") or "unknown"))
                continue
            absent = [field for field in required_fields if field not in normalization]
            if absent:
                missing.append(f"{row.get('corpus_row_id')}:{','.join(sorted(absent))}")
                continue
            if not bool(normalization.get("export_ready")):
                missing.append(f"{row.get('corpus_row_id')}:export_ready_false")

        metrics = {
            "row_count": len(rows),
            "normalization_issues": len(missing),
        }
        if missing:
            return GateResult(
                status="fail",
                reason="C9 normalization/exportability fields are incomplete.",
                metrics=metrics,
                blockers=["normalization_or_exportability_missing"],
            )
        return GateResult(
            status="pass",
            reason="C9 normalized/exportable fields are present across corpus rows.",
            metrics=metrics,
            blockers=[],
        )

    def _evaluate_c9a(self, *, matrix: dict[str, Any]) -> GateResult:
        product_surface = matrix.get("product_surface")
        if not isinstance(product_surface, dict):
            return GateResult(
                status="fail",
                reason="C9a requires explicit product_surface contract metadata.",
                metrics={"has_product_surface": False},
                blockers=["product_surface_missing"],
            )

        required_fields = {
            "read_api_endpoint",
            "export_artifact_path",
            "schema_fields",
            "access_control",
            "query_examples",
        }
        missing = [field for field in required_fields if field not in product_surface]
        query_dimensions = {
            str(item.get("dimension"))
            for item in product_surface.get("query_examples", [])
            if isinstance(item, dict)
        }
        required_dimensions = {
            "jurisdiction",
            "policy_family",
            "source_family",
            "officialness",
            "freshness",
            "classification",
        }
        missing_dimensions = sorted(required_dimensions - query_dimensions)

        metrics = {
            "has_product_surface": True,
            "query_example_dimension_count": len(query_dimensions),
            "missing_query_dimensions": missing_dimensions,
        }
        blockers = []
        if missing:
            blockers.append("product_surface_required_fields_missing")
        if missing_dimensions:
            blockers.append("product_surface_query_dimensions_missing")
        if blockers:
            return GateResult(
                status="fail",
                reason="C9a product surface contract is incomplete.",
                metrics=metrics,
                blockers=blockers,
            )
        return GateResult(
            status="pass",
            reason="C9a product surface contract and query examples are present.",
            metrics=metrics,
            blockers=[],
        )

    def _evaluate_c10(self, *, rows: list[dict[str, Any]]) -> GateResult:
        required_fields = {
            "license_posture",
            "robots_tos_posture",
            "rate_limit_notes",
            "attribution_notes",
            "allowed_storage_export_posture",
        }
        missing_rows = []
        for row in rows:
            licensing = row.get("licensing")
            if not isinstance(licensing, dict):
                missing_rows.append(str(row.get("corpus_row_id") or "unknown"))
                continue
            absent = [field for field in required_fields if field not in licensing]
            if absent:
                missing_rows.append(
                    f"{row.get('corpus_row_id')}:{','.join(sorted(absent))}"
                )

        metrics = {
            "row_count": len(rows),
            "licensing_rows_missing": len(missing_rows),
        }
        if missing_rows:
            return GateResult(
                status="fail",
                reason="C10 licensing/robots/ToS posture is incomplete.",
                metrics=metrics,
                blockers=["licensing_or_tos_fields_missing"],
            )
        return GateResult(
            status="pass",
            reason="C10 licensing/robots/ToS posture is documented for all rows.",
            metrics=metrics,
            blockers=[],
        )

    def _evaluate_c11(
        self, *, matrix: dict[str, Any], rows: list[dict[str, Any]]
    ) -> GateResult:
        top_level_required = {
            "schema_version",
            "taxonomy_version",
            "gate_version",
            "schema_contract",
        }
        missing_top = [field for field in top_level_required if field not in matrix]
        schema_contract = matrix.get("schema_contract")
        missing_schema_contract_fields = []
        if isinstance(schema_contract, dict):
            for field in {
                "package_schema_version",
                "source_taxonomy_version",
                "gate_version",
                "migration_backfill_notes",
                "field_change_rules",
                "unknown_field_handling",
            }:
                if field not in schema_contract:
                    missing_schema_contract_fields.append(field)
        else:
            missing_schema_contract_fields = ["schema_contract_not_object"]

        row_mismatch = []
        for row in rows:
            row_schema = row.get("schema_contract")
            if not isinstance(row_schema, dict):
                row_mismatch.append(
                    f"{row.get('corpus_row_id')}:schema_contract_missing"
                )
                continue
            if row_schema.get("taxonomy_version") != matrix.get("taxonomy_version"):
                row_mismatch.append(
                    f"{row.get('corpus_row_id')}:taxonomy_version_mismatch"
                )
            if row_schema.get("gate_version") != matrix.get("gate_version"):
                row_mismatch.append(f"{row.get('corpus_row_id')}:gate_version_mismatch")

        metrics = {
            "missing_top_level_fields": missing_top,
            "missing_schema_contract_fields": missing_schema_contract_fields,
            "row_schema_mismatch_count": len(row_mismatch),
        }
        blockers = []
        if missing_top:
            blockers.append("matrix_schema_version_fields_missing")
        if missing_schema_contract_fields:
            blockers.append("schema_contract_fields_missing")
        if row_mismatch:
            blockers.append("row_schema_contract_mismatch")
        if blockers:
            return GateResult(
                status="fail",
                reason="C11 schema/taxonomy/gate version contract is incomplete.",
                metrics=metrics,
                blockers=blockers,
            )
        return GateResult(
            status="pass",
            reason="C11 schema/taxonomy/gate version contract is explicit and aligned.",
            metrics=metrics,
            blockers=[],
        )

    def _evaluate_c12(
        self, *, matrix: dict[str, Any], rows: list[dict[str, Any]]
    ) -> GateResult:
        known_refs = matrix.get("known_policy_references")
        if not isinstance(known_refs, list) or not known_refs:
            return GateResult(
                status="fail",
                reason="C12 known policy reference list is missing.",
                metrics={"known_policy_reference_count": 0},
                blockers=["known_policy_reference_list_missing"],
            )

        known_ids = {
            str(item.get("known_policy_reference_id") or "")
            for item in known_refs
            if isinstance(item, dict)
        }
        observed_ids = {
            str(row.get("known_policy_reference_id") or "")
            for row in rows
            if str(row.get("known_policy_reference_id") or "")
        }
        blind_rows = [
            row
            for row in rows
            if bool(row.get("blind_seed"))
            and str(row.get("evaluation_split") or "") == "blind_evaluation"
        ]
        covered = sorted(known_ids & observed_ids)
        missing = sorted(known_ids - observed_ids)
        coverage_ratio = len(covered) / len(known_ids) if known_ids else 0.0
        metrics = {
            "known_policy_reference_count": len(known_ids),
            "covered_known_policy_count": len(covered),
            "missing_known_policy_count": len(missing),
            "coverage_ratio": round(coverage_ratio, 4),
            "blind_seed_row_count": len(blind_rows),
        }

        blockers = []
        if not blind_rows:
            blockers.append("blind_seed_holdout_missing")
        if coverage_ratio < 0.8:
            blockers.append("known_policy_coverage_below_80_percent")
        if blockers:
            return GateResult(
                status="fail",
                reason="C12 known-policy coverage/holdout requirements are not met.",
                metrics=metrics,
                blockers=blockers,
            )
        return GateResult(
            status="pass",
            reason="C12 known-policy coverage includes blind holdout and adequate coverage.",
            metrics=metrics,
            blockers=[],
        )

    def _build_c13_rows_with_proof_overlay(
        self,
        *,
        matrix: dict[str, Any],
        rows: list[dict[str, Any]],
        windmill_orchestration_artifact: dict[str, Any] | None,
        windmill_row_proof_overlay: dict[str, dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        overlay_by_row_id = self._collect_windmill_row_overlay(
            matrix=matrix,
            windmill_orchestration_artifact=windmill_orchestration_artifact,
            windmill_row_proof_overlay=windmill_row_proof_overlay,
        )
        if not overlay_by_row_id:
            return rows

        overlaid_rows: list[dict[str, Any]] = []
        for row in rows:
            row_id = str(row.get("corpus_row_id") or "")
            row_overlay = overlay_by_row_id.get(row_id)
            if not row_overlay:
                overlaid_rows.append(row)
                continue

            infra = row.get("infrastructure_status")
            overlaid_infra = dict(infra) if isinstance(infra, dict) else {}
            refs = overlaid_infra.get("windmill_refs")
            overlaid_refs = dict(refs) if isinstance(refs, dict) else {}

            refs_overlay = row_overlay.get("windmill_refs")
            if isinstance(refs_overlay, dict):
                for key, value in refs_overlay.items():
                    if isinstance(value, str) and value:
                        overlaid_refs[key] = value

            for key in (
                "flow_id",
                "run_id",
                "job_id",
                "proof_status",
                "proof_source",
                "blocker_class",
            ):
                value = row_overlay.get(key)
                if isinstance(value, str) and value:
                    overlaid_refs[key] = value

            if overlaid_refs:
                overlaid_infra["windmill_refs"] = overlaid_refs

            mode = str(row_overlay.get("orchestration_mode") or "")
            if mode in ORCHESTRATION_MODES:
                overlaid_infra["orchestration_mode"] = mode

            overlaid_row = dict(row)
            overlaid_row["infrastructure_status"] = overlaid_infra
            overlaid_rows.append(overlaid_row)

        return overlaid_rows

    def _collect_windmill_row_overlay(
        self,
        *,
        matrix: dict[str, Any],
        windmill_orchestration_artifact: dict[str, Any] | None,
        windmill_row_proof_overlay: dict[str, dict[str, Any]] | None,
    ) -> dict[str, dict[str, Any]]:
        artifact_payload = windmill_orchestration_artifact
        if not isinstance(artifact_payload, dict):
            matrix_artifact = matrix.get("windmill_orchestration_artifact")
            artifact_payload = matrix_artifact if isinstance(matrix_artifact, dict) else None

        overlay: dict[str, dict[str, Any]] = {}
        if artifact_payload:
            overlay.update(
                self._extract_windmill_row_overlay_from_artifact(artifact=artifact_payload)
            )

        matrix_overlay = matrix.get("windmill_row_proof_overlay")
        if isinstance(matrix_overlay, dict):
            overlay.update(self._normalize_windmill_row_overlay(matrix_overlay))
        if isinstance(windmill_row_proof_overlay, dict):
            overlay.update(self._normalize_windmill_row_overlay(windmill_row_proof_overlay))

        return overlay

    def _normalize_windmill_row_overlay(
        self, overlay: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}
        for raw_row_id, payload in overlay.items():
            row_id = str(raw_row_id or "")
            if not row_id or not isinstance(payload, dict):
                continue
            normalized_payload: dict[str, Any] = {}

            refs = payload.get("windmill_refs")
            if isinstance(refs, dict):
                normalized_payload["windmill_refs"] = {
                    key: value
                    for key, value in refs.items()
                    if isinstance(value, str) and value
                }

            for key in (
                "flow_id",
                "run_id",
                "job_id",
                "proof_status",
                "proof_source",
                "blocker_class",
            ):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    normalized_payload[key] = value

            mode = str(payload.get("orchestration_mode") or "")
            if mode in ORCHESTRATION_MODES:
                normalized_payload["orchestration_mode"] = mode

            if normalized_payload:
                normalized[row_id] = normalized_payload
        return normalized

    def _extract_windmill_row_overlay_from_artifact(
        self, *, artifact: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        extracted: dict[str, dict[str, Any]] = {}
        rows = artifact.get("rows")
        if isinstance(rows, list):
            for payload in rows:
                parsed = self._overlay_entry_from_artifact_payload(payload=payload)
                if parsed:
                    row_id, row_payload = parsed
                    extracted[row_id] = row_payload
        attempts = artifact.get("attempts")
        if isinstance(attempts, list):
            for payload in attempts:
                parsed = self._overlay_entry_from_artifact_payload(payload=payload)
                if parsed:
                    row_id, row_payload = parsed
                    extracted[row_id] = row_payload
        return extracted

    def _overlay_entry_from_artifact_payload(
        self, *, payload: Any
    ) -> tuple[str, dict[str, Any]] | None:
        if not isinstance(payload, dict):
            return None

        row_id = str(payload.get("corpus_row_id") or "")
        if not row_id:
            return None

        status = str(payload.get("status") or payload.get("row_status") or "").lower()
        mode = str(payload.get("orchestration_mode") or "")
        run_id = str(payload.get("windmill_run_id") or payload.get("run_id") or "")
        job_id = str(payload.get("windmill_job_id") or payload.get("job_id") or "")
        flow_id = str(
            payload.get("windmill_flow_path")
            or payload.get("windmill_flow_id")
            or payload.get("flow_id")
            or ""
        )
        blocker_class = str(payload.get("blocker_class") or payload.get("blocker") or "")

        if status == "blocked" or mode == "blocked" or blocker_class:
            blocker_class_normalized = blocker_class.strip().lower()
            proof_status = "blocked"
            if "unsupported" in blocker_class_normalized:
                proof_status = "unsupported_scope"
            blocked_overlay: dict[str, Any] = {
                "proof_status": proof_status,
                "proof_source": "windmill_orchestration_artifact",
            }
            if blocker_class:
                blocked_overlay["blocker_class"] = blocker_class
            if flow_id:
                blocked_overlay["flow_id"] = flow_id
            if run_id:
                blocked_overlay["run_id"] = run_id
            if job_id:
                blocked_overlay["job_id"] = job_id
            return row_id, blocked_overlay

        if not run_id or not job_id:
            return None
        if run_id.startswith("wm::") or job_id.startswith("wm-job::"):
            return None

        proven_overlay: dict[str, Any] = {
            "run_id": run_id,
            "job_id": job_id,
            "proof_status": "live_proven",
            "proof_source": "windmill_orchestration_artifact",
        }
        if flow_id:
            proven_overlay["flow_id"] = flow_id
        if mode in LIVE_ORCHESTRATION_MODES:
            proven_overlay["orchestration_mode"] = mode
        return row_id, proven_overlay

    def _evaluate_c13(
        self, *, matrix: dict[str, Any], rows: list[dict[str, Any]]
    ) -> GateResult:
        mode_counts = {
            "windmill_live": 0,
            "mixed": 0,
            "orchestration_intent": 0,
            "cli_only": 0,
        }
        missing_mode_rows = []
        orchestration_intent_missing_refs_rows = []
        missing_live_refs_rows = []
        live_proven_rows = []
        seeded_not_live_proven_rows = []
        orchestration_intent_rows = []
        blocked_backend_scope_rows = []
        unsupported_scope_rows = []
        cli_only_rows = []
        for row in rows:
            row_id = str(row.get("corpus_row_id") or "unknown")
            infra = row.get("infrastructure_status")
            if not isinstance(infra, dict):
                missing_mode_rows.append(row_id)
                continue
            mode = str(infra.get("orchestration_mode") or "")
            if mode not in mode_counts:
                missing_mode_rows.append(row_id)
                continue
            mode_counts[mode] += 1
            refs = infra.get("windmill_refs")
            if mode == "cli_only":
                cli_only_rows.append(row_id)
                if isinstance(refs, dict):
                    scope_class = self._classify_windmill_scope_block(refs=refs)
                    if scope_class == "blocked_backend_scope":
                        blocked_backend_scope_rows.append(row_id)
                    elif scope_class == "unsupported_scope":
                        unsupported_scope_rows.append(row_id)
                continue
            if mode == ORCHESTRATION_INTENT_MODE:
                orchestration_intent_rows.append(row_id)
                scope_class = (
                    self._classify_windmill_scope_block(refs=refs)
                    if isinstance(refs, dict)
                    else None
                )
                if scope_class == "blocked_backend_scope":
                    blocked_backend_scope_rows.append(row_id)
                    seeded_not_live_proven_rows.append(row_id)
                    continue
                if scope_class == "unsupported_scope":
                    unsupported_scope_rows.append(row_id)
                    seeded_not_live_proven_rows.append(row_id)
                    continue
                if not isinstance(refs, dict) or not all(
                    refs.get(key) for key in {"flow_id", "run_id", "job_id"}
                ):
                    orchestration_intent_missing_refs_rows.append(row_id)
                    continue
                if not self._windmill_refs_are_live_proven(refs=refs):
                    seeded_not_live_proven_rows.append(row_id)
                    continue
                live_proven_rows.append(row_id)
                continue
            if mode in LIVE_ORCHESTRATION_MODES:
                scope_class = (
                    self._classify_windmill_scope_block(refs=refs)
                    if isinstance(refs, dict)
                    else None
                )
                if scope_class == "blocked_backend_scope":
                    blocked_backend_scope_rows.append(row_id)
                    seeded_not_live_proven_rows.append(row_id)
                    continue
                if scope_class == "unsupported_scope":
                    unsupported_scope_rows.append(row_id)
                    seeded_not_live_proven_rows.append(row_id)
                    continue
                if not isinstance(refs, dict) or not all(
                    refs.get(key) for key in {"flow_id", "run_id", "job_id"}
                ):
                    missing_live_refs_rows.append(row_id)
                    continue
                if not self._windmill_refs_are_live_proven(refs=refs):
                    seeded_not_live_proven_rows.append(row_id)
                    continue
                live_proven_rows.append(row_id)

        total = len(rows)
        cli_share = (mode_counts["cli_only"] / total) if total else 0.0
        seeded_ref_target_rows = len(live_proven_rows) + len(seeded_not_live_proven_rows)
        live_proof_coverage_ratio = (
            round(len(live_proven_rows) / seeded_ref_target_rows, 4)
            if seeded_ref_target_rows
            else 1.0
        )
        remaining_seeded_ref_rows = list(seeded_not_live_proven_rows)
        next_seeded_ref_target_rows = remaining_seeded_ref_rows[:10]
        metrics = {
            "row_count": total,
            "mode_counts": mode_counts,
            "cli_only_share": round(cli_share, 4),
            "live_proven_rows": len(live_proven_rows),
            "seeded_ref_target_rows": seeded_ref_target_rows,
            "live_proof_coverage_ratio": live_proof_coverage_ratio,
            "sample_live_proven_rows": live_proven_rows[:10],
            "orchestration_intent_rows": len(orchestration_intent_rows),
            "sample_orchestration_intent_rows": orchestration_intent_rows[:10],
            "cli_only_rows": len(cli_only_rows),
            "sample_cli_only_rows": cli_only_rows[:10],
            "missing_mode_rows": len(missing_mode_rows),
            "orchestration_intent_missing_refs_rows": len(
                orchestration_intent_missing_refs_rows
            ),
            "sample_orchestration_intent_missing_refs_rows": (
                orchestration_intent_missing_refs_rows[:10]
            ),
            "missing_live_refs_rows": len(missing_live_refs_rows),
            "seeded_not_live_proven_rows": len(seeded_not_live_proven_rows),
            "remaining_seeded_ref_row_count": len(remaining_seeded_ref_rows),
            "remaining_seeded_ref_rows": remaining_seeded_ref_rows,
            "next_seeded_ref_target_rows": next_seeded_ref_target_rows,
            "sample_seeded_not_live_proven_rows": seeded_not_live_proven_rows[:10],
            "blocked_backend_scope_rows": len(blocked_backend_scope_rows),
            "sample_blocked_backend_scope_rows": blocked_backend_scope_rows[:10],
            "unsupported_scope_rows": len(unsupported_scope_rows),
            "sample_unsupported_scope_rows": unsupported_scope_rows[:10],
        }

        blockers = []
        if missing_mode_rows:
            blockers.append("orchestration_mode_missing")
        if orchestration_intent_missing_refs_rows:
            blockers.append("orchestration_intent_refs_missing")
        if missing_live_refs_rows:
            blockers.append("windmill_refs_missing_for_live_rows")
        if seeded_not_live_proven_rows:
            blockers.append("windmill_refs_seeded_not_live_proven")
        if blocked_backend_scope_rows:
            blockers.append("windmill_rows_blocked_backend_scope")
        if unsupported_scope_rows:
            blockers.append("windmill_rows_unsupported_scope")
        if blockers:
            if (
                missing_mode_rows
                or missing_live_refs_rows
                or orchestration_intent_missing_refs_rows
            ):
                return GateResult(
                    status="fail",
                    reason="C13 orchestration metadata is incomplete.",
                    metrics=metrics,
                    blockers=blockers,
                )
            if blocked_backend_scope_rows or unsupported_scope_rows:
                return GateResult(
                    status="not_proven",
                    reason=(
                        "C13 has blocked or unsupported backend-scope rows; "
                        "live orchestration is not corpus-proven."
                    ),
                    metrics=metrics,
                    blockers=blockers,
                )
            return GateResult(
                status="not_proven",
                reason=(
                    "C13 has orchestration intent metadata, but live Windmill "
                    "run/job refs are not proven."
                ),
                metrics=metrics,
                blockers=blockers,
            )

        if str(matrix.get("corpus_readiness_target") or "") == "decision_grade_corpus":
            if cli_share > 0.1:
                return GateResult(
                    status="fail",
                    reason="C13 cli_only share exceeds 10 percent cap for decision-grade claim.",
                    metrics=metrics,
                    blockers=["cli_only_share_above_10_percent"],
                )
            return GateResult(
                status="pass",
                reason="C13 orchestration share and live linkage satisfy decision-grade threshold.",
                metrics=metrics,
                blockers=[],
            )

        if cli_share > 0.1:
            return GateResult(
                status="not_proven",
                reason="C13 live orchestration exists but cli_only share is above decision-grade cap.",
                metrics=metrics,
                blockers=["cli_only_share_above_10_percent"],
            )
        return GateResult(
            status="pass",
            reason="C13 orchestration metadata is complete and within caps.",
            metrics=metrics,
            blockers=[],
        )

    @staticmethod
    def _windmill_refs_are_live_proven(*, refs: dict[str, Any]) -> bool:
        run_id = str(refs.get("run_id") or "")
        job_id = str(refs.get("job_id") or "")
        if run_id.startswith("wm::") or job_id.startswith("wm-job::"):
            return False
        proof_status = str(refs.get("proof_status") or "")
        proof_source = str(refs.get("proof_source") or "")
        if proof_status in {"live_proven", "proven"}:
            return True
        if proof_status:
            return False
        return proof_source in {
            "windmill_cli_live",
            "windmill_backend_live",
            "windmill_orchestration_artifact",
            "windmill_row_overlay",
        }

    @staticmethod
    def _classify_windmill_scope_block(*, refs: dict[str, Any]) -> str | None:
        proof_status = str(refs.get("proof_status") or "").strip().lower()
        blocker_class = str(refs.get("blocker_class") or refs.get("blocker") or "")
        blocker_class = blocker_class.strip().lower()

        if proof_status in {"unsupported_scope", "unsupported", "unsupported_backend_scope"}:
            return "unsupported_scope"
        if "unsupported" in blocker_class:
            return "unsupported_scope"
        if proof_status in {"blocked", "blocked_backend_scope"}:
            return "blocked_backend_scope"
        if "backend_scope" in blocker_class:
            return "blocked_backend_scope"
        return None

    def _evaluate_c14(
        self, *, matrix: dict[str, Any], rows: list[dict[str, Any]]
    ) -> GateResult:
        templates = matrix.get("non_fee_extraction_templates")
        if not isinstance(templates, list) or not templates:
            return GateResult(
                status="fail",
                reason="C14 non-fee extraction templates are missing.",
                metrics={"template_count": 0},
                blockers=["non_fee_templates_missing"],
            )

        non_fee_rows = [
            row
            for row in rows
            if _is_non_fee_policy_family(str(row.get("policy_family") or ""))
        ]
        live_non_fee_families = set()
        cataloged_non_fee_families = set()
        required_fact_fields = {
            "applicability_present",
            "effective_date_or_unknown_present",
            "jurisdiction_geography_present",
            "source_locator_present",
            "policy_action_type_present",
        }
        rows_missing_facts = []
        for row in non_fee_rows:
            extraction = row.get("extraction_depth")
            if not isinstance(extraction, dict):
                rows_missing_facts.append(str(row.get("corpus_row_id") or "unknown"))
                continue
            proof_status = str(extraction.get("proof_status") or "")
            live_exercised = bool(extraction.get("live_exercised")) and (
                not proof_status or proof_status in LIVE_STRUCTURED_PROOF_STATUSES
            )
            if live_exercised:
                live_non_fee_families.add(str(row.get("policy_family") or ""))
            elif proof_status == "cataloged_intent":
                cataloged_non_fee_families.add(str(row.get("policy_family") or ""))
            missing = [
                field for field in required_fact_fields if field not in extraction
            ]
            if missing:
                rows_missing_facts.append(
                    f"{row.get('corpus_row_id')}:{','.join(sorted(missing))}"
                )

        metrics = {
            "template_count": len(templates),
            "non_fee_row_count": len(non_fee_rows),
            "live_non_fee_family_count": len(live_non_fee_families),
            "cataloged_non_fee_family_count": len(cataloged_non_fee_families),
            "rows_missing_fact_fields": len(rows_missing_facts),
        }

        blockers = []
        if len(templates) < 3:
            blockers.append("non_fee_template_count_below_3")
        if len(live_non_fee_families) < 2:
            blockers.append("live_non_fee_family_count_below_2")
        if cataloged_non_fee_families:
            blockers.append("non_fee_extraction_templates_cataloged_not_live_proven")
        if rows_missing_facts:
            blockers.append("non_fee_extraction_fact_fields_missing")
        if blockers:
            status = (
                "not_proven"
                if "live_non_fee_family_count_below_2" in blockers
                or "non_fee_extraction_templates_cataloged_not_live_proven" in blockers
                else "fail"
            )
            return GateResult(
                status=status,
                reason="C14 non-fee extraction depth is incomplete.",
                metrics=metrics,
                blockers=blockers,
            )
        return GateResult(
            status="pass",
            reason="C14 non-fee extraction templates and live exercised families satisfy depth contract.",
            metrics=metrics,
            blockers=[],
        )

    def _build_core_metrics(
        self,
        *,
        rows: list[dict[str, Any]],
        gate_results: dict[str, GateResult],
    ) -> dict[str, Any]:
        c1 = gate_results["C1"].metrics
        c2 = gate_results["C2"].metrics
        c3 = gate_results["C3"].metrics
        c5 = gate_results["C5"].metrics
        return {
            "official_source_dominance": {
                "corpus_official_primary_ratio": c1.get(
                    "corpus_official_primary_ratio"
                ),
                "audited_official_primary_ratio": c1.get(
                    "audited_official_primary_ratio"
                ),
            },
            "tavily_exa_primary_caps": {
                "audited_ratio": c1.get("tavily_exa_primary_ratio_audited"),
                "corpus_ratio": c1.get("tavily_exa_primary_ratio_corpus"),
            },
            "structured_source_depth_coverage": {
                "coverage_ratio": c2.get("coverage_ratio"),
                "true_structured_family_count": c2.get("true_structured_family_count"),
                "non_legistar_true_structured_present": c2.get(
                    "non_legistar_true_structured_present"
                ),
            },
            "c3_d11_reconciliation": {
                "reconciled_ratio": c3.get("handoff_taxonomy_reconciled_ratio"),
                "not_policy_evidence_ratio": c3.get("not_policy_evidence_ratio"),
            },
            "manual_audit_completeness": {
                "sampled_count": c5.get("sampled_count"),
                "required_sample_count": c5.get("required_sample_count"),
            },
            "c0_c14_status": {
                gate_id: gate_results[gate_id].status for gate_id in gate_results
            },
            "package_count": len(rows),
        }

    def _build_package_gate_projection(
        self, *, rows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        per_gate_counts: dict[str, dict[str, int]] = {}
        row_projection = []

        for gate_id in PACKAGE_GATE_IDS + ECONOMIC_GATE_IDS:
            per_gate_counts[gate_id] = {
                "pass": 0,
                "fail": 0,
                "not_proven": 0,
                "blocked_hitl": 0,
            }

        for row in rows:
            row_id = str(row.get("corpus_row_id") or "unknown")
            gate_status = (
                row.get("package_gate_status")
                if isinstance(row.get("package_gate_status"), dict)
                else {}
            )
            for gate_id in PACKAGE_GATE_IDS + ECONOMIC_GATE_IDS:
                status = str(gate_status.get(gate_id) or "not_proven")
                if status not in per_gate_counts[gate_id]:
                    status = "not_proven"
                per_gate_counts[gate_id][status] += 1

            classification = row.get("classification") or {}
            class_value = str(
                classification.get("data_moat_package_classification") or ""
            )
            d11_quality = str(classification.get("d11_handoff_quality") or "")
            reconciled = False
            try:
                enum_value = DataMoatPackageClassification(class_value)
                reconciled = d11_quality in C3_D11_ALLOWED_QUALITIES[enum_value]
            except ValueError:
                reconciled = False

            row_projection.append(
                {
                    "corpus_row_id": row_id,
                    "package_id": row.get("package_id"),
                    "classification": class_value,
                    "d11_handoff_quality": d11_quality,
                    "handoff_taxonomy_reconciled": reconciled,
                    "package_gate_status": {
                        gate_id: str(gate_status.get(gate_id) or "not_proven")
                        for gate_id in PACKAGE_GATE_IDS + ECONOMIC_GATE_IDS
                    },
                }
            )

        return {
            "row_count": len(rows),
            "per_gate_counts": per_gate_counts,
            "rows": row_projection,
        }

    @staticmethod
    def _derive_corpus_state(*, gates: dict[str, dict[str, Any]]) -> str:
        statuses = [str(payload.get("status") or "") for payload in gates.values()]
        if any(status == "fail" for status in statuses):
            return "fail"
        if statuses and all(status == "pass" for status in statuses):
            return "decision_grade_corpus"
        if any(status == "blocked_hitl" for status in statuses):
            return "blocked_hitl"
        return "corpus_ready_with_gaps"

    @staticmethod
    def _derive_next_blocker(*, gates: dict[str, dict[str, Any]]) -> dict[str, Any]:
        ordered = [
            "C0",
            "C1",
            "C2",
            "C3",
            "C4",
            "C5",
            "C6",
            "C7",
            "C8",
            "C9",
            "C9a",
            "C10",
            "C11",
            "C12",
            "C13",
            "C14",
        ]
        for gate_id in ordered:
            gate = gates.get(gate_id) or {}
            if str(gate.get("status") or "") != "pass":
                return {
                    "gate": gate_id,
                    "status": gate.get("status"),
                    "reason": gate.get("reason"),
                    "blockers": gate.get("blockers", []),
                }
        return {
            "gate": None,
            "status": "pass",
            "reason": "all_gates_pass",
            "blockers": [],
        }
