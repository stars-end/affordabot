from __future__ import annotations

from typing import Any
import asyncio

from services.pipeline.structured_source_catalog import san_jose_structured_source_catalog
from services.pipeline.structured_source_enrichment import StructuredSourceEnricher


def test_san_jose_structured_source_catalog_contract_fields() -> None:
    catalog = san_jose_structured_source_catalog()
    assert len(catalog) >= 2

    required = {
        "source_family",
        "free_status",
        "signup_or_key",
        "signup_url",
        "access_method",
        "endpoint_or_file_url",
        "cadence_freshness",
        "jurisdiction_coverage",
        "policy_domain_relevance",
        "storage_target",
        "economic_usefulness_score",
        "lane_classification",
        "runtime_status",
    }
    for row in catalog:
        assert required.issubset(row.keys())
        assert row["jurisdiction_coverage"] == "san_jose_ca"
        assert isinstance(row["economic_usefulness_score"], float)


def test_structured_source_enricher_skips_non_san_jose_jurisdiction() -> None:
    enricher = StructuredSourceEnricher(timeout_seconds=0.01)
    result = asyncio.run(
        enricher.enrich(
            jurisdiction="california_state",
            source_family="meeting_minutes",
            search_query="housing impact fee",
            selected_url="https://example.org/a",
        )
    )
    assert result.status == "not_applicable"
    assert result.candidates == []
    assert "structured_enrichment_skipped_non_san_jose_jurisdiction" in result.alerts
    assert len(result.source_catalog) >= 2


def test_structured_source_enricher_returns_integrated_status_when_candidates_exist(
    monkeypatch: Any,
) -> None:
    enricher = StructuredSourceEnricher()

    async def _fake_legistar(*, client: Any) -> dict[str, Any]:
        _ = client
        return {
            "source_lane": "structured",
            "provider": "legistar_web_api",
            "source_family": "legistar_web_api",
            "access_method": "public_api_json",
            "jurisdiction": "san_jose_ca",
            "artifact_url": "https://webapi.legistar.com/v1/sanjose/Events/13001",
            "artifact_type": "meeting_metadata",
            "source_tier": "tier_b",
            "retrieved_at": "2026-04-16T00:00:00+00:00",
            "query_text": "latest san jose legistar event metadata",
            "excerpt": "Event metadata",
            "structured_policy_facts": [{"field": "event_id", "value": 13001.0, "unit": "count"}],
            "provider_run_id": "13001",
        }

    async def _fake_ckan(*, client: Any, search_query: str) -> dict[str, Any]:
        _ = (client, search_query)
        return {
            "source_lane": "structured",
            "provider": "san_jose_open_data_ckan",
            "source_family": "san_jose_open_data_ckan",
            "access_method": "ckan_api_json",
            "jurisdiction": "san_jose_ca",
            "artifact_url": "https://data.sanjoseca.gov/d/example",
            "artifact_type": "open_data_catalog_metadata",
            "source_tier": "tier_b",
            "retrieved_at": "2026-04-16T00:00:00+00:00",
            "query_text": "housing impact fee",
            "excerpt": "Dataset metadata",
            "structured_policy_facts": [{"field": "dataset_match_count", "value": 7.0, "unit": "count"}],
            "provider_run_id": "7",
        }

    monkeypatch.setattr(
        enricher,
        "_fetch_legistar_event_metadata",
        _fake_legistar,
    )
    monkeypatch.setattr(
        enricher,
        "_fetch_san_jose_ckan_metadata",
        _fake_ckan,
    )

    result = asyncio.run(
        enricher.enrich(
            jurisdiction="San Jose CA",
            source_family="meeting_minutes",
            search_query="housing impact fee",
            selected_url="https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
        )
    )

    assert result.status == "integrated"
    assert len(result.candidates) == 2
    assert {candidate["provider"] for candidate in result.candidates} == {
        "legistar_web_api",
        "san_jose_open_data_ckan",
    }
    assert result.alerts == []
