"""Canonical structured source catalog entries for policy evidence packaging."""

from __future__ import annotations

from typing import Any


def san_jose_structured_source_catalog() -> list[dict[str, Any]]:
    """Return backend-owned structured-source catalog entries for San Jose."""
    return [
        {
            "source_family": "legistar_web_api",
            "display_name": "San Jose Legistar Web API",
            "free_status": "free_public",
            "signup_or_key": "none_required",
            "signup_url": "https://webapi.legistar.com/",
            "access_method": "public_api_json",
            "endpoint_or_file_url": "https://webapi.legistar.com/v1/sanjose/Events",
            "cadence_freshness": "meeting-driven; near-real-time event updates",
            "jurisdiction_coverage": "san_jose_ca",
            "policy_domain_relevance": "meeting agendas, minutes, ordinance/resolution metadata",
            "storage_target": "policy_evidence_packages.package_payload.run_context.structured_sources",
            "economic_usefulness_score": 0.78,
            "lane_classification": "structured_lane",
            "runtime_status": "integrated",
        },
        {
            "source_family": "san_jose_open_data_ckan",
            "display_name": "San Jose Open Data (CKAN)",
            "free_status": "free_public",
            "signup_or_key": "none_required",
            "signup_url": "https://data.sanjoseca.gov/",
            "access_method": "ckan_api_json",
            "endpoint_or_file_url": "https://data.sanjoseca.gov/api/3/action/package_search",
            "cadence_freshness": "dataset-dependent metadata freshness",
            "jurisdiction_coverage": "san_jose_ca",
            "policy_domain_relevance": "permits, housing/open data metadata, contextual economic indicators",
            "storage_target": "policy_evidence_packages.package_payload.run_context.structured_sources",
            "economic_usefulness_score": 0.63,
            "lane_classification": "structured_lane",
            "runtime_status": "integrated",
        },
    ]
