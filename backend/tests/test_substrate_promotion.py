import pytest

from services.substrate_promotion import DURABLE_RAW
from services.substrate_promotion import PROMOTED_SUBSTRATE
from services.substrate_promotion import apply_promotion_decision
from services.substrate_promotion import evaluate_rules
from services.substrate_promotion import evaluate_with_fallback
from services.substrate_promotion import seed_capture_promotion_metadata
from services.substrate_promotion import GLM46VPromotionBoundary


def test_seed_capture_metadata_official_host_defaults_to_durable_raw():
    metadata = seed_capture_promotion_metadata(
        metadata={
            "canonical_url": "https://www.sanjoseca.gov/business",
            "document_type": "agenda",
        },
        canonical_url="https://www.sanjoseca.gov/business",
        trust_tier=None,
    )

    assert metadata["promotion_state"] == DURABLE_RAW
    assert metadata["promotion_method"] == "rules"
    assert metadata["trust_host_classification"] == "official_government"


def test_evaluate_rules_promotes_non_retrievable_official_pdf():
    decision = evaluate_rules(
        {
            "canonical_url": "https://sanjose.legistar.com/View.ashx?M=A",
            "trust_tier": "primary_government",
            "trust_host_classification": "official_civic_partner",
            "promotion_state": DURABLE_RAW,
            "document_type": "agenda",
            "content_class": "pdf_binary",
            "title": "Planning Commission Agenda",
            "preview_text": "",
            "ingestion_truth": {"retrievable": False},
        }
    )

    assert decision.promotion_state == PROMOTED_SUBSTRATE
    assert decision.reason_category == "substantive_official_document"
    assert decision.confidence == "medium"


def test_evaluate_rules_promotes_retrievable_official_pdf():
    decision = evaluate_rules(
        {
            "canonical_url": "https://sanjose.legistar.com/View.ashx?M=A",
            "trust_tier": "primary_government",
            "trust_host_classification": "official_civic_partner",
            "promotion_state": DURABLE_RAW,
            "document_type": "agenda",
            "content_class": "pdf_binary",
            "title": "Planning Commission Agenda",
            "preview_text": "",
            "ingestion_truth": {"retrievable": True},
        }
    )

    assert decision.promotion_state == PROMOTED_SUBSTRATE
    assert decision.reason_category == "substantive_official_document"


def test_evaluate_rules_denies_shell_page():
    decision = evaluate_rules(
        {
            "canonical_url": "https://library.municode.com/ca/san_jose/codes",
            "trust_tier": "primary_government",
            "promotion_state": DURABLE_RAW,
            "document_type": "municipal_code",
            "content_class": "html_text",
            "title": "Municode Library",
            "preview_text": "Municode Library",
            "ingestion_truth": {"retrievable": True},
        }
    )

    assert decision.promotion_state == DURABLE_RAW
    assert decision.reason_category == "index_or_shell_page"


def test_evaluate_rules_legacy_unknown_when_missing_truth_and_state():
    decision = evaluate_rules(
        {
            "canonical_url": "https://www.sanjoseca.gov/business",
            "trust_tier": "primary_government",
            "document_type": "agenda",
        }
    )

    assert decision.promotion_state is None
    assert decision.reason_category == "legacy_unknown"


@pytest.mark.asyncio
async def test_evaluate_with_fallback_sets_llm_fallback_error():
    boundary = GLM46VPromotionBoundary(
        api_key="test-key",
        enabled=True,
        transport=None,
    )
    decision = await evaluate_with_fallback(
        metadata={
            "canonical_url": "https://www.sanjoseca.gov/business",
            "trust_tier": "primary_government",
            "promotion_state": DURABLE_RAW,
            "document_type": "other",
            "content_class": "html_text",
            "title": "Unknown item",
            "preview_text": "short",
            "ingestion_truth": {"retrievable": False},
        },
        llm_boundary=boundary,
    )

    assert decision.method == "llm_fallback_rules"
    assert decision.promotion_state == DURABLE_RAW
    assert "transport not configured" in (decision.promotion_error or "").lower()


def test_apply_promotion_decision_persists_machine_fields():
    decision = evaluate_rules(
        {
            "canonical_url": "https://www.sanjoseca.gov/path",
            "trust_tier": "primary_government",
            "promotion_state": DURABLE_RAW,
            "document_type": "agenda",
            "content_class": "html_text",
            "title": "City Council Agenda",
            "preview_text": "This agenda includes substantive and actionable items across multiple sections.",
            "ingestion_truth": {"retrievable": True},
        }
    )
    updated = apply_promotion_decision(
        metadata={"canonical_url": "https://www.sanjoseca.gov/path"},
        decision=decision,
    )

    assert updated["promotion_state"] == PROMOTED_SUBSTRATE
    assert updated["promotion_method"] == "rules"
    assert updated["promotion_reason_category"] == "substantive_official_document"
    assert updated["promotion_policy_version"]
    assert updated["promotion_last_evaluated_at"]
    assert "promotion_error" in updated
