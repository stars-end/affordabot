from __future__ import annotations

from datetime import UTC, datetime

from services.pipeline.source_identity import (
    build_external_source_promotion_entry,
    build_source_durability_profile,
    classify_source_candidate,
    compute_official_source_dominance,
)


def test_official_sources_are_primary_evidence_allowed() -> None:
    cases = [
        {
            "artifact_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=1328259",
            "title": "Resolution 80069 Fee Schedule Attachment",
            "snippet": "Commercial linkage fee table with adopted rate schedule per square foot.",
            "provider": "private_searxng",
            "source_lane": "scrape_search",
            "jurisdiction": "san_jose_ca",
            "policy_families": ["commercial_linkage_fee"],
        },
        {
            "artifact_url": "https://www.sccgov.org/sites/ceo/agenda/2026-04-16-county-board-agenda.pdf",
            "title": "County Board Agenda Packet",
            "snippet": "County board ordinance and fee adoption packet.",
            "provider": "private_searxng",
            "source_lane": "scrape_search",
            "jurisdiction": "santa_clara_county_ca",
            "policy_families": ["meeting_action"],
        },
        {
            "artifact_url": "https://ww2.arb.ca.gov/rulemaking/transportation-fuels",
            "title": "California Air Resources Board Rulemaking",
            "snippet": "Regional/state regulatory source for local implementation impact.",
            "provider": "private_searxng",
            "source_lane": "scrape_search",
            "jurisdiction": "california_state",
            "policy_families": ["general_governance"],
        },
    ]
    for candidate in cases:
        classification = classify_source_candidate(
            candidate=candidate,
            jurisdiction=candidate["jurisdiction"],
            policy_families=candidate["policy_families"],
        )
        assert classification["source_officialness"].startswith("official_")
        assert classification["source_of_truth_role"] == "primary_official"
        assert classification["primary_evidence_allowed"] is True


def test_external_sources_default_to_context_only() -> None:
    cases = [
        {
            "artifact_url": "https://www.sierraclub.org/policy/municipal-fee-impact-study.pdf",
            "title": "Advocacy Report PDF",
            "snippet": "Advocacy summary of fee impacts.",
            "expected_officialness": "external_advocacy",
        },
        {
            "artifact_url": "https://www.planetizen.com/news/2026/01/local-fee-update",
            "title": "News Recap",
            "snippet": "News article summarizing municipal fee updates.",
            "expected_officialness": "external_news",
        },
        {
            "artifact_url": "https://www.vendorfeesolutions.com/local-government-fee-benchmark",
            "title": "Vendor Benchmark",
            "snippet": "Commercial fee benchmark dashboard.",
            "expected_officialness": "external_vendor",
        },
        {
            "artifact_url": "https://cityportal-123.example.com/agenda?item=42",
            "title": "Agenda Portal",
            "snippet": "Portal page with item summary only.",
            "expected_officialness": "ambiguous_portal",
        },
    ]

    for candidate in cases:
        classification = classify_source_candidate(
            candidate={
                **candidate,
                "provider": "private_searxng",
                "source_lane": "scrape_search",
            },
            jurisdiction="san_jose_ca",
            policy_families=["meeting_action"],
        )
        assert (
            classification["source_officialness"] == candidate["expected_officialness"]
        )
        assert classification["external_context_allowed"] is True
        assert classification["primary_evidence_allowed"] is False


def test_external_source_promotion_requires_audited_rule() -> None:
    pending = classify_source_candidate(
        candidate={
            "artifact_url": "https://www.sierraclub.org/policy/municipal-fee-impact-study.pdf",
            "title": "Advocacy Report PDF",
            "snippet": "Advocacy summary of fee impacts.",
            "provider": "private_searxng",
            "source_lane": "scrape_search",
            "source_identity_promotion_rule_id": "ext-promote-001",
            "source_identity_promotion_reason": "Only published source for retired archival policy.",
            "source_identity_promotion_audit_status": "pending",
        },
        jurisdiction="san_jose_ca",
        policy_families=["meeting_action"],
    )
    assert pending["primary_evidence_allowed"] is False
    assert pending["source_of_truth_role"] != "primary_external_promoted"

    approved = classify_source_candidate(
        candidate={
            "artifact_url": "https://www.sierraclub.org/policy/municipal-fee-impact-study.pdf",
            "title": "Advocacy Report PDF",
            "snippet": "Advocacy summary of fee impacts.",
            "provider": "private_searxng",
            "source_lane": "scrape_search",
            "source_identity_promotion_rule_id": "ext-promote-001",
            "source_identity_promotion_reason": "Only published source for retired archival policy.",
            "source_identity_promotion_audit_status": "approved",
        },
        jurisdiction="san_jose_ca",
        policy_families=["meeting_action"],
    )
    assert approved["primary_evidence_allowed"] is True
    assert approved["source_of_truth_role"] == "primary_external_promoted"
    register = build_external_source_promotion_entry(
        classification=approved,
        package_id="pkg-1",
    )
    assert register is not None
    assert register["rule_id"] == "ext-promote-001"
    assert register["package_id"] == "pkg-1"


def test_official_source_dominance_enforces_thresholds_and_secondary_caps() -> None:
    official = classify_source_candidate(
        candidate={
            "artifact_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=1328259",
            "title": "Resolution 80069 Fee Schedule Attachment",
            "snippet": "Official source.",
            "provider": "private_searxng",
            "source_lane": "scrape_search",
        },
        jurisdiction="san_jose_ca",
        policy_families=["commercial_linkage_fee"],
    )
    external_promoted = classify_source_candidate(
        candidate={
            "artifact_url": "https://www.planetizen.com/news/2026/01/local-fee-update",
            "title": "News Recap",
            "snippet": "News article summarizing fee updates.",
            "provider": "tavily",
            "source_lane": "scrape_search",
            "source_identity_promotion_rule_id": "ext-promote-002",
            "source_identity_promotion_reason": "Documented legal publication exception.",
            "source_identity_promotion_audit_status": "approved",
        },
        jurisdiction="san_jose_ca",
        policy_families=["commercial_linkage_fee"],
    )
    dominance = compute_official_source_dominance(
        classifications=[official, external_promoted]
    )
    assert dominance["status"] == "fail"
    assert dominance["corpus_official_primary_percent"] == 50.0
    assert "official_dominance_corpus_hard_fail" in dominance["failure_codes"]
    assert (
        "secondary_provider_primary_cap_exceeded_audited" in dominance["failure_codes"]
    )


def test_durability_profiles_mark_stale_and_shape_changed_sources() -> None:
    profile = build_source_durability_profile(
        candidate={
            "artifact_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=1328259",
            "source_family": "legistar_web_api",
            "source_lane": "structured",
            "artifact_type": "meeting_metadata",
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "last_successful_refresh": "2026-01-01T00:00:00+00:00",
            "update_cadence": "weekly",
            "reconciliation_status": "source_shape_changed",
            "structured_policy_facts": [
                {"field": "commercial_linkage_fee_rate_usd_per_sqft"}
            ],
        },
        freshness_status="stale_blocked",
        now=datetime(2026, 4, 17, tzinfo=UTC),
    )

    assert profile["source_shape_changed"] is True
    assert profile["update_cadence_drift"] is True
    assert profile["stale_for_policy_use"] is True
    assert profile["next_refresh_recommendation"] == "refresh_immediately"
