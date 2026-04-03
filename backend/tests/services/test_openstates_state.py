"""Tests for shared OpenStates state-discovery helpers."""

import pytest

from services.scraper.openstates_state import (
    OpenStatesBillDiscoveryClient,
    OpenStatesDiscoveryConfig,
    extract_preferred_source_url,
)


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummyClient:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def _freeze(self, value):
        if isinstance(value, list):
            return tuple(self._freeze(item) for item in value)
        if isinstance(value, tuple):
            return tuple(self._freeze(item) for item in value)
        if isinstance(value, dict):
            return tuple(sorted((k, self._freeze(v)) for k, v in value.items()))
        return value

    async def get(self, url, params=None, headers=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        key = (
            url,
            frozenset((k, self._freeze(v)) for k, v in (params or {}).items())
            if params
            else None,
        )
        if key in self._responses:
            return DummyResponse(self._responses[key])
        if url in self._responses:
            return DummyResponse(self._responses[url])
        raise AssertionError(f"Unexpected request: {url} params={params}")


def test_extract_preferred_source_url_prefers_official_domain():
    versions = [
        {
            "links": [{"url": "https://example.com/bill/1"}],
            "url": "https://mirror.example.net/1",
        },
        {
            "links": [{"url": "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260SB277"}]
        },
    ]
    sources = [{"url": "https://openstates.org/bill/ca/20252026/SB277"}]

    selected = extract_preferred_source_url(
        versions, sources, preferred_domains=("leginfo.legislature.ca.gov",)
    )

    assert "leginfo.legislature.ca.gov" in selected


def test_extract_preferred_source_url_falls_back_to_first_available():
    versions = [{"links": [{"url": "https://example.org/a"}]}]
    sources = []

    selected = extract_preferred_source_url(
        versions, sources, preferred_domains=("leginfo.legislature.ca.gov",)
    )

    assert selected == "https://example.org/a"


@pytest.mark.asyncio
async def test_list_bills_uses_discovery_config_contract():
    config = OpenStatesDiscoveryConfig(
        jurisdiction="ca",
        session="20252026",
        preferred_source_domains=("leginfo.legislature.ca.gov",),
    )
    responses = {
        "https://v3.openstates.org/bills": {"results": []},
    }
    client = DummyClient(responses)
    discovery = OpenStatesBillDiscoveryClient(api_key="test-api-key")

    bills = await discovery.list_bills(client=client, config=config)

    assert bills == []
    assert client.calls[0]["headers"] == {"X-API-KEY": "test-api-key"}
    assert client.calls[0]["params"]["jurisdiction"] == "ca"
    assert client.calls[0]["params"]["session"] == "20252026"
    assert client.calls[0]["params"]["include"] == [
        "sponsorships",
        "actions",
        "versions",
    ]


@pytest.mark.asyncio
async def test_discover_bill_rows_enriches_with_detail_and_source_url():
    config = OpenStatesDiscoveryConfig(
        jurisdiction="ca",
        session="20252026",
        preferred_source_domains=("leginfo.legislature.ca.gov",),
    )
    list_params = frozenset(
        {
            ("jurisdiction", "ca"),
            ("session", "20252026"),
            ("per_page", 20),
            ("sort", "updated_desc"),
            ("include", ("sponsorships", "actions", "versions")),
        }
    )
    detail_params = frozenset({("include", ("versions", "actions", "sources"))})
    responses = {
        ("https://v3.openstates.org/bills", list_params): {
            "results": [
                {
                    "id": "ocd-bill/1",
                    "identifier": "SB 277",
                    "title": "Housing bill",
                }
            ]
        },
        ("https://v3.openstates.org/bills/ocd-bill/1", detail_params): {
            "versions": [
                {
                    "id": "v1",
                    "note": "Introduced",
                    "links": [
                        {
                            "url": "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260SB277"
                        }
                    ],
                }
            ],
            "sources": [{"url": "https://openstates.org/bill/ca/20252026/SB277"}],
            "actions": [],
        },
    }
    client = DummyClient(responses)
    discovery = OpenStatesBillDiscoveryClient(api_key="test-api-key")

    rows = await discovery.discover_bill_rows(client=client, config=config)

    assert len(rows) == 1
    row = rows[0]
    assert row["bill_meta"]["identifier"] == "SB 277"
    assert row["versions"][0]["id"] == "v1"
    assert "leginfo.legislature.ca.gov" in row["source_url"]
