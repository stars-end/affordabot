#!/usr/bin/env python3
"""Verify C5 manual audit stratification + golden regression set contracts."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any


REQUIRED_MANUAL_AUDIT_FIELDS = {
    "selected_primary_source",
    "source_officialness",
    "source_family_type",
    "structured_source_contribution",
    "package_identity",
    "storage_readback_evidence",
    "data_moat_classification",
    "d11_economic_handoff_classification",
    "freshness_drift",
    "licensing_schema_posture",
    "windmill_orchestration_classification",
    "product_surface_export_status",
    "dominant_failure_class",
}

REQUIRED_GOLDEN_FIELDS = {
    "stable_query_input",
    "expected_jurisdiction_id",
    "expected_policy_family",
    "selected_source_url",
    "package_id",
    "verdict",
    "failure_class",
    "taxonomy_version",
    "split",
}

ALLOWED_SPLITS = {"tuning", "blind"}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        msg = f"{path} must contain a JSON object"
        raise ValueError(msg)
    return payload


def _corpus_rows(matrix_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in matrix_payload.get("rows", [])
        if isinstance(row, dict) and row.get("row_type") == "corpus_package"
    ]


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _normalize_split(split: Any) -> str:
    text = str(split or "").strip().lower()
    if text == "blind_evaluation":
        return "blind"
    return text


def _selected_source_url(row: dict[str, Any]) -> str:
    selected = row.get("selected_primary_source") or {}
    if not isinstance(selected, dict):
        return ""
    return str(selected.get("source_url") or selected.get("url") or "")


def _manual_dominant_failure_default(classification: str, source_officialness: str) -> str:
    if source_officialness in {"external_advocacy", "news_media", "vendor"}:
        return "external_primary_not_allowed"
    if classification == "secondary_research_needed":
        return "secondary_research_required"
    if classification in {"qualitative_only", "stored_not_economic"}:
        return "insufficient_quantitative_evidence"
    if classification == "not_policy_evidence":
        return "policy_scope_mismatch"
    if classification == "fail":
        return "package_failed_quality_gate"
    return "none"


def verify_manual_audit_and_golden(
    *,
    matrix_payload: dict[str, Any],
    manual_audit_payload: dict[str, Any],
    golden_payload: dict[str, Any],
) -> dict[str, Any]:
    matrix_rows = _corpus_rows(matrix_payload)
    matrix_by_package = {
        str(row.get("package_id") or ""): row for row in matrix_rows if row.get("package_id")
    }
    matrix_package_ids = set(matrix_by_package)
    matrix_taxonomy_version = str(matrix_payload.get("taxonomy_version") or "")
    required_sample_count = len(matrix_rows) if len(matrix_rows) < 30 else 30

    failures: list[str] = []

    audits_raw = manual_audit_payload.get("audits")
    audits = audits_raw if isinstance(audits_raw, list) else []
    if not isinstance(audits_raw, list):
        failures.append("manual_audit_audits_not_list")

    audit_missing_required: list[str] = []
    audit_unknown_package: list[str] = []
    audit_mismatch: list[str] = []
    audit_package_ids: list[str] = []

    jurisdiction_counter: Counter[str] = Counter()
    policy_family_counter: Counter[str] = Counter()
    source_family_counter: Counter[str] = Counter()

    for index, audit in enumerate(audits):
        if not isinstance(audit, dict):
            failures.append(f"manual_audit_row_not_object:{index}")
            continue

        package_id = str(audit.get("package_id") or "")
        audit_package_ids.append(package_id)

        missing_fields = sorted(
            field
            for field in REQUIRED_MANUAL_AUDIT_FIELDS
            if not _is_present(audit.get(field))
        )
        if missing_fields:
            audit_missing_required.append(f"{package_id or f'index_{index}'}:{','.join(missing_fields)}")

        jurisdiction_id = str(audit.get("jurisdiction_id") or "")
        policy_family = str(audit.get("policy_family") or "")
        source_family_type = str(audit.get("source_family_type") or "")
        if jurisdiction_id:
            jurisdiction_counter[jurisdiction_id] += 1
        if policy_family:
            policy_family_counter[policy_family] += 1
        if source_family_type:
            source_family_counter[source_family_type] += 1

        row = matrix_by_package.get(package_id)
        if row is None:
            audit_unknown_package.append(package_id or f"index_{index}")
            continue

        row_jurisdiction = str((row.get("jurisdiction") or {}).get("id") or "")
        row_policy_family = str(row.get("policy_family") or "")
        row_source_family = str(
            (row.get("selected_primary_source") or {}).get("source_family") or ""
        )
        row_source_officialness = str(
            (row.get("selected_primary_source") or {}).get("source_officialness") or ""
        )
        row_selected_source = _selected_source_url(row)
        row_classification = str(
            (row.get("classification") or {}).get("data_moat_package_classification") or ""
        )
        row_d11 = str((row.get("classification") or {}).get("d11_handoff_quality") or "")

        if jurisdiction_id != row_jurisdiction:
            audit_mismatch.append(f"{package_id}:jurisdiction_id")
        if policy_family != row_policy_family:
            audit_mismatch.append(f"{package_id}:policy_family")
        if source_family_type != row_source_family:
            audit_mismatch.append(f"{package_id}:source_family_type")
        if str(audit.get("source_officialness") or "") != row_source_officialness:
            audit_mismatch.append(f"{package_id}:source_officialness")
        if str(audit.get("selected_primary_source") or "") != row_selected_source:
            audit_mismatch.append(f"{package_id}:selected_primary_source")
        if str(audit.get("data_moat_classification") or "") != row_classification:
            audit_mismatch.append(f"{package_id}:data_moat_classification")
        if str(audit.get("d11_economic_handoff_classification") or "") != row_d11:
            audit_mismatch.append(f"{package_id}:d11_economic_handoff_classification")

        expected_dominant_failure = _manual_dominant_failure_default(
            classification=row_classification,
            source_officialness=row_source_officialness,
        )
        if str(audit.get("dominant_failure_class") or "") != expected_dominant_failure:
            audit_mismatch.append(f"{package_id}:dominant_failure_class")

    unique_audit_packages = {package for package in audit_package_ids if package}
    duplicate_count = len(audit_package_ids) - len(unique_audit_packages)
    if duplicate_count:
        failures.append(f"manual_audit_duplicate_package_rows:{duplicate_count}")

    if audit_missing_required:
        failures.append(
            f"manual_audit_missing_required_fields:{'|'.join(sorted(audit_missing_required))}"
        )
    if audit_unknown_package:
        failures.append(
            f"manual_audit_unknown_package_id:{'|'.join(sorted(set(audit_unknown_package)))}"
        )
    if audit_mismatch:
        failures.append(
            f"manual_audit_matrix_mismatch:{'|'.join(sorted(set(audit_mismatch)))}"
        )

    if len(matrix_rows) < 30:
        missing_packages = sorted(matrix_package_ids - unique_audit_packages)
        if missing_packages:
            failures.append(
                "manual_audit_missing_packages_for_sub30_matrix:"
                + ",".join(missing_packages)
            )
    elif len(unique_audit_packages) < 30:
        failures.append("manual_audit_sample_count_below_30_requirement")

    if len(unique_audit_packages) < required_sample_count:
        failures.append("manual_audit_sample_size_below_requirement")

    if jurisdiction_counter == {"san_jose_ca": len(audits)} and audits:
        failures.append("manual_audit_san_jose_only_sample")

    jurisdictions_below_min = sorted(
        jurisdiction
        for jurisdiction, count in jurisdiction_counter.items()
        if count < 3
    )
    if jurisdictions_below_min:
        failures.append(
            "manual_audit_jurisdiction_count_below_3:"
            + ",".join(jurisdictions_below_min)
        )

    policy_families_below_min = sorted(
        policy_family
        for policy_family, count in policy_family_counter.items()
        if count < 2
    )
    if policy_families_below_min:
        failures.append(
            "manual_audit_policy_family_count_below_2:"
            + ",".join(policy_families_below_min)
        )

    source_families_below_min = sorted(
        source_family
        for source_family, count in source_family_counter.items()
        if count < 2
    )
    if source_families_below_min:
        failures.append(
            "manual_audit_source_family_count_below_2:"
            + ",".join(source_families_below_min)
        )

    non_san_jose_with_five_or_more = sorted(
        jurisdiction
        for jurisdiction, count in jurisdiction_counter.items()
        if jurisdiction != "san_jose_ca" and count >= 5
    )
    if len(non_san_jose_with_five_or_more) < 2:
        failures.append("manual_audit_non_san_jose_jurisdiction_coverage_below_2x5")

    golden_rows_raw = golden_payload.get("rows")
    golden_rows = golden_rows_raw if isinstance(golden_rows_raw, list) else []
    if not isinstance(golden_rows_raw, list):
        failures.append("golden_rows_not_list")

    golden_missing_required: list[str] = []
    golden_unknown_package: list[str] = []
    golden_mismatch: list[str] = []
    golden_package_ids: list[str] = []
    golden_split_counter: Counter[str] = Counter()

    for index, golden_row in enumerate(golden_rows):
        if not isinstance(golden_row, dict):
            failures.append(f"golden_row_not_object:{index}")
            continue

        package_id = str(golden_row.get("package_id") or "")
        golden_package_ids.append(package_id)

        missing_fields = sorted(
            field
            for field in REQUIRED_GOLDEN_FIELDS
            if not _is_present(golden_row.get(field))
        )
        if missing_fields:
            golden_missing_required.append(
                f"{package_id or f'index_{index}'}:{','.join(missing_fields)}"
            )

        normalized_split = _normalize_split(golden_row.get("split"))
        if normalized_split in ALLOWED_SPLITS:
            golden_split_counter[normalized_split] += 1
        else:
            golden_mismatch.append(f"{package_id}:split")

        row = matrix_by_package.get(package_id)
        if row is None:
            golden_unknown_package.append(package_id or f"index_{index}")
            continue

        expected_jurisdiction = str((row.get("jurisdiction") or {}).get("id") or "")
        expected_policy_family = str(row.get("policy_family") or "")
        expected_source_url = _selected_source_url(row)
        if str(golden_row.get("expected_jurisdiction_id") or "") != expected_jurisdiction:
            golden_mismatch.append(f"{package_id}:expected_jurisdiction_id")
        if str(golden_row.get("expected_policy_family") or "") != expected_policy_family:
            golden_mismatch.append(f"{package_id}:expected_policy_family")
        if str(golden_row.get("selected_source_url") or "") != expected_source_url:
            golden_mismatch.append(f"{package_id}:selected_source_url")
        if str(golden_row.get("taxonomy_version") or "") != matrix_taxonomy_version:
            golden_mismatch.append(f"{package_id}:taxonomy_version")

    unique_golden_packages = {package for package in golden_package_ids if package}
    golden_duplicate_count = len(golden_package_ids) - len(unique_golden_packages)
    if golden_duplicate_count:
        failures.append(f"golden_duplicate_package_rows:{golden_duplicate_count}")

    if golden_missing_required:
        failures.append(
            f"golden_missing_required_fields:{'|'.join(sorted(golden_missing_required))}"
        )
    if golden_unknown_package:
        failures.append(
            f"golden_unknown_package_id:{'|'.join(sorted(set(golden_unknown_package)))}"
        )
    if golden_mismatch:
        failures.append(f"golden_matrix_mismatch:{'|'.join(sorted(set(golden_mismatch)))}")

    missing_golden_for_audit = sorted(unique_audit_packages - unique_golden_packages)
    if missing_golden_for_audit:
        failures.append(
            "golden_missing_audited_packages:" + ",".join(missing_golden_for_audit)
        )

    if golden_split_counter.get("tuning", 0) == 0 or golden_split_counter.get("blind", 0) == 0:
        failures.append("golden_split_coverage_missing_tuning_or_blind")

    return {
        "status": "pass" if not failures else "fail",
        "benchmark_id": matrix_payload.get("benchmark_id"),
        "taxonomy_version": matrix_taxonomy_version,
        "manual_audit": {
            "matrix_package_count": len(matrix_rows),
            "required_sample_count": required_sample_count,
            "audit_row_count": len(audits),
            "unique_audited_package_count": len(unique_audit_packages),
            "jurisdiction_counts": dict(sorted(jurisdiction_counter.items())),
            "policy_family_counts": dict(sorted(policy_family_counter.items())),
            "source_family_counts": dict(sorted(source_family_counter.items())),
            "non_san_jose_jurisdictions_with_min_5": non_san_jose_with_five_or_more,
            "missing_required_field_count": len(audit_missing_required),
            "matrix_mismatch_count": len(set(audit_mismatch)),
        },
        "golden_regression": {
            "row_count": len(golden_rows),
            "unique_package_count": len(unique_golden_packages),
            "split_counts": dict(sorted(golden_split_counter.items())),
            "missing_required_field_count": len(golden_missing_required),
            "matrix_mismatch_count": len(set(golden_mismatch)),
        },
        "failures": failures,
    }


def verify_local_government_manual_audit(
    *,
    matrix_path: Path,
    manual_audit_path: Path,
    golden_path: Path,
) -> dict[str, Any]:
    matrix_payload = _load_json(matrix_path)
    manual_audit_payload = _load_json(manual_audit_path)
    golden_payload = _load_json(golden_path)
    return verify_manual_audit_and_golden(
        matrix_payload=matrix_payload,
        manual_audit_payload=manual_audit_payload,
        golden_payload=golden_payload,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Verify C5 stratified manual audit coverage and the local-government "
            "golden regression set."
        )
    )
    repo_root = Path(__file__).resolve().parents[3]
    default_artifact_dir = (
        repo_root / "docs" / "poc" / "policy-evidence-quality-spine" / "artifacts"
    )
    parser.add_argument(
        "--matrix-path",
        type=Path,
        default=default_artifact_dir / "local_government_corpus_matrix.json",
    )
    parser.add_argument(
        "--manual-audit-path",
        type=Path,
        default=default_artifact_dir / "manual_audit_local_government_corpus.json",
    )
    parser.add_argument(
        "--golden-path",
        type=Path,
        default=default_artifact_dir / "golden_policy_regression_set.json",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = verify_local_government_manual_audit(
        matrix_path=args.matrix_path,
        manual_audit_path=args.manual_audit_path,
        golden_path=args.golden_path,
    )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"local_government_corpus_manual_audit: {report['status']}")
        print(
            "manual_audit_rows="
            f"{report['manual_audit']['audit_row_count']}/"
            f"{report['manual_audit']['required_sample_count']}"
        )
        print(f"golden_rows={report['golden_regression']['row_count']}")
        for failure in report["failures"]:
            print(f"- {failure}")

    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
