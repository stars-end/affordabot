"""Canonical identity helpers for the v2 pipeline boundary contract."""

from __future__ import annotations

import re
from typing import Any, Mapping

from services.revision_identity import normalize_canonical_url


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "unknown"


def _normalize_text(value: Any, fallback: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    return text if text else fallback


def _normalize_date_hint(value: Any) -> str:
    if not value:
        return "unknown"
    text = str(value).strip()
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    return _normalize_text(text, "unknown")


def _normalize_document_type(metadata: Mapping[str, Any], data: Mapping[str, Any]) -> str:
    value = (
        metadata.get("document_type")
        or data.get("document_type")
        or metadata.get("manual_asset_class")
        or "unknown"
    )
    normalized = re.sub(r"\s+", "_", str(value).strip().lower())
    return normalized or "unknown"


def build_v2_canonical_document_key(
    *,
    jurisdiction_id: str,
    source_family: str,
    url: str | None,
    metadata: Mapping[str, Any] | None = None,
    data: Mapping[str, Any] | None = None,
) -> str:
    """Build v2 canonical document identity scoped by jurisdiction and source family."""
    jurisdiction_slug = slugify(jurisdiction_id)
    family = slugify(source_family).replace("-", "_")
    meta = dict(metadata or {})
    payload = dict(data or {})
    document_type = _normalize_document_type(meta, payload)

    canonical_url = normalize_canonical_url(
        meta.get("canonical_url") or payload.get("canonical_url") or url
    )
    if canonical_url and not canonical_url.startswith("unknown://"):
        return (
            f"v2|jurisdiction={jurisdiction_slug}|family={family}|doctype={document_type}"
            f"|url={canonical_url}"
        )

    title = _normalize_text(meta.get("title") or payload.get("title"), "untitled")
    date_hint = _normalize_date_hint(
        payload.get("published_date")
        or meta.get("published_date")
        or payload.get("meeting_date")
        or meta.get("meeting_date")
    )
    return (
        f"v2|jurisdiction={jurisdiction_slug}|family={family}|doctype={document_type}"
        f"|title={title}|date={date_hint}"
    )
