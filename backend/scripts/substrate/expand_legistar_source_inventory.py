#!/usr/bin/env python3
"""Expand seeded Legistar calendar roots into agenda/minutes source rows."""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


ROW_PATTERN = re.compile(
    r"<tr[^>]*class=\"(?:rgRow|rgAltRow)\"[^>]*>(.*?)</tr>",
    re.IGNORECASE | re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_manifest() -> list[dict[str, Any]]:
    manifest_path = _repo_root() / "scripts" / "lib" / "substrate_source_inventory.json"
    return json.loads(manifest_path.read_text())


def _strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_PATTERN.sub(" ", value or ""))).strip()


def _extract_first(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else None


def normalize_jurisdiction_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", (value or "").strip().lower())
    for prefix in ("city of ", "county of "):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    return normalized


def extract_legistar_document_sources(
    *,
    calendar_html: str,
    calendar_url: str,
    jurisdiction_name: str,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []

    for row_html in ROW_PATTERN.findall(calendar_html):
        meeting_name_html = _extract_first(
            r"<td[^>]*>\s*<a[^>]*?(?:hypName|LinkButtonName)[^>]*>(.*?)</a>",
            row_html,
        ) or _extract_first(r"<td[^>]*>(.*?)</td>", row_html)
        meeting_date_html = _extract_first(
            r"<td[^>]*>([^<]*\d{1,2}/\d{1,2}/\d{4}[^<]*)</td>",
            row_html,
        )

        meeting_name = _strip_tags(meeting_name_html or "") or jurisdiction_name
        meeting_date = _strip_tags(meeting_date_html or "")

        for document_type, anchor_suffix in (("agenda", "hypAgenda"), ("minutes", "hypMinutes")):
            href = _extract_first(
                rf"id=\"[^\"]*_{anchor_suffix}\"[^>]*href=\"([^\"]+)\"",
                row_html,
            )
            if not href:
                continue

            absolute_url = urljoin(calendar_url, html.unescape(href))
            title_parts = [jurisdiction_name, meeting_name, document_type.title()]
            if meeting_date:
                title_parts.append(meeting_date)
            sources.append(
                {
                    "url": absolute_url,
                    "source_name": " - ".join(title_parts),
                    "document_type": document_type,
                    "meeting_name": meeting_name,
                    "meeting_date": meeting_date,
                }
            )

    return sources


def fetch_calendar_html(url: str) -> str:
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8", "replace")


async def _resolve_jurisdiction_id(
    db: Any, *, jurisdiction_name: str, jurisdiction_type: str
) -> str | None:
    row = await db._fetchrow(
        """
        SELECT id
        FROM jurisdictions
        WHERE name = $1 AND type = $2
        LIMIT 1
        """,
        jurisdiction_name,
        jurisdiction_type,
    )
    if row:
        return str(row["id"])

    rows = await db._fetch(
        """
        SELECT id, name
        FROM jurisdictions
        WHERE type = $1
        """,
        jurisdiction_type,
    )
    target = normalize_jurisdiction_name(jurisdiction_name)
    for candidate in rows:
        if normalize_jurisdiction_name(candidate["name"]) == target:
            return str(candidate["id"])
    return None


async def _upsert_source(
    db: Any,
    *,
    jurisdiction_id: str,
    jurisdiction_name: str,
    calendar_entry: dict[str, Any],
    candidate: dict[str, Any],
) -> str:
    existing = await db._fetchrow("SELECT id, metadata FROM sources WHERE url = $1 LIMIT 1", candidate["url"])
    metadata = {
        "provider_family": "legistar_calendar",
        "document_type": candidate["document_type"],
        "trust_tier": "official",
        "origin_calendar_url": calendar_entry["url"],
        "meeting_name": candidate["meeting_name"],
        "meeting_date": candidate["meeting_date"],
        "inventory_scope": "existing_family_deepening",
        "seed_wave": "bd-paba",
    }
    payload = {
        "jurisdiction_id": jurisdiction_id,
        "url": candidate["url"],
        "type": "meeting_document",
        "status": "active",
        "source_method": "manual",
        "handler": "substrate_legistar_document",
        "metadata": json.dumps(metadata),
        "name": candidate["source_name"],
        "scrape_url": candidate["url"],
    }
    if existing:
        await db.update_source(str(existing["id"]), payload)
        return "updated"
    await db.create_source(payload)
    return "created"


async def expand_manifest(
    *,
    jurisdiction_slugs: set[str] | None,
    limit_per_document_type: int,
    write: bool,
) -> dict[str, Any]:
    manifest = load_manifest()
    db = None
    if write:
        from db.postgres_client import PostgresDB

        db = PostgresDB()
    results: list[dict[str, Any]] = []
    try:
        for entry in manifest:
            if entry.get("metadata", {}).get("provider_family") != "legistar_calendar":
                continue
            if jurisdiction_slugs and entry["jurisdiction_slug"] not in jurisdiction_slugs:
                continue

            html_text = fetch_calendar_html(entry["url"])
            extracted = extract_legistar_document_sources(
                calendar_html=html_text,
                calendar_url=entry["url"],
                jurisdiction_name=entry["jurisdiction_name"],
            )

            grouped: dict[str, list[dict[str, Any]]] = {"agenda": [], "minutes": []}
            for candidate in extracted:
                grouped[candidate["document_type"]].append(candidate)

            jurisdiction_result = {
                "jurisdiction_slug": entry["jurisdiction_slug"],
                "calendar_url": entry["url"],
                "agenda_count": len(grouped["agenda"]),
                "minutes_count": len(grouped["minutes"]),
                "written": [],
            }

            if write and db:
                jurisdiction_id = await _resolve_jurisdiction_id(
                    db,
                    jurisdiction_name=entry["jurisdiction_name"],
                    jurisdiction_type=entry["jurisdiction_type"],
                )
                if not jurisdiction_id:
                    jurisdiction_result["error"] = "jurisdiction_not_found"
                    results.append(jurisdiction_result)
                    continue

                for document_type in ("agenda", "minutes"):
                    for candidate in grouped[document_type][:limit_per_document_type]:
                        action = await _upsert_source(
                            db,
                            jurisdiction_id=jurisdiction_id,
                            jurisdiction_name=entry["jurisdiction_name"],
                            calendar_entry=entry,
                            candidate=candidate,
                        )
                        jurisdiction_result["written"].append(
                            {
                                "document_type": document_type,
                                "url": candidate["url"],
                                "action": action,
                            }
                        )
            else:
                jurisdiction_result["sample_urls"] = {
                    "agenda": [item["url"] for item in grouped["agenda"][:limit_per_document_type]],
                    "minutes": [item["url"] for item in grouped["minutes"][:limit_per_document_type]],
                }

            results.append(jurisdiction_result)
    finally:
        if db:
            await db.close()

    return {
        "provider_family": "legistar_calendar",
        "write": write,
        "limit_per_document_type": limit_per_document_type,
        "jurisdictions": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jurisdiction-slug", action="append", default=[])
    parser.add_argument("--limit-per-document-type", type=int, default=3)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = asyncio.run(
        expand_manifest(
            jurisdiction_slugs=set(args.jurisdiction_slug) or None,
            limit_per_document_type=args.limit_per_document_type,
            write=args.write,
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
