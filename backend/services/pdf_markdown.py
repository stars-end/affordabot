"""PDF to Markdown extraction boundary for substrate ingestion.

This module keeps library usage optional and swappable:
- default extractor: ``markitdown`` (permissive MIT license, lighter rollout risk)
- fallback extractor: ``pymupdf4llm`` (stronger structural markdown, AGPL caveat)
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Callable


DEFAULT_EXTRACTOR = "markitdown"
FALLBACK_EXTRACTOR = "pymupdf4llm"
SUPPORTED_EXTRACTORS = (DEFAULT_EXTRACTOR, FALLBACK_EXTRACTOR)


class PDFMarkdownError(RuntimeError):
    """Raised when all configured PDF-to-markdown extractors fail."""


@dataclass(frozen=True)
class PDFMarkdownResult:
    """Successful markdown extraction metadata."""

    extractor: str
    markdown: str


def _extract_with_markitdown(pdf_path: str | Path) -> str:
    markitdown_module = import_module("markitdown")
    converter = markitdown_module.MarkItDown(enable_plugins=False)
    converted = converter.convert(str(pdf_path))
    return (getattr(converted, "text_content", "") or "").strip()


def _extract_with_pymupdf4llm(pdf_path: str | Path) -> str:
    pymupdf4llm = import_module("pymupdf4llm")
    return (pymupdf4llm.to_markdown(str(pdf_path)) or "").strip()


EXTRACTOR_IMPLS: dict[str, Callable[[str | Path], str]] = {
    DEFAULT_EXTRACTOR: _extract_with_markitdown,
    FALLBACK_EXTRACTOR: _extract_with_pymupdf4llm,
}


def _extractor_order(preferred: str, fallback: str | None) -> list[str]:
    if preferred not in SUPPORTED_EXTRACTORS:
        raise ValueError(f"Unsupported preferred extractor: {preferred}")
    if fallback is not None and fallback not in SUPPORTED_EXTRACTORS:
        raise ValueError(f"Unsupported fallback extractor: {fallback}")
    order = [preferred]
    if fallback and fallback != preferred:
        order.append(fallback)
    return order


def extract_pdf_markdown(
    pdf_path: str | Path,
    *,
    preferred: str = DEFAULT_EXTRACTOR,
    fallback: str | None = FALLBACK_EXTRACTOR,
) -> PDFMarkdownResult:
    """Extract markdown from a PDF using preferred -> fallback strategy."""

    errors: dict[str, str] = {}

    for extractor in _extractor_order(preferred=preferred, fallback=fallback):
        impl = EXTRACTOR_IMPLS[extractor]
        try:
            markdown = impl(pdf_path)
        except ModuleNotFoundError as exc:
            errors[extractor] = f"dependency_missing: {exc.name}"
            continue
        except Exception as exc:  # pragma: no cover
            errors[extractor] = f"{type(exc).__name__}: {exc}"
            continue

        if markdown:
            return PDFMarkdownResult(extractor=extractor, markdown=markdown)

        errors[extractor] = "empty_markdown_output"

    details = "; ".join(f"{name}={reason}" for name, reason in errors.items())
    raise PDFMarkdownError(f"All PDF extractors failed for {pdf_path}: {details}")
