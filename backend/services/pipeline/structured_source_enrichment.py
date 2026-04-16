"""Structured-source enrichment for PolicyEvidencePackage materialization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx

from services.pipeline.structured_source_catalog import san_jose_structured_source_catalog


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _is_san_jose_jurisdiction(value: str) -> bool:
    normalized = value.strip().lower().replace(" ", "_")
    return "san_jose" in normalized or "san-jose" in normalized


_ECONOMIC_DATASET_TOKENS = {
    "housing",
    "rent",
    "permit",
    "development",
    "construction",
    "planning",
    "zoning",
    "affordable",
    "income",
    "wage",
    "employment",
    "tax",
    "fee",
    "budget",
    "property",
    "parcel",
    "cost",
}


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
            legistar_matter_candidate = await self._fetch_legistar_matter_metadata(
                client=client,
                selected_url=selected_url,
                search_query=search_query,
            )
            if legistar_matter_candidate:
                candidates.append(legistar_matter_candidate)
            else:
                legistar_event_candidate = await self._fetch_legistar_event_metadata(client=client)
                if legistar_event_candidate:
                    candidates.append(legistar_event_candidate)
                else:
                    alerts.append("structured_enrichment_legistar_unavailable")

            ckan_candidate = await self._fetch_san_jose_ckan_metadata(
                client=client,
                search_query=search_query,
                selected_url=selected_url,
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

    @staticmethod
    def _extract_legistar_matter_id(*, selected_url: str) -> int | None:
        raw = str(selected_url or "").strip()
        if not raw:
            return None
        parsed = urlparse(raw)
        query = parse_qs(parsed.query)
        candidate_ids: list[str] = []
        for key in ("ID", "Id", "id"):
            if key in query and query[key]:
                candidate_ids.extend(query[key])
        for value in candidate_ids:
            text = str(value).strip()
            nested_match = re.search(r"(?:matterid|key)=(\d+)", unquote(text), flags=re.IGNORECASE)
            if nested_match:
                return int(nested_match.group(1))
            path = parsed.path.lower()
            if text.isdigit() and any(
                signal in path
                for signal in ("gateway.aspx", "legislationdetail.aspx", "matter.aspx")
            ):
                return int(text)
        for pattern in (r"/Matters/(\d+)", r"\bMatterId=(\d+)"):
            match = re.search(pattern, raw, flags=re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def _is_economic_dataset(
        *,
        dataset: dict[str, Any],
        search_query: str,
        selected_url: str,
    ) -> bool:
        dataset_parts = [
            str(dataset.get("title") or ""),
            str(dataset.get("name") or ""),
            str(dataset.get("notes") or ""),
        ]
        tags = dataset.get("tags")
        if isinstance(tags, list):
            dataset_parts.extend(str(tag.get("name") or "") for tag in tags if isinstance(tag, dict))
        dataset_text = " ".join(dataset_parts).lower()

        economic_match = any(token in dataset_text for token in _ECONOMIC_DATASET_TOKENS)
        query_terms = {
            token
            for token in re.findall(r"[a-z0-9]+", f"{search_query} {selected_url}".lower())
            if len(token) >= 4
        }
        query_match = any(token in dataset_text for token in query_terms) if query_terms else False
        return economic_match or query_match

    @staticmethod
    def _resource_urls(dataset: dict[str, Any]) -> list[str]:
        resources = dataset.get("resources")
        if not isinstance(resources, list):
            return []
        urls: list[str] = []
        for item in resources:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if url.startswith("http://") or url.startswith("https://"):
                urls.append(url)
        return urls

    async def _fetch_legistar_matter_metadata(
        self,
        *,
        client: httpx.AsyncClient,
        selected_url: str,
        search_query: str,
    ) -> dict[str, Any] | None:
        matter_id = self._extract_legistar_matter_id(selected_url=selected_url)
        if not matter_id:
            return None

        matter_endpoint = f"https://webapi.legistar.com/v1/sanjose/Matters/{matter_id}"
        attachments_endpoint = f"https://webapi.legistar.com/v1/sanjose/Matters/{matter_id}/Attachments"

        try:
            matter_response = await client.get(matter_endpoint)
            matter_response.raise_for_status()
            matter_payload = matter_response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not isinstance(matter_payload, dict):
            return None

        attachments_payload: list[dict[str, Any]] = []
        try:
            attachments_response = await client.get(attachments_endpoint)
            attachments_response.raise_for_status()
            raw_attachments = attachments_response.json()
            if isinstance(raw_attachments, list):
                attachments_payload = [item for item in raw_attachments if isinstance(item, dict)]
        except (httpx.HTTPError, ValueError):
            attachments_payload = []

        matter_url = str(matter_payload.get("MatterInSiteURL") or selected_url or matter_endpoint)
        matter_title = str(matter_payload.get("MatterTitle") or "").strip()
        file_refs: list[str] = []
        for attachment in attachments_payload:
            file_url = str(attachment.get("MatterAttachmentHyperlink") or "").strip()
            if file_url.startswith("http://") or file_url.startswith("https://"):
                file_refs.append(file_url)

        structured_policy_facts = [
            {"field": "matter_attachment_count", "value": float(len(file_refs)), "unit": "count"},
            {
                "field": "matter_attachment_url_count",
                "value": float(len(file_refs)),
                "unit": "count",
            },
        ]

        return {
            "source_lane": "structured",
            "provider": "legistar_web_api",
            "source_family": "legistar_web_api",
            "access_method": "public_api_json",
            "jurisdiction": "san_jose_ca",
            "artifact_url": matter_url if matter_url.startswith("http") else matter_endpoint,
            "artifact_type": "matter_metadata",
            "source_tier": "tier_b",
            "retrieved_at": _utc_now_iso(),
            "query_text": search_query.strip() or "san jose matter metadata",
            "excerpt": (
                "Structured Legistar matter metadata fetched from San Jose Web API; "
                f"MatterTitle='{matter_title or 'unknown'}', attachments={len(file_refs)}."
            ),
            "structured_policy_facts": structured_policy_facts,
            "diagnostic_facts": [{"field": "matter_id", "value": float(matter_id), "unit": "count"}],
            "provider_run_id": str(matter_id),
            "linked_artifact_refs": file_refs,
            "reader_artifact_refs": [],
        }

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
            {"field": "event_attachment_hint_count", "value": 0.0, "unit": "count"},
        ]
        diagnostic_facts: list[dict[str, Any]] = [
            {"field": "event_id", "value": float(event_id), "unit": "count"},
        ]
        if isinstance(event_body_id, int):
            diagnostic_facts.append(
                {"field": "event_body_id", "value": float(event_body_id), "unit": "count"}
            )

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
            "diagnostic_facts": diagnostic_facts,
            "provider_run_id": str(event_id),
        }

    async def _fetch_san_jose_ckan_metadata(
        self,
        *,
        client: httpx.AsyncClient,
        search_query: str,
        selected_url: str,
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

        row_dicts = [row for row in rows if isinstance(row, dict)]
        relevant_rows = [
            row
            for row in row_dicts
            if self._is_economic_dataset(
                dataset=row,
                search_query=search_query,
                selected_url=selected_url,
            )
        ]
        with_resource_urls = [
            row
            for row in relevant_rows
            if self._resource_urls(row)
        ]
        if not with_resource_urls:
            return None

        top_dataset = with_resource_urls[0]
        top_dataset_urls = self._resource_urls(top_dataset)
        top_dataset_url = top_dataset_urls[0]
        resource_count = len(top_dataset_urls)
        facts: list[dict[str, Any]] = [
            {"field": "relevant_dataset_count", "value": float(len(relevant_rows)), "unit": "count"},
            {
                "field": "relevant_dataset_with_resource_url_count",
                "value": float(len(with_resource_urls)),
                "unit": "count",
            },
        ]
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
                f"query='{safe_query}', relevant_datasets={len(relevant_rows)}, "
                f"relevant_with_resource_urls={len(with_resource_urls)}."
            ),
            "structured_policy_facts": facts,
            "diagnostic_facts": [
                {"field": "dataset_match_count_raw", "value": float(total_count), "unit": "count"}
            ],
            "provider_run_id": str(total_count),
            "linked_artifact_refs": top_dataset_urls,
        }
