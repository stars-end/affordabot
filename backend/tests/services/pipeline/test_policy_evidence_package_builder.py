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
