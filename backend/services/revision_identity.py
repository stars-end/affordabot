"""Revision identity helpers for raw substrate captures.

Phase 1 intentionally focuses on deterministic identity and revision defaults.
Duplicate suppression and revision chaining behaviors are implemented later.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}


def _coerce_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _normalize_document_type(metadata: dict[str, Any], data: dict[str, Any]) -> str:
    value = (
        metadata.get("document_type")
        or data.get("document_type")
        or metadata.get("manual_asset_class")
        or "unknown"
    )
    return re.sub(r"\s+", "_", str(value).strip().lower()) or "unknown"


def _normalize_text(value: Any, fallback: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    return text or fallback


def _normalize_date_hint(value: Any) -> str:
    if not value:
        return "unknown"
    text = str(value).strip()
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    return _normalize_text(text, "unknown")


def normalize_canonical_url(url: str | None) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""

    parts = urlsplit(raw)
    scheme = (parts.scheme or "").lower()
    netloc = (parts.netloc or "").lower()
    path = re.sub(r"/+", "/", parts.path or "/")

    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    filtered_pairs = []
    for key, value in query_pairs:
        lower_key = key.lower()
        if lower_key.startswith("utm_") or lower_key in TRACKING_QUERY_KEYS:
            continue
        filtered_pairs.append((key, value))

    query = urlencode(sorted(filtered_pairs), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def build_canonical_document_key(
    *,
    source_id: str,
    url: str | None,
    metadata: Mapping[str, Any] | None = None,
    data: Mapping[str, Any] | None = None,
) -> str:
    """Build a deterministic canonical key for a logical document identity."""
    meta = dict(metadata or {})
    payload = dict(data or {})

    source = str(source_id).strip()
    if not source:
        raise ValueError("source_id is required for canonical document identity")

    document_type = _normalize_document_type(meta, payload)

    canonical_url = normalize_canonical_url(
        meta.get("canonical_url") or payload.get("canonical_url") or url
    )
    if canonical_url and not canonical_url.startswith("unknown://"):
        return f"v1|source={source}|doctype={document_type}|url={canonical_url}"

    title = _normalize_text(meta.get("title") or payload.get("title"), "untitled")
    date_hint = _normalize_date_hint(
        payload.get("published_date")
        or meta.get("published_date")
        or meta.get("meeting_date")
        or payload.get("meeting_date")
    )
    return f"v1|source={source}|doctype={document_type}|title={title}|date={date_hint}"


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def build_revision_seed(scrape_record: Mapping[str, Any]) -> dict[str, Any]:
    """Seed phase-1 revision identity fields for raw scrape inserts."""
    metadata = _coerce_object(scrape_record.get("metadata"))
    data = _coerce_object(scrape_record.get("data"))
    source_id = str(scrape_record.get("source_id") or "").strip()

    canonical_document_key = (
        scrape_record.get("canonical_document_key")
        or metadata.get("canonical_document_key")
        or build_canonical_document_key(
            source_id=source_id,
            url=scrape_record.get("url"),
            metadata=metadata,
            data=data,
        )
    )

    revision_number = int(
        scrape_record.get("revision_number") or metadata.get("revision_number") or 1
    )
    seen_count = int(scrape_record.get("seen_count") or metadata.get("seen_count") or 1)
    if revision_number < 1:
        revision_number = 1
    if seen_count < 1:
        seen_count = 1

    last_seen_at = _coerce_datetime(scrape_record.get("last_seen_at"))
    previous_raw_scrape_id = scrape_record.get("previous_raw_scrape_id")

    return {
        "canonical_document_key": canonical_document_key,
        "previous_raw_scrape_id": previous_raw_scrape_id,
        "revision_number": revision_number,
        "last_seen_at": last_seen_at,
        "seen_count": seen_count,
    }
