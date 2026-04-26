from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_ARTIFACTS = {
    "taxonomy": "corpus_taxonomy_v1.json",
    "known_policies": "known_policy_reference_list.json",
    "licensing": "source_licensing_tos_register.json",
    "schema_contract": "package_schema_version_contract.json",
    "surface_contract": "data_product_surface_contract.json",
}

REQUIRED_CLASSIFICATIONS = {
    "economic_analysis_ready",
    "economic_handoff_candidate",
    "secondary_research_needed",
    "qualitative_only",
    "stored_not_economic",
    "not_policy_evidence",
    "fail",
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def verify_surface(artifact_dir: Path) -> dict[str, Any]:
    loaded = {
        name: _load_json(artifact_dir / filename)
        for name, filename in REQUIRED_ARTIFACTS.items()
    }
    failures: list[str] = []

    taxonomy = loaded["taxonomy"]
    classifications = set(taxonomy.get("classification_values") or taxonomy.get("handoff_classes") or [])
    if not REQUIRED_CLASSIFICATIONS.issubset(classifications):
        failures.append("taxonomy_missing_required_classification_values")

    jurisdictions = taxonomy.get("jurisdictions") or []
    non_ca = [row for row in jurisdictions if row.get("state") not in {None, "CA"}]
    if len(jurisdictions) < 6 or len(non_ca) < 2:
        failures.append("taxonomy_missing_ultra_reach_jurisdiction_seed")

    source_families = set(taxonomy.get("source_families") or [])
    if len(source_families) < 5:
        failures.append("taxonomy_missing_source_family_breadth")

    known_rows = loaded["known_policies"].get("rows") or []
    blind_rows = [row for row in known_rows if row.get("blind_holdout") is True]
    policy_families = {row.get("policy_family") for row in known_rows}
    known_jurisdictions = {row.get("jurisdiction_id") for row in known_rows}
    if len(known_rows) < 10:
        failures.append("known_policy_reference_list_too_small")
    if len(blind_rows) < 5:
        failures.append("known_policy_reference_list_missing_blind_holdouts")
    if len(policy_families) < 6:
        failures.append("known_policy_reference_list_missing_policy_family_breadth")
    if len(known_jurisdictions) < 6:
        failures.append("known_policy_reference_list_missing_jurisdiction_breadth")

    licensing_rows = loaded["licensing"].get("source_families") or []
    licensed_families = {row.get("source_family") for row in licensing_rows}
    missing_license = sorted(source_families - licensed_families)
    if missing_license:
        failures.append(f"licensing_register_missing_source_families:{','.join(missing_license)}")
    unknown_license = [
        row.get("source_family")
        for row in licensing_rows
        if str(row.get("licensing_status") or "").lower() == "unknown"
    ]
    if unknown_license:
        failures.append(f"licensing_register_has_unknown_status:{','.join(unknown_license)}")

    schema_contract = loaded["schema_contract"]
    required_export_fields = set(schema_contract.get("minimum_export_row_fields") or [])
    for field in {
        "package_id",
        "taxonomy_version",
        "gate_version",
        "data_moat_classification",
        "licensing_status",
        "known_policy_reference_id",
    }:
        if field not in required_export_fields:
            failures.append(f"schema_contract_missing_export_field:{field}")

    surfaces = {
        row.get("surface")
        for row in (loaded["surface_contract"].get("consumer_surfaces") or [])
    }
    for surface in {"admin_read_model", "bulk_export", "corpus_scorecard"}:
        if surface not in surfaces:
            failures.append(f"surface_contract_missing:{surface}")

    return {
        "status": "pass" if not failures else "fail",
        "artifact_dir": str(artifact_dir),
        "checked_artifacts": REQUIRED_ARTIFACTS,
        "jurisdiction_count": len(jurisdictions),
        "non_ca_jurisdiction_count": len(non_ca),
        "known_policy_count": len(known_rows),
        "blind_holdout_count": len(blind_rows),
        "known_policy_family_count": len(policy_families),
        "known_policy_jurisdiction_count": len(known_jurisdictions),
        "licensed_source_family_count": len(licensed_families),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify local-government data product surface artifacts."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path(__file__).resolve().parents[3]
        / "docs"
        / "poc"
        / "policy-evidence-quality-spine"
        / "artifacts",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = verify_surface(args.artifact_dir)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"local_government_data_product_surface: {result['status']}")
        for failure in result["failures"]:
            print(f"- {failure}")
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
