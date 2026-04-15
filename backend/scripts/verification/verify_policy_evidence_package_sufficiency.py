#!/usr/bin/env python3
"""Verifier for persisted package sufficiency gate (bd-3wefe.5)."""

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

from services.pipeline.policy_evidence_package_builder import PolicyEvidencePackageBuilder
from services.pipeline.policy_evidence_package_storage import (
    InMemoryArtifactProbe,
    InMemoryArtifactWriter,
    InMemoryPolicyEvidencePackageStore,
    PersistedPackageRecord,
    PolicyEvidencePackageStorageService,
)
from services.pipeline.policy_evidence_package_sufficiency import (
    PolicyEvidencePackageSufficiencyService,
)


DEFAULT_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-package-sufficiency"
    / "artifacts"
    / "policy_evidence_package_sufficiency_report.json"
)

INTEGRATION_FIXTURE = (
    REPO_ROOT / "docs" / "poc" / "source-integration" / "artifacts" / "scrape_structured_integration_report.json"
)
VERIFY_TS = "2026-04-15T00:00:00+00:00"


def _load_fixture() -> list[dict[str, Any]]:
    payload = json.loads(INTEGRATION_FIXTURE.read_text(encoding="utf-8"))
    return [dict(item) for item in payload.get("envelopes", []) if isinstance(item, dict)]


def _pick(*, source_lane: str, provider: str) -> dict[str, Any]:
    for envelope in _load_fixture():
        if envelope.get("source_lane") == source_lane and envelope.get("provider") == provider:
            return envelope
    raise RuntimeError(f"fixture missing lane={source_lane} provider={provider}")


def _build_package(*, package_id: str) -> dict[str, Any]:
    scraped = _pick(source_lane="scrape_search", provider="private_searxng")
    structured = _pick(source_lane="structured", provider="legistar")
    return PolicyEvidencePackageBuilder().build(
        package_id=package_id,
        jurisdiction="san_jose_ca",
        scraped_candidates=[scraped],
        structured_candidates=[structured],
        freshness_gate={"freshness_status": "fresh"},
        economic_hints={"impact_mode": "direct_fiscal", "mechanism_family": "direct_fiscal"},
        storage_refs={
            "postgres_package_row": "policy_evidence_packages:pending",
            "reader_artifact": f"minio://policy-evidence/reader/private_searxng/{package_id}.txt",
            "pgvector_chunk_ref": "chunk:meeting-minutes-1",
        },
    )


def _persist_record(
    *,
    package_id: str,
    proven_readback: bool,
    payload_override: dict[str, Any] | None = None,
) -> PersistedPackageRecord:
    payload = _build_package(package_id=package_id)
    if payload_override:
        payload.update(payload_override)
    artifact_uri = f"minio://policy-evidence/packages/{package_id}.json"
    reader_uri = f"minio://policy-evidence/reader/private_searxng/{package_id}.txt"
    known_uris = {artifact_uri, reader_uri} if proven_readback else None
    store = InMemoryPolicyEvidencePackageStore()
    service = PolicyEvidencePackageStorageService(
        store=store,
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(known_uris=known_uris) if known_uris is not None else None,
    )
    result = service.persist(package_payload=payload, idempotency_key=f"idem-{package_id}")
    if not result.stored:
        raise RuntimeError(f"storage persist failed for {package_id}: {result.failure_class}")
    record = store.get_by_idempotency(idempotency_key=f"idem-{package_id}")
    if record is None:
        raise RuntimeError(f"missing persisted record for {package_id}")
    return record


def _with_payload(record: PersistedPackageRecord, payload: dict[str, Any], *, gate_state: str) -> PersistedPackageRecord:
    return PersistedPackageRecord(
        record_id=record.record_id,
        package_id=record.package_id,
        idempotency_key=record.idempotency_key,
        content_hash=record.content_hash,
        schema_version=record.schema_version,
        jurisdiction=record.jurisdiction,
        canonical_document_key=record.canonical_document_key,
        policy_identifier=record.policy_identifier,
        package_status=record.package_status,
        economic_handoff_ready=bool(payload.get("economic_handoff_ready", False)),
        fail_closed=record.fail_closed,
        gate_state=gate_state,
        insufficiency_reasons=record.insufficiency_reasons,
        storage_refs=record.storage_refs,
        package_payload=payload,
        artifact_write_status=record.artifact_write_status,
        artifact_readback_status=record.artifact_readback_status,
        pgvector_truth_role=record.pgvector_truth_role,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _result_to_json(result: Any) -> dict[str, Any]:
    return {
        "passed": result.passed,
        "blocking_gate": None if result.blocking_gate is None else result.blocking_gate.value,
        "readiness_level": result.readiness_level.value,
        "failure_reasons": result.failure_reasons,
        "recommendations_for_bd_3wefe_6": result.recommendations_for_bd_3wefe_6,
    }


def run(out_path: Path) -> dict[str, Any]:
    verifier = PolicyEvidencePackageSufficiencyService()

    positive_record = _persist_record(package_id="pkg-suff-pos", proven_readback=True)
    positive_result = verifier.evaluate(record=positive_record)

    unproven_record = _persist_record(package_id="pkg-suff-unproven", proven_readback=False)
    unproven_result = verifier.evaluate(record=unproven_record)

    stale_base = _persist_record(package_id="pkg-suff-stale", proven_readback=True)
    stale_payload = dict(stale_base.package_payload)
    stale_payload["assumption_usage"] = [
        {
            "assumption_id": stale_payload["assumption_cards"][0]["id"],
            "used_for_quantitative_claim": True,
            "applicable": True,
            "stale": False,
        }
    ]
    stale_payload["freshness_status"] = "stale_blocked"
    stale_record = _with_payload(stale_base, stale_payload, gate_state=stale_base.gate_state)
    stale_result = verifier.evaluate(record=stale_record)

    missing_params_base = _persist_record(package_id="pkg-suff-no-params", proven_readback=True)
    missing_params_payload = dict(missing_params_base.package_payload)
    missing_params_payload["parameter_cards"] = []
    missing_params_payload["model_cards"] = []
    missing_params_payload["economic_handoff_ready"] = False
    missing_params_payload["gate_projection"] = {
        **missing_params_payload["gate_projection"],
        "runtime_sufficiency_state": "quantified",
    }
    missing_params_record = _with_payload(
        missing_params_base,
        missing_params_payload,
        gate_state="quantified",
    )
    missing_params_result = verifier.evaluate(record=missing_params_record)

    qual_base = _persist_record(package_id="pkg-suff-qual", proven_readback=True)
    qual_payload = dict(qual_base.package_payload)
    qual_payload["parameter_cards"] = []
    qual_payload["model_cards"] = []
    qual_payload["economic_handoff_ready"] = False
    qual_payload["gate_projection"] = {
        **qual_payload["gate_projection"],
        "runtime_sufficiency_state": "qualitative_only",
    }
    qual_payload["gate_report"] = {
        **qual_payload["gate_report"],
        "verdict": "qualitative_only",
        "blocking_gate": "parameterization",
        "stage_results": [
            {
                "stage": "parameterization",
                "passed": False,
                "failure_codes": ["parameter_missing"],
                "note": "qualitative fallback",
            }
        ],
    }
    qual_record = _with_payload(qual_base, qual_payload, gate_state="qualitative_only")
    qual_result = verifier.evaluate(record=qual_record)

    unsupported_base = _persist_record(package_id="pkg-suff-unsupported", proven_readback=True)
    unsupported_payload = dict(unsupported_base.package_payload)
    unsupported_payload["economic_handoff_ready"] = False
    unsupported_payload["parameter_cards"] = []
    unsupported_payload["model_cards"] = []
    unsupported_payload["gate_projection"] = {
        **unsupported_payload["gate_projection"],
        "runtime_sufficiency_state": "insufficient_evidence",
        "runtime_failure_codes": ["parameter_unverifiable"],
    }
    unsupported_payload["gate_report"] = {
        **unsupported_payload["gate_report"],
        "verdict": "fail_closed",
        "blocking_gate": "parameterization",
        "unsupported_claim_count": 1,
        "failure_codes": ["parameter_unverifiable"],
        "stage_results": [
            {
                "stage": "parameterization",
                "passed": False,
                "failure_codes": ["parameter_unverifiable"],
                "note": "unsupported quantitative claim",
            }
        ],
    }
    unsupported_record = _with_payload(
        unsupported_base,
        unsupported_payload,
        gate_state="insufficient_evidence",
    )
    unsupported_result = verifier.evaluate(record=unsupported_record)

    gates = {
        "positive_quant_handoff": positive_result.passed
        and positive_result.readiness_level.value == "economic_handoff_ready",
        "unproven_readback_fail_closed": (not unproven_result.passed)
        and unproven_result.blocking_gate is not None
        and unproven_result.blocking_gate.value == "storage_readback",
        "stale_assumption_blocks_quant": (not stale_result.passed)
        and stale_result.blocking_gate is not None
        and stale_result.blocking_gate.value == "assumption_staleness",
        "missing_parameter_support_fail_closed": (not missing_params_result.passed)
        and missing_params_result.blocking_gate is not None
        and missing_params_result.blocking_gate.value == "parameter_readiness",
        "qualitative_only_allowed": qual_result.passed
        and qual_result.readiness_level.value == "qualitative_only",
        "unsupported_claim_fail_closed_compatible": (not unsupported_result.passed)
        and unsupported_result.blocking_gate is not None
        and unsupported_result.blocking_gate.value == "parameter_readiness",
    }

    payload = {
        "feature_key": "bd-3wefe.5",
        "generated_at": VERIFY_TS,
        "report_version": "2026-04-15.policy-evidence-package-sufficiency.v1",
        "gates": {name: {"status": "passed" if ok else "failed"} for name, ok in gates.items()},
        "cases": {
            "positive": _result_to_json(positive_result),
            "unproven_readback": _result_to_json(unproven_result),
            "stale_assumption": _result_to_json(stale_result),
            "missing_parameter_support": _result_to_json(missing_params_result),
            "qualitative_only": _result_to_json(qual_result),
            "unsupported_claim_fail_closed": _result_to_json(unsupported_result),
        },
        "recommendations_for_bd_3wefe_6": sorted(
            {
                *positive_result.recommendations_for_bd_3wefe_6,
                *unproven_result.recommendations_for_bd_3wefe_6,
                *stale_result.recommendations_for_bd_3wefe_6,
                *missing_params_result.recommendations_for_bd_3wefe_6,
                *qual_result.recommendations_for_bd_3wefe_6,
                *unsupported_result.recommendations_for_bd_3wefe_6,
            }
        ),
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
    failed = [name for name, gate in report["gates"].items() if gate["status"] != "passed"]
    print(
        "policy_evidence_package_sufficiency verification complete: "
        f"gates_passed={len(report['gates']) - len(failed)}/{len(report['gates'])}"
    )
    if failed:
        print(f"failed_gates={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
