"""Storage proof harness for policy evidence packages (bd-3wefe.10).

This module provides a deterministic, Postgres-shaped persistence contract for
PolicyEvidencePackage and explicit storage-proof semantics for MinIO refs and
pgvector derived-index refs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import ValidationError

from schemas.policy_evidence_package import (
    PolicyEvidencePackage,
    StorageSystem,
    StorageTruthRole,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def stable_payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StorageResult:
    record_id: str | None
    package_id: str
    idempotency_key: str
    stored: bool
    idempotent_reuse: bool
    fail_closed: bool
    failure_class: str | None
    compensated_rollback: bool
    artifact_write_status: str
    artifact_readback_status: str
    pgvector_truth_role: str


@dataclass(frozen=True)
class PersistedPackageRecord:
    record_id: str
    package_id: str
    idempotency_key: str
    content_hash: str
    schema_version: str
    jurisdiction: str
    canonical_document_key: str
    policy_identifier: str
    package_status: str
    economic_handoff_ready: bool
    fail_closed: bool
    gate_state: str
    insufficiency_reasons: list[str]
    storage_refs: list[dict[str, Any]]
    package_payload: dict[str, Any]
    artifact_write_status: str
    artifact_readback_status: str
    pgvector_truth_role: str
    created_at: str
    updated_at: str

    def to_row_json(self) -> dict[str, Any]:
        return {
            "id": self.record_id,
            "package_id": self.package_id,
            "idempotency_key": self.idempotency_key,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "jurisdiction": self.jurisdiction,
            "canonical_document_key": self.canonical_document_key,
            "policy_identifier": self.policy_identifier,
            "package_status": self.package_status,
            "economic_handoff_ready": self.economic_handoff_ready,
            "fail_closed": self.fail_closed,
            "gate_state": self.gate_state,
            "insufficiency_reasons": self.insufficiency_reasons,
            "storage_refs": self.storage_refs,
            "package_payload": self.package_payload,
            "artifact_write_status": self.artifact_write_status,
            "artifact_readback_status": self.artifact_readback_status,
            "pgvector_truth_role": self.pgvector_truth_role,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class PolicyEvidencePackageStore(Protocol):
    def get_by_idempotency(self, *, idempotency_key: str) -> PersistedPackageRecord | None:
        ...

    def upsert(self, *, row: PersistedPackageRecord) -> PersistedPackageRecord:
        ...

    def delete_by_idempotency(self, *, idempotency_key: str) -> None:
        ...


class ArtifactWriter(Protocol):
    def write_package_artifact(self, *, package_id: str, payload: dict[str, Any]) -> str:
        ...


class ArtifactProbe(Protocol):
    def exists(self, *, uri: str) -> bool:
        ...


class InMemoryPolicyEvidencePackageStore(PolicyEvidencePackageStore):
    """Deterministic store used by tests/verifier when Postgres is unavailable."""

    def __init__(self) -> None:
        self.by_idempotency: dict[str, PersistedPackageRecord] = {}
        self.fail_next_upsert = False

    def get_by_idempotency(self, *, idempotency_key: str) -> PersistedPackageRecord | None:
        return self.by_idempotency.get(idempotency_key)

    def upsert(self, *, row: PersistedPackageRecord) -> PersistedPackageRecord:
        if self.fail_next_upsert:
            self.fail_next_upsert = False
            raise RuntimeError("db_upsert_failed")

        existing = self.by_idempotency.get(row.idempotency_key)
        if existing:
            updated = PersistedPackageRecord(
                record_id=existing.record_id,
                package_id=row.package_id,
                idempotency_key=row.idempotency_key,
                content_hash=row.content_hash,
                schema_version=row.schema_version,
                jurisdiction=row.jurisdiction,
                canonical_document_key=row.canonical_document_key,
                policy_identifier=row.policy_identifier,
                package_status=row.package_status,
                economic_handoff_ready=row.economic_handoff_ready,
                fail_closed=row.fail_closed,
                gate_state=row.gate_state,
                insufficiency_reasons=row.insufficiency_reasons,
                storage_refs=row.storage_refs,
                package_payload=row.package_payload,
                artifact_write_status=row.artifact_write_status,
                artifact_readback_status=row.artifact_readback_status,
                pgvector_truth_role=row.pgvector_truth_role,
                created_at=existing.created_at,
                updated_at=row.updated_at,
            )
            self.by_idempotency[row.idempotency_key] = updated
            return updated

        self.by_idempotency[row.idempotency_key] = row
        return row

    def delete_by_idempotency(self, *, idempotency_key: str) -> None:
        self.by_idempotency.pop(idempotency_key, None)


class PostgresPolicyEvidencePackageStore(PolicyEvidencePackageStore):
    """Postgres-backed adapter for policy_evidence_packages."""

    def __init__(
        self,
        *,
        database_url: str | None = None,
        connection_factory: Any | None = None,
    ) -> None:
        self.database_url = (
            database_url
            or os.getenv("DATABASE_URL_PUBLIC")
            or os.getenv("DATABASE_URL")
            or ""
        )
        self._connection_factory = connection_factory or self._default_connection_factory

    def _default_connection_factory(self) -> Any:
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not set")
        try:
            import psycopg2  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise RuntimeError("psycopg2_not_available") from exc
        return psycopg2.connect(self.database_url)

    @staticmethod
    def _real_dict_cursor() -> Any:
        try:
            from psycopg2.extras import RealDictCursor  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            return None
        return RealDictCursor

    @staticmethod
    def _json_param(value: Any) -> Any:
        try:
            from psycopg2.extras import Json  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            return json.dumps(value, ensure_ascii=True)
        return Json(value)

    @staticmethod
    def _json_value(value: Any, *, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default
        return value

    @staticmethod
    def _time_value(value: Any) -> str:
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        if isinstance(value, str):
            return value
        return _utc_now().isoformat()

    def _record_from_row(self, row: dict[str, Any]) -> PersistedPackageRecord:
        return PersistedPackageRecord(
            record_id=str(row["id"]),
            package_id=str(row["package_id"]),
            idempotency_key=str(row["idempotency_key"]),
            content_hash=str(row["content_hash"]),
            schema_version=str(row["schema_version"]),
            jurisdiction=str(row["jurisdiction"]),
            canonical_document_key=str(row["canonical_document_key"]),
            policy_identifier=str(row["policy_identifier"]),
            package_status=str(row["package_status"]),
            economic_handoff_ready=bool(row["economic_handoff_ready"]),
            fail_closed=bool(row["fail_closed"]),
            gate_state=str(row["gate_state"]),
            insufficiency_reasons=list(
                self._json_value(row.get("insufficiency_reasons"), default=[])
            ),
            storage_refs=list(self._json_value(row.get("storage_refs"), default=[])),
            package_payload=dict(self._json_value(row.get("package_payload"), default={})),
            artifact_write_status=str(row["artifact_write_status"]),
            artifact_readback_status=str(row["artifact_readback_status"]),
            pgvector_truth_role=str(row["pgvector_truth_role"]),
            created_at=self._time_value(row.get("created_at")),
            updated_at=self._time_value(row.get("updated_at")),
        )

    def get_by_idempotency(self, *, idempotency_key: str) -> PersistedPackageRecord | None:
        query = """
            SELECT id, package_id, idempotency_key, content_hash, schema_version, jurisdiction,
                   canonical_document_key, policy_identifier, package_status, economic_handoff_ready,
                   fail_closed, gate_state, insufficiency_reasons, storage_refs, package_payload,
                   artifact_write_status, artifact_readback_status, pgvector_truth_role,
                   created_at, updated_at
            FROM public.policy_evidence_packages
            WHERE idempotency_key = %s
            LIMIT 1
        """
        cursor_factory = self._real_dict_cursor()
        try:
            with self._connection_factory() as conn:
                with conn.cursor(cursor_factory=cursor_factory) as cursor:
                    cursor.execute(query, (idempotency_key,))
                    row = cursor.fetchone()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("db_read_failed") from exc
        if not row:
            return None
        return self._record_from_row(dict(row))

    def upsert(self, *, row: PersistedPackageRecord) -> PersistedPackageRecord:
        query = """
            INSERT INTO public.policy_evidence_packages (
                id, package_id, idempotency_key, content_hash, schema_version, jurisdiction,
                canonical_document_key, policy_identifier, package_status, economic_handoff_ready,
                fail_closed, gate_state, insufficiency_reasons, storage_refs, package_payload,
                artifact_write_status, artifact_readback_status, pgvector_truth_role, created_at, updated_at
            ) VALUES (
                %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s, %s::timestamptz, %s::timestamptz
            )
            ON CONFLICT (idempotency_key) DO UPDATE SET
                package_id = EXCLUDED.package_id,
                content_hash = EXCLUDED.content_hash,
                schema_version = EXCLUDED.schema_version,
                jurisdiction = EXCLUDED.jurisdiction,
                canonical_document_key = EXCLUDED.canonical_document_key,
                policy_identifier = EXCLUDED.policy_identifier,
                package_status = EXCLUDED.package_status,
                economic_handoff_ready = EXCLUDED.economic_handoff_ready,
                fail_closed = EXCLUDED.fail_closed,
                gate_state = EXCLUDED.gate_state,
                insufficiency_reasons = EXCLUDED.insufficiency_reasons,
                storage_refs = EXCLUDED.storage_refs,
                package_payload = EXCLUDED.package_payload,
                artifact_write_status = EXCLUDED.artifact_write_status,
                artifact_readback_status = EXCLUDED.artifact_readback_status,
                pgvector_truth_role = EXCLUDED.pgvector_truth_role,
                updated_at = EXCLUDED.updated_at
            RETURNING id, package_id, idempotency_key, content_hash, schema_version, jurisdiction,
                      canonical_document_key, policy_identifier, package_status, economic_handoff_ready,
                      fail_closed, gate_state, insufficiency_reasons, storage_refs, package_payload,
                      artifact_write_status, artifact_readback_status, pgvector_truth_role,
                      created_at, updated_at
        """
        args = (
            row.record_id,
            row.package_id,
            row.idempotency_key,
            row.content_hash,
            row.schema_version,
            row.jurisdiction,
            row.canonical_document_key,
            row.policy_identifier,
            row.package_status,
            row.economic_handoff_ready,
            row.fail_closed,
            row.gate_state,
            self._json_param(row.insufficiency_reasons),
            self._json_param(row.storage_refs),
            self._json_param(row.package_payload),
            row.artifact_write_status,
            row.artifact_readback_status,
            row.pgvector_truth_role,
            row.created_at,
            row.updated_at,
        )
        cursor_factory = self._real_dict_cursor()
        try:
            with self._connection_factory() as conn:
                with conn.cursor(cursor_factory=cursor_factory) as cursor:
                    cursor.execute(query, args)
                    saved = cursor.fetchone()
                    conn.commit()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("db_upsert_failed") from exc
        if not saved:
            raise RuntimeError("db_upsert_failed")
        return self._record_from_row(dict(saved))

    def delete_by_idempotency(self, *, idempotency_key: str) -> None:
        query = "DELETE FROM public.policy_evidence_packages WHERE idempotency_key = %s"
        try:
            with self._connection_factory() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (idempotency_key,))
                    conn.commit()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("db_delete_failed") from exc


class InMemoryArtifactWriter(ArtifactWriter):
    def __init__(self, *, fail_next_write: bool = False) -> None:
        self.fail_next_write = fail_next_write
        self.objects: dict[str, dict[str, Any]] = {}

    def write_package_artifact(self, *, package_id: str, payload: dict[str, Any]) -> str:
        if self.fail_next_write:
            self.fail_next_write = False
            raise RuntimeError("artifact_write_failed")
        uri = f"minio://policy-evidence/packages/{package_id}.json"
        self.objects[uri] = payload
        return uri


class InMemoryArtifactProbe(ArtifactProbe):
    def __init__(self, *, known_uris: set[str] | None = None) -> None:
        self.known_uris = known_uris or set()

    def exists(self, *, uri: str) -> bool:
        return uri in self.known_uris


class PolicyEvidencePackageStorageService:
    """Persist PolicyEvidencePackage to Postgres-shaped rows with fail-closed semantics."""

    def __init__(
        self,
        *,
        store: PolicyEvidencePackageStore,
        artifact_writer: ArtifactWriter | None = None,
        artifact_probe: ArtifactProbe | None = None,
    ) -> None:
        self.store = store
        self.artifact_writer = artifact_writer
        self.artifact_probe = artifact_probe

    def persist(
        self,
        *,
        package_payload: dict[str, Any],
        idempotency_key: str,
    ) -> StorageResult:
        try:
            package = PolicyEvidencePackage.model_validate(package_payload)
        except ValidationError:
            return StorageResult(
                record_id=None,
                package_id=str(package_payload.get("package_id") or "unknown"),
                idempotency_key=idempotency_key,
                stored=False,
                idempotent_reuse=False,
                fail_closed=True,
                failure_class="schema_validation_failed",
                compensated_rollback=False,
                artifact_write_status="not_started",
                artifact_readback_status="not_applicable",
                pgvector_truth_role="unknown",
            )
        normalized = package.model_dump(mode="json")
        raw_run_context = package_payload.get("run_context")
        if isinstance(raw_run_context, dict):
            backend_run_id = raw_run_context.get("backend_run_id")
            if backend_run_id is not None:
                normalized["run_context"] = {"backend_run_id": str(backend_run_id)}
        content_hash = stable_payload_hash(normalized)

        existing = self.store.get_by_idempotency(idempotency_key=idempotency_key)
        if existing:
            if (
                existing.package_id != package.package_id
                or existing.content_hash != content_hash
            ):
                return StorageResult(
                    record_id=existing.record_id,
                    package_id=package.package_id,
                    idempotency_key=idempotency_key,
                    stored=False,
                    idempotent_reuse=False,
                    fail_closed=True,
                    failure_class="idempotency_conflict",
                    compensated_rollback=False,
                    artifact_write_status="not_started",
                    artifact_readback_status="not_applicable",
                    pgvector_truth_role=existing.pgvector_truth_role,
                )

            return StorageResult(
                record_id=existing.record_id,
                package_id=existing.package_id,
                idempotency_key=idempotency_key,
                stored=True,
                idempotent_reuse=True,
                fail_closed=existing.fail_closed,
                failure_class=None,
                compensated_rollback=False,
                artifact_write_status=existing.artifact_write_status,
                artifact_readback_status=existing.artifact_readback_status,
                pgvector_truth_role=existing.pgvector_truth_role,
            )

        pgvector_truth_role = "missing"
        minio_uris: list[str] = []
        for ref in package.storage_refs:
            if ref.storage_system == StorageSystem.PGVECTOR:
                pgvector_truth_role = ref.truth_role.value
                if ref.truth_role != StorageTruthRole.DERIVED_INDEX:
                    return StorageResult(
                        record_id=None,
                        package_id=package.package_id,
                        idempotency_key=idempotency_key,
                        stored=False,
                        idempotent_reuse=False,
                        fail_closed=True,
                        failure_class="pgvector_truth_violation",
                        compensated_rollback=False,
                        artifact_write_status="not_started",
                        artifact_readback_status="not_applicable",
                        pgvector_truth_role=ref.truth_role.value,
                    )
            if ref.storage_system == StorageSystem.MINIO:
                probe_uri = ref.uri or (
                    ref.reference_id if "://" in ref.reference_id else None
                )
                if probe_uri:
                    minio_uris.append(probe_uri)

        artifact_write_status = "not_configured"
        written_uri = None
        if self.artifact_writer is not None:
            artifact_write_status = "attempted"
            try:
                written_uri = self.artifact_writer.write_package_artifact(
                    package_id=package.package_id,
                    payload=normalized,
                )
                artifact_write_status = "succeeded"
                minio_uris.append(written_uri)
            except RuntimeError:
                return StorageResult(
                    record_id=None,
                    package_id=package.package_id,
                    idempotency_key=idempotency_key,
                    stored=False,
                    idempotent_reuse=False,
                    fail_closed=True,
                    failure_class="artifact_write_failed",
                    compensated_rollback=False,
                    artifact_write_status="failed",
                    artifact_readback_status="not_applicable",
                    pgvector_truth_role=pgvector_truth_role,
                )

        artifact_readback_status = "not_present"
        if minio_uris:
            if self.artifact_probe is None:
                artifact_readback_status = "unproven"
            else:
                artifact_readback_status = (
                    "proven" if all(self.artifact_probe.exists(uri=uri) for uri in minio_uris) else "missing"
                )

        now = _utc_now().isoformat()
        fail_closed = (not package.economic_handoff_ready) or artifact_readback_status != "proven"
        gate_state = package.gate_projection.runtime_sufficiency_state.value
        row = PersistedPackageRecord(
            record_id=str(uuid5(NAMESPACE_URL, f"policy-evidence-package:{idempotency_key}")),
            package_id=package.package_id,
            idempotency_key=idempotency_key,
            content_hash=content_hash,
            schema_version=package.schema_version.value,
            jurisdiction=package.jurisdiction,
            canonical_document_key=package.canonical_document_key,
            policy_identifier=package.policy_identifier,
            package_status="stored" if not fail_closed else "stored_fail_closed",
            economic_handoff_ready=package.economic_handoff_ready,
            fail_closed=fail_closed,
            gate_state=gate_state,
            insufficiency_reasons=[reason.value for reason in package.insufficiency_reasons],
            storage_refs=[ref.model_dump(mode="json") for ref in package.storage_refs],
            package_payload=normalized,
            artifact_write_status=artifact_write_status,
            artifact_readback_status=artifact_readback_status,
            pgvector_truth_role=pgvector_truth_role,
            created_at=now,
            updated_at=now,
        )

        try:
            saved = self.store.upsert(row=row)
        except RuntimeError:
            if written_uri:
                self.store.delete_by_idempotency(idempotency_key=idempotency_key)
            return StorageResult(
                record_id=None,
                package_id=package.package_id,
                idempotency_key=idempotency_key,
                stored=False,
                idempotent_reuse=False,
                fail_closed=True,
                failure_class="db_upsert_failed",
                compensated_rollback=bool(written_uri),
                artifact_write_status=artifact_write_status,
                artifact_readback_status="not_applicable",
                pgvector_truth_role=pgvector_truth_role,
            )

        return StorageResult(
            record_id=saved.record_id,
            package_id=package.package_id,
            idempotency_key=idempotency_key,
            stored=True,
            idempotent_reuse=False,
            fail_closed=saved.fail_closed,
            failure_class=None,
            compensated_rollback=False,
            artifact_write_status=saved.artifact_write_status,
            artifact_readback_status=saved.artifact_readback_status,
            pgvector_truth_role=saved.pgvector_truth_role,
        )
