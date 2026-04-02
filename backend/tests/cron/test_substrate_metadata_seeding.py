import importlib
import json
import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock


sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../affordabot_scraper"))

if "asyncpg" not in sys.modules:
    sys.modules["asyncpg"] = types.SimpleNamespace(Pool=object, Record=dict)
if "psycopg2" not in sys.modules:
    stub_psycopg2 = types.ModuleType("psycopg2")
    stub_psycopg2.connect = MagicMock()
    sys.modules["psycopg2"] = stub_psycopg2
if "tenacity" not in sys.modules:
    stub_tenacity = types.ModuleType("tenacity")

    def _retry(*args, **kwargs):  # noqa: ARG001
        def _decorator(func):
            return func

        return _decorator

    stub_tenacity.retry = _retry
    stub_tenacity.stop_after_attempt = lambda *args, **kwargs: None
    stub_tenacity.wait_exponential = lambda *args, **kwargs: None
    sys.modules["tenacity"] = stub_tenacity

if "services.scraper.registry" not in sys.modules:
    stub_registry = types.ModuleType("services.scraper.registry")
    stub_registry.SCRAPERS = {}
    sys.modules["services.scraper.registry"] = stub_registry

from scripts.substrate.metadata_contract import build_substrate_raw_metadata
from scripts.cron.run_universal_harvester import UniversalHarvester
from affordabot_scraper.pipelines import RawScrapePipeline

run_daily_scrape = importlib.import_module("scripts.cron.run_daily_scrape")
ScrapeJob = run_daily_scrape.ScrapeJob


REQUIRED_METADATA_KEYS = {
    "canonical_url",
    "document_type",
    "content_class",
    "trust_tier",
    "trust_host_classification",
    "promotion_state",
    "promotion_method",
    "promotion_reason_category",
    "promotion_policy_version",
    "ingestion_truth",
}


def test_build_substrate_raw_metadata_contains_required_contract_fields():
    metadata = build_substrate_raw_metadata(
        canonical_url="https://sanjose.legistar.com/View.ashx?M=A#agenda",
        source_type="meetings",
        response_content_type="application/pdf",
        capture_method="cron_test",
        title="Agenda",
    )

    assert REQUIRED_METADATA_KEYS.issubset(metadata.keys())
    assert metadata["canonical_url"] == "https://sanjose.legistar.com/View.ashx?M=A"
    assert metadata["document_type"] == "meeting_detail"
    assert metadata["content_class"] == "pdf_binary"
    assert metadata["ingestion_truth"]["stage"] == "raw_captured"
    assert metadata["ingestion_truth"]["raw_captured"] is True


def test_daily_scrape_records_are_seeded_with_substrate_metadata_contract():
    job = ScrapeJob(db=MagicMock())
    generic_bill = SimpleNamespace(
        title="Budget Bill",
        status="Introduced",
        text="Creates a new fiscal allocation for city operations.",
        bill_number="SB-100",
    )

    generic_record = job._build_generic_scrape_record(
        generic_bill,
        source_id="source-1",
        slug="san-jose",
        source_url="https://webapi.legistar.com/v1/san-jose/matters",
    )
    assert REQUIRED_METADATA_KEYS.issubset(generic_record["metadata"].keys())
    assert generic_record["metadata"]["document_type"] == "legislation"
    assert generic_record["metadata"]["trust_tier"] == "official_partner"
    assert (
        generic_record["metadata"]["canonical_url"]
        == "https://webapi.legistar.com/v1/san-jose/matters"
    )

    raw_california_record = {
        "source_id": "source-2",
        "url": "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml",
        "content_hash": "hash-1",
        "content_type": "text/html",
        "data": {"content": "Official text"},
        "metadata": {"title": "AB 12"},
    }
    scraper = SimpleNamespace(
        to_raw_scrape_record=lambda bill, source_id: dict(raw_california_record)
    )
    california_record = job._build_california_scrape_record(
        SimpleNamespace(bill_number="AB 12"),
        source_id="source-2",
        scraper=scraper,
    )
    assert REQUIRED_METADATA_KEYS.issubset(california_record["metadata"].keys())
    assert california_record["metadata"]["trust_tier"] == "primary_government"
    assert california_record["metadata"]["document_type"] == "legislation"


def test_universal_harvester_records_are_seeded_with_substrate_metadata_contract():
    runner = UniversalHarvester()
    source = {
        "id": "src-1",
        "name": "City Portal",
        "type": "web",
        "metadata": json.dumps({"document_type": "staff_report"}),
    }
    record = runner._build_scrape_record(
        source=source,
        url="https://www.sanjoseca.gov/your-government/departments/city-manager",
        markdown_content="# Staff Report",
        task_id="task-1",
        content_hash="hash-2",
    )
    assert REQUIRED_METADATA_KEYS.issubset(record["metadata"].keys())
    assert record["metadata"]["document_type"] == "staff_report"
    assert record["metadata"]["source_type"] == "web"
    assert record["metadata"]["capture_method"] == "cron_universal_harvester"


def test_rag_pipeline_inserts_framework_complete_metadata():
    pipeline = RawScrapePipeline()
    cursor = MagicMock()
    pipeline.conn = MagicMock()
    pipeline.conn.cursor.return_value.__enter__.return_value = cursor

    spider = SimpleNamespace(
        source_id="source-3",
        name="sanjose_municode",
        start_urls=["https://library.municode.com/ca/san_jose/codes"],
        logger=MagicMock(),
    )
    item = {
        "url": "https://library.municode.com/ca/san_jose/codes/code_of_ordinances",
        "title": "San Jose Municipal Code",
        "content": "Title 24 zoning text",
        "scraped_at": "2026-04-02T00:00:00Z",
    }

    pipeline.process_item(item, spider)

    insert_call = cursor.execute.call_args_list[0]
    params = insert_call.args[1]
    metadata = json.loads(params[5])
    assert REQUIRED_METADATA_KEYS.issubset(metadata.keys())
    assert metadata["document_type"] == "municipal_code"
    assert metadata["capture_method"] == "cron_rag_spiders"
