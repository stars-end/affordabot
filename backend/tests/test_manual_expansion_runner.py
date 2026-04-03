import pytest
import sys
import types

if "asyncpg" not in sys.modules:
    sys.modules["asyncpg"] = types.SimpleNamespace(Pool=object, Record=object)
if "tenacity" not in sys.modules:
    sys.modules["tenacity"] = types.SimpleNamespace(
        retry=lambda *args, **kwargs: (lambda fn: fn),
        stop_after_attempt=lambda *args, **kwargs: None,
        wait_exponential=lambda *args, **kwargs: None,
    )
if "llm_common" not in sys.modules:
    llm_common_module = types.ModuleType("llm_common")
    llm_common_module.WebSearchResult = dict
    retrieval_module = types.ModuleType("llm_common.retrieval")
    embeddings_module = types.ModuleType("llm_common.embeddings")

    class RetrievalBackend:  # pragma: no cover - import stub
        pass

    class RetrievedChunk:  # pragma: no cover - import stub
        pass

    class EmbeddingService:  # pragma: no cover - import stub
        pass

    retrieval_module.RetrievalBackend = RetrievalBackend
    retrieval_module.RetrievedChunk = RetrievedChunk
    embeddings_module.EmbeddingService = EmbeddingService
    sys.modules["llm_common"] = llm_common_module
    sys.modules["llm_common.retrieval"] = retrieval_module
    sys.modules["llm_common.embeddings"] = embeddings_module
if "minio" not in sys.modules:
    minio_module = types.ModuleType("minio")

    class Minio:  # pragma: no cover - import stub
        pass

    minio_module.Minio = Minio
    minio_error_module = types.ModuleType("minio.error")

    class S3Error(Exception):  # pragma: no cover - import stub
        pass

    minio_error_module.S3Error = S3Error
    sys.modules["minio"] = minio_module
    sys.modules["minio.error"] = minio_error_module

from scripts.substrate import manual_expansion_runner
from scripts.substrate.manual_expansion_runner import _execute_legislation_capture
from scripts.substrate.manual_expansion_runner import _resolve_source_targets
from scripts.substrate.manual_expansion_runner import _resolved_targets_payload


@pytest.mark.asyncio
async def test_resolve_source_targets_selects_supported_document_types_only():
    source_rows = [
        {
            "id": "1",
            "name": "San Jose Agenda",
            "type": "meetings",
            "url": "https://example.gov/agenda.pdf",
            "metadata": {"document_type": "agenda"},
            "jurisdiction_name": "San Jose",
            "jurisdiction_type": "city",
        },
        {
            "id": "2",
            "name": "San Jose Minutes",
            "type": "meetings",
            "url": "https://example.gov/minutes.pdf",
            "metadata": {"document_type": "minutes"},
            "jurisdiction_name": "San Jose",
            "jurisdiction_type": "city",
        },
        {
            "id": "3",
            "name": "Unknown Root",
            "type": "meetings",
            "url": "unknown://root",
            "metadata": {"document_type": "agenda"},
            "jurisdiction_name": "San Jose",
            "jurisdiction_type": "city",
        },
    ]

    targets, failures = await _resolve_source_targets(
        source_rows=source_rows,
        jurisdictions=["san-jose"],
        asset_classes=["agendas", "meeting_details"],
        max_documents_per_source=5,
    )

    assert len(targets) == 1
    assert targets[0].asset_class == "agendas"
    assert targets[0].document_type == "agenda"
    assert failures == [
        {
            "jurisdiction": "san-jose",
            "asset_class": "meeting_details",
            "reason": "no_matching_sources",
        }
    ]


@pytest.mark.asyncio
async def test_resolve_source_targets_matches_county_slug_alias():
    source_rows = [
        {
            "id": "county-1",
            "name": "Santa Clara County Agendas",
            "type": "meetings",
            "url": "https://sccgov.legistar.com/Calendar.aspx",
            "metadata": {"document_type": "agenda"},
            "jurisdiction_name": "County of Santa Clara",
            "jurisdiction_type": "county",
        }
    ]

    targets, failures = await _resolve_source_targets(
        source_rows=source_rows,
        jurisdictions=["santa-clara-county"],
        asset_classes=["agendas"],
        max_documents_per_source=5,
    )

    assert len(targets) == 1
    assert targets[0].jurisdiction_slug == "santa-clara-county"
    assert failures == []


@pytest.mark.asyncio
async def test_ensure_pack_a_source_inventory_upserts_for_requested_assets():
    captured = []

    class FakeDB:
        async def get_or_create_jurisdiction(self, name, jur_type):
            assert name in {
                "City of Sunnyvale",
                "County of Santa Clara",
                "City of San Jose",
                "City of Saratoga",
            }
            assert jur_type in {"city", "county"}
            return f"{name}:{jur_type}"

        async def upsert_source(self, data):
            assert data["source_method"] in {"scrape"}
            captured.append(data)
            assert data["handler"] in {
                "sunnyvale_agendas",
                "legistar_calendar",
                "agenda_center",
            }
            assert data["metadata"]["document_type"] in {
                "agenda_packet",
                "attachment",
                "staff_report",
            }
            return {"id": f"id-{data['name']}"}

    result = await manual_expansion_runner._ensure_pack_a_source_inventory(
        db=FakeDB(),
        jurisdictions=["san-jose", "santa-clara-county", "saratoga", "sunnyvale"],
        asset_classes=["agenda_packets", "attachments", "staff_reports"],
    )

    assert result["attempted"] == 11
    assert result["upserted"] == 11
    assert result["failures"] == []

    sunnyvale_doc_types = {
        row["metadata"]["document_type"]
        for row in captured
        if row["jurisdiction_id"] == "City of Sunnyvale:city"
    }
    assert sunnyvale_doc_types == {"agenda_packet", "attachment"}


@pytest.mark.asyncio
async def test_ensure_pack_b_source_inventory_upserts_supported_handlers_only():
    captured = []

    class FakeDB:
        async def get_or_create_jurisdiction(self, name, jur_type):
            assert name in {
                "City of Cupertino",
                "City of Mountain View",
                "County of San Mateo",
                "San Francisco City County",
                "City of Campbell",
            }
            assert jur_type in {"city", "county"}
            return f"{name}:{jur_type}"

        async def upsert_source(self, data):
            captured.append(data)
            assert data["handler"] in {"legistar_calendar", "agenda_center"}
            assert data["metadata"]["provider_family"] == "pack_b_default"
            assert data["metadata"]["document_type"] in {
                "meeting_detail",
                "agenda",
                "minutes",
                "agenda_packet",
                "attachment",
                "staff_report",
            }
            return {"id": f"id-{data['name']}"}

    result = await manual_expansion_runner._ensure_pack_a_source_inventory(
        db=FakeDB(),
        jurisdictions=[
            "cupertino",
            "mountain-view",
            "san-mateo-county",
            "san-francisco-city-county",
            "campbell",
        ],
        asset_classes=[
            "meeting_details",
            "agendas",
            "minutes",
            "agenda_packets",
            "attachments",
            "staff_reports",
        ],
    )

    assert result["attempted"] == 29
    assert result["upserted"] == 29
    assert result["failures"] == []
    seeded_slugs = {
        row["metadata"]["title"].split(" ")[0].lower()
        for row in captured
    }
    assert "cupertino" in seeded_slugs


@pytest.mark.asyncio
async def test_resolved_targets_payload_counts_source_and_legislation_targets():
    source_rows = [
        {
            "id": "1",
            "name": "San Jose Agenda",
            "type": "meetings",
            "url": "https://example.gov/agenda.pdf",
            "metadata": {"document_type": "agenda"},
            "jurisdiction_name": "San Jose",
            "jurisdiction_type": "city",
        }
    ]
    targets, _ = await _resolve_source_targets(
        source_rows=source_rows,
        jurisdictions=["san-jose"],
        asset_classes=["agendas"],
        max_documents_per_source=5,
    )

    payload = _resolved_targets_payload(
        source_targets=targets,
        legislation_slugs=["california"],
        max_documents_per_source=5,
    )

    assert payload["count"] == 2
    assert payload["by_jurisdiction"]["san-jose"] == 1
    assert payload["by_jurisdiction"]["california"] == 1
    assert payload["by_asset_class"]["agendas"] == 1
    assert payload["by_asset_class"]["legislation"] == 1
    assert payload["potential_target_documents"] == 10


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "jurisdiction_slug", "asset_class", "expected_fragment", "html_text"),
    [
        (
            "legistar_calendar",
            "san-jose",
            "agendas",
            "View.ashx?M=A&ID=100",
            """
            <html>
              <body>
                <a href="/MeetingDetail.aspx?ID=100&GUID=abc">Meeting Details</a>
                <a href="/View.ashx?M=A&ID=100"><img alt="Agenda"></a>
              </body>
            </html>
            """,
        ),
        (
            "agenda_center",
            "saratoga",
            "agendas",
            "/DocumentCenter/View/1234/City-Council-Agenda",
            """
            <html>
              <body>
                <a href="/DocumentCenter/View/1234/City-Council-Agenda">Download Agenda PDF</a>
                <a href="/DocumentCenter/View/1235/City-Council-Minutes">Download Minutes PDF</a>
              </body>
            </html>
            """,
        ),
        (
            "sunnyvale_agendas",
            "sunnyvale",
            "agendas",
            "View.ashx?M=A&ID=200",
            """
            <html>
              <body>
                <a href="/View.ashx?M=A&ID=200">Agenda</a>
                <a href="/View.ashx?M=M&ID=200">Minutes</a>
              </body>
            </html>
            """,
        ),
        (
            "legistar_calendar",
            "san-jose",
            "agenda_packets",
            "View.ashx?M=PA&ID=100",
            """
            <html>
              <body>
                <a href="/View.ashx?M=PA&ID=100">Agenda Packet</a>
              </body>
            </html>
            """,
        ),
        (
            "legistar_calendar",
            "san-jose",
            "attachments",
            "Attachment-100.pdf",
            """
            <html>
              <body>
                <a href="/attachments/Attachment-100.pdf">Attachment</a>
              </body>
            </html>
            """,
        ),
        (
            "legistar_calendar",
            "santa-clara-county",
            "staff_reports",
            "staff-report-100.pdf",
            """
            <html>
              <body>
                <a href="/docs/staff-report-100.pdf">Staff Report</a>
              </body>
            </html>
            """,
        ),
        (
            "agenda_center",
            "saratoga",
            "agenda_packets",
            "/DocumentCenter/View/6000/City-Council-Agenda-Packet",
            """
            <html>
              <body>
                <a href="/DocumentCenter/View/6000/City-Council-Agenda-Packet">Agenda Packet</a>
              </body>
            </html>
            """,
        ),
        (
            "agenda_center",
            "saratoga",
            "attachments",
            "/DocumentCenter/View/6001/City-Council-Attachment",
            """
            <html>
              <body>
                <a href="/DocumentCenter/View/6001/City-Council-Attachment">Attachment</a>
              </body>
            </html>
            """,
        ),
        (
            "agenda_center",
            "saratoga",
            "staff_reports",
            "/DocumentCenter/View/6002/City-Council-Staff-Report",
            """
            <html>
              <body>
                <a href="/DocumentCenter/View/6002/City-Council-Staff-Report">Staff Report</a>
              </body>
            </html>
            """,
        ),
    ],
)
async def test_resolve_source_targets_expands_handler_roots_to_document_targets(
    monkeypatch,
    handler,
    jurisdiction_slug,
    asset_class,
    expected_fragment,
    html_text,
):
    class FakeResponse:
        def __init__(self, text):
            self.status_code = 200
            self.text = text

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, timeout=None):
            return FakeResponse(html_text)

    monkeypatch.setattr(manual_expansion_runner.httpx, "AsyncClient", FakeAsyncClient)

    source_rows = [
        {
            "id": "source-1",
            "name": "Root calendar/index source",
            "type": "meetings",
            "url": (
                "https://sunnyvaleca.legistar.com/Calendar.aspx"
                if handler == "sunnyvale_agendas"
                else "https://example.gov/root"
            ),
            "handler": handler,
            "metadata": {"document_type": "agenda", "trust_tier": "official_partner"},
            "jurisdiction_name": jurisdiction_slug.replace("-", " ").title(),
            "jurisdiction_type": "city",
        }
    ]

    targets, failures = await _resolve_source_targets(
        source_rows=source_rows,
        jurisdictions=[jurisdiction_slug],
        asset_classes=[asset_class],
        max_documents_per_source=5,
    )

    assert failures == []
    assert len(targets) == 1
    assert expected_fragment in targets[0].url
    assert targets[0].url != source_rows[0]["url"]


def test_pack_a_defaults_do_not_add_fake_sunnyvale_staff_reports_lane():
    sunnyvale_staff_report_rows = [
        seed
        for seed in manual_expansion_runner.PACK_A_SOURCE_DEFAULTS
        if seed.jurisdiction_slug == "sunnyvale"
        and seed.asset_class == "staff_reports"
    ]
    assert sunnyvale_staff_report_rows == []


def test_pack_b_defaults_defer_non_matching_jurisdictions():
    deferred = {"palo-alto", "milpitas", "alameda-county"}
    present_pack_b = {
        seed.jurisdiction_slug for seed in manual_expansion_runner.PACK_B_SOURCE_DEFAULTS
    }
    assert deferred.isdisjoint(present_pack_b)


@pytest.mark.asyncio
async def test_resolve_source_targets_sunnyvale_filters_non_legistar_agenda_links(
    monkeypatch,
):
    class FakeResponse:
        def __init__(self, text):
            self.status_code = 200
            self.text = text

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, timeout=None):
            return FakeResponse(
                """
                <html>
                  <body>
                    <a href="https://www.sunnyvale.ca.gov/your-government/governance/city-council/pending-council-agendas">Agenda</a>
                  </body>
                </html>
                """
            )

    monkeypatch.setattr(manual_expansion_runner.httpx, "AsyncClient", FakeAsyncClient)

    source_rows = [
        {
            "id": "sunnyvale-agenda",
            "name": "Sunnyvale Agendas",
            "type": "meetings",
            "url": "https://sunnyvaleca.legistar.com/Calendar.aspx",
            "handler": "sunnyvale_agendas",
            "metadata": {"document_type": "agenda", "trust_tier": "official_partner"},
            "jurisdiction_name": "City of Sunnyvale",
            "jurisdiction_type": "city",
        }
    ]

    targets, failures = await _resolve_source_targets(
        source_rows=source_rows,
        jurisdictions=["sunnyvale"],
        asset_classes=["agendas"],
        max_documents_per_source=5,
    )

    assert failures == []
    assert len(targets) == 1
    assert targets[0].url == "https://sunnyvaleca.legistar.com/Calendar.aspx"


@pytest.mark.asyncio
async def test_resolve_source_targets_keeps_municode_root_for_code_lane(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, timeout=None):  # pragma: no cover - should not be used
            raise AssertionError("municode should not fetch during root resolution")

    monkeypatch.setattr(manual_expansion_runner.httpx, "AsyncClient", FakeAsyncClient)

    source_rows = [
        {
            "id": "municode-1",
            "name": "San Jose Municipal Code",
            "type": "code",
            "url": "https://library.municode.com/ca/san_jose/codes/code_of_ordinances",
            "handler": "municode",
            "metadata": {
                "document_type": "municipal_code",
                "trust_tier": "official_partner",
            },
            "jurisdiction_name": "City of San Jose",
            "jurisdiction_type": "city",
        }
    ]

    targets, failures = await _resolve_source_targets(
        source_rows=source_rows,
        jurisdictions=["san-jose"],
        asset_classes=["municipal_code"],
        max_documents_per_source=5,
    )

    assert failures == []
    assert len(targets) == 1
    assert targets[0].document_type == "municipal_code"
    assert targets[0].url == source_rows[0]["url"]


@pytest.mark.asyncio
async def test_execute_legislation_capture_records_scrape_failures(monkeypatch):
    class FailingScraper:
        jurisdiction_name = "State of California"

        async def scrape(self):
            raise RuntimeError("openstates 422")

    monkeypatch.setitem(
        manual_expansion_runner.SCRAPERS,
        "california",
        (FailingScraper, "state"),
    )

    created, failures = await _execute_legislation_capture(
        db=None,
        job=None,
        slug="california",
        run_id="run-1",
        run_label="label",
        max_documents_per_source=2,
        ingest=False,
        ingestion_service=None,
    )

    assert created == 0
    assert failures == [
        {
            "jurisdiction": "california",
            "asset_class": "legislation",
            "reason": "scrape_failed",
            "detail": "openstates 422",
        }
    ]
