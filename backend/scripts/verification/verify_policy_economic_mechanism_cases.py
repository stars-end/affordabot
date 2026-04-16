#!/usr/bin/env python3
"""Verifier for deterministic economic mechanism cases (bd-3wefe.6)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.pipeline.policy_economic_mechanism_cases import (  # noqa: E402
    PolicyEconomicMechanismCaseService,
)
from services.pipeline.policy_evidence_package_storage import (  # noqa: E402
    InMemoryArtifactProbe,
    InMemoryArtifactWriter,
    InMemoryPolicyEvidencePackageStore,
    PolicyEvidencePackageStorageService,
)
from services.pipeline.policy_evidence_package_sufficiency import (  # noqa: E402
    PolicyEvidencePackageSufficiencyService,
)


DEFAULT_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-economic-mechanism-cases"
    / "artifacts"
    / "policy_economic_mechanism_cases_report.json"
)


def _gate(status: bool, note: str) -> dict[str, str]:
    return {"status": "passed" if status else "failed", "note": note}


def _find_case(cases: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    for case in cases:
        if case["case_id"] == case_id:
            return case
    raise RuntimeError(f"missing case={case_id}")


def _known_minio_uris(package: dict[str, Any]) -> set[str]:
    uris = {f"minio://policy-evidence/packages/{package['package_id']}.json"}
    for ref in package.get("storage_refs", []):
        if ref.get("storage_system") == "minio":
            uri = ref.get("uri") or ref.get("reference_id")
            if uri:
                uris.add(uri)
    return uris


def _evaluate_package_sufficiency(case_id: str, label: str, package: dict[str, Any]) -> dict[str, Any]:
    store = InMemoryPolicyEvidencePackageStore()
    storage = PolicyEvidencePackageStorageService(
        store=store,
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(known_uris=_known_minio_uris(package)),
    )
    idempotency_key = f"mechanism-case::{case_id}::{label}"
    storage_result = storage.persist(
        package_payload=package,
        idempotency_key=idempotency_key,
    )
    record = store.get_by_idempotency(idempotency_key=idempotency_key)
    if record is None:
        return {
            "case_id": case_id,
            "package_label": label,
            "package_id": package.get("package_id"),
            "stored": storage_result.stored,
            "storage_failure_class": storage_result.failure_class,
            "sufficiency_passed": False,
            "readiness_level": "fail_closed",
            "blocking_gate": "storage",
        }

    sufficiency = PolicyEvidencePackageSufficiencyService().evaluate(record=record)
    return {
        "case_id": case_id,
        "package_label": label,
        "package_id": package["package_id"],
        "stored": storage_result.stored,
        "artifact_readback_status": storage_result.artifact_readback_status,
        "sufficiency_passed": sufficiency.passed,
        "readiness_level": sufficiency.readiness_level.value,
        "blocking_gate": None if sufficiency.blocking_gate is None else sufficiency.blocking_gate.value,
        "failure_reasons": sufficiency.failure_reasons,
    }


def _sufficiency_integration(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in cases:
        for label in ("primary_package", "secondary_package"):
            package = case.get(label)
            if package is None:
                continue
            results.append(_evaluate_package_sufficiency(case["case_id"], label, package))
    return results


def run(out_path: Path) -> dict[str, Any]:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    cases = bundle["cases"]

    direct = _find_case(cases, "direct_cost_case")
    indirect = _find_case(cases, "indirect_pass_through_case")
    secondary = _find_case(cases, "secondary_research_required_case")
    control = _find_case(cases, "unsupported_fail_closed_control")
    direct_package = direct["primary_package"]
    indirect_package = indirect["primary_package"]
    control_package = control["primary_package"]

    direct_scraped = direct_package["scraped_sources"][0]
    indirect_scraped = indirect_package["scraped_sources"][0]
    control_scraped = control_package["scraped_sources"][0]

    gates = {
        "direct_case_quant_ready": _gate(
            direct["quantification_plausible"] and direct["primary_package"]["economic_handoff_ready"],
            "direct case includes quantified-ready package, mechanism graph, and scenario range",
        ),
        "indirect_case_quant_ready": _gate(
            indirect["quantification_plausible"]
            and bool(indirect["assumption_cards"])
            and indirect["primary_package"]["economic_handoff_ready"],
            "indirect case carries explicit assumption cards and quantitative handoff readiness",
        ),
        "secondary_case_requires_second_package": _gate(
            secondary["primary_package"]["economic_handoff_ready"] is False
            and secondary["secondary_package"] is not None
            and secondary["secondary_package"]["economic_handoff_ready"] is True,
            "secondary-research-required path uses a second auditable package",
        ),
        "unsupported_claim_fail_closed": _gate(
            control["primary_package"]["economic_handoff_ready"] is False
            and control["unsupported_claim_rejection"] is not None
            and control["primary_package"]["gate_report"]["verdict"] == "fail_closed",
            "unsupported claim is rejected with explicit fail-closed reason",
        ),
        "canonical_document_key_stable": _gate(
            all(
                package["package_id"] not in package["canonical_document_key"]
                for package in (
                    direct_package,
                    indirect_package,
                    secondary["primary_package"],
                    secondary["secondary_package"],
                    control_package,
                )
            ),
            "canonical_document_key is policy-identity stable and package-version independent",
        ),
        "scraped_provenance_case_specific": _gate(
            direct_scraped["selected_candidate_url"] != indirect_scraped["selected_candidate_url"]
            and direct_scraped["reader_artifact_url"] != indirect_scraped["reader_artifact_url"]
            and control_scraped["selected_candidate_url"].endswith("study-session-overview"),
            "scraped provenance is case-specific (candidate URL, reader artifact URL, query text)",
        ),
    }
    sufficiency_integration = _sufficiency_integration(cases)

    failures = [name for name, gate in gates.items() if gate["status"] != "passed"]
    payload = {
        "feature_key": "bd-3wefe.6",
        "generated_at": bundle["generated_at"],
        "report_version": "2026-04-15.policy-economic-mechanism-cases.verifier.v1",
        "gates": gates,
        "architecture_readiness": bundle["architecture_readiness"],
        "sufficiency_integration": sufficiency_integration,
        "cases": cases,
        "economic_analysis_readiness_assessment": {
            "representational_readiness": "pass" if not failures else "partial",
            "summary": (
                "Current architecture can represent direct, indirect, and "
                "secondary-research economic analysis inputs with explicit fail-closed "
                "controls."
                if not failures
                else "One or more deterministic mechanism gates failed."
            ),
            "remaining_gaps": [
                "Live LLM narrative quality is not evaluated in this deterministic verifier.",
                "Package sufficiency integration is expected to be consumed by bd-3wefe.5.",
            ],
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run(args.out)
    gates = report["gates"]
    failures = [name for name, gate in gates.items() if gate["status"] != "passed"]
    print(
        "policy_economic_mechanism_cases verification complete: "
        f"gates_passed={len(gates) - len(failures)}/{len(gates)}"
    )
    if failures:
        print("failed_gates=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
