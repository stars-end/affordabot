"""Structured-source enrichment for PolicyEvidencePackage materialization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus

import httpx

from services.pipeline.structured_source_catalog import san_jose_structured_source_catalog


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _is_san_jose_jurisdiction(value: str) -> bool:
    normalized = value.strip().lower().replace(" ", "_")
    return "san_jose" in normalized or "san-jose" in normalized


@dataclass(frozen=True)
class StructuredEnrichmentResult:
    status: str
    candidates: list[dict[str, Any]]
    alerts: list[str]
    source_catalog: list[dict[str, Any]]


class StructuredSourceEnricher:
    """Runtime structured-source collector for San Jose source families."""

    def __init__(self, *, timeout_seconds: float = 4.0) -> None:
        self.timeout_seconds = timeout_seconds

    async def enrich(
        self,
        *,
        jurisdiction: str,
        source_family: str,
        search_query: str,
        selected_url: str,
    ) -> StructuredEnrichmentResult:
        catalog = san_jose_structured_source_catalog()
        if not _is_san_jose_jurisdiction(jurisdiction):
            return StructuredEnrichmentResult(
                status="not_applicable",
                candidates=[],
                alerts=["structured_enrichment_skipped_non_san_jose_jurisdiction"],
                source_catalog=catalog,
            )

        candidates: list[dict[str, Any]] = []
        alerts: list[str] = []

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            legistar_candidate = await self._fetch_legistar_event_metadata(client=client)
            if legistar_candidate:
                candidates.append(legistar_candidate)
            else:
                alerts.append("structured_enrichment_legistar_unavailable")

            ckan_candidate = await self._fetch_san_jose_ckan_metadata(
                client=client,
                search_query=search_query,
            )
            if ckan_candidate:
                candidates.append(ckan_candidate)
            else:
                alerts.append("structured_enrichment_ckan_unavailable")

        status = "integrated" if candidates else "unavailable"
        if not candidates and selected_url:
            alerts.append("structured_enrichment_no_candidates_for_selected_url_context")
        _ = source_family

        return StructuredEnrichmentResult(
            status=status,
            candidates=candidates,
            alerts=list(dict.fromkeys(alerts)),
            source_catalog=catalog,
        )

    async def _fetch_legistar_event_metadata(
        self, *, client: httpx.AsyncClient
    ) -> dict[str, Any] | None:
        endpoint = "https://webapi.legistar.com/v1/sanjose/Events?$top=1&$orderby=EventDate desc"
        try:
            response = await client.get(endpoint)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not isinstance(payload, list) or not payload:
            return None

        event = payload[0] if isinstance(payload[0], dict) else {}
        event_id = event.get("EventId")
        event_body_id = event.get("EventBodyId")
        event_date = str(event.get("EventDate") or "")
        event_url = str(event.get("EventInSiteURL") or endpoint)
        if not event_id:
            return None

        facts: list[dict[str, Any]] = [
            {"field": "event_id", "value": float(event_id), "unit": "count"},
        ]
        if isinstance(event_body_id, int):
            facts.append({"field": "event_body_id", "value": float(event_body_id), "unit": "count"})

        return {
            "source_lane": "structured",
            "provider": "legistar_web_api",
            "source_family": "legistar_web_api",
            "access_method": "public_api_json",
            "jurisdiction": "san_jose_ca",
            "artifact_url": event_url,
            "artifact_type": "meeting_metadata",
            "source_tier": "tier_b",
            "retrieved_at": _utc_now_iso(),
            "query_text": "latest san jose legistar event metadata",
            "excerpt": (
                "Structured Legistar event metadata fetched from San Jose Web API; "
                f"EventId={event_id}, EventDate={event_date or 'unknown'}."
            ),
            "structured_policy_facts": facts,
            "provider_run_id": str(event_id),
        }

    async def _fetch_san_jose_ckan_metadata(
        self,
        *,
        client: httpx.AsyncClient,
        search_query: str,
    ) -> dict[str, Any] | None:
        safe_query = search_query.strip() or "housing"
        endpoint = (
            "https://data.sanjoseca.gov/api/3/action/package_search"
            f"?q={quote_plus(safe_query)}&rows=5"
        )
        try:
            response = await client.get(endpoint)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not isinstance(payload, dict) or payload.get("success") is not True:
            return None

        result = payload.get("result")
        if not isinstance(result, dict):
            return None
        total_count = result.get("count")
        rows = result.get("results")
        if not isinstance(total_count, int) or not isinstance(rows, list):
            return None

        top_dataset = rows[0] if rows and isinstance(rows[0], dict) else {}
        top_dataset_url = str(top_dataset.get("url") or top_dataset.get("name") or endpoint)
        resource_count = top_dataset.get("num_resources")
        facts: list[dict[str, Any]] = [
            {"field": "dataset_match_count", "value": float(total_count), "unit": "count"},
        ]
        if isinstance(resource_count, int):
            facts.append({"field": "top_dataset_resource_count", "value": float(resource_count), "unit": "count"})

        return {
            "source_lane": "structured",
            "provider": "san_jose_open_data_ckan",
            "source_family": "san_jose_open_data_ckan",
            "access_method": "ckan_api_json",
            "jurisdiction": "san_jose_ca",
            "artifact_url": top_dataset_url if top_dataset_url.startswith("http") else endpoint,
            "artifact_type": "open_data_catalog_metadata",
            "source_tier": "tier_b",
            "retrieved_at": _utc_now_iso(),
            "query_text": safe_query,
            "excerpt": (
                "Structured CKAN metadata from San Jose Open Data; "
                f"query='{safe_query}', dataset_count={total_count}."
            ),
            "structured_policy_facts": facts,
            "provider_run_id": str(total_count),
        }
