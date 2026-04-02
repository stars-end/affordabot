import pytest
import sys
import types

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
