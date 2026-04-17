from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts.verification.verify_local_government_corpus_manual_audit import (
    verify_local_government_manual_audit,
    verify_manual_audit_and_golden,
)


def _build_compliant_payloads() -> tuple[dict, dict, dict]:
    taxonomy_version = "corpus_taxonomy_v1"
    jurisdictions = ["san_jose_ca", "austin_tx", "king_county_wa"]
    policy_families = [
        "parking_policy",
        "zoning_land_use",
        "code_enforcement",
        "short_term_rental",
        "housing_permits",
    ]
    source_families = [
        "official_pdf_html_attachment",
        "official_clerk_or_code_portal",
        "agenda_meeting_api",
    ]

    rows: list[dict] = []
    manual_audits: list[dict] = []
    golden_rows: list[dict] = []

    for index in range(30):
        package_num = index + 1
        package_id = f"pkg::fixture-{package_num:03d}"
        corpus_row_id = f"fixture-{package_num:03d}"
        jurisdiction_id = jurisdictions[index // 10]
        policy_family = policy_families[index % len(policy_families)]
        source_family = source_families[index % len(source_families)]
        source_url = f"https://example.gov/source/{package_num:03d}.pdf"
        split = "tuning" if index % 2 == 0 else "blind_evaluation"

        row = {
            "row_type": "corpus_package",
            "corpus_row_id": corpus_row_id,
            "package_id": package_id,
            "jurisdiction": {"id": jurisdiction_id},
            "policy_family": policy_family,
            "selected_primary_source": {
                "source_family": source_family,
                "source_url": source_url,
                "source_officialness": "official_primary",
            },
            "classification": {
                "data_moat_package_classification": "economic_handoff_candidate",
                "d11_handoff_quality": "analysis_ready_with_gaps",
            },
            "evaluation_split": split,
        }
        rows.append(row)

        manual_audits.append(
            {
                "package_id": package_id,
                "corpus_row_id": corpus_row_id,
                "jurisdiction_id": jurisdiction_id,
                "policy_family": policy_family,
                "selected_primary_source": source_url,
                "source_officialness": "official_primary",
                "source_family_type": source_family,
                "structured_source_contribution": "structured_sources_present",
                "package_identity": f"id::{package_id}",
                "storage_readback_evidence": "d6_d7_d8_pass",
                "data_moat_classification": "economic_handoff_candidate",
                "d11_economic_handoff_classification": "analysis_ready_with_gaps",
                "freshness_drift": "stale=false;drift=false",
                "licensing_schema_posture": "public_record_or_open_data|schema_v1",
                "windmill_orchestration_classification": "windmill_live",
                "product_surface_export_status": "export_ready=true",
                "dominant_failure_class": "none",
            }
        )

        golden_rows.append(
            {
                "stable_query_input": f"fixture query {package_num:03d}",
                "expected_jurisdiction_id": jurisdiction_id,
                "expected_policy_family": policy_family,
                "selected_source_url": source_url,
                "package_id": package_id,
                "verdict": "corpus_ready_with_gaps",
                "failure_class": "none",
                "taxonomy_version": taxonomy_version,
                "split": "tuning" if split == "tuning" else "blind",
            }
        )

    matrix_payload = {
        "benchmark_id": "local_government_data_moat_benchmark_v0",
        "taxonomy_version": taxonomy_version,
        "rows": rows,
    }
    manual_payload = {"audits": manual_audits}
    golden_payload = {"rows": golden_rows}
    return matrix_payload, manual_payload, golden_payload


def test_manual_audit_and_golden_pass_with_compliant_fixture() -> None:
    matrix_payload, manual_payload, golden_payload = _build_compliant_payloads()
    report = verify_manual_audit_and_golden(
        matrix_payload=matrix_payload,
        manual_audit_payload=manual_payload,
        golden_payload=golden_payload,
    )

    assert report["status"] == "pass", report["failures"]
    assert report["manual_audit"]["required_sample_count"] == 30
    assert report["manual_audit"]["audit_row_count"] == 30
    assert report["golden_regression"]["row_count"] == 30


def test_san_jose_only_audit_cannot_false_pass() -> None:
    matrix_payload, manual_payload, golden_payload = _build_compliant_payloads()
    san_jose_packages = {
        audit["package_id"]
        for audit in manual_payload["audits"]
        if audit["jurisdiction_id"] == "san_jose_ca"
    }
    mutated_manual = deepcopy(manual_payload)
    mutated_manual["audits"] = [
        audit for audit in mutated_manual["audits"] if audit["package_id"] in san_jose_packages
    ]
    mutated_golden = deepcopy(golden_payload)
    mutated_golden["rows"] = [
        row for row in mutated_golden["rows"] if row["package_id"] in san_jose_packages
    ]

    report = verify_manual_audit_and_golden(
        matrix_payload=matrix_payload,
        manual_audit_payload=mutated_manual,
        golden_payload=mutated_golden,
    )

    assert report["status"] == "fail"
    assert "manual_audit_san_jose_only_sample" in report["failures"]
    assert "manual_audit_sample_count_below_30_requirement" in report["failures"]
    assert "manual_audit_non_san_jose_jurisdiction_coverage_below_2x5" in report["failures"]


def test_missing_manual_audit_required_field_fails() -> None:
    matrix_payload, manual_payload, golden_payload = _build_compliant_payloads()
    mutated_manual = deepcopy(manual_payload)
    mutated_manual["audits"][0].pop("windmill_orchestration_classification", None)

    report = verify_manual_audit_and_golden(
        matrix_payload=matrix_payload,
        manual_audit_payload=mutated_manual,
        golden_payload=golden_payload,
    )

    assert report["status"] == "fail"
    assert any(
        failure.startswith("manual_audit_missing_required_fields:")
        for failure in report["failures"]
    )


def test_missing_golden_required_field_fails() -> None:
    matrix_payload, manual_payload, golden_payload = _build_compliant_payloads()
    mutated_golden = deepcopy(golden_payload)
    mutated_golden["rows"][0].pop("selected_source_url", None)

    report = verify_manual_audit_and_golden(
        matrix_payload=matrix_payload,
        manual_audit_payload=manual_payload,
        golden_payload=mutated_golden,
    )

    assert report["status"] == "fail"
    assert any(
        failure.startswith("golden_missing_required_fields:")
        for failure in report["failures"]
    )


def test_repo_manual_audit_artifacts_have_required_fields() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    artifact_dir = repo_root / "docs" / "poc" / "policy-evidence-quality-spine" / "artifacts"

    report = verify_local_government_manual_audit(
        matrix_path=artifact_dir / "local_government_corpus_matrix.json",
        manual_audit_path=artifact_dir / "manual_audit_local_government_corpus.json",
        golden_path=artifact_dir / "golden_policy_regression_set.json",
    )

    assert report["manual_audit"]["audit_row_count"] >= report["manual_audit"]["required_sample_count"]
    assert report["manual_audit"]["missing_required_field_count"] == 0
    assert report["golden_regression"]["missing_required_field_count"] == 0

    payload = json.loads((artifact_dir / "golden_policy_regression_set.json").read_text(encoding="utf-8"))
    assert payload.get("rows"), "golden policy regression set must not be empty"
