#!/usr/bin/env python3
"""Verifier for policy evidence package storage proof (bd-3wefe.10)."""

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
    PolicyEvidencePackageStorageService,
)


DEFAULT_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-package-storage"
    / "artifacts"
    / "policy_evidence_package_storage_report.json"
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
        storage_refs={
            "postgres_package_row": "policy_evidence_packages:pending",
            "reader_artifact": "minio://policy-evidence/reader/private_searxng/sj-13000001.txt",
            "pgvector_chunk_ref": "chunk:meeting-minutes-1",
        },
    )


def _gate(status: bool, note: str) -> dict[str, Any]:
    return {"status": "passed" if status else "failed", "note": note}


def run(out_path: Path) -> dict[str, Any]:
    base_package = _build_package(package_id="pkg-bd-3wefe-10")
    expected_artifact_uri = "minio://policy-evidence/packages/pkg-bd-3wefe-10.json"
    store = InMemoryPolicyEvidencePackageStore()
    writer = InMemoryArtifactWriter()
    service = PolicyEvidencePackageStorageService(
        store=store,
        artifact_writer=writer,
        artifact_probe=InMemoryArtifactProbe(
            known_uris={
                expected_artifact_uri,
                "minio://policy-evidence/reader/private_searxng/sj-13000001.txt",
            }
        ),
    )

    first = service.persist(package_payload=base_package, idempotency_key="idem-bd-3wefe-10")
    replay = service.persist(package_payload=base_package, idempotency_key="idem-bd-3wefe-10")

    artifact_fail = PolicyEvidencePackageStorageService(
        store=InMemoryPolicyEvidencePackageStore(),
        artifact_writer=InMemoryArtifactWriter(fail_next_write=True),
        artifact_probe=InMemoryArtifactProbe(),
    ).persist(
        package_payload=_build_package(package_id="pkg-artifact-drill"),
        idempotency_key="idem-artifact-drill",
    )

    db_fail_store = InMemoryPolicyEvidencePackageStore()
    db_fail_store.fail_next_upsert = True
    db_fail = PolicyEvidencePackageStorageService(
        store=db_fail_store,
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(),
    ).persist(
        package_payload=_build_package(package_id="pkg-db-drill"),
        idempotency_key="idem-db-drill",
    )

    storage_gates = {
        "postgres_row_written": _gate(
            first.stored and first.record_id is not None,
            f"record_id={first.record_id}",
        ),
        "idempotent_replay": _gate(
            replay.idempotent_reuse and replay.record_id == first.record_id,
            f"replay_reuse={replay.idempotent_reuse}",
        ),
        "pgvector_derived_only": _gate(
            first.pgvector_truth_role == "derived_index",
            f"pgvector_truth_role={first.pgvector_truth_role}",
        ),
        "minio_readback_proven": _gate(
            first.artifact_readback_status == "proven",
            f"artifact_readback_status={first.artifact_readback_status}",
        ),
        "artifact_failure_fail_closed": _gate(
            (not artifact_fail.stored) and artifact_fail.fail_closed and artifact_fail.failure_class == "artifact_write_failed",
            f"failure_class={artifact_fail.failure_class}",
        ),
        "db_failure_fail_closed": _gate(
            (not db_fail.stored) and db_fail.fail_closed and db_fail.failure_class == "db_upsert_failed",
            f"failure_class={db_fail.failure_class}",
        ),
    }

    payload = {
        "feature_key": "bd-3wefe.10",
        "generated_at": VERIFY_TS,
        "report_version": "2026-04-15.policy-evidence-package-storage.v1",
        "storage_gates": storage_gates,
        "first_persist_result": first.__dict__,
        "replay_result": replay.__dict__,
        "artifact_failure_drill": artifact_fail.__dict__,
        "db_failure_drill": db_fail.__dict__,
        "store_row_count": len(store.by_idempotency),
        "storage_boundary_assertions": {
            "postgres_truth": "policy_evidence_packages row stores package truth envelope",
            "minio_truth": "artifact refs require explicit readback proof; unproven is fail_closed",
            "pgvector_truth": "pgvector refs are derived_index only",
        },
        "live_runtime_note": (
            "Offline deterministic proof only. Live Railway/Postgres/MinIO smoke is not attempted by this verifier."
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
    failures = [name for name, gate in report["storage_gates"].items() if gate["status"] != "passed"]
    print(
        "policy_evidence_package_storage verification complete: "
        f"gates_passed={len(report['storage_gates']) - len(failures)}/{len(report['storage_gates'])}"
    )
    if failures:
        print(f"failed_gates={','.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
