#!/usr/bin/env python3
"""Shared substrate metadata helpers for scheduled ingestion paths.

This module provides utilities to build framework-complete substrate metadata
for scheduled ingestion entry points, ensuring new rows always carry:
- canonical_url
- document_type
- content_class
- trust_tier
- promotion_state
- ingestion_truth

This aligns scheduled ingestion with the framework locked in bd-z8qp.4.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_content_class(content_type: str) -> str:
    """Detect content class from content-type header."""
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype in {"text/html", "application/xhtml+xml"}:
        return "html_text"
    if ctype in {"text/plain"}:
        return "plain_text"
    if ctype in {"application/json", "application/ld+json"}:
        return "json_text"
    if ctype == "application/pdf":
        return "pdf_binary"
    return "binary_blob"


def build_substrate_metadata(
    *,
    canonical_url: str,
    document_type: str,
    trust_tier: str,
    capture_method: str,
    source_type: str = "scheduled",
    source_name: str = "",
    content_class: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build complete substrate metadata for scheduled ingestion.

    This seeds all required fields and applies promotion rules immediately
    so the row is machine-checkable from the moment of capture.

    Args:
        canonical_url: The authoritative URL for this document
        document_type: Type of document (legislation, meeting, agenda, etc.)
        trust_tier: Trust classification (primary_government, official_partner, non_official)
        capture_method: How this was captured (legislation_api, scheduled_web_scrape, etc.)
        source_type: Type of source (scheduled, general, etc.)
        source_name: Human-readable source name
        content_class: Optional content class override (html_text, plain_text, etc.)
        extra: Additional metadata fields to include

    Returns:
        Complete substrate metadata dict with all required fields
    """
    from services.substrate_promotion import (
        apply_promotion_decision,
        evaluate_rules,
        seed_capture_promotion_metadata,
    )

    base_metadata = {
        "substrate_version": "scheduled-v1",
        "canonical_url": canonical_url,
        "document_type": document_type,
        "content_class": content_class or "html_text",
        "trust_tier": trust_tier,
        "capture_method": capture_method,
        "source_type": source_type,
        "source_name": source_name,
        "active": True,
        "scheduled": True,
        "ingestion_truth": {
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
            "last_updated_at": _utc_iso(),
        },
    }

    if extra:
        base_metadata.update(extra)

    seeded = seed_capture_promotion_metadata(
        metadata=base_metadata,
        canonical_url=canonical_url,
        trust_tier=trust_tier,
    )

    return apply_promotion_decision(
        metadata=seeded,
        decision=evaluate_rules(seeded),
        canonical_url=canonical_url,
    )


def build_raw_scrape_record(
    *,
    source_id: str,
    canonical_url: str,
    content: str,
    content_type: str,
    metadata: dict[str, Any],
    extra_data: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a complete raw_scrape record with substrate metadata.

    This is a convenience wrapper that handles content hashing and
    record construction for scheduled ingestion paths.

    Args:
        source_id: UUID of the source
        canonical_url: The authoritative URL for this document
        content: The raw content text
        content_type: MIME type of the content
        metadata: Pre-built substrate metadata dict
        extra_data: Additional data fields to include in the data payload

    Returns:
        Complete raw_scrape record dict ready for insertion
    """
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    data_payload = {"content": content}
    if extra_data:
        data_payload.update(extra_data)

    return {
        "source_id": source_id,
        "url": canonical_url,
        "content_hash": content_hash,
        "content_type": content_type,
        "data": data_payload,
        "metadata": metadata,
    }


def build_raw_scrape_record(
    *,
    source_id: str,
    canonical_url: str,
    content: str,
    content_type: str,
    metadata: Optional[dict[str, Any]] = None,
    extra_data: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a complete raw_scrape record with substrate metadata.

    This is a convenience wrapper that handles content hashing and
    record construction for scheduled ingestion paths.

    Args:
        source_id: The source ID to associate with this scrape
        canonical_url: The authoritative URL for this document
        content: The raw content text
        content_type: MIME type of the content
        metadata: Pre-built substrate metadata (from build_substrate_metadata)
        extra_data: Additional data fields to include in the data payload

    Returns:
        Complete raw_scrape record dict ready for insertion
    """
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    data_payload = {"content": content}
    if extra_data:
        data_payload.update(extra_data)

    return {
        "source_id": source_id,
        "url": canonical_url,
        "content_hash": content_hash,
        "content_type": content_type,
        "data": data_payload,
        "metadata": metadata or {},
    }


# Trust tier constants
TRUST_TIER_OFFICIAL_GOVERNMENT = "primary_government"
TRUST_TIER_OFFICIAL_PARTNER = "official_partner"
TRUST_TIER_NON_OFFICIAL = "non_official"

# Document type constants
DOCUMENT_TYPE_LEGISLATION = "legislation"
DOCUMENT_TYPE_MEETING = "meeting"
DOCUMENT_TYPE_AGENDA = "agenda"
DOCUMENT_TYPE_MINUTES = "minutes"
DOCUMENT_TYPE_MUNICIPAL_CODE = "municipal_code"
DOCUMENT_TYPE_WEB_REFERENCE = "web_reference"
DOCUMENT_TYPE_UNKNOWN = "unknown"

# Capture method constants
CAPTURE_METHOD_API = "legislation_api"
CAPTURE_METHOD_WEB_SCRAPE = "scheduled_web_scrape"
CAPTURE_METHOD_LLM_HARVEST = "llm_harvest"
CAPTURE_METHOD_SPIDER = "scrapy_spider"

# Content class constants
CONTENT_CLASS_HTML = "html_text"
CONTENT_CLASS_PLAIN = "plain_text"
CONTENT_CLASS_JSON = "json_text"
CONTENT_CLASS_PDF = "pdf_binary"
