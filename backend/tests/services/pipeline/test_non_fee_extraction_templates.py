from __future__ import annotations

from services.pipeline.non_fee_extraction_templates import (
    extract_non_fee_policy_facts,
    non_fee_extraction_templates,
)


def test_non_fee_template_catalog_covers_multiple_policy_families() -> None:
    templates = non_fee_extraction_templates()
    families = {row["policy_family"] for row in templates}
    assert {"zoning_land_use", "parking_policy", "business_compliance", "meeting_action"}.issubset(
        families
    )


def test_non_fee_template_extraction_emits_required_structured_fields() -> None:
    facts = extract_non_fee_policy_facts(
        text=(
            "Council meeting agenda adopted zoning overlay updates, transportation demand management "
            "parking standards, and business licensing inspection compliance requirements."
        ),
        source_url="https://data.ca.gov/dataset/local-policy-actions.csv",
        source_family="california_open_data_ckan",
        jurisdiction="california_state",
        retrieved_at="2026-04-16T00:00:00+00:00",
        source_locator_prefix="structured_template:test",
        geography="california_state",
    )

    assert len(facts) >= 3
    for fact in facts:
        assert fact["policy_family"]
        assert fact["evidence_use"]
        assert fact["economic_relevance"] in {"indirect", "contextual", "none", "unknown"}
        assert fact["jurisdiction"] == "california_state"
        assert fact["geography"] == "california_state"
        assert fact["applicability"]
        assert fact["action_type"]
        assert fact["source_locator"].startswith("structured_template:test:")
        assert fact["effective_date"] == "unknown"
        assert fact["adoption_date"] == "unknown"
        assert fact["retrieved_at"] == "2026-04-16T00:00:00+00:00"
        assert fact["moat_value_reason"]
