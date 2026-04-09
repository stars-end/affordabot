"""Shared OpenStates discovery helpers for state legislation scrapers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence
from urllib.parse import urlsplit

import httpx

OPENSTATES_BASE_URL = "https://v3.openstates.org"
DEFAULT_DISCOVERY_INCLUDE = ("sponsorships", "actions", "versions")
DEFAULT_DETAIL_INCLUDE = ("versions", "actions", "sources")


@dataclass(frozen=True)
class OpenStatesDiscoveryConfig:
    """Configuration for OpenStates bill discovery."""

    jurisdiction: str
    session: str
    preferred_source_domains: tuple[str, ...]
    per_page: int = 20
    sort: str = "updated_desc"
    discovery_include: tuple[str, ...] = DEFAULT_DISCOVERY_INCLUDE
    detail_include: tuple[str, ...] = DEFAULT_DETAIL_INCLUDE


def _url_matches_domains(url: str, domains: Sequence[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    if not host:
        return False
    normalized = [domain.lower() for domain in domains]
    return any(host == domain or host.endswith(f".{domain}") for domain in normalized)


def extract_preferred_source_url(
    versions: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    preferred_domains: Sequence[str],
) -> str:
    """Pick the best source URL, preferring official domains."""
    for version in versions:
        for link in version.get("links", []):
            url = link.get("url", "")
            if _url_matches_domains(url, preferred_domains):
                return url
        url = version.get("url", "")
        if _url_matches_domains(url, preferred_domains):
            return url

    for source in sources:
        url = source.get("url", "")
        if _url_matches_domains(url, preferred_domains):
            return url

    if versions:
        for link in versions[0].get("links", []):
            url = link.get("url", "")
            if url:
                return url
        url = versions[0].get("url", "")
        if url:
            return url

    if sources:
        url = sources[0].get("url", "")
        if url:
            return url

    return ""


class OpenStatesBillDiscoveryClient:
    """Thin OpenStates API client for reusable state bill discovery."""

    def __init__(self, api_key: str, base_url: str = OPENSTATES_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-API-KEY": self.api_key}

    async def list_bills(
        self,
        *,
        client: httpx.AsyncClient,
        config: OpenStatesDiscoveryConfig,
    ) -> list[dict[str, Any]]:
        response = await client.get(
            f"{self.base_url}/bills",
            params={
                "jurisdiction": config.jurisdiction,
                "session": config.session,
                "per_page": config.per_page,
                "sort": config.sort,
                "include": list(config.discovery_include),
            },
            headers=self._headers,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    async def search_bills_by_identifier(
        self,
        *,
        client: httpx.AsyncClient,
        config: OpenStatesDiscoveryConfig,
        identifier: str,
    ) -> list[dict[str, Any]]:
        response = await client.get(
            f"{self.base_url}/bills",
            params={
                "jurisdiction": config.jurisdiction,
                "session": config.session,
                "identifier": identifier,
                "include": list(config.discovery_include),
            },
            headers=self._headers,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    async def get_bill_detail(
        self,
        *,
        client: httpx.AsyncClient,
        bill_id: str,
        include: Sequence[str] = DEFAULT_DETAIL_INCLUDE,
    ) -> dict[str, Any]:
        response = await client.get(
            f"{self.base_url}/bills/{bill_id}",
            params={"include": list(include)},
            headers=self._headers,
        )
        response.raise_for_status()
        return response.json()

    async def discover_bill_rows(
        self,
        *,
        client: httpx.AsyncClient,
        config: OpenStatesDiscoveryConfig,
    ) -> list[dict[str, Any]]:
        bill_meta = await self.list_bills(client=client, config=config)
        return await self._enrich_rows(client=client, bill_meta=bill_meta, config=config)

    async def discover_specific_bill_rows(
        self,
        *,
        client: httpx.AsyncClient,
        config: OpenStatesDiscoveryConfig,
        identifier: str,
    ) -> list[dict[str, Any]]:
        bill_meta = await self.search_bills_by_identifier(
            client=client,
            config=config,
            identifier=identifier,
        )
        return await self._enrich_rows(client=client, bill_meta=bill_meta, config=config)

    async def _enrich_rows(
        self,
        *,
        client: httpx.AsyncClient,
        bill_meta: list[dict[str, Any]],
        config: OpenStatesDiscoveryConfig,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in bill_meta:
            bill_id = item.get("id")
            if not bill_id:
                continue
            detail = await self.get_bill_detail(
                client=client,
                bill_id=bill_id,
                include=config.detail_include,
            )
            versions = detail.get("versions", [])
            sources = detail.get("sources", [])
            rows.append(
                {
                    "bill_meta": item,
                    "bill_detail": detail,
                    "versions": versions,
                    "sources": sources,
                    "source_url": extract_preferred_source_url(
                        versions,
                        sources,
                        config.preferred_source_domains,
                    ),
                    "version_info": versions[0] if versions else {},
                }
            )
        return rows

