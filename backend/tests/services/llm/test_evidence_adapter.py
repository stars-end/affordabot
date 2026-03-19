import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import pytest
from schemas.analysis import ImpactEvidence, PersistedEvidence, SourceTier
from services.llm.evidence_adapter import (
    envelope_to_persisted_evidence,
    persisted_to_impact_evidence,
    envelope_to_impact_evidence,
    research_data_to_evidence_items,
    _classify_tier,
)


class TestTierClassification:
    def test_ca_gov_is_tier_a(self):
        assert (
            _classify_tier("https://leginfo.legislature.ca.gov/bill")
            == SourceTier.TIER_A
        )

    def test_lao_ca_gov_is_tier_a(self):
        assert _classify_tier("https://lao.ca.gov/report") == SourceTier.TIER_A

    def test_usa_gov_is_tier_a(self):
        assert _classify_tier("https://www.cbo.gov/report") == SourceTier.TIER_A

    def test_org_is_tier_b(self):
        assert _classify_tier("https://urban.org/research") == SourceTier.TIER_B

    def test_edu_is_tier_b(self):
        assert _classify_tier("https://stanford.edu/paper") == SourceTier.TIER_B

    def test_com_is_tier_c(self):
        assert _classify_tier("https://news.com/article") == SourceTier.TIER_C

    def test_empty_url_is_none(self):
        assert _classify_tier("") is None

    def test_none_url_is_none(self):
        assert _classify_tier(None) is None


class TestEnvelopeToPersistedEvidence:
    def test_converts_envelope_dict(self):
        envelope = {
            "evidence": [
                {
                    "id": "abc-123",
                    "kind": "url",
                    "url": "https://lao.ca.gov/fiscal",
                    "excerpt": "Fiscal impact estimated at $50M.",
                    "content_hash": "sha256:abc",
                    "derived_from": ["src-1"],
                    "tool_name": "retriever",
                    "tool_args": {"query": "fiscal impact SB 277"},
                    "confidence": 0.85,
                    "label": "LAO Fiscal Note",
                    "content": "Full content here",
                }
            ]
        }
        result = envelope_to_persisted_evidence(envelope)
        assert len(result) == 1
        p = result[0]
        assert isinstance(p, PersistedEvidence)
        assert p.id == "abc-123"
        assert p.kind == "url"
        assert p.url == "https://lao.ca.gov/fiscal"
        assert p.excerpt == "Fiscal impact estimated at $50M."
        assert p.content_hash == "sha256:abc"
        assert p.derived_from == ["src-1"]
        assert p.tool_name == "retriever"
        assert p.tool_args == {"query": "fiscal impact SB 277"}
        assert p.confidence == 0.85

    def test_preserves_all_required_provenance_fields(self):
        required_fields = [
            "id",
            "kind",
            "url",
            "excerpt",
            "content_hash",
            "derived_from",
            "tool_name",
            "tool_args",
            "confidence",
        ]
        envelope = {
            "evidence": [
                {
                    "id": "e1",
                    "kind": "internal",
                    "url": "https://leginfo.ca.gov",
                    "excerpt": "Bill text excerpt",
                    "content_hash": "hash-1",
                    "derived_from": [],
                    "tool_name": "scraper",
                    "tool_args": {"url": "https://leginfo.ca.gov"},
                    "confidence": 0.9,
                    "label": "CA Legislature",
                }
            ]
        }
        persisted = envelope_to_persisted_evidence(envelope)[0]
        for field in required_fields:
            assert hasattr(persisted, field), f"Missing required field: {field}"

    def test_empty_evidence_list(self):
        result = envelope_to_persisted_evidence({"evidence": []})
        assert result == []

    def test_missing_evidence_key(self):
        result = envelope_to_persisted_evidence({})
        assert result == []

    def test_non_dict_evidence_items_skipped(self):
        result = envelope_to_persisted_evidence({"evidence": ["string", 42]})
        assert result == []


class TestPersistedToImpactEvidence:
    def test_basic_conversion(self):
        persisted = PersistedEvidence(
            id="e1",
            kind="url",
            url="https://lao.ca.gov/fiscal",
            excerpt="Fiscal note",
            content_hash="hash",
            source_name="LAO",
            label="LAO Fiscal Note",
        )
        impact = persisted_to_impact_evidence(persisted)
        assert impact.url == "https://lao.ca.gov/fiscal"
        assert impact.source_name == "LAO"
        assert impact.persisted_evidence_id == "e1"
        assert impact.persisted_evidence_kind == "url"
        assert impact.source_tier == SourceTier.TIER_A

    def test_non_gov_url_gets_tier_c(self):
        persisted = PersistedEvidence(
            url="https://example.com/article",
            source_name="News",
        )
        impact = persisted_to_impact_evidence(persisted)
        assert impact.source_tier == SourceTier.TIER_C


class TestEnvelopeToImpactEvidence:
    def test_full_pipeline(self):
        envelope = {
            "evidence": [
                {
                    "id": "e1",
                    "kind": "url",
                    "url": "https://lao.ca.gov/fiscal",
                    "excerpt": "Fiscal impact",
                    "content_hash": "hash",
                    "derived_from": [],
                    "tool_name": "retriever",
                    "tool_args": None,
                    "confidence": 0.9,
                    "label": "LAO",
                }
            ]
        }
        result = envelope_to_impact_evidence(envelope)
        assert len(result) == 1
        assert result[0].url == "https://lao.ca.gov/fiscal"
        assert result[0].source_tier == SourceTier.TIER_A
        assert result[0].persisted_evidence_id == "e1"


class TestResearchDataToEvidenceItems:
    def test_converts_url_based_research(self):
        research_data = [
            {
                "url": "https://lao.ca.gov/report",
                "title": "LAO Report",
                "snippet": "Fiscal analysis shows...",
            },
        ]
        result = research_data_to_evidence_items(research_data)
        assert len(result) == 1
        assert result[0].url == "https://lao.ca.gov/report"
        assert result[0].source_name == "LAO Report"
        assert result[0].source_tier == SourceTier.TIER_A

    def test_converts_source_key(self):
        research_data = [
            {
                "source": "https://news.com/article",
                "title": "News",
                "content": "Article about bill",
            },
        ]
        result = research_data_to_evidence_items(research_data)
        assert result[0].url == "https://news.com/article"
        assert result[0].source_tier == SourceTier.TIER_C

    def test_empty_list(self):
        assert research_data_to_evidence_items([]) == []

    def test_skips_non_dicts(self):
        assert research_data_to_evidence_items(["string", 42]) == []

    def test_long_content_truncated(self):
        research_data = [
            {"url": "https://example.com", "title": "Test", "content": "x" * 1000},
        ]
        result = research_data_to_evidence_items(research_data)
        assert len(result[0].excerpt) <= 500
