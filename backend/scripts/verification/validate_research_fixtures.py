#!/usr/bin/env python3
"""Validate the bd-bkco.2 research fixtures contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set


REQUIRED_FIELDS: Set[str] = {
    "fixture_version",
    "feature_key",
    "bill_id",
    "captured_at",
    "capture_mode",
    "scraped_bill_text",
    "rag_chunks",
    "web_sources",
    "sufficiency_breakdown",
}

SCRAPED_BILL_REQUIRED_FIELDS: Set[str] = {
    "bill_number",
    "title",
    "text",
}

SUFFICIENCY_REQUIRED_FIELDS: Set[str] = {
    "source_text_present",
    "rag_chunks_retrieved",
    "web_research_sources_found",
}

VALID_CAPTURE_MODES: Set[str] = {"live", "synthetic"}

FIXTURE_VERSION = "1.0"
FEATURE_KEY = "bd-bkco.2"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def validate_fixture(fixture_path: Path, manifest_bill_ids: Set[str]) -> List[str]:
    errors: List[str] = []

    try:
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"invalid JSON: {e}")
        return errors

    missing_top_level = REQUIRED_FIELDS - set(data.keys())
    if missing_top_level:
        errors.append(f"missing required fields: {sorted(missing_top_level)}")

    if "fixture_version" in data:
        if data["fixture_version"] != FIXTURE_VERSION:
            errors.append(
                f"unsupported fixture_version: {data['fixture_version']} "
                f"(expected {FIXTURE_VERSION})"
            )

    if "feature_key" in data:
        if data["feature_key"] != FEATURE_KEY:
            errors.append(
                f"invalid feature_key: {data['feature_key']} (expected {FEATURE_KEY})"
            )

    bill_id = data.get("bill_id", "")
    if bill_id:
        if bill_id not in manifest_bill_ids:
            errors.append(f"bill_id '{bill_id}' not in manifest corpus")
    else:
        errors.append("missing bill_id")

    capture_mode = data.get("capture_mode", "")
    if capture_mode and capture_mode not in VALID_CAPTURE_MODES:
        errors.append(
            f"invalid capture_mode: {capture_mode} "
            f"(expected one of {sorted(VALID_CAPTURE_MODES)})"
        )

    scraped = data.get("scraped_bill_text")
    if scraped is not None:
        if not isinstance(scraped, dict):
            errors.append("scraped_bill_text must be an object")
        else:
            missing_scraped = SCRAPED_BILL_REQUIRED_FIELDS - set(scraped.keys())
            if missing_scraped:
                errors.append(
                    f"scraped_bill_text missing fields: {sorted(missing_scraped)}"
                )
    else:
        errors.append("scraped_bill_text is required")

    rag_chunks = data.get("rag_chunks")
    if rag_chunks is not None:
        if not isinstance(rag_chunks, list):
            errors.append("rag_chunks must be an array")
        else:
            for idx, chunk in enumerate(rag_chunks):
                if not isinstance(chunk, dict):
                    errors.append(f"rag_chunks[{idx}] must be an object")
                    continue
                if "content" not in chunk:
                    errors.append(f"rag_chunks[{idx}] missing 'content'")
    else:
        errors.append("rag_chunks is required")

    web_sources = data.get("web_sources")
    if web_sources is not None:
        if not isinstance(web_sources, list):
            errors.append("web_sources must be an array")
        else:
            for idx, source in enumerate(web_sources):
                if not isinstance(source, dict):
                    errors.append(f"web_sources[{idx}] must be an object")
    else:
        errors.append("web_sources is required")

    sufficiency = data.get("sufficiency_breakdown")
    if sufficiency is not None:
        if not isinstance(sufficiency, dict):
            errors.append("sufficiency_breakdown must be an object")
        else:
            missing_sufficiency = SUFFICIENCY_REQUIRED_FIELDS - set(sufficiency.keys())
            if missing_sufficiency:
                errors.append(
                    f"sufficiency_breakdown missing fields: {sorted(missing_sufficiency)}"
                )
    else:
        errors.append("sufficiency_breakdown is required")

    return errors


def load_manifest_bill_ids(repo_root: Path) -> Set[str]:
    manifest_path = (
        repo_root
        / "backend"
        / "scripts"
        / "verification"
        / "fixtures"
        / "golden_bill_corpus_manifest.json"
    )

    if not manifest_path.exists():
        fail(f"manifest not found: {manifest_path}")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    bills = data.get("bills", [])
    return {b["bill_id"] for b in bills if isinstance(b, dict) and "bill_id" in b}


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    fixtures_dir = (
        repo_root
        / "backend"
        / "scripts"
        / "verification"
        / "fixtures"
        / "research_fixtures"
    )

    manifest_bill_ids = load_manifest_bill_ids(repo_root)

    if not fixtures_dir.exists():
        fail(f"fixtures directory not found: {fixtures_dir}")

    fixture_files = list(fixtures_dir.glob("*.json"))
    if not fixture_files:
        print("WARN: no fixture files found (directory exists but is empty)")
        print("PASS: fixture directory structure is valid")
        return

    total_errors = 0
    fixture_bill_ids: Set[str] = set()

    for fixture_path in sorted(fixture_files):
        errors = validate_fixture(fixture_path, manifest_bill_ids)
        bill_id = fixture_path.stem

        if errors:
            print(f"FAIL: {fixture_path.name}")
            for error in errors:
                print(f"  - {error}")
            total_errors += len(errors)
        else:
            print(f"PASS: {fixture_path.name}")
            fixture_bill_ids.add(bill_id)

    missing_fixtures = manifest_bill_ids - fixture_bill_ids
    if missing_fixtures:
        print(f"WARN: {len(missing_fixtures)} bills from manifest have no fixture:")
        for bill_id in sorted(missing_fixtures)[:5]:
            print(f"  - {bill_id}")
        if len(missing_fixtures) > 5:
            print(f"  ... and {len(missing_fixtures) - 5} more")

    if total_errors > 0:
        fail(f"{total_errors} validation error(s) found")

    print(f"PASS: all {len(fixture_files)} fixture(s) validated")
    print(
        f"PASS: fixture-to-manifest coverage: {len(fixture_bill_ids)}/{len(manifest_bill_ids)}"
    )


if __name__ == "__main__":
    main()
