from pathlib import Path

import httpx
import pytest

from clients.zai_layout_parsing_client import ZaiLayoutParsingClient
from clients.zai_layout_parsing_client import ZaiLayoutParsingError


def test_parse_file_success(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "model": "GLM-OCR",
                "md_results": "# Parsed",
                "request_id": "req_123",
                "usage": {"total_tokens": 12},
                "data_info": {"num_pages": 2},
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, endpoint, headers, json):
            captured["endpoint"] = endpoint
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    client = ZaiLayoutParsingClient(api_key="test-key")
    result = client.parse_file("https://example.com/doc.pdf", start_page_id=2, end_page_id=4)

    assert result.markdown == "# Parsed"
    assert result.request_id == "req_123"
    assert captured["json"]["file"] == "https://example.com/doc.pdf"
    assert captured["json"]["start_page_id"] == 2
    assert captured["json"]["end_page_id"] == 4


def test_parse_file_raises_on_non_200(monkeypatch):
    class FakeResponse:
        status_code = 429
        text = "rate limited"

        @staticmethod
        def json():
            return {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, endpoint, headers, json):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    client = ZaiLayoutParsingClient(api_key="test-key")
    with pytest.raises(ZaiLayoutParsingError):
        client.parse_file("https://example.com/doc.pdf")


def test_parse_path_base64_encodes_file(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    captured: dict[str, object] = {}

    def fake_parse_file(self, file_ref: str, **kwargs):
        captured["file_ref"] = file_ref
        return object()

    monkeypatch.setattr(ZaiLayoutParsingClient, "parse_file", fake_parse_file)

    client = ZaiLayoutParsingClient(api_key="test-key")
    client.parse_path(pdf_path)

    assert isinstance(captured["file_ref"], str)
    assert captured["file_ref"]
