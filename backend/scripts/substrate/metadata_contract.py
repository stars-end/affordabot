"""Shared substrate metadata contract helpers for scheduled captures.

These helpers keep scheduled ingestion entry points aligned with the
framework-complete raw metadata contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from services.substrate_promotion import apply_promotion_decision
from services.substrate_promotion import evaluate_rules
from services.substrate_promotion import seed_capture_promotion_metadata

DEFAULT_SUBSTRATE_VERSION = "poc-v1"

SOURCE_TYPE_TO_DOCUMENT_TYPE = {
    "meetings": "meeting_detail",
    "code": "municipal_code",
    "legislation_api": "legislation",
    "legislation": "legislation",
    "web": "web_reference",
    "general": "web_reference",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_canonical_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    parts = urlsplit(text)
    cleaned = parts._replace(fragment="")
    return urlunsplit(cleaned)


def detect_content_class(content_type: str, canonical_url: str) -> str:
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    if ctype in {"text/html", "application/xhtml+xml", "text/markdown"}:
        return "html_text"
    if ctype == "text/plain":
        return "plain_text"
    if ctype in {"application/json", "application/ld+json"}:
        return "json_text"
    if ctype == "application/pdf":
        return "pdf_binary"

    if canonical_url.lower().endswith(".pdf"):
        return "pdf_binary"
    return "binary_blob"


def initial_ingestion_truth() -> dict[str, Any]:
    return {
        "stage": "raw_captured",
        "raw_captured": True,
        "blob_stored": False,
        "storage_uri_present": False,
        "parsed": False,
        "chunked": False,
        "embedded": False,
        "vector_upserted": False,
        "retrievable": False,
        "ingest_attempted": False,
        "last_updated_at": now_iso(),
    }


def build_substrate_raw_metadata(
    *,
    canonical_url: str,
    source_type: str,
    response_content_type: str,
    capture_method: str,
    title: str | None = None,
    trust_tier: str | None = None,
    document_type: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = normalize_canonical_url(canonical_url)
    effective_source_type = (source_type or "general").strip().lower()
    effective_document_type = (
        (document_type or "").strip().lower()
        or SOURCE_TYPE_TO_DOCUMENT_TYPE.get(effective_source_type, "web_reference")
    )
    content_class = detect_content_class(response_content_type, canonical)

    metadata = {
        "substrate_version": DEFAULT_SUBSTRATE_VERSION,
        "canonical_url": canonical,
        "document_type": effective_document_type,
        "source_type": effective_source_type,
        "content_class": content_class,
        "capture_method": capture_method,
        "response_content_type": response_content_type,
        "captured_at": now_iso(),
        "title": title or "",
        "ingestion_truth": initial_ingestion_truth(),
    }
    if trust_tier:
        metadata["trust_tier"] = trust_tier
    if extra_metadata:
        metadata.update(extra_metadata)

    seeded = seed_capture_promotion_metadata(
        metadata=metadata,
        canonical_url=canonical,
        trust_tier=metadata.get("trust_tier"),
    )
    return apply_promotion_decision(
        metadata=seeded,
        decision=evaluate_rules(seeded),
        canonical_url=canonical,
    )

