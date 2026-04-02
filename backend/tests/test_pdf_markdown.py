from pathlib import Path

import pytest

from services import pdf_markdown
from services.pdf_markdown import PDFMarkdownError


def test_extract_pdf_markdown_uses_preferred_extractor(monkeypatch):
    calls: list[str] = []

    def fake_markitdown(_: str | Path) -> str:
        calls.append("markitdown")
        return "# agenda"

    def fake_pymupdf(_: str | Path) -> str:
        calls.append("pymupdf4llm")
        return "should-not-run"

    monkeypatch.setitem(
        pdf_markdown.EXTRACTOR_IMPLS, pdf_markdown.DEFAULT_EXTRACTOR, fake_markitdown
    )
    monkeypatch.setitem(
        pdf_markdown.EXTRACTOR_IMPLS, pdf_markdown.PYMUPDF_EXTRACTOR, fake_pymupdf
    )

    result = pdf_markdown.extract_pdf_markdown("agenda.pdf")

    assert result.extractor == "markitdown"
    assert result.markdown == "# agenda"
    assert calls == ["markitdown"]


def test_extract_pdf_markdown_falls_back_when_preferred_missing(monkeypatch):
    def missing_markitdown(_: str | Path) -> str:
        raise ModuleNotFoundError("markitdown")

    def working_pymupdf(_: str | Path) -> str:
        return "## heading"

    monkeypatch.setitem(
        pdf_markdown.EXTRACTOR_IMPLS,
        pdf_markdown.DEFAULT_EXTRACTOR,
        missing_markitdown,
    )
    monkeypatch.setitem(
        pdf_markdown.EXTRACTOR_IMPLS,
        pdf_markdown.PYMUPDF_EXTRACTOR,
        working_pymupdf,
    )

    result = pdf_markdown.extract_pdf_markdown(
        "agenda.pdf",
        fallback=pdf_markdown.PYMUPDF_EXTRACTOR,
    )

    assert result.extractor == "pymupdf4llm"
    assert result.markdown.startswith("##")


def test_extract_pdf_markdown_raises_when_all_extractors_fail(monkeypatch):
    def empty_markitdown(_: str | Path) -> str:
        return ""

    def broken_pymupdf(_: str | Path) -> str:
        raise RuntimeError("boom")

    monkeypatch.setitem(
        pdf_markdown.EXTRACTOR_IMPLS,
        pdf_markdown.DEFAULT_EXTRACTOR,
        empty_markitdown,
    )
    monkeypatch.setitem(
        pdf_markdown.EXTRACTOR_IMPLS,
        pdf_markdown.PYMUPDF_EXTRACTOR,
        broken_pymupdf,
    )

    with pytest.raises(PDFMarkdownError) as exc:
        pdf_markdown.extract_pdf_markdown(
            "agenda.pdf",
            fallback=pdf_markdown.PYMUPDF_EXTRACTOR,
        )

    message = str(exc.value)
    assert "markitdown=empty_markdown_output" in message
    assert "pymupdf4llm=RuntimeError: boom" in message


def test_extract_pdf_markdown_rejects_unknown_extractor():
    with pytest.raises(ValueError):
        pdf_markdown.extract_pdf_markdown(
            "agenda.pdf",
            preferred="unknown-extractor",
        )


def test_extract_pdf_markdown_supports_glm_ocr_extractor(monkeypatch):
    def fake_glm_ocr(_: str | Path) -> str:
        return "# OCR output"

    monkeypatch.setitem(
        pdf_markdown.EXTRACTOR_IMPLS,
        pdf_markdown.GLM_OCR_EXTRACTOR,
        fake_glm_ocr,
    )

    result = pdf_markdown.extract_pdf_markdown(
        "agenda.pdf",
        preferred=pdf_markdown.GLM_OCR_EXTRACTOR,
        fallback=None,
    )

    assert result.extractor == "glm_ocr"
    assert result.markdown == "# OCR output"
