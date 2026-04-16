from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.pipeline.policy_evidence_package_builder import PolicyEvidencePackageBuilder
from services.pipeline.policy_evidence_package_storage import (
    InMemoryArtifactProbe,
    InMemoryArtifactWriter,
    InMemoryPolicyEvidencePackageStore,
    PostgresPolicyEvidencePackageStore,
    PolicyEvidencePackageStorageService,
)


ROOT = Path(__file__).resolve().parents[4]
INTEGRATION_REPORT = (
    ROOT / "docs" / "poc" / "source-integration" / "artifacts" / "scrape_structured_integration_report.json"
)


def _load_envelopes() -> list[dict[str, Any]]:
    payload = json.loads(INTEGRATION_REPORT.read_text(encoding="utf-8"))
    return [dict(item) for item in payload.get("envelopes", []) if isinstance(item, dict)]


def _pick_envelope(*, source_lane: str, provider: str) -> dict[str, Any]:
    for envelope in _load_envelopes():
        if envelope.get("source_lane") == source_lane and envelope.get("provider") == provider:
            return envelope
    raise AssertionError(f"missing fixture envelope lane={source_lane} provider={provider}")


def _sample_package(*, package_id: str = "pkg-storage-proof") -> dict[str, Any]:
    scraped = _pick_envelope(source_lane="scrape_search", provider="private_searxng")
    structured = _pick_envelope(source_lane="structured", provider="legistar")
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


def test_storage_marks_minio_readback_unproven_without_probe() -> None:
    service = PolicyEvidencePackageStorageService(
        store=InMemoryPolicyEvidencePackageStore(),
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=None,
    )
    result = service.persist(
        package_payload=_sample_package(),
        idempotency_key="idem-unproven",
    )

    assert result.stored is True
    assert result.artifact_write_status == "succeeded"
    assert result.artifact_readback_status == "unproven"
    assert result.fail_closed is True


def test_storage_marks_minio_readback_proven_with_probe() -> None:
    writer = InMemoryArtifactWriter()
    expected_uri = "minio://policy-evidence/packages/pkg-storage-proof.json"
    existing_reader_uri = "minio://policy-evidence/reader/private_searxng/sj-13000001.txt"
    service = PolicyEvidencePackageStorageService(
        store=InMemoryPolicyEvidencePackageStore(),
        artifact_writer=writer,
        artifact_probe=InMemoryArtifactProbe(known_uris={expected_uri, existing_reader_uri}),
    )

    result = service.persist(
        package_payload=_sample_package(),
        idempotency_key="idem-proven",
    )

    assert result.stored is True
    assert result.artifact_readback_status == "proven"
    assert result.fail_closed is False
    assert expected_uri in writer.objects


def test_storage_replay_is_idempotent_and_reuses_same_record() -> None:
    store = InMemoryPolicyEvidencePackageStore()
    service = PolicyEvidencePackageStorageService(
        store=store,
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(
            known_uris={
                "minio://policy-evidence/packages/pkg-storage-proof.json",
                "minio://policy-evidence/reader/private_searxng/sj-13000001.txt",
            }
        ),
    )
    payload = _sample_package()

    first = service.persist(package_payload=payload, idempotency_key="idem-replay")
    second = service.persist(package_payload=payload, idempotency_key="idem-replay")

    assert first.stored is True
    assert second.stored is True
    assert second.idempotent_reuse is True
    assert second.record_id == first.record_id
    assert len(store.by_idempotency) == 1


def test_storage_replay_conflict_fails_closed_when_payload_changes() -> None:
    store = InMemoryPolicyEvidencePackageStore()
    service = PolicyEvidencePackageStorageService(
        store=store,
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(
            known_uris={
                "minio://policy-evidence/packages/pkg-storage-proof.json",
                "minio://policy-evidence/reader/private_searxng/sj-13000001.txt",
            }
        ),
    )
    payload = _sample_package()
    first = service.persist(package_payload=payload, idempotency_key="idem-replay-conflict")
    assert first.stored is True

    conflict_payload = dict(payload)
    conflict_payload["package_id"] = "pkg-storage-proof-conflict"
    second = service.persist(
        package_payload=conflict_payload,
        idempotency_key="idem-replay-conflict",
    )

    assert second.stored is False
    assert second.idempotent_reuse is False
    assert second.fail_closed is True
    assert second.failure_class == "idempotency_conflict"
    assert len(store.by_idempotency) == 1


def test_storage_probes_minio_reference_id_when_uri_missing() -> None:
    payload = _sample_package(package_id="pkg-storage-refid-probe")
    expected_uri = "minio://policy-evidence/packages/pkg-storage-refid-probe.json"
    reader_uri = "minio://policy-evidence/reader/private_searxng/sj-13000001.txt"
    for ref in payload["storage_refs"]:
        if ref["storage_system"] == "minio":
            ref.pop("uri", None)

    service = PolicyEvidencePackageStorageService(
        store=InMemoryPolicyEvidencePackageStore(),
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(known_uris={expected_uri, reader_uri}),
    )
    result = service.persist(
        package_payload=payload,
        idempotency_key="idem-refid-probe",
    )

    assert result.stored is True
    assert result.artifact_readback_status == "proven"
    assert result.fail_closed is False


def test_storage_rejects_pgvector_source_of_truth() -> None:
    payload = _sample_package()
    for ref in payload["storage_refs"]:
        if ref["storage_system"] == "pgvector":
            ref["truth_role"] = "source_of_truth"

    service = PolicyEvidencePackageStorageService(
        store=InMemoryPolicyEvidencePackageStore(),
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(),
    )
    result = service.persist(package_payload=payload, idempotency_key="idem-pgvector-violation")

    assert result.stored is False
    assert result.fail_closed is True
    assert result.failure_class == "schema_validation_failed"


def test_storage_fails_closed_and_rolls_back_on_artifact_write_failure() -> None:
    store = InMemoryPolicyEvidencePackageStore()
    service = PolicyEvidencePackageStorageService(
        store=store,
        artifact_writer=InMemoryArtifactWriter(fail_next_write=True),
        artifact_probe=InMemoryArtifactProbe(),
    )

    result = service.persist(
        package_payload=_sample_package(package_id="pkg-artifact-failure"),
        idempotency_key="idem-artifact-failure",
    )

    assert result.stored is False
    assert result.fail_closed is True
    assert result.failure_class == "artifact_write_failed"
    assert len(store.by_idempotency) == 0


def test_storage_fails_closed_on_db_write_failure() -> None:
    store = InMemoryPolicyEvidencePackageStore()
    store.fail_next_upsert = True
    service = PolicyEvidencePackageStorageService(
        store=store,
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(),
    )

    result = service.persist(
        package_payload=_sample_package(package_id="pkg-db-failure"),
        idempotency_key="idem-db-failure",
    )

    assert result.stored is False
    assert result.fail_closed is True
    assert result.failure_class == "db_upsert_failed"
    assert result.compensated_rollback is True
    assert len(store.by_idempotency) == 0


class _FakeDbState:
    def __init__(self) -> None:
        self.rows_by_idempotency: dict[str, dict[str, Any]] = {}


class _FakeConnection:
    def __init__(self, state: _FakeDbState) -> None:
        self.state = state
        self.committed = False

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    def cursor(self, cursor_factory: Any | None = None) -> "_FakeCursor":  # noqa: ARG002
        return _FakeCursor(self.state)

    def commit(self) -> None:
        self.committed = True


class _FakeCursor:
    def __init__(self, state: _FakeDbState) -> None:
        self.state = state
        self.fetchone_result: dict[str, Any] | None = None

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    def execute(self, query: str, args: tuple[Any, ...]) -> None:
        compact = " ".join(query.split())
        if "SELECT id, package_id, idempotency_key" in compact:
            idempotency_key = str(args[0])
            self.fetchone_result = self.state.rows_by_idempotency.get(idempotency_key)
            return
        if "INSERT INTO public.policy_evidence_packages" in compact:
            idempotency_key = str(args[2])
            existing = self.state.rows_by_idempotency.get(idempotency_key)
            created_at = existing["created_at"] if existing else args[18]
            row = {
                "id": args[0],
                "package_id": args[1],
                "idempotency_key": args[2],
                "content_hash": args[3],
                "schema_version": args[4],
                "jurisdiction": args[5],
                "canonical_document_key": args[6],
                "policy_identifier": args[7],
                "package_status": args[8],
                "economic_handoff_ready": args[9],
                "fail_closed": args[10],
                "gate_state": args[11],
                "insufficiency_reasons": args[12].adapted if hasattr(args[12], "adapted") else args[12],
                "storage_refs": args[13].adapted if hasattr(args[13], "adapted") else args[13],
                "package_payload": args[14].adapted if hasattr(args[14], "adapted") else args[14],
                "artifact_write_status": args[15],
                "artifact_readback_status": args[16],
                "pgvector_truth_role": args[17],
                "created_at": created_at,
                "updated_at": args[19],
            }
            self.state.rows_by_idempotency[idempotency_key] = row
            self.fetchone_result = row
            return
        if "DELETE FROM public.policy_evidence_packages WHERE idempotency_key = %s" in compact:
            idempotency_key = str(args[0])
            self.state.rows_by_idempotency.pop(idempotency_key, None)
            self.fetchone_result = None
            return
        raise AssertionError(f"unexpected query: {query}")

    def fetchone(self) -> dict[str, Any] | None:
        return self.fetchone_result


def _postgres_store_for_tests() -> tuple[PostgresPolicyEvidencePackageStore, _FakeDbState]:
    state = _FakeDbState()
    store = PostgresPolicyEvidencePackageStore(
        connection_factory=lambda: _FakeConnection(state),
    )
    return store, state


def test_postgres_store_roundtrip_includes_backend_run_context() -> None:
    store, _state = _postgres_store_for_tests()
    service = PolicyEvidencePackageStorageService(
        store=store,
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(
            known_uris={
                "minio://policy-evidence/packages/pkg-storage-proof.json",
                "minio://policy-evidence/reader/private_searxng/sj-13000001.txt",
            }
        ),
    )
    payload = _sample_package()
    payload["run_context"] = {"backend_run_id": "run-live-001"}

    persisted = service.persist(
        package_payload=payload,
        idempotency_key="idem-postgres-roundtrip",
    )

    assert persisted.stored is True
    fetched = store.get_by_idempotency(idempotency_key="idem-postgres-roundtrip")
    assert fetched is not None
    assert fetched.package_payload["run_context"]["backend_run_id"] == "run-live-001"


def test_postgres_store_idempotent_upsert_reuses_idempotency_key() -> None:
    store, state = _postgres_store_for_tests()
    service = PolicyEvidencePackageStorageService(
        store=store,
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(
            known_uris={
                "minio://policy-evidence/packages/pkg-storage-proof.json",
                "minio://policy-evidence/reader/private_searxng/sj-13000001.txt",
            }
        ),
    )
    payload = _sample_package()

    first = service.persist(package_payload=payload, idempotency_key="idem-postgres-replay")
    second = service.persist(package_payload=payload, idempotency_key="idem-postgres-replay")

    assert first.stored is True
    assert second.stored is True
    assert second.idempotent_reuse is True
    assert len(state.rows_by_idempotency) == 1


def test_storage_conflict_remains_fail_closed_with_postgres_store() -> None:
    store, state = _postgres_store_for_tests()
    service = PolicyEvidencePackageStorageService(
        store=store,
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(
            known_uris={
                "minio://policy-evidence/packages/pkg-storage-proof.json",
                "minio://policy-evidence/reader/private_searxng/sj-13000001.txt",
            }
        ),
    )
    payload = _sample_package()
    first = service.persist(package_payload=payload, idempotency_key="idem-postgres-conflict")
    assert first.stored is True

    changed = dict(payload)
    changed["package_id"] = "pkg-storage-proof-conflict-postgres"
    second = service.persist(package_payload=changed, idempotency_key="idem-postgres-conflict")

    assert second.stored is False
    assert second.fail_closed is True
    assert second.failure_class == "idempotency_conflict"
    assert len(state.rows_by_idempotency) == 1
