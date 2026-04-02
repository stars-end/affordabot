#!/usr/bin/env python3
"""Quick grounded bakeoff for PDF extractors on hard municipal documents."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.pdf_markdown import SUPPORTED_EXTRACTORS
from services.pdf_markdown import PDFMarkdownError
from services.pdf_markdown import extract_pdf_markdown


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = REPO_ROOT / "backend/scripts/substrate/artifacts/bd-z8qp.4_glm_ocr_bakeoff.json"


@dataclass(frozen=True)
class BakeoffDoc:
    doc_id: str
    url: str
    description: str


DEFAULT_DOCS = [
    BakeoffDoc(
        doc_id="sj_city_council_agenda",
        url="https://legistar.granicus.com/sanjose/meetings/2026/4/7616_A_City_Council_26-04-07_Agenda.pdf",
        description="Agenda PDF with mixed layout and structured sections.",
    ),
    BakeoffDoc(
        doc_id="city_council_agenda_packet",
        url="https://swagit-attachments.granicus.com/uploads/video/agenda_file/191514/12192022Plus.pdf",
        description="Large municipal agenda packet PDF with appended attachments.",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extractor",
        action="append",
        dest="extractors",
        help="Extractor to evaluate (repeatable). Defaults to markitdown + glm_ocr.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Output artifact path (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def _selected_extractors(values: list[str] | None) -> list[str]:
    if values:
        return values
    selected = ["markitdown", "glm_ocr"]
    if "pymupdf4llm" in SUPPORTED_EXTRACTORS:
        selected.append("pymupdf4llm")
    return selected


def _doc_download(url: str) -> bytes:
    response = httpx.get(url, follow_redirects=True, timeout=120.0)
    response.raise_for_status()
    return response.content


def _evaluate_one(pdf_path: str, extractor: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = extract_pdf_markdown(pdf_path, preferred=extractor, fallback=None)
        duration = time.perf_counter() - started
        markdown = result.markdown
        return {
            "status": "success",
            "extractor": result.extractor,
            "duration_seconds": round(duration, 3),
            "markdown_chars": len(markdown),
            "markdown_lines": len(markdown.splitlines()),
            "preview": markdown[:300],
        }
    except PDFMarkdownError as exc:
        duration = time.perf_counter() - started
        return {
            "status": "error",
            "extractor": extractor,
            "duration_seconds": round(duration, 3),
            "error": str(exc),
        }


def main() -> int:
    args = parse_args()
    extractors = _selected_extractors(args.extractors)
    report: dict[str, Any] = {
        "extractors": extractors,
        "documents": [],
    }

    for doc in DEFAULT_DOCS:
        try:
            doc_bytes = _doc_download(doc.url)
        except Exception as exc:  # noqa: BLE001 - artifact should capture source failures
            report["documents"].append(
                {
                    **asdict(doc),
                    "status": "download_error",
                    "error": str(exc),
                }
            )
            continue

        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_file:
            tmp_file.write(doc_bytes)
            tmp_file.flush()
            evaluations = {
                extractor: _evaluate_one(tmp_file.name, extractor) for extractor in extractors
            }
            report["documents"].append(
                {
                    **asdict(doc),
                    "status": "downloaded",
                    "byte_length": len(doc_bytes),
                    "evaluations": evaluations,
                }
            )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Wrote bakeoff report to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
