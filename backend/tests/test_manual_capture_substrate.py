from scripts.substrate.manual_capture import (
    DEFAULT_PROMOTION_STATE,
    DEFAULT_SUBSTRATE_VERSION,
    SubstrateDefaults,
    build_data_payload,
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
        canonical_url="https://example.com/code",
        content_class="html_text",
    )

    metadata = build_source_metadata(
        defaults=defaults,
        source_name="Example Code",
        source_type="code",
    )

    assert metadata["promotion_state"] == DEFAULT_PROMOTION_STATE
    assert metadata["substrate_version"] == DEFAULT_SUBSTRATE_VERSION
    assert metadata["document_type"] == "municipal_code"
    assert metadata["source_type"] == "code"
    assert metadata["content_class"] == "html_text"


def test_build_raw_metadata_keeps_content_class():
    defaults = SubstrateDefaults(
        document_type="agenda",
        trust_tier="primary_government",
        capture_method="manual_http",
        canonical_url="https://example.com/agenda.pdf",
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
