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


def test_resolve_source_targets_matches_county_slug_alias():
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

    targets, failures = _resolve_source_targets(
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
    class FakeDB:
        async def get_or_create_jurisdiction(self, name, jur_type):
            assert name in {
                "City of Sunnyvale",
                "County of Santa Clara",
            }
            assert jur_type in {"city", "county"}
            return f"{name}:{jur_type}"

        async def upsert_source(self, data):
            assert data["source_method"] in {"scrape"}
            assert data["handler"] in {"sunnyvale_agendas", "legistar_calendar"}
            assert data["metadata"]["document_type"] in {"agenda", "meeting_detail"}
            return {"id": f"id-{data['name']}"}

    result = await manual_expansion_runner._ensure_pack_a_source_inventory(
        db=FakeDB(),
        jurisdictions=["sunnyvale", "santa-clara-county"],
        asset_classes=["agendas", "meeting_details"],
    )

    assert result["attempted"] >= 2
    assert result["upserted"] >= 2
    assert result["failures"] == []


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
