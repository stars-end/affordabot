from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.pipeline.policy_evidence_package_builder import PolicyEvidencePackageBuilder
from schemas.policy_evidence_package import PolicyEvidencePackage


ROOT = Path(__file__).resolve().parents[4]
INTEGRATION_REPORT = (
    ROOT / "docs" / "poc" / "source-integration" / "artifacts" / "scrape_structured_integration_report.json"
)


def _load_integration_envelopes() -> list[dict[str, Any]]:
    payload = json.loads(INTEGRATION_REPORT.read_text(encoding="utf-8"))
    return [dict(item) for item in payload.get("envelopes", []) if isinstance(item, dict)]


def _find_envelope(*, source_lane: str, provider: str) -> dict[str, Any]:
    for envelope in _load_integration_envelopes():
        if envelope.get("source_lane") == source_lane and envelope.get("provider") == provider:
            return envelope
    raise AssertionError(f"missing fixture envelope: lane={source_lane} provider={provider}")


def test_builder_preserves_scraped_and_structured_lineage_happy_path() -> None:
    structured = _find_envelope(source_lane="structured", provider="legistar")
    scraped = _find_envelope(source_lane="scrape_search", provider="private_searxng")

    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-happy-path",
        jurisdiction="san_jose_ca",
        scraped_candidates=[scraped],
        structured_candidates=[structured],
        freshness_gate={"freshness_status": "fresh"},
    )

    assert payload["economic_handoff_ready"] is True
    assert payload["insufficiency_reasons"] == []
    cards = payload["evidence_cards"]
    assert len(cards) == 2
    assert payload["source_lanes"] == ["scraped", "structured"]
    assert payload["scraped_sources"][0]["search_provider"] == "private_searxng"
    assert payload["scraped_sources"][0]["reader_substance_passed"] is True
    assert payload["structured_sources"][0]["source_family"] == "legistar"
    assert payload["canonical_document_key"].startswith("san_jose_ca::")


def test_builder_fails_closed_for_portal_or_reader_insufficient_scraped_input() -> None:
    bad_scraped = {
        "source_lane": "scrape_search",
        "provider": "private_searxng",
        "jurisdiction": "san_jose_ca",
        "artifact_url": "https://www.sanjoseca.gov/your-government/agendas-minutes",
        "artifact_type": "meeting_portal",
        "source_tier": "tier_b",
        "retrieved_at": "2026-04-15T00:00:00+00:00",
        "query_family": "meeting_minutes",
        "prefetch_skip_reason": "/your-government/agendas-minutes",
        "reader_substance_reason": "reader_output_insufficient_substance",
        "selected_impact_mode": "pass_through_incidence",
        "mechanism_family": "fee_or_tax_pass_through",
    }

    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-portal-fail",
        jurisdiction="san_jose_ca",
        scraped_candidates=[bad_scraped],
        structured_candidates=[],
        freshness_gate={"freshness_status": "fresh"},
    )

    assert payload["economic_handoff_ready"] is False
    assert payload["gate_report"]["verdict"] == "fail_closed"
    assert payload["gate_report"]["blocking_gate"] in {"reader_substance", "parameterization"}
    reasons = set(payload["insufficiency_reasons"])
    assert "blocking_gate_present" in reasons


def test_builder_fails_closed_instead_of_schema_error_when_reader_gate_blocks_quantified_candidate() -> None:
    bad_scraped = _find_envelope(source_lane="scrape_search", provider="private_searxng")
    bad_scraped["reader_artifact_refs"] = []

    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-reader-blocked-quant-candidate",
        jurisdiction="san_jose_ca",
        scraped_candidates=[bad_scraped],
        structured_candidates=[],
        freshness_gate={"freshness_status": "fresh"},
    )

    assert payload["economic_handoff_ready"] is False
    assert payload["gate_report"]["verdict"] == "fail_closed"
    assert payload["gate_report"]["blocking_gate"] == "reader_substance"
    assert "blocking_gate_present" in set(payload["insufficiency_reasons"])


def test_builder_allows_structured_only_package_when_fields_are_economic_relevant() -> None:
    structured = _find_envelope(source_lane="structured", provider="ckan")
    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-structured-only",
        jurisdiction="california_state",
        scraped_candidates=[],
        structured_candidates=[structured],
        freshness_gate={"freshness_status": "fresh"},
        economic_hints={"mechanism_family": "adoption_take_up"},
    )

    assert payload["economic_handoff_ready"] is True
    assert payload["source_lanes"] == ["structured"]
    assert len(payload["evidence_cards"]) == 1
    assert payload["parameter_cards"]
    assert payload["structured_sources"][0]["source_family"] == "ckan"


def test_builder_keeps_structured_secondary_search_out_of_scraped_provenance() -> None:
    scraped = _find_envelope(source_lane="scrape_search", provider="private_searxng")
    secondary = {
        "source_lane": "structured_secondary_source",
        "provider": "tavily_search",
        "source_family": "tavily_secondary_search",
        "access_method": "tavily_search_api",
        "jurisdiction": "san_jose_ca",
        "artifact_url": "https://www.sanjoseca.gov/Home/Components/News/News/1801",
        "artifact_type": "secondary_search_rate_snippet",
        "source_tier": "tier_c",
        "retrieved_at": "2026-04-16T00:00:00+00:00",
        "structured_policy_facts": [
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "value": 3.0,
                "unit": "usd_per_square_foot",
                "source_url": "https://www.sanjoseca.gov/Home/Components/News/News/1801",
                "source_excerpt": "San Jose adopted a $3.00 commercial linkage fee.",
            }
        ],
    }

    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-secondary-search",
        jurisdiction="san_jose_ca",
        scraped_candidates=[scraped],
        structured_candidates=[secondary],
        freshness_gate={"freshness_status": "fresh"},
    )

    assert len(payload["scraped_sources"]) == 1
    assert payload["scraped_sources"][0]["search_provider"] == "private_searxng"
    assert len(payload["structured_sources"]) == 1
    assert payload["structured_sources"][0]["source_family"] == "tavily_secondary_search"
    assert payload["structured_sources"][0]["true_structured"] is False
    assert "scraped_provider_identity_missing" not in set(payload["insufficiency_reasons"])
    assert payload["economic_handoff_ready"] is False


def test_builder_does_not_let_secondary_search_rescue_true_structured_depth() -> None:
    scraped = _find_envelope(source_lane="scrape_search", provider="private_searxng")
    shallow_structured = {
        "source_lane": "structured",
        "provider": "legistar_web_api",
        "source_family": "legistar_web_api",
        "jurisdiction": "san_jose_ca",
        "artifact_url": scraped["artifact_url"],
        "artifact_type": "meeting_metadata",
        "source_tier": "tier_b",
        "retrieved_at": "2026-04-16T00:00:00+00:00",
        "structured_policy_facts": [{"field": "event_attachment_hint_count", "value": 0.0, "unit": "count"}],
        "policy_match_key": scraped["canonical_document_key"],
        "policy_match_confidence": 0.9,
        "reconciliation_status": "confirmed",
        "lineage_metadata": {"event_date": "2026-04-16", "event_body_id": "258", "matter_id": "14575"},
    }
    secondary = {
        "source_lane": "structured_secondary_source",
        "provider": "tavily",
        "source_family": "tavily_secondary_search",
        "access_method": "tavily_search_api",
        "jurisdiction": "san_jose_ca",
        "artifact_url": "https://www.sanjoseca.gov/Home/Components/News/News/1801",
        "artifact_type": "secondary_search_rate_snippet",
        "source_tier": "tier_c",
        "retrieved_at": "2026-04-16T00:00:00+00:00",
        "structured_policy_facts": [
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "value": 3.0,
                "unit": "usd_per_square_foot",
                "source_url": "https://www.sanjoseca.gov/Home/Components/News/News/1801",
                "source_excerpt": "San Jose adopted a $3.00 commercial linkage fee.",
            }
        ],
        "true_structured": False,
        "policy_match_key": scraped["canonical_document_key"],
        "reconciliation_status": "secondary_search_derived_not_authoritative",
    }

    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-secondary-not-structured-depth",
        jurisdiction="san_jose_ca",
        scraped_candidates=[scraped],
        structured_candidates=[shallow_structured, secondary],
        freshness_gate={"freshness_status": "fresh"},
    )

    assert payload["parameter_cards"]
    assert payload["structured_sources"][1]["true_structured"] is False
    assert payload["economic_handoff_ready"] is False
    assert "blocking_gate_present" in set(payload["insufficiency_reasons"])
    assert all(
        card["parameter_name"] != "event_attachment_hint_count"
        for card in payload["parameter_cards"]
    )


def test_builder_does_not_emit_diagnostic_structured_counts_as_parameter_cards() -> None:
    structured = {
        "source_lane": "structured",
        "provider": "legistar_web_api",
        "source_family": "legistar_web_api",
        "jurisdiction": "san_jose_ca",
        "artifact_url": "https://webapi.legistar.com/v1/sanjose/Matters/7526",
        "artifact_type": "matter_metadata",
        "source_tier": "tier_b",
        "retrieved_at": "2026-04-16T00:00:00+00:00",
        "structured_policy_facts": [
            {"field": "matter_attachment_count", "value": 19.0, "unit": "count"},
            {"field": "matter_attachment_url_count", "value": 19.0, "unit": "count"},
        ],
        "true_structured": True,
        "policy_match_key": "legistar::matter::7526",
        "reconciliation_status": "contextual_metadata_linked_to_policy_query",
        "lineage_metadata": {"matter_id": "7526"},
    }

    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-diagnostic-structured-counts",
        jurisdiction="san_jose_ca",
        structured_candidates=[structured],
    )

    assert payload["structured_sources"][0]["field_count"] == 2
    assert payload["parameter_cards"] == []
    assert payload["economic_handoff_ready"] is False


def test_builder_marks_storage_proof_unproven_when_refs_absent() -> None:
    structured = _find_envelope(source_lane="structured", provider="legistar")
    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-storage-unproven",
        jurisdiction="san_jose_ca",
        structured_candidates=[structured],
    )
    refs = payload["storage_refs"]
    assert len(refs) == 3
    assert any(
        ref["storage_system"] == "pgvector" and ref["truth_role"] == "derived_index"
        for ref in refs
    )


def test_builder_blocks_unreconciled_structured_latest_event_fallback() -> None:
    scraped = _find_envelope(source_lane="scrape_search", provider="private_searxng")
    structured_unreconciled = {
        "source_lane": "structured",
        "provider": "legistar_web_api",
        "source_family": "legistar_web_api",
        "jurisdiction": "san_jose_ca",
        "artifact_url": "https://webapi.legistar.com/v1/sanjose/Events/99999",
        "artifact_type": "meeting_metadata",
        "source_tier": "tier_b",
        "retrieved_at": "2026-04-16T00:00:00+00:00",
        "structured_policy_facts": [{"field": "event_attachment_hint_count", "value": 0.0, "unit": "count"}],
        "policy_match_key": "legistar::event::99999",
        "policy_match_confidence": 0.2,
        "reconciliation_status": "latest_event_fallback_unreconciled",
        "lineage_metadata": {"event_date": "2026-04-16", "event_body_id": "258", "matter_id": None},
    }

    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-unreconciled-structured",
        jurisdiction="san_jose_ca",
        scraped_candidates=[scraped],
        structured_candidates=[structured_unreconciled],
        freshness_gate={"freshness_status": "fresh"},
    )

    assert payload["economic_handoff_ready"] is False
    assert "blocking_gate_present" in set(payload["insufficiency_reasons"])
    assert payload["structured_sources"][0]["reconciliation_status"] in {
        "conflict_unresolved",
        "latest_event_fallback_unreconciled",
    }


def test_builder_fails_closed_when_structured_shape_drifts() -> None:
    """D8: malformed structured payloads should fail closed instead of crashing/pass-through."""
    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-structured-shape-drift",
        jurisdiction="san_jose_ca",
        structured_candidates=[
            {
                "source_lane": "structured",
                "provider": "legistar_web_api",
                "source_family": "legistar_web_api",
                "jurisdiction": "san_jose_ca",
                "artifact_url": "https://webapi.legistar.com/v1/sanjose/Matters/14575",
                "artifact_type": "matter_metadata",
                "source_tier": "tier_b",
                "retrieved_at": "2026-04-16T00:00:00+00:00",
                "structured_policy_facts": {"unexpected": "dict_instead_of_list"},
                "policy_match_key": "legistar::matter::14575",
                "policy_match_confidence": 0.8,
                "reconciliation_status": "source_shape_changed",
                "lineage_metadata": {"matter_id": "14575"},
            }
        ],
        freshness_gate={"freshness_status": "fresh"},
    )

    assert payload["economic_handoff_ready"] is False
    assert "blocking_gate_present" in set(payload["insufficiency_reasons"])


def test_builder_output_is_json_serializable() -> None:
    structured = _find_envelope(source_lane="structured", provider="legistar")
    scraped = _find_envelope(source_lane="scrape_search", provider="private_searxng")
    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-json-serializable",
        jurisdiction="san_jose_ca",
        structured_candidates=[structured],
        scraped_candidates=[scraped],
        storage_refs={"raw_provider_response": "minio://bucket/raw/provider.json"},
    )
    serialized = json.dumps(payload)
    roundtrip = json.loads(serialized)
    assert roundtrip["package_id"] == "pkg-json-serializable"
    assert isinstance(roundtrip["evidence_cards"], list)
    assert "schema_validation" not in roundtrip
    validated = PolicyEvidencePackage.model_validate(roundtrip)
    assert validated.package_id == "pkg-json-serializable"


def test_builder_dedupes_duplicate_candidates_without_double_counting_cards() -> None:
    scraped = _find_envelope(source_lane="scrape_search", provider="private_searxng")
    duplicate_scraped = dict(scraped)
    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-dedupe",
        jurisdiction="san_jose_ca",
        scraped_candidates=[scraped, duplicate_scraped],
        structured_candidates=[],
    )
    assert len(payload["evidence_cards"]) == 1
    assert payload["gate_report"]["artifact_counts"]["evidence_cards"] == 1
    assert "deduped_candidates=" in payload["gate_report"]["manual_audit_notes"]


def test_builder_storage_refs_propagate_content_hash_for_provenance() -> None:
    structured = _find_envelope(source_lane="structured", provider="legistar")
    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-storage-hash",
        jurisdiction="san_jose_ca",
        structured_candidates=[structured],
    )
    refs = payload["storage_refs"]
    assert all(ref.get("content_hash") for ref in refs)


def test_builder_marks_ambiguous_parameter_when_citation_sanity_fails() -> None:
    scraped = _find_envelope(source_lane="scrape_search", provider="private_searxng")
    scraped["structured_policy_facts"] = [
        {
            "field": "commercial_linkage_fee_rate_usd_per_sqft",
            "raw_value": "$18.706.00",
            "normalized_value": None,
            "unit": "usd_per_square_foot",
            "denominator": "per_square_foot",
            "category": "retail",
            "land_use": "retail",
            "subarea": "downtown",
            "threshold": "<100,000 sq. ft.",
            "payment_timing": "paid_before_building_permit_issuance",
            "payment_reduction_context": "20% reduction applies when paid in full prior to permit issuance",
            "payment_reduction_percent": 20.0,
            "exemption_context": "no_fee_for_threshold:<100,000 sq. ft.",
            "raw_land_use_label": "Downtown Office",
            "source_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
            "source_excerpt": "Commercial Linkage Fee table excerpt",
            "source_locator": "reader_content:1:fee_table_row",
            "table_locator": "commercial_linkage_fee_table",
            "page_locator": "p.7",
            "locator_quality": "table_row_chunk_locator",
            "source_family": "official_page",
            "source_ref": "legistar::matter::7526::attachment::8758120",
            "policy_match_key": "legistar::matter::7526",
            "source_hierarchy_status": "bill_or_reg_text",
            "currency_sanity": "invalid",
            "unit_sanity": "valid",
            "ambiguity_flag": True,
            "ambiguity_reason": "currency_format_anomaly",
            "fail_closed_signals": ["locator_precision_insufficient_for_artifact_grade"],
            "effective_date": "2026-01-01",
            "adoption_date": "2025-12-08",
            "final_status": "adopted",
            "confidence": 0.33,
        }
    ]

    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-ambiguous-citation",
        jurisdiction="san_jose_ca",
        scraped_candidates=[scraped],
        structured_candidates=[],
        freshness_gate={"freshness_status": "fresh"},
    )

    cards = payload["parameter_cards"]
    assert len(cards) == 1
    assert cards[0]["state"] == "ambiguous"
    assert cards[0]["ambiguity_reason"] == "currency_format_anomaly"
    assert cards[0]["value"] is None
    assert "raw=$18.706.00" in cards[0]["source_excerpt"]
    assert "subarea=downtown" in cards[0]["source_excerpt"]
    assert "threshold=<100,000 sq. ft." in cards[0]["source_excerpt"]
    assert "payment_timing=paid_before_building_permit_issuance" in cards[0]["source_excerpt"]
    assert "payment_reduction_percent=20.00" in cards[0]["source_excerpt"]
    assert "exemption_context=no_fee_for_threshold:<100,000 sq. ft." in cards[0]["source_excerpt"]
    assert "raw_land_use_label=Downtown Office" in cards[0]["source_excerpt"]
    assert "source_family=official_page" in cards[0]["source_excerpt"]
    assert "locator_quality=table_row_chunk_locator" in cards[0]["source_excerpt"]
    assert "fail_closed_signals=locator_precision_insufficient_for_artifact_grade" in cards[0]["source_excerpt"]


def test_builder_parameter_cards_capture_official_attachment_metadata() -> None:
    structured = {
        "source_lane": "structured",
        "provider": "legistar_web_api",
        "source_family": "legistar_web_api",
        "jurisdiction": "san_jose_ca",
        "artifact_url": "https://webapi.legistar.com/v1/sanjose/Matters/7526",
        "artifact_type": "matter_metadata",
        "source_tier": "tier_b",
        "retrieved_at": "2026-04-16T00:00:00+00:00",
        "true_structured": True,
        "policy_match_key": "legistar::matter::7526",
        "reconciliation_status": "confirmed",
        "structured_policy_facts": [
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "raw_value": "$14.31",
                "normalized_value": 14.31,
                "value": 14.31,
                "unit": "usd_per_square_foot",
                "land_use": "office",
                "raw_land_use_label": "Downtown Office",
                "threshold": ">=100,000 sq. ft.",
                "payment_timing": "paid_before_building_permit_issuance",
                "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                "source_locator": "attachment_probe:301:1:fee_table_row",
                "table_locator": "commercial_linkage_fee_table",
                "locator_quality": "table_row_chunk_locator",
                "source_family": "resolution",
                "source_ref": "legistar::matter::7526::attachment::301",
                "attachment_id": "301",
                "attachment_title": "Resolution No. 80069",
                "source_hierarchy_status": "bill_or_reg_text",
            }
        ],
    }

    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-official-attachment-parameter",
        jurisdiction="san_jose_ca",
        structured_candidates=[structured],
        freshness_gate={"freshness_status": "fresh"},
    )

    assert payload["parameter_cards"]
    card = payload["parameter_cards"][0]
    assert card["state"] == "resolved"
    assert card["value"] == 14.31
    assert "source_family=resolution" in card["source_excerpt"]
    assert "attachment_id=301" in card["source_excerpt"]
    assert "attachment_title=Resolution No. 80069" in card["source_excerpt"]
    assert "source_locator=attachment_probe:301:1:fee_table_row" in card["source_excerpt"]


def test_builder_parameter_cards_filter_weak_attachment_excerpt_rows() -> None:
    structured = {
        "source_lane": "structured",
        "provider": "legistar_web_api",
        "source_family": "legistar_web_api",
        "jurisdiction": "san_jose_ca",
        "artifact_url": "https://webapi.legistar.com/v1/sanjose/Matters/7526",
        "artifact_type": "matter_metadata",
        "source_tier": "tier_b",
        "retrieved_at": "2026-04-16T00:00:00+00:00",
        "true_structured": True,
        "policy_match_key": "legistar::matter::7526",
        "reconciliation_status": "confirmed",
        "structured_policy_facts": [
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "raw_value": "$6.00",
                "normalized_value": 6.0,
                "value": 6.0,
                "unit": "usd_per_square_foot",
                "denominator": "per_square_foot",
                "land_use": "office",
                "raw_land_use_label": "Downtown Office",
                "source_excerpt": "Downtown Office (>=100,000 sq. ft.) $6.00 per square foot.",
                "source_locator": "attachment_probe:301:1:fee_table_row",
                "chunk_locator": "attachment_probe:301:1",
                "table_locator": "commercial_linkage_fee_table",
                "locator_quality": "chunk_locator_only",
                "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                "source_family": "resolution",
                "attachment_id": "301",
            },
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "raw_value": "$600",
                "normalized_value": 600.0,
                "value": 600.0,
                "unit": "usd",
                "land_use": "unknown",
                "category": "unknown",
                "source_excerpt": "Memorandum excerpt says $600.",
                "source_locator": "attachment_probe:excerpt",
                "locator_quality": "attachment_probe_excerpt",
                "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758121",
                "source_family": "memorandum",
                "attachment_id": "302",
            },
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "raw_value": "$52.30",
                "normalized_value": 52.3,
                "value": 52.3,
                "unit": "usd",
                "land_use": "unknown",
                "category": "unknown",
                "source_excerpt": "Excerpt-only mention of $52.30 with no table row cue.",
                "source_locator": "attachment_probe:302:excerpt",
                "locator_quality": "attachment_probe_excerpt",
                "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758122",
                "source_family": "memorandum",
                "attachment_id": "303",
            },
        ],
    }

    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-attachment-row-quality-gate",
        jurisdiction="san_jose_ca",
        structured_candidates=[structured],
        freshness_gate={"freshness_status": "fresh"},
    )

    cards = payload["parameter_cards"]
    assert len(cards) == 1
    assert cards[0]["state"] == "resolved"
    assert cards[0]["value"] == 6.0
    assert "attachment_probe:301:1:fee_table_row" in cards[0]["source_excerpt"]
    assert "$600" not in cards[0]["source_excerpt"]
    assert "$52.30" not in cards[0]["source_excerpt"]


def test_builder_parameter_cards_keep_direct_line_rate_rows_with_land_use() -> None:
    structured = {
        "source_lane": "structured",
        "provider": "legistar_web_api",
        "source_family": "legistar_web_api",
        "jurisdiction": "san_jose_ca",
        "artifact_url": "https://webapi.legistar.com/v1/sanjose/Matters/7526",
        "artifact_type": "matter_metadata",
        "source_tier": "tier_b",
        "retrieved_at": "2026-04-16T00:00:00+00:00",
        "true_structured": True,
        "policy_match_key": "legistar::matter::7526",
        "reconciliation_status": "confirmed",
        "structured_policy_facts": [
            {
                "field": "commercial_linkage_fee_rate_usd_per_sqft",
                "raw_value": "$14.31",
                "normalized_value": 14.31,
                "value": 14.31,
                "unit": "usd_per_square_foot",
                "land_use": "office",
                "raw_land_use_label": "Office",
                "source_excerpt": "Office projects pay $14.31 per square foot.",
                "source_locator": "attachment_probe:line_segment",
                "locator_quality": "attachment_probe_line_rate",
                "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758123",
                "source_family": "memorandum",
                "attachment_id": "304",
            }
        ],
    }

    payload = PolicyEvidencePackageBuilder().build(
        package_id="pkg-attachment-line-rate-quality-gate",
        jurisdiction="san_jose_ca",
        structured_candidates=[structured],
        freshness_gate={"freshness_status": "fresh"},
    )

    cards = payload["parameter_cards"]
    assert len(cards) == 1
    assert cards[0]["value"] == 14.31
    assert "Office projects pay $14.31 per square foot." in cards[0]["source_excerpt"]
