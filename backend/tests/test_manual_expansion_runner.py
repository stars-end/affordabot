import pytest

from scripts.substrate import manual_expansion_runner
from scripts.substrate.manual_expansion_runner import _execute_legislation_capture
from scripts.substrate.manual_expansion_runner import _resolve_source_targets
from scripts.substrate.manual_expansion_runner import _resolved_targets_payload


def test_resolve_source_targets_selects_supported_document_types_only():
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

    targets, failures = _resolve_source_targets(
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


def test_resolved_targets_payload_counts_source_and_legislation_targets():
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
    targets, _ = _resolve_source_targets(
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
