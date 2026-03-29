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
    "fixture_provenance",
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
VALID_PROVENANCE_TYPES: Set[str] = {"live_capture", "synthetic_control"}
VALID_SYNTHETIC_MODE_BUCKETS: Set[str] = {
    "fail_closed_control",
    "adversarial_control",
}
VALID_SYNTHETIC_USE_CASES: Set[str] = {
    "control_path_replay",
    "adversarial_path_replay",
    "schema_contract_validation",
    "deterministic_fixture_loading",
}
REQUIRED_SYNTHETIC_LIMITATIONS: Set[str] = {
    "not_live_capture",
    "not_search_volatility_proof",
    "not_quantitative_ground_truth",
}

FIXTURE_VERSION = "1.0"
FEATURE_KEY = "bd-bkco.2"
FIXTURE_SET_VERSION = "1.0"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def load_fixture_set_metadata(repo_root: Path) -> Dict[str, Any]:
    metadata_path = (
        repo_root
        / "backend"
        / "scripts"
        / "verification"
        / "fixtures"
        / "research_fixture_set_metadata.json"
    )

    if not metadata_path.exists():
        fail(f"fixture set metadata not found: {metadata_path}")

    data = json.loads(metadata_path.read_text(encoding="utf-8"))

    required_fields = {
        "fixture_set_version",
        "feature_key",
        "scope",
        "corpus_freeze",
        "search_volatility_separated",
        "live_capture_required_for_quantitative_modes",
        "expected_fixture_bill_ids",
    }
    missing_fields = required_fields - set(data.keys())
    if missing_fields:
        fail(f"fixture set metadata missing fields: {sorted(missing_fields)}")

    if data["fixture_set_version"] != FIXTURE_SET_VERSION:
        fail(
            "unsupported fixture_set_version: "
            f"{data['fixture_set_version']} (expected {FIXTURE_SET_VERSION})"
        )

    if data["feature_key"] != FEATURE_KEY:
        fail(
            f"invalid fixture set feature_key: {data['feature_key']} "
            f"(expected {FEATURE_KEY})"
        )

    if data["scope"] != "bootstrap_control_subset":
        fail(
            "fixture set scope must remain 'bootstrap_control_subset' until "
            "live quantitative fixtures exist"
        )

    if data["corpus_freeze"] is not False:
        fail("fixture set metadata must declare corpus_freeze=false")

    if data["search_volatility_separated"] is not False:
        fail(
            "fixture set metadata must declare "
            "search_volatility_separated=false"
        )

    if data["live_capture_required_for_quantitative_modes"] is not True:
        fail(
            "fixture set metadata must declare "
            "live_capture_required_for_quantitative_modes=true"
        )

    expected_fixture_bill_ids = data["expected_fixture_bill_ids"]
    if (
        not isinstance(expected_fixture_bill_ids, list)
        or not expected_fixture_bill_ids
        or not all(isinstance(item, str) for item in expected_fixture_bill_ids)
    ):
        fail("expected_fixture_bill_ids must be a non-empty array of strings")

    return data


def validate_fixture(
    fixture_path: Path, manifest_bills: Dict[str, Dict[str, Any]]
) -> List[str]:
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
    manifest_record = manifest_bills.get(bill_id)
    if bill_id:
        if manifest_record is None:
            errors.append(f"bill_id '{bill_id}' not in manifest corpus")
    else:
        errors.append("missing bill_id")

    capture_mode = data.get("capture_mode", "")
    if capture_mode and capture_mode not in VALID_CAPTURE_MODES:
        errors.append(
            f"invalid capture_mode: {capture_mode} "
            f"(expected one of {sorted(VALID_CAPTURE_MODES)})"
        )

    provenance = data.get("fixture_provenance")
    if provenance is None:
        errors.append("fixture_provenance is required")
    elif not isinstance(provenance, dict):
        errors.append("fixture_provenance must be an object")
    else:
        provenance_type = provenance.get("provenance_type", "")
        if provenance_type not in VALID_PROVENANCE_TYPES:
            errors.append(
                f"invalid provenance_type: {provenance_type} "
                f"(expected one of {sorted(VALID_PROVENANCE_TYPES)})"
            )

        search_volatility_separated = provenance.get("search_volatility_separated")
        if not isinstance(search_volatility_separated, bool):
            errors.append(
                "fixture_provenance.search_volatility_separated must be a boolean"
            )

        valid_for = provenance.get("valid_for")
        if not isinstance(valid_for, list) or not valid_for:
            errors.append("fixture_provenance.valid_for must be a non-empty array")
        elif provenance_type == "synthetic_control":
            invalid_valid_for = [
                item
                for item in valid_for
                if not isinstance(item, str) or item not in VALID_SYNTHETIC_USE_CASES
            ]
            if invalid_valid_for:
                errors.append(
                    "fixture_provenance.valid_for contains unsupported values: "
                    f"{invalid_valid_for}"
                )

        limitations = provenance.get("limitations")
        if not isinstance(limitations, list) or not limitations:
            errors.append("fixture_provenance.limitations must be a non-empty array")
        else:
            invalid_limitations = [
                item for item in limitations if not isinstance(item, str)
            ]
            if invalid_limitations:
                errors.append(
                    "fixture_provenance.limitations contains non-string values: "
                    f"{invalid_limitations}"
                )

        if capture_mode == "synthetic":
            if provenance_type != "synthetic_control":
                errors.append(
                    "synthetic fixtures must declare provenance_type="
                    "'synthetic_control'"
                )
            if search_volatility_separated is True:
                errors.append(
                    "synthetic fixtures cannot claim search volatility separation"
                )
            if manifest_record is not None:
                if (
                    manifest_record.get("mode_bucket") not in VALID_SYNTHETIC_MODE_BUCKETS
                    or manifest_record.get("expected_quantifiable") is not False
                ):
                    errors.append(
                        "synthetic fixtures are only allowed for explicit "
                        "fail-closed/adversarial control bills"
                    )
            if isinstance(limitations, list):
                missing_limitations = REQUIRED_SYNTHETIC_LIMITATIONS - set(limitations)
                if missing_limitations:
                    errors.append(
                        "synthetic fixtures missing required limitations: "
                        f"{sorted(missing_limitations)}"
                    )

        if search_volatility_separated is True and (
            capture_mode != "live" or provenance_type != "live_capture"
        ):
            errors.append(
                "search volatility separation may only be claimed by live_capture "
                "fixtures"
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


def load_manifest_bills(repo_root: Path) -> Dict[str, Dict[str, Any]]:
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
    return {
        b["bill_id"]: b for b in bills if isinstance(b, dict) and "bill_id" in b
    }


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

    fixture_set_metadata = load_fixture_set_metadata(repo_root)
    manifest_bills = load_manifest_bills(repo_root)
    manifest_bill_ids = set(manifest_bills.keys())

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
        errors = validate_fixture(fixture_path, manifest_bills)
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
    expected_fixture_bill_ids = set(fixture_set_metadata["expected_fixture_bill_ids"])

    missing_expected_fixtures = expected_fixture_bill_ids - fixture_bill_ids
    extra_expected_mismatches = fixture_bill_ids - expected_fixture_bill_ids

    if missing_expected_fixtures:
        fail(
            "fixture files missing from expected bootstrap subset: "
            f"{sorted(missing_expected_fixtures)}"
        )

    if extra_expected_mismatches:
        fail(
            "fixture files exceed declared bootstrap subset: "
            f"{sorted(extra_expected_mismatches)}"
        )

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
    print(
        "PASS: fixture set scope is "
        f"{fixture_set_metadata['scope']} ({len(expected_fixture_bill_ids)} bill(s))"
    )


if __name__ == "__main__":
    main()
