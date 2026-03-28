#!/usr/bin/env python3
"""Validate the bd-bkco.1 golden bill corpus manifest contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_FIELDS = {
    "bill_id",
    "title",
    "jurisdiction",
    "year",
    "mode_bucket",
    "expected_quantifiable",
    "control_type",
    "inclusion_rationale",
    "minimum_required_sources",
    "exclusion_risks",
    "confidence",
}

QUOTA_BUCKETS = (
    "direct_fiscal",
    "compliance_cost",
    "pass_through_incidence",
    "adoption_take_up",
)

CONTROL_BUCKETS = ("fail_closed_control", "adversarial_control")


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
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
    bills = data.get("bills")
    gap_notes = data.get("gap_notes")

    if not isinstance(bills, list):
        fail("'bills' must be a list")
    if not isinstance(gap_notes, list):
        fail("'gap_notes' must be a list")

    total = len(bills)
    if total < 10 or total > 16:
        fail(f"total corpus size must be in [10, 16], got {total}")

    seen_ids: set[str] = set()
    mode_counts: dict[str, int] = {}

    for idx, bill in enumerate(bills):
        if not isinstance(bill, dict):
            fail(f"record[{idx}] must be an object")

        missing = REQUIRED_FIELDS - set(bill.keys())
        if missing:
            fail(f"record[{idx}] missing fields: {sorted(missing)}")

        bill_id = bill["bill_id"]
        if bill_id in seen_ids:
            fail(f"duplicate bill_id: {bill_id}")
        seen_ids.add(bill_id)

        if not isinstance(bill["expected_quantifiable"], bool):
            fail(f"{bill_id}: expected_quantifiable must be boolean")

        if not isinstance(bill["year"], int):
            fail(f"{bill_id}: year must be integer")

        confidence = bill["confidence"]
        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            fail(f"{bill_id}: confidence must be number in [0, 1]")

        for list_field in ("minimum_required_sources", "exclusion_risks"):
            if not isinstance(bill[list_field], list) or not bill[list_field]:
                fail(f"{bill_id}: {list_field} must be a non-empty list")

        mode_bucket = bill["mode_bucket"]
        mode_counts[mode_bucket] = mode_counts.get(mode_bucket, 0) + 1

    unmet_quota_notes = []
    for bucket in QUOTA_BUCKETS:
        if mode_counts.get(bucket, 0) < 2:
            unmet_quota_notes.append(bucket)

    for bucket in CONTROL_BUCKETS:
        if mode_counts.get(bucket, 0) < 2:
            unmet_quota_notes.append(bucket)

    if unmet_quota_notes and not gap_notes:
        fail(f"quota shortfall without documented gap_notes: {sorted(unmet_quota_notes)}")

    print("PASS: golden bill corpus manifest contract is valid")
    print(f"PASS: total records = {total}")
    for bucket in (*QUOTA_BUCKETS, *CONTROL_BUCKETS):
        print(f"PASS: {bucket} = {mode_counts.get(bucket, 0)}")


if __name__ == "__main__":
    main()
