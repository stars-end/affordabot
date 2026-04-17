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
        "live_proven",
        "runtime_status",
    }
    for row in catalog:
        assert required.issubset(row.keys())
        assert row["jurisdiction_coverage"]
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
    enricher = StructuredSourceEnricher(tavily_api_key="")

    async def _fake_matter(
        *,
        client: Any,
        selected_url: str,
        search_query: str,
        selected_candidate_context: str,
    ) -> None:
        _ = (client, selected_url, search_query, selected_candidate_context)
        return None

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

    async def _fake_ckan(*, client: Any, search_query: str, selected_url: str) -> dict[str, Any]:
        _ = (client, search_query, selected_url)
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
            "structured_policy_facts": [{"field": "relevant_dataset_count", "value": 7.0, "unit": "count"}],
            "provider_run_id": "7",
        }

    monkeypatch.setattr(
        enricher,
        "_fetch_legistar_matter_metadata",
        _fake_matter,
    )
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
    catalog_by_family = {row["source_family"]: row for row in result.source_catalog}
    assert catalog_by_family["legistar_web_api"]["live_proven"] is True
    assert catalog_by_family["san_jose_open_data_ckan"]["live_proven"] is True


def test_extract_legistar_matter_id_from_gateway_url() -> None:
    matter_id = StructuredSourceEnricher._extract_legistar_matter_id(
        selected_url="https://sanjoseca.legistar.com/gateway.aspx?M=L&ID=14575&GUID=ABC",
    )
    assert matter_id == 14575


def test_extract_legistar_matter_id_from_nested_gateway_matter_url() -> None:
    matter_id = StructuredSourceEnricher._extract_legistar_matter_id(
        selected_url="https://sanjose.legistar.com/gateway.aspx?m=l&id=/matter.aspx?key=15360",
    )
    assert matter_id == 15360


def test_extract_legistar_matter_id_ignores_view_attachment_id() -> None:
    matter_id = StructuredSourceEnricher._extract_legistar_matter_id(
        selected_url="https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
    )
    assert matter_id is None


def test_classify_legistar_attachment_source_family() -> None:
    classify = StructuredSourceEnricher._classify_legistar_attachment_family
    assert classify(attachment_name="Resolution No. 80069", attachment_url="") == "resolution"
    assert classify(attachment_name="Ordinance 30710", attachment_url="") == "ordinance"
    assert classify(attachment_name="Staff Report - Housing Department", attachment_url="") == "staff_report"
    assert classify(attachment_name="Housing Department Memorandum", attachment_url="") == "memorandum"
    assert classify(attachment_name="Commercial Linkage Fee Study", attachment_url="") == "fee_study"
    assert classify(attachment_name="Nexus Study Appendix", attachment_url="") == "nexus_study"
    assert classify(attachment_name="Commercial Linkage Fee Schedule", attachment_url="") == "fee_schedule"
    assert classify(attachment_name="Commercial Linkage Feasibility Study", attachment_url="") == "feasibility_study"
    assert classify(attachment_name="City Council Minutes", attachment_url="") == "agenda/minutes"
    assert classify(attachment_name="Exhibit A", attachment_url="") == "exhibit"
    assert classify(attachment_name="Attachment", attachment_url="") == "unknown"


def test_legistar_event_ids_are_diagnostic_not_economic_parameters() -> None:
    enricher = StructuredSourceEnricher()

    class _Response:
        def __init__(self, payload: Any) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            return self._payload

    class _Client:
        async def get(self, endpoint: str) -> _Response:
            _ = endpoint
            return _Response(
                [
                    {
                        "EventId": 13001,
                        "EventBodyId": 44,
                        "EventDate": "2026-04-11",
                        "EventInSiteURL": "https://webapi.legistar.com/v1/sanjose/Events/13001",
                    }
                ]
            )

    candidate = asyncio.run(enricher._fetch_legistar_event_metadata(client=_Client()))
    assert candidate is not None
    fact_fields = {fact["field"] for fact in candidate["structured_policy_facts"]}
    assert "event_id" not in fact_fields
    assert "event_body_id" not in fact_fields
    diag_fields = {fact["field"] for fact in candidate.get("diagnostic_facts", [])}
    assert {"event_id", "event_body_id"}.issubset(diag_fields)


def test_legistar_matter_metadata_includes_provenance_and_non_id_facts() -> None:
    enricher = StructuredSourceEnricher()

    class _Response:
        def __init__(self, payload: Any) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            return self._payload

    class _Client:
        async def get(self, endpoint: str) -> _Response:
            if endpoint.endswith("/Matters/14575"):
                return _Response(
                    {
                        "MatterId": 14575,
                        "MatterTitle": "Commercial Linkage Fee Update",
                        "MatterInSiteURL": "https://sanjoseca.legistar.com/LegislationDetail.aspx?ID=14575",
                    }
                )
            if endpoint.endswith("/Matters/14575/Attachments"):
                return _Response(
                    [
                        {
                            "MatterAttachmentId": 123,
                            "MatterAttachmentName": "Resolution No. 80069",
                            "MatterAttachmentHyperlink": (
                                "https://sanjoseca.legistar.com/View.ashx?M=F&ID=9988776"
                            )
                        }
                    ]
                )
            raise AssertionError(f"unexpected endpoint: {endpoint}")

    candidate = asyncio.run(
        enricher._fetch_legistar_matter_metadata(
            client=_Client(),
            selected_url="https://sanjoseca.legistar.com/gateway.aspx?M=L&ID=14575",
            search_query="commercial linkage fee san jose",
            selected_candidate_context="",
        )
    )
    assert candidate is not None
    assert candidate["artifact_type"] == "matter_metadata"
    assert candidate["linked_artifact_refs"]
    fact_fields = {fact["field"] for fact in candidate["structured_policy_facts"]}
    assert "matter_id" not in fact_fields
    assert "matter_attachment_count" in fact_fields
    diag_fields = {fact["field"] for fact in candidate.get("diagnostic_facts", [])}
    assert "matter_id" in diag_fields
    assert candidate["related_attachment_refs"] == [
        {
            "attachment_id": "123",
            "title": "Resolution No. 80069",
            "url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=9988776",
            "source_family": "resolution",
        }
    ]
    assert candidate["lineage_metadata"]["related_attachment_refs"] == candidate["related_attachment_refs"]


def test_legistar_matter_metadata_attachment_probe_marks_ingested_and_not_ingested() -> None:
    enricher = StructuredSourceEnricher()

    class _Response:
        def __init__(
            self,
            payload: Any | None = None,
            *,
            headers: dict[str, str] | None = None,
            content: bytes | None = None,
        ) -> None:
            self._payload = payload
            self.headers = headers or {}
            if content is not None:
                self.content = content
            elif payload is not None:
                self.content = str(payload).encode("utf-8")
            else:
                self.content = b""

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            return self._payload

    class _Client:
        async def get(self, endpoint: str, params: dict[str, str] | None = None) -> _Response:
            _ = params
            if endpoint.endswith("/Matters/14575"):
                return _Response(
                    {
                        "MatterId": 14575,
                        "MatterTitle": "Commercial Linkage Fee Update",
                        "MatterInSiteURL": "https://sanjoseca.legistar.com/LegislationDetail.aspx?ID=14575",
                    }
                )
            if endpoint.endswith("/Matters/14575/Attachments"):
                return _Response(
                    [
                        {
                            "MatterAttachmentId": 123,
                            "MatterAttachmentName": "Resolution No. 80069",
                            "MatterAttachmentHyperlink": (
                                "https://sanjoseca.legistar.com/View.ashx?M=F&ID=9988776"
                            ),
                        },
                        {
                            "MatterAttachmentId": 124,
                            "MatterAttachmentName": "Housing Department Memorandum",
                            "MatterAttachmentHyperlink": (
                                "https://www.sanjoseca.gov/DocumentCenter/View/12345/memorandum.txt"
                            ),
                        },
                        {
                            "MatterAttachmentId": 125,
                            "MatterAttachmentName": "Public Comment Procedures",
                            "MatterAttachmentHyperlink": (
                                "https://www.sanjoseca.gov/DocumentCenter/View/99999/public-comment.pdf"
                            ),
                        },
                    ]
                )
            if endpoint == "https://sanjoseca.legistar.com/View.ashx?M=F&ID=9988776":
                return _Response(headers={"content-type": "application/pdf"}, content=b"%PDF-1.7 fake")
            if endpoint == "https://www.sanjoseca.gov/DocumentCenter/View/12345/memorandum.txt":
                return _Response(
                    headers={"content-type": "text/plain; charset=utf-8"},
                    content=(
                        b"Commercial Linkage Fee memorandum. Office projects pay $14.31 per square foot. "
                        b"Industrial projects pay $3.58 per square foot."
                    ),
                )
            raise AssertionError(f"unexpected endpoint: {endpoint}")

    candidate = asyncio.run(
        enricher._fetch_legistar_matter_metadata(
            client=_Client(),
            selected_url="https://sanjoseca.legistar.com/gateway.aspx?M=L&ID=14575",
            search_query="commercial linkage fee san jose",
            selected_candidate_context="",
        )
    )
    assert candidate is not None
    probes = candidate["attachment_content_probes"]
    assert len(probes) == 2
    by_family = {probe["source_family"]: probe for probe in probes}
    assert by_family["resolution"]["status"] == "binary_pdf_unparsed"
    assert by_family["resolution"]["read_status"] == "binary_unparsed"
    assert by_family["resolution"]["failure_class"] == "binary_pdf_unparsed"
    assert by_family["resolution"]["content_hash"]
    assert by_family["resolution"]["content_ingested"] is False
    assert by_family["memorandum"]["status"] == "ingested_excerpt"
    assert by_family["memorandum"]["read_status"] == "read_text"
    assert by_family["memorandum"]["failure_class"] is None
    assert by_family["memorandum"]["content_hash"]
    assert by_family["memorandum"]["content_ingested"] is True
    assert by_family["memorandum"]["economic_row_count"] >= 1
    assert by_family["memorandum"]["source_url"].startswith("https://www.sanjoseca.gov/")
    assert by_family["memorandum"]["source_title"] == "Housing Department Memorandum"
    assert candidate["lineage_metadata"]["attachment_content_ingested_count"] == 1


def test_legistar_matter_metadata_normalizes_relative_view_attachment_urls_for_probe_fetch() -> None:
    enricher = StructuredSourceEnricher()

    class _Response:
        def __init__(
            self,
            payload: Any | None = None,
            *,
            headers: dict[str, str] | None = None,
            content: bytes | None = None,
        ) -> None:
            self._payload = payload
            self.headers = headers or {}
            if content is not None:
                self.content = content
            elif payload is not None:
                self.content = str(payload).encode("utf-8")
            else:
                self.content = b""

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            return self._payload

    class _Client:
        async def get(self, endpoint: str, params: dict[str, str] | None = None) -> _Response:
            _ = params
            if endpoint.endswith("/Matters/14575"):
                return _Response(
                    {
                        "MatterId": 14575,
                        "MatterTitle": "Commercial Linkage Fee Update",
                        "MatterInSiteURL": "https://sanjoseca.legistar.com/LegislationDetail.aspx?ID=14575",
                    }
                )
            if endpoint.endswith("/Matters/14575/Attachments"):
                return _Response(
                    [
                        {
                            "MatterAttachmentId": 124,
                            "MatterAttachmentName": "Housing Department Memorandum",
                            "MatterAttachmentHyperlink": "/View.ashx?M=F&ID=9988777",
                        }
                    ]
                )
            if endpoint == "https://sanjoseca.legistar.com/View.ashx?M=F&ID=9988777":
                return _Response(
                    headers={"content-type": "text/plain; charset=utf-8"},
                    content=(
                        b"Commercial Linkage Fee memorandum for office projects is $14.31 per square foot."
                    ),
                )
            raise AssertionError(f"unexpected endpoint: {endpoint}")

    candidate = asyncio.run(
        enricher._fetch_legistar_matter_metadata(
            client=_Client(),
            selected_url="https://sanjoseca.legistar.com/gateway.aspx?M=L&ID=14575",
            search_query="commercial linkage fee san jose",
            selected_candidate_context="",
        )
    )
    assert candidate is not None
    assert candidate["related_attachment_refs"][0]["url"] == "https://sanjoseca.legistar.com/View.ashx?M=F&ID=9988777"
    probes = candidate["attachment_content_probes"]
    assert len(probes) == 1
    assert probes[0]["url"] == "https://sanjoseca.legistar.com/View.ashx?M=F&ID=9988777"
    assert probes[0]["content_ingested"] is True
    assert probes[0]["economic_row_count"] >= 1


def test_legistar_matter_metadata_resolves_view_attachment_via_context_search_fallback() -> None:
    enricher = StructuredSourceEnricher()

    class _Response:
        def __init__(self, payload: Any) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            return self._payload

    class _Client:
        async def get(self, endpoint: str, params: dict[str, str] | None = None) -> _Response:
            if endpoint.endswith("/Matters") and params:
                if "2020-09-01" in str(params.get("$filter") or ""):
                    return _Response(
                        [
                            {
                                "MatterId": 7526,
                                "MatterFile": "20-969",
                                "MatterTitle": "Council Policy Priority # 5: Commercial Linkage Impact Fee.",
                                "MatterAgendaDate": "2020-09-01T00:00:00",
                            },
                            {
                                "MatterId": 1111,
                                "MatterFile": "20-100",
                                "MatterTitle": "Tree Program Update",
                                "MatterAgendaDate": "2020-09-01T00:00:00",
                            },
                        ]
                    )
                return _Response([])
            if endpoint.endswith("/Matters/7526"):
                return _Response(
                    {
                        "MatterId": 7526,
                        "MatterFile": "20-969",
                        "MatterTitle": "Council Policy Priority # 5: Commercial Linkage Impact Fee.",
                    }
                )
            if endpoint.endswith("/Matters/7526/Attachments"):
                return _Response(
                    [
                        {
                            "MatterAttachmentId": 201,
                            "MatterAttachmentName": "Resolution No. 80069",
                            "MatterAttachmentHyperlink": (
                                "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120"
                            )
                        },
                        {
                            "MatterAttachmentId": 202,
                            "MatterAttachmentName": "Commercial Linkage Nexus Study",
                            "MatterAttachmentHyperlink": (
                                "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758132"
                            ),
                        }
                    ]
                )
            raise AssertionError(f"unexpected endpoint: {endpoint} params={params}")

    candidate = asyncio.run(
        enricher._fetch_legistar_matter_metadata(
            client=_Client(),
            selected_url="https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
            search_query="san jose commercial linkage impact fee",
            selected_candidate_context=(
                "Council Policy Priority # 5: Commercial Linkage Impact Fee. "
                "Matter 20-969 September 1, 2020"
            ),
        )
    )
    assert candidate is not None
    assert candidate["true_structured"] is True
    assert candidate["source_family"] == "legistar_web_api"
    assert candidate["artifact_url"].endswith("/Matters/7526")
    assert candidate["lineage_metadata"]["matter_id"] == "7526"
    fact_fields = {fact["field"] for fact in candidate["structured_policy_facts"]}
    assert "matter_attachment_count" in fact_fields
    assert "matter_id" not in fact_fields
    assert candidate["linked_artifact_refs"]
    attachment_refs = candidate["related_attachment_refs"]
    assert len(attachment_refs) == 2
    assert {item["source_family"] for item in attachment_refs} == {
        "resolution",
        "nexus_study",
    }
    assert all(item["attachment_id"] for item in attachment_refs)
    assert all(item["title"] for item in attachment_refs)


def test_legistar_matter_search_uses_policy_phrase_and_skips_deferred_item() -> None:
    enricher = StructuredSourceEnricher()

    class _Response:
        def __init__(self, payload: Any) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            return self._payload

    class _Client:
        async def get(self, endpoint: str, params: dict[str, str] | None = None) -> _Response:
            assert endpoint.endswith("/Matters")
            if params and "Commercial Linkage" in str(params.get("$filter") or ""):
                return _Response(
                    [
                        {
                            "MatterId": 7481,
                            "MatterFile": "20-927",
                            "MatterTitle": "Council Policy Priority # 5: Commercial Linkage Impact Fee. - DEFERRED",
                            "MatterAgendaDate": "2020-08-25T00:00:00",
                        },
                        {
                            "MatterId": 7526,
                            "MatterFile": "20-969",
                            "MatterTitle": "Council Policy Priority # 5: Commercial Linkage Impact Fee.",
                            "MatterAgendaDate": "2020-09-01T00:00:00",
                        },
                    ]
                )
            return _Response([])

    match = asyncio.run(
        enricher._search_legistar_matter_by_context(
            client=_Client(),
            selected_url="https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
            search_query="San Jose CA city council meeting minutes housing",
            selected_candidate_context=(
                "A RESOLUTION OF THE COUNCIL OF THE CITY OF SAN JOSE. "
                "Aug 21, 2020 Linkage Fee are set forth in the Ordinance; "
                "The Commercial Linkage Fees adopted in Chapter 5.11."
            ),
        )
    )
    assert match is not None
    assert match["MatterId"] == 7526


def test_structured_enricher_uses_matter_candidate_before_latest_event(monkeypatch: Any) -> None:
    enricher = StructuredSourceEnricher(tavily_api_key="")
    calls = {"event": 0}

    async def _fake_matter(
        *,
        client: Any,
        selected_url: str,
        search_query: str,
        selected_candidate_context: str,
    ) -> dict[str, Any]:
        _ = (client, selected_url, search_query, selected_candidate_context)
        return {
            "source_lane": "structured",
            "provider": "legistar_web_api",
            "source_family": "legistar_web_api",
            "access_method": "public_api_json",
            "jurisdiction": "san_jose_ca",
            "artifact_url": "https://sanjoseca.legistar.com/LegislationDetail.aspx?ID=7526",
            "artifact_type": "matter_metadata",
            "source_tier": "tier_b",
            "retrieved_at": "2026-04-16T00:00:00+00:00",
            "query_text": "commercial linkage impact fee",
            "excerpt": "Matter metadata",
            "structured_policy_facts": [{"field": "matter_attachment_count", "value": 1.0, "unit": "count"}],
            "provider_run_id": "7526",
            "true_structured": True,
        }

    async def _fake_legistar_event(*, client: Any) -> dict[str, Any]:
        _ = client
        calls["event"] += 1
        return {
            "source_lane": "structured",
            "provider": "legistar_web_api",
            "source_family": "legistar_web_api",
            "artifact_url": "https://webapi.legistar.com/v1/sanjose/Events/13001",
            "artifact_type": "meeting_metadata",
            "structured_policy_facts": [{"field": "event_attachment_hint_count", "value": 0.0, "unit": "count"}],
            "true_structured": True,
        }

    async def _fake_ckan(*, client: Any, search_query: str, selected_url: str) -> None:
        _ = (client, search_query, selected_url)
        return None

    monkeypatch.setattr(enricher, "_fetch_legistar_matter_metadata", _fake_matter)
    monkeypatch.setattr(enricher, "_fetch_legistar_event_metadata", _fake_legistar_event)
    monkeypatch.setattr(enricher, "_fetch_san_jose_ckan_metadata", _fake_ckan)

    result = asyncio.run(
        enricher.enrich(
            jurisdiction="San Jose CA",
            source_family="meeting_minutes",
            search_query="commercial linkage impact fee",
            selected_url="https://sanjose.legistar.com/View.ashx?M=F&ID=8758120",
            selected_candidate_context="Council Policy Priority # 5: Commercial Linkage Impact Fee",
        )
    )
    assert result.status == "integrated"
    assert calls["event"] == 0


def test_ckan_metadata_uses_only_economic_datasets_with_urls() -> None:
    enricher = StructuredSourceEnricher()

    class _Response:
        def __init__(self, payload: Any) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            return self._payload

    class _Client:
        async def get(self, endpoint: str) -> _Response:
            _ = endpoint
            return _Response(
                {
                    "success": True,
                    "result": {
                        "count": 4,
                        "results": [
                            {
                                "title": "City Trees Inventory",
                                "name": "trees",
                                "resources": [{"url": "https://data.sanjoseca.gov/tree.csv"}],
                            },
                            {
                                "title": "Building Permits by Month",
                                "name": "building-permits",
                                "resources": [{"url": "https://data.sanjoseca.gov/permits.csv"}],
                            },
                            {
                                "title": "Affordable Housing Production",
                                "name": "affordable-housing",
                                "resources": [],
                            },
                            {
                                "title": "Commercial Development Fees",
                                "name": "commercial-fees",
                                "resources": [{"url": "https://data.sanjoseca.gov/fees.csv"}],
                            },
                        ],
                    },
                }
            )

    candidate = asyncio.run(
        enricher._fetch_san_jose_ckan_metadata(
            client=_Client(),
            search_query="commercial linkage fee housing",
            selected_url="https://sanjoseca.legistar.com/gateway.aspx?M=L&ID=14575",
        )
    )
    assert candidate is not None
    assert candidate["artifact_url"] == "https://data.sanjoseca.gov/permits.csv"
    assert candidate["linked_artifact_refs"] == ["https://data.sanjoseca.gov/permits.csv"]
    facts = {item["field"]: item["value"] for item in candidate["structured_policy_facts"]}
    assert facts["relevant_dataset_count"] == 3.0
    assert facts["relevant_dataset_with_resource_url_count"] == 2.0
    assert facts["top_dataset_resource_count"] == 1.0


def test_tavily_secondary_fee_metadata_extracts_official_facts() -> None:
    enricher = StructuredSourceEnricher(tavily_api_key="test-key")

    class _Response:
        def __init__(self, payload: Any) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            return self._payload

    class _Client:
        async def post(self, endpoint: str, json: dict[str, Any]) -> _Response:
            assert endpoint == "https://api.tavily.com/search"
            assert json["max_results"] == 5
            return _Response(
                {
                    "query_id": "q-123",
                    "results": [
                        {
                            "url": (
                                "https://www.sanjoseca.gov/your-government/departments-offices/housing/"
                                "developers/inclusionary-housing-linkage-fees/commercial-linkage-fee"
                            ),
                            "title": "Commercial Linkage Fee",
                            "content": (
                                "Commercial Linkage Fee rates include office projects >=100,000 sq.ft. "
                                "$14.31/$17.89 per net square foot. Office <100,000 sq.ft. is $0 for "
                                "first 50,000 sq.ft. and $3.58 for remaining area."
                            ),
                        },
                        {
                            "url": "https://example.com/blog-fees",
                            "title": "Non official",
                            "content": "Rate is $99 per square foot.",
                        },
                    ],
                }
            )

    candidate = asyncio.run(
        enricher._fetch_tavily_secondary_fee_metadata(
            client=_Client(),
            source_family="policy_documents",
            search_query="san jose commercial linkage fee rates",
            selected_url="https://www.sanjoseca.gov",
        )
    )
    assert candidate is not None
    assert candidate["source_lane"] == "structured_secondary_source"
    assert candidate["provider"] == "tavily_search"
    assert "structured_secondary_source_tavily" in candidate["alerts"]
    assert candidate["secondary_search"] is True
    assert candidate["true_structured"] is False
    assert candidate["reconciliation_status"] == "secondary_search_derived_not_authoritative"
    facts = candidate["structured_policy_facts"]
    values = sorted({fact["value"] for fact in facts})
    assert values == [0.0, 3.58, 14.31, 17.89]
    assert all(fact["source_url"].startswith("https://www.sanjoseca.gov/") for fact in facts)


def test_tavily_secondary_fee_metadata_fail_closed_for_non_official_payload() -> None:
    enricher = StructuredSourceEnricher(tavily_api_key="test-key")

    class _Response:
        def __init__(self, payload: Any) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            return self._payload

    class _Client:
        async def post(self, endpoint: str, json: dict[str, Any]) -> _Response:
            _ = (endpoint, json)
            return _Response(
                {
                    "query_id": "q-456",
                    "results": [
                        {
                            "url": "https://siliconvalleyathome.org/resources/commercial-linkage-fees-2/",
                            "title": "SV@Home",
                            "content": "Commercial linkage fee policy context.",
                        }
                    ],
                }
            )

    candidate = asyncio.run(
        enricher._fetch_tavily_secondary_fee_metadata(
            client=_Client(),
            source_family="policy_documents",
            search_query="san jose commercial linkage fee rates",
            selected_url="https://www.sanjoseca.gov",
        )
    )
    assert candidate is None
