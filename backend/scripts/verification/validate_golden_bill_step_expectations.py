#!/usr/bin/env python3
"""Validate the bd-bkco.3 golden bill step expectations contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Set


EXPECTATION_SET_VERSION = "1.0"
FEATURE_KEY = "bd-bkco.3"

ALLOWED_EXPECTATION_STRENGTHS = {"strong", "provisional_bootstrap"}
ALLOWED_FIXTURE_STATUS = {
    "checked_in_synthetic_control_fixture",
    "manifest_only_no_checked_in_fixture",
}
ALLOWED_MODES = {
    "direct_fiscal",
    "compliance_cost",
    "pass_through_incidence",
    "adoption_take_up",
    "qualitative_only",
}
ALLOWED_SUFFICIENCY_STATES = {
    "research_incomplete",
    "insufficient_evidence",
    "qualitative_only",
    "quantified",
}
ALLOWED_FAILURE_CODES = {
    "impact_discovery_failed",
    "mode_selection_failed",
    "parameter_missing",
    "parameter_unverifiable",
    "source_hierarchy_failed",
    "excerpt_validation_failed",
    "invalid_scenario_construction",
    "validation_failed",
    "fixture_invalid",
}

REQUIRED_TOP_LEVEL_FIELDS = {
    "expectation_set_version",
    "feature_key",
    "description",
    "generated_on",
    "source_contracts",
    "bills",
}
REQUIRED_BILL_FIELDS = {
    "bill_id",
    "mode_bucket",
    "fixture_status",
    "expectation_strength",
    "expected_steps",
    "analyst_conclusion",
}
MODE_REQUIRED_PARAMETERS = {
    "direct_fiscal": ["fiscal_amount"],
    "compliance_cost": ["population", "frequency", "time_burden", "wage_rate"],
    "pass_through_incidence": ["total_levied_cost", "pass_through_rate"],
    "adoption_take_up": [
        "eligible_population",
        "take_up_rate",
        "benefit_per_capita",
    ],
    "qualitative_only": [],
}


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def load_json(path: Path, label: str) -> Dict[str, Any]:
    if not path.exists():
        fail(f"{label} not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest_bills(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    bills = manifest.get("bills")
    if not isinstance(bills, list):
        fail("manifest.bills must be a list")
    return {
        bill["bill_id"]: bill
        for bill in bills
        if isinstance(bill, dict) and isinstance(bill.get("bill_id"), str)
    }


def validate_impact_count(bill_id: str, impact_payload: Dict[str, Any]) -> None:
    if "expected_impact_count" not in impact_payload:
        fail(f"{bill_id}: expected_steps.impact_discovery.expected_impact_count is required")
    count_payload = impact_payload["expected_impact_count"]
    if not isinstance(count_payload, dict):
        fail(f"{bill_id}: expected_impact_count must be an object")

    has_exact = "exact" in count_payload
    has_min = "minimum" in count_payload
    if not has_exact and not has_min:
        fail(f"{bill_id}: expected_impact_count must include 'exact' or 'minimum'")
    if has_exact and has_min:
        fail(f"{bill_id}: expected_impact_count cannot include both 'exact' and 'minimum'")

    key = "exact" if has_exact else "minimum"
    value = count_payload[key]
    if not isinstance(value, int) or value < 0:
        fail(f"{bill_id}: expected_impact_count.{key} must be a non-negative integer")


def validate_bill(
    bill: Dict[str, Any],
    manifest_bills: Dict[str, Dict[str, Any]],
    expected_fixture_bill_ids: Set[str],
) -> None:
    missing_fields = REQUIRED_BILL_FIELDS - set(bill.keys())
    if missing_fields:
        fail(f"bill expectation missing fields: {sorted(missing_fields)}")

    bill_id = bill["bill_id"]
    if bill_id not in manifest_bills:
        fail(f"{bill_id}: bill_id not found in manifest")

    expectation_strength = bill["expectation_strength"]
    if expectation_strength not in ALLOWED_EXPECTATION_STRENGTHS:
        fail(
            f"{bill_id}: invalid expectation_strength={expectation_strength}; "
            f"expected one of {sorted(ALLOWED_EXPECTATION_STRENGTHS)}"
        )

    fixture_status = bill["fixture_status"]
    if fixture_status not in ALLOWED_FIXTURE_STATUS:
        fail(
            f"{bill_id}: invalid fixture_status={fixture_status}; "
            f"expected one of {sorted(ALLOWED_FIXTURE_STATUS)}"
        )

    has_checked_in_fixture = bill_id in expected_fixture_bill_ids
    if has_checked_in_fixture and fixture_status != "checked_in_synthetic_control_fixture":
        fail(f"{bill_id}: fixture_status must be checked_in_synthetic_control_fixture")
    if (
        not has_checked_in_fixture
        and fixture_status != "manifest_only_no_checked_in_fixture"
    ):
        fail(f"{bill_id}: fixture_status must be manifest_only_no_checked_in_fixture")

    expected_steps = bill["expected_steps"]
    if not isinstance(expected_steps, dict):
        fail(f"{bill_id}: expected_steps must be an object")

    for required_step in (
        "impact_discovery",
        "mode_selection",
        "parameter_resolution",
        "sufficiency_gate",
    ):
        if required_step not in expected_steps:
            fail(f"{bill_id}: missing expected_steps.{required_step}")

    impact_discovery = expected_steps["impact_discovery"]
    if not isinstance(impact_discovery, dict):
        fail(f"{bill_id}: expected_steps.impact_discovery must be an object")
    validate_impact_count(bill_id, impact_discovery)

    mode_selection = expected_steps["mode_selection"]
    if not isinstance(mode_selection, dict):
        fail(f"{bill_id}: expected_steps.mode_selection must be an object")
    selected_mode = mode_selection.get("expected_selected_mode")
    if selected_mode not in ALLOWED_MODES:
        fail(
            f"{bill_id}: expected_selected_mode={selected_mode} is invalid; "
            f"expected one of {sorted(ALLOWED_MODES)}"
        )

    parameter_resolution = expected_steps["parameter_resolution"]
    if not isinstance(parameter_resolution, dict):
        fail(f"{bill_id}: expected_steps.parameter_resolution must be an object")

    required_parameters = parameter_resolution.get("required_parameters")
    resolved_parameters = parameter_resolution.get("expected_resolved_parameters")
    missing_parameters = parameter_resolution.get("expected_missing_parameters")
    for key, value in (
        ("required_parameters", required_parameters),
        ("expected_resolved_parameters", resolved_parameters),
        ("expected_missing_parameters", missing_parameters),
    ):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            fail(f"{bill_id}: parameter_resolution.{key} must be an array of strings")

    mode_required = MODE_REQUIRED_PARAMETERS[selected_mode]
    if required_parameters != mode_required:
        fail(
            f"{bill_id}: required_parameters {required_parameters} must match "
            f"mode {selected_mode} requirement {mode_required}"
        )

    if expected_steps["sufficiency_gate"].get("overall_quantification_eligible") is True:
        if missing_parameters:
            fail(
                f"{bill_id}: quantification_eligible=true requires empty expected_missing_parameters"
            )

    sufficiency_gate = expected_steps["sufficiency_gate"]
    if not isinstance(sufficiency_gate, dict):
        fail(f"{bill_id}: expected_steps.sufficiency_gate must be an object")

    quant_eligible = sufficiency_gate.get("overall_quantification_eligible")
    if not isinstance(quant_eligible, bool):
        fail(f"{bill_id}: sufficiency_gate.overall_quantification_eligible must be boolean")

    sufficiency_state = sufficiency_gate.get("overall_sufficiency_state")
    if sufficiency_state not in ALLOWED_SUFFICIENCY_STATES:
        fail(
            f"{bill_id}: invalid sufficiency_state={sufficiency_state}; "
            f"expected one of {sorted(ALLOWED_SUFFICIENCY_STATES)}"
        )

    bill_level_failures = sufficiency_gate.get("bill_level_failures")
    if (
        not isinstance(bill_level_failures, list)
        or not all(isinstance(item, str) for item in bill_level_failures)
    ):
        fail(f"{bill_id}: sufficiency_gate.bill_level_failures must be an array of strings")
    unknown_failure_codes = set(bill_level_failures) - ALLOWED_FAILURE_CODES
    if unknown_failure_codes:
        fail(f"{bill_id}: unknown bill_level_failures={sorted(unknown_failure_codes)}")

    analyst_conclusion = bill["analyst_conclusion"]
    if not isinstance(analyst_conclusion, dict):
        fail(f"{bill_id}: analyst_conclusion must be an object")
    if not isinstance(analyst_conclusion.get("label"), str) or not analyst_conclusion["label"]:
        fail(f"{bill_id}: analyst_conclusion.label must be a non-empty string")
    if (
        not isinstance(analyst_conclusion.get("conclusion"), str)
        or not analyst_conclusion["conclusion"]
    ):
        fail(f"{bill_id}: analyst_conclusion.conclusion must be a non-empty string")

    manifest_record = manifest_bills[bill_id]
    if bill["mode_bucket"] != manifest_record.get("mode_bucket"):
        fail(
            f"{bill_id}: mode_bucket mismatch with manifest "
            f"({bill['mode_bucket']} != {manifest_record.get('mode_bucket')})"
        )

    if manifest_record.get("expected_quantifiable") is False:
        if selected_mode != "qualitative_only":
            fail(f"{bill_id}: non-quantifiable control bills must use qualitative_only mode")
        if quant_eligible:
            fail(
                f"{bill_id}: non-quantifiable control bills must set "
                "overall_quantification_eligible=false"
            )

    # Provisional bootstrap contract:
    # manifest-only bills with no checked-in fixture must stay deterministic placeholders
    # and must not assert successful quantitative discovery/mode/parameter outcomes.
    if expectation_strength == "provisional_bootstrap":
        if fixture_status != "manifest_only_no_checked_in_fixture":
            fail(
                f"{bill_id}: provisional_bootstrap requires "
                "fixture_status=manifest_only_no_checked_in_fixture"
            )
        impact_count = impact_discovery.get("expected_impact_count", {})
        if impact_count.get("exact") != 0 or "minimum" in impact_count:
            fail(
                f"{bill_id}: provisional_bootstrap requires expected_impact_count.exact=0 "
                "with no minimum field"
            )
        if selected_mode != "qualitative_only":
            fail(
                f"{bill_id}: provisional_bootstrap must use "
                "mode_selection.expected_selected_mode=qualitative_only"
            )
        if required_parameters or resolved_parameters or missing_parameters:
            fail(
                f"{bill_id}: provisional_bootstrap requires empty "
                "required/resolved/missing parameter expectations"
            )
        if quant_eligible:
            fail(
                f"{bill_id}: provisional_bootstrap must set "
                "overall_quantification_eligible=false"
            )
        if sufficiency_state != "research_incomplete":
            fail(
                f"{bill_id}: provisional_bootstrap must set "
                "overall_sufficiency_state=research_incomplete"
            )
        if bill_level_failures != ["impact_discovery_failed"]:
            fail(
                f"{bill_id}: provisional_bootstrap must set bill_level_failures "
                "to exactly ['impact_discovery_failed']"
            )


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    fixtures_dir = repo_root / "backend" / "scripts" / "verification" / "fixtures"

    expectations = load_json(
        fixtures_dir / "golden_bill_step_expectations.json",
        "golden bill step expectations",
    )
    manifest = load_json(fixtures_dir / "golden_bill_corpus_manifest.json", "manifest")
    fixture_metadata = load_json(
        fixtures_dir / "research_fixture_set_metadata.json", "fixture set metadata"
    )

    missing_top_level = REQUIRED_TOP_LEVEL_FIELDS - set(expectations.keys())
    if missing_top_level:
        fail(f"expectations file missing fields: {sorted(missing_top_level)}")

    if expectations["expectation_set_version"] != EXPECTATION_SET_VERSION:
        fail(
            "unsupported expectation_set_version: "
            f"{expectations['expectation_set_version']} "
            f"(expected {EXPECTATION_SET_VERSION})"
        )

    if expectations["feature_key"] != FEATURE_KEY:
        fail(
            f"invalid feature_key: {expectations['feature_key']} "
            f"(expected {FEATURE_KEY})"
        )

    bills = expectations["bills"]
    if not isinstance(bills, list):
        fail("expectations.bills must be a list")

    manifest_bills = load_manifest_bills(manifest)
    expected_fixture_bill_ids = set(fixture_metadata.get("expected_fixture_bill_ids", []))

    expectation_bill_ids: Set[str] = set()
    for record in bills:
        if not isinstance(record, dict):
            fail("each expectation record must be an object")
        bill_id = record.get("bill_id")
        if not isinstance(bill_id, str):
            fail("each expectation record must include string bill_id")
        if bill_id in expectation_bill_ids:
            fail(f"duplicate expectation bill_id: {bill_id}")
        expectation_bill_ids.add(bill_id)
        validate_bill(record, manifest_bills, expected_fixture_bill_ids)

    manifest_bill_ids = set(manifest_bills.keys())
    missing_from_expectations = manifest_bill_ids - expectation_bill_ids
    if missing_from_expectations:
        fail(
            "manifest bills missing expectation records: "
            f"{sorted(missing_from_expectations)}"
        )

    extra_expectations = expectation_bill_ids - manifest_bill_ids
    if extra_expectations:
        fail(f"expectations contains unknown bill ids: {sorted(extra_expectations)}")

    print("PASS: golden bill step expectations contract is valid")
    print(f"PASS: expectation records = {len(expectation_bill_ids)}")
    strong_count = len([b for b in bills if b.get("expectation_strength") == "strong"])
    provisional_count = len(bills) - strong_count
    print(f"PASS: strong expectations = {strong_count}")
    print(f"PASS: provisional bootstrap expectations = {provisional_count}")


if __name__ == "__main__":
    main()
