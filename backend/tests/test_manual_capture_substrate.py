import pytest
import sys
import types
from types import SimpleNamespace

if "asyncpg" not in sys.modules:
    sys.modules["asyncpg"] = types.SimpleNamespace(Pool=object, Record=dict)
if "llm_common" not in sys.modules:
    llm_common = types.ModuleType("llm_common")
    retrieval = types.ModuleType("llm_common.retrieval")
    embeddings = types.ModuleType("llm_common.embeddings")
    setattr(retrieval, "RetrievalBackend", object)
    setattr(retrieval, "RetrievedChunk", object)
    setattr(embeddings, "EmbeddingService", object)
    setattr(llm_common, "retrieval", retrieval)
    setattr(llm_common, "embeddings", embeddings)
    setattr(llm_common, "WebSearchResult", object)
    sys.modules["llm_common"] = llm_common
    sys.modules["llm_common.retrieval"] = retrieval
    sys.modules["llm_common.embeddings"] = embeddings
if "minio" not in sys.modules:
    minio_module = types.ModuleType("minio")
    setattr(minio_module, "Minio", object)
    sys.modules["minio"] = minio_module
if "minio.error" not in sys.modules:
    minio_error_module = types.ModuleType("minio.error")
    setattr(minio_error_module, "S3Error", Exception)
    sys.modules["minio.error"] = minio_error_module

from scripts.substrate.manual_capture import (
    DEFAULT_SUBSTRATE_VERSION,
    EMBEDDING_DIMENSIONS,
    SubstrateDefaults,
    build_data_payload,
    build_embedding_service,
    build_raw_metadata,
    build_source_metadata,
    detect_content_class,
    normalize_canonical_url,
    parse_metadata_blob,
)


def test_normalize_canonical_url_strips_fragment_only():
    url = "https://example.com/path?a=1#section"
    assert normalize_canonical_url(url) == "https://example.com/path?a=1"


def test_detect_content_class_html_and_pdf():
    assert detect_content_class("text/html; charset=utf-8") == "html_text"
    assert detect_content_class("application/pdf") == "pdf_binary"


def test_detect_content_class_fallback_binary():
    assert detect_content_class("application/octet-stream") == "binary_blob"


def test_build_source_metadata_uses_contract_defaults():
    defaults = SubstrateDefaults(
        document_type="municipal_code",
        trust_tier="primary_government",
        capture_method="manual_http",
        canonical_url="https://www.sanjoseca.gov/code",
        content_class="html_text",
    )

    metadata = build_source_metadata(
        defaults=defaults,
        source_name="Example Code",
        source_type="code",
    )

    assert metadata["promotion_state"] == "durable_raw"
    assert metadata["substrate_version"] == DEFAULT_SUBSTRATE_VERSION
    assert metadata["document_type"] == "municipal_code"
    assert metadata["source_type"] == "code"
    assert metadata["content_class"] == "html_text"
    assert metadata["promotion_method"] == "rules"
    assert metadata["trust_host_classification"] == "official_government"


def test_build_raw_metadata_keeps_content_class():
    defaults = SubstrateDefaults(
        document_type="agenda",
        trust_tier="primary_government",
        capture_method="manual_http",
        canonical_url="https://sanjose.legistar.com/View.ashx?M=A",
        content_class="pdf_binary",
    )

    metadata = build_raw_metadata(
        defaults=defaults,
        source_name="Meetings",
        source_type="meetings",
        title="Example Agenda",
        response_content_type="application/pdf",
    )

    assert metadata["title"] == "Example Agenda"
    assert metadata["trust_tier"] == "primary_government"
    assert metadata["source_type"] == "meetings"
    assert metadata["response_content_type"] == "application/pdf"
    assert metadata["content_class"] == "pdf_binary"
    assert metadata["promotion_state"] in {"durable_raw", "promoted_substrate"}
    assert metadata["promotion_method"] == "rules"
    assert metadata["promotion_reason_category"]


def test_build_raw_metadata_contains_initial_ingestion_truth():
    defaults = SubstrateDefaults(
        document_type="agenda",
        trust_tier="primary_government",
        capture_method="manual_http",
        canonical_url="https://sanjose.legistar.com/View.ashx?M=A",
        content_class="pdf_binary",
    )

    metadata = build_raw_metadata(
        defaults=defaults,
        source_name="Meetings",
        source_type="meetings",
        title="Example Agenda",
        response_content_type="application/pdf",
    )

    truth = metadata.get("ingestion_truth", {})
    assert truth.get("stage") == "raw_captured"
    assert truth.get("raw_captured") is True
    assert truth.get("blob_stored") is False
    assert truth.get("retrievable") is False


def test_parse_metadata_blob_accepts_json_string():
    parsed = parse_metadata_blob('{"trust_tier":"primary_government","poc":true}')

    assert parsed["trust_tier"] == "primary_government"
    assert parsed["poc"] is True


def test_build_data_payload_binary_uses_external_storage_contract():
    payload, preview = build_data_payload(
        content_class="pdf_binary",
        content_bytes=b"\x00\x01PDF",
        title="Agenda",
        canonical_url="https://example.com/a.pdf",
    )

    assert "content" not in payload
    assert payload["content_storage"] == "external_blob"
    assert payload["byte_length"] == 5
    assert "content_base64" not in payload
    assert preview.startswith("[binary:pdf_binary]")


def test_build_data_payload_html_is_text():
    payload, preview = build_data_payload(
        content_class="html_text",
        content_bytes=b"<html><title>X</title><body>Hello</body></html>",
        title="X",
        canonical_url="https://example.com/x",
    )

    assert "content_base64" not in payload
    assert "content" in payload
    assert "Hello" in payload["content"]
    assert preview


@pytest.mark.asyncio
async def test_build_embedding_service_mock_uses_4096_contract(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    service = await build_embedding_service()
    query_embedding = await service.embed_query("agenda")
    doc_embeddings = await service.embed_documents(["one", "two"])

    assert len(query_embedding) == EMBEDDING_DIMENSIONS
    assert all(len(item) == EMBEDDING_DIMENSIONS for item in doc_embeddings)


def _manual_capture_args(*, ingest: bool) -> SimpleNamespace:
    return SimpleNamespace(
        url="https://example.gov/agenda",
        jurisdiction_name="Sample City",
        jurisdiction_type="city",
        source_name="Sample Agenda Feed",
        source_type="meetings",
        document_type="agenda",
        trust_tier="primary_government",
        capture_method="manual_http",
        title=None,
        ingest=ingest,
    )


@pytest.mark.asyncio
async def test_capture_document_reuses_existing_revision_when_content_hash_unchanged(
    monkeypatch,
):
    from scripts.substrate import manual_capture as mod

    html_body = b"<html><title>Agenda</title><body>Hello agenda</body></html>"

    class FakeResponse:
        content = html_body
        headers = {"content-type": "text/html; charset=utf-8"}

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            return FakeResponse()

    content_hash = __import__("hashlib").sha256(html_body).hexdigest()
    reused_row = {
        "id": "scrape-existing",
        "metadata": {"manual_run_id": "run-1"},
        "document_id": None,
        "storage_uri": None,
        "error_message": None,
        "processed": False,
        "content_hash": content_hash,
        "revision_number": 2,
    }

    class FakeDB:
        def __init__(self):
            self.create_called = False
            self.mark_seen_called = False

        async def get_or_create_jurisdiction(self, *args, **kwargs):
            return "jur-1"

        async def get_or_create_source(self, *args, **kwargs):
            return "source-1"

        async def get_source(self, *args, **kwargs):
            return {"metadata": {}}

        async def update_source(self, *args, **kwargs):
            return {}

        async def get_latest_raw_scrape_for_canonical_document(self, *args, **kwargs):
            return dict(reused_row)

        async def mark_raw_scrape_seen(self, scrape_id, *args, **kwargs):
            assert scrape_id == "scrape-existing"
            self.mark_seen_called = True
            return True

        async def create_raw_scrape(self, *args, **kwargs):
            self.create_called = True
            raise AssertionError("should not create new row for unchanged content")

        async def _fetchrow(self, query, scrape_id):
            assert "SELECT * FROM raw_scrapes WHERE id = $1" in query
            assert scrape_id == "scrape-existing"
            return dict(reused_row)

        async def _execute(self, *args, **kwargs):
            return "UPDATE 1"

        async def close(self):
            return None

    fake_db = FakeDB()

    class ForbiddenIngestionService:
        def __init__(self, *args, **kwargs):
            pass

        async def process_raw_scrape(self, *args, **kwargs):
            raise AssertionError("ingestion must be skipped for reused unchanged revisions")

    monkeypatch.setattr(mod.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(mod, "PostgresDB", lambda: fake_db)
    monkeypatch.setattr(mod, "IngestionService", ForbiddenIngestionService)

    result = await mod.capture_document(_manual_capture_args(ingest=True))

    assert result["scrape_id"] == "scrape-existing"
    assert result["reused_existing_revision"] is True
    assert result["ingest_attempted"] is False
    assert result["ingest_skipped_reason"] == "unchanged_content_revision_reused"
    assert fake_db.mark_seen_called is True
    assert fake_db.create_called is False


@pytest.mark.asyncio
async def test_capture_document_links_previous_revision_when_content_changed(monkeypatch):
    from scripts.substrate import manual_capture as mod

    html_body = b"<html><title>Agenda</title><body>Updated agenda text</body></html>"

    class FakeResponse:
        content = html_body
        headers = {"content-type": "text/html; charset=utf-8"}

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            return FakeResponse()

    class FakeDB:
        def __init__(self):
            self.created_record = None

        async def get_or_create_jurisdiction(self, *args, **kwargs):
            return "jur-1"

        async def get_or_create_source(self, *args, **kwargs):
            return "source-1"

        async def get_source(self, *args, **kwargs):
            return {"metadata": {}}

        async def update_source(self, *args, **kwargs):
            return {}

        async def get_latest_raw_scrape_for_canonical_document(self, *args, **kwargs):
            return {
                "id": "scrape-prev",
                "content_hash": "different-content-hash",
                "revision_number": 3,
            }

        async def mark_raw_scrape_seen(self, *args, **kwargs):
            raise AssertionError("mark_raw_scrape_seen should not run for changed content")

        async def create_raw_scrape(self, scrape_record):
            self.created_record = dict(scrape_record)
            return "scrape-new"

        async def _fetchrow(self, query, scrape_id):
            assert scrape_id == "scrape-new"
            return {
                "id": "scrape-new",
                "metadata": {},
                "document_id": None,
                "storage_uri": None,
                "error_message": None,
                "processed": False,
            }

        async def _execute(self, *args, **kwargs):
            return "UPDATE 1"

        async def close(self):
            return None

    fake_db = FakeDB()
    monkeypatch.setattr(mod.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(mod, "PostgresDB", lambda: fake_db)

    result = await mod.capture_document(_manual_capture_args(ingest=False))

    assert result["scrape_id"] == "scrape-new"
    assert result["reused_existing_revision"] is False
    assert fake_db.created_record is not None
    assert fake_db.created_record["previous_raw_scrape_id"] == "scrape-prev"
    assert fake_db.created_record["revision_number"] == 4
