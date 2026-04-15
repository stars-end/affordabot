#!/usr/bin/env python3
"""Verifier for policy evidence package storage proof (bd-3wefe.10)."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.pipeline.policy_evidence_package_builder import PolicyEvidencePackageBuilder
from services.pipeline.policy_evidence_package_storage import (
    ArtifactProbe,
    ArtifactWriter,
    InMemoryArtifactProbe,
    InMemoryArtifactWriter,
    InMemoryPolicyEvidencePackageStore,
    PersistedPackageRecord,
    PolicyEvidencePackageStore,
    PolicyEvidencePackageStorageService,
)
from services.storage.s3_storage import S3Storage


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


def _build_package(*, package_id: str, reader_artifact_uri: str) -> dict[str, Any]:
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
            "reader_artifact": reader_artifact_uri,
            "pgvector_chunk_ref": "chunk:meeting-minutes-1",
        },
    )


def _gate(status: bool, note: str) -> dict[str, Any]:
    return {"status": "passed" if status else "failed", "note": note}


class LivePostgresStore(PolicyEvidencePackageStore):
    _COLUMNS = (
        "id, package_id, idempotency_key, content_hash, schema_version, jurisdiction, "
        "canonical_document_key, policy_identifier, package_status, economic_handoff_ready, "
        "fail_closed, gate_state, insufficiency_reasons, storage_refs, package_payload, "
        "artifact_write_status, artifact_readback_status, pgvector_truth_role, created_at, updated_at"
    )

    def __init__(self, *, database_url: str) -> None:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        self._psycopg2 = psycopg2
        self._RealDictCursor = RealDictCursor
        self.database_url = database_url
        self._ensure_table()

    def _connect(self):
        return self._psycopg2.connect(self.database_url)

    def _ensure_table(self) -> None:
        sql = """
CREATE TABLE IF NOT EXISTS public.policy_evidence_packages (
  id uuid PRIMARY KEY,
  package_id text NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  content_hash text NOT NULL,
  schema_version text NOT NULL,
  jurisdiction text NOT NULL,
  canonical_document_key text NOT NULL,
  policy_identifier text NOT NULL,
  package_status text NOT NULL,
  economic_handoff_ready boolean NOT NULL DEFAULT false,
  fail_closed boolean NOT NULL DEFAULT true,
  gate_state text NOT NULL,
  insufficiency_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  storage_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  package_payload jsonb NOT NULL,
  artifact_write_status text NOT NULL DEFAULT 'not_configured',
  artifact_readback_status text NOT NULL DEFAULT 'unproven',
  pgvector_truth_role text NOT NULL DEFAULT 'derived_index',
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now()
);
"""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()

    @staticmethod
    def _ts(value: Any) -> str:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    def _row_to_record(self, row: dict[str, Any]) -> PersistedPackageRecord:
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
            insufficiency_reasons=list(row["insufficiency_reasons"] or []),
            storage_refs=list(row["storage_refs"] or []),
            package_payload=dict(row["package_payload"] or {}),
            artifact_write_status=str(row["artifact_write_status"]),
            artifact_readback_status=str(row["artifact_readback_status"]),
            pgvector_truth_role=str(row["pgvector_truth_role"]),
            created_at=self._ts(row["created_at"]),
            updated_at=self._ts(row["updated_at"]),
        )

    def get_by_idempotency(self, *, idempotency_key: str) -> PersistedPackageRecord | None:
        sql = f"SELECT {self._COLUMNS} FROM public.policy_evidence_packages WHERE idempotency_key = %s LIMIT 1"
        with self._connect() as conn:
            with conn.cursor(cursor_factory=self._RealDictCursor) as cur:
                cur.execute(sql, (idempotency_key,))
                row = cur.fetchone()
        return self._row_to_record(row) if row else None

    def upsert(self, *, row: PersistedPackageRecord) -> PersistedPackageRecord:
        from psycopg2.extras import Json

        sql = f"""
INSERT INTO public.policy_evidence_packages (
  id, package_id, idempotency_key, content_hash, schema_version, jurisdiction,
  canonical_document_key, policy_identifier, package_status, economic_handoff_ready,
  fail_closed, gate_state, insufficiency_reasons, storage_refs, package_payload,
  artifact_write_status, artifact_readback_status, pgvector_truth_role, created_at, updated_at
) VALUES (
  %(id)s, %(package_id)s, %(idempotency_key)s, %(content_hash)s, %(schema_version)s, %(jurisdiction)s,
  %(canonical_document_key)s, %(policy_identifier)s, %(package_status)s, %(economic_handoff_ready)s,
  %(fail_closed)s, %(gate_state)s, %(insufficiency_reasons)s, %(storage_refs)s, %(package_payload)s,
  %(artifact_write_status)s, %(artifact_readback_status)s, %(pgvector_truth_role)s, %(created_at)s, %(updated_at)s
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
RETURNING {self._COLUMNS}
"""
        params = {
            "id": row.record_id,
            "package_id": row.package_id,
            "idempotency_key": row.idempotency_key,
            "content_hash": row.content_hash,
            "schema_version": row.schema_version,
            "jurisdiction": row.jurisdiction,
            "canonical_document_key": row.canonical_document_key,
            "policy_identifier": row.policy_identifier,
            "package_status": row.package_status,
            "economic_handoff_ready": row.economic_handoff_ready,
            "fail_closed": row.fail_closed,
            "gate_state": row.gate_state,
            "insufficiency_reasons": Json(row.insufficiency_reasons),
            "storage_refs": Json(row.storage_refs),
            "package_payload": Json(row.package_payload),
            "artifact_write_status": row.artifact_write_status,
            "artifact_readback_status": row.artifact_readback_status,
            "pgvector_truth_role": row.pgvector_truth_role,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        with self._connect() as conn:
            with conn.cursor(cursor_factory=self._RealDictCursor) as cur:
                cur.execute(sql, params)
                saved = cur.fetchone()
            conn.commit()
        if not saved:
            raise RuntimeError("db_upsert_failed")
        return self._row_to_record(saved)

    def delete_by_idempotency(self, *, idempotency_key: str) -> None:
        sql = "DELETE FROM public.policy_evidence_packages WHERE idempotency_key = %s"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (idempotency_key,))
            conn.commit()


class LiveMinioArtifactWriter(ArtifactWriter):
    def __init__(self, *, storage: S3Storage) -> None:
        self.storage = storage

    def write_package_artifact(self, *, package_id: str, payload: dict[str, Any]) -> str:
        path = f"policy-evidence/packages/{package_id}.json"
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        asyncio.run(self.storage.upload(path=path, content=body, content_type="application/json"))
        return f"minio://{self.storage.bucket}/{path}"


class LiveMinioArtifactProbe(ArtifactProbe):
    def __init__(self, *, storage: S3Storage) -> None:
        self.storage = storage

    def exists(self, *, uri: str) -> bool:
        parsed = urlparse(uri)
        if parsed.scheme != "minio":
            return False
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        if not bucket or not key:
            return False
        if bucket != self.storage.bucket:
            return False
        try:
            asyncio.run(self.storage.download(path=key))
            return True
        except Exception:  # noqa: BLE001
            return False


def _probe_railway_auth() -> dict[str, Any]:
    cmd = "~/agent-skills/scripts/dx-load-railway-auth.sh -- railway whoami"
    proc = subprocess.run(
        ["bash", "-lc", cmd],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "status": "passed" if proc.returncode == 0 else "blocked",
        "return_code": proc.returncode,
        "stdout_redacted": bool(proc.stdout.strip()),
        "stderr_redacted": bool(proc.stderr.strip()),
    }


def _run_live_probe(*, live_mode: str) -> dict[str, Any]:
    if live_mode == "off":
        return {"status": "skipped", "reason": "live_mode_off"}

    railway_auth = _probe_railway_auth()
    database_url = (
        os.getenv("POLICY_EVIDENCE_STORAGE_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("RAILWAY_DATABASE_URL")
    )
    storage = S3Storage()

    blockers: list[str] = []
    if not database_url:
        blockers.append("database_url_missing")
    if storage.client is None:
        blockers.append("minio_runtime_missing")
    if blockers:
        return {
            "status": "blocked",
            "blockers": blockers,
            "railway_auth_probe": railway_auth,
            "required_env_hints": [
                "DATABASE_URL or POLICY_EVIDENCE_STORAGE_DATABASE_URL",
                "MINIO_URL or S3_ENDPOINT",
                "MINIO_ACCESS_KEY or AWS_ACCESS_KEY_ID",
                "MINIO_SECRET_KEY or AWS_SECRET_ACCESS_KEY",
                "MINIO_BUCKET or S3_BUCKET_NAME",
            ],
        }

    package_id = "pkg-bd-3wefe-10-live"
    reader_artifact_uri = f"minio://{storage.bucket}/policy-evidence/packages/{package_id}.json"
    live_package = _build_package(package_id=package_id, reader_artifact_uri=reader_artifact_uri)
    idempotency_key = "idem-bd-3wefe-10-live"

    store = LivePostgresStore(database_url=str(database_url))
    service = PolicyEvidencePackageStorageService(
        store=store,
        artifact_writer=LiveMinioArtifactWriter(storage=storage),
        artifact_probe=LiveMinioArtifactProbe(storage=storage),
    )

    result = service.persist(package_payload=live_package, idempotency_key=idempotency_key)
    row = store.get_by_idempotency(idempotency_key=idempotency_key)

    # Best-effort cleanup for repeatable runs.
    store.delete_by_idempotency(idempotency_key=idempotency_key)

    passed = bool(
        result.stored
        and (not result.fail_closed)
        and result.artifact_readback_status == "proven"
        and row is not None
    )
    return {
        "status": "passed" if passed else "failed",
        "railway_auth_probe": railway_auth,
        "persist_result": asdict(result),
        "readback_row_present": row is not None,
        "readback_row_summary": {
            "record_id": row.record_id if row else None,
            "package_id": row.package_id if row else None,
            "artifact_readback_status": row.artifact_readback_status if row else None,
            "fail_closed": row.fail_closed if row else None,
        },
        "runtime_targets": {
            "postgres_table": "public.policy_evidence_packages",
            "minio_bucket": storage.bucket,
        },
    }


def run(out_path: Path, *, live_mode: str) -> dict[str, Any]:
    base_package = _build_package(
        package_id="pkg-bd-3wefe-10",
        reader_artifact_uri="minio://policy-evidence/reader/private_searxng/sj-13000001.txt",
    )
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
    replay_conflict = service.persist(
        package_payload=_build_package(
            package_id="pkg-bd-3wefe-10-conflict",
            reader_artifact_uri="minio://policy-evidence/reader/private_searxng/sj-13000001.txt",
        ),
        idempotency_key="idem-bd-3wefe-10",
    )

    artifact_fail = PolicyEvidencePackageStorageService(
        store=InMemoryPolicyEvidencePackageStore(),
        artifact_writer=InMemoryArtifactWriter(fail_next_write=True),
        artifact_probe=InMemoryArtifactProbe(),
    ).persist(
        package_payload=_build_package(
            package_id="pkg-artifact-drill",
            reader_artifact_uri="minio://policy-evidence/reader/private_searxng/pkg-artifact-drill.txt",
        ),
        idempotency_key="idem-artifact-drill",
    )

    db_fail_store = InMemoryPolicyEvidencePackageStore()
    db_fail_store.fail_next_upsert = True
    db_fail = PolicyEvidencePackageStorageService(
        store=db_fail_store,
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(),
    ).persist(
        package_payload=_build_package(
            package_id="pkg-db-drill",
            reader_artifact_uri="minio://policy-evidence/reader/private_searxng/pkg-db-drill.txt",
        ),
        idempotency_key="idem-db-drill",
    )
    live_probe = _run_live_probe(live_mode=live_mode)

    storage_gates = {
        "postgres_row_written": _gate(
            first.stored and first.record_id is not None,
            f"record_id={first.record_id}",
        ),
        "idempotent_replay": _gate(
            replay.idempotent_reuse and replay.record_id == first.record_id,
            f"replay_reuse={replay.idempotent_reuse}",
        ),
        "idempotency_conflict_fail_closed": _gate(
            (not replay_conflict.stored)
            and replay_conflict.fail_closed
            and replay_conflict.failure_class == "idempotency_conflict",
            f"failure_class={replay_conflict.failure_class}",
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
        "report_version": "2026-04-15.policy-evidence-package-storage.v2",
        "storage_gates": storage_gates,
        "first_persist_result": first.__dict__,
        "replay_result": replay.__dict__,
        "replay_conflict_result": replay_conflict.__dict__,
        "artifact_failure_drill": artifact_fail.__dict__,
        "db_failure_drill": db_fail.__dict__,
        "store_row_count": len(store.by_idempotency),
        "storage_boundary_assertions": {
            "postgres_truth": "policy_evidence_packages row stores package truth envelope",
            "minio_truth": "artifact refs require explicit readback proof; unproven is fail_closed",
            "pgvector_truth": "pgvector refs are derived_index only",
        },
        "deterministic_harness_status": "passed"
        if all(g["status"] == "passed" for g in storage_gates.values())
        else "failed",
        "live_probe": live_probe,
        "live_runtime_note": (
            "Live probe attempts real Postgres+MinIO when runtime env is available; otherwise records exact blockers."
        ),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path")
    parser.add_argument(
        "--live-mode",
        choices=["off", "auto", "required"],
        default="auto",
        help="off=skip live probe; auto=record blockers; required=fail if live probe is not passed",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run(args.out, live_mode=args.live_mode)
    failures = [name for name, gate in report["storage_gates"].items() if gate["status"] != "passed"]
    live_status = report.get("live_probe", {}).get("status")
    live_required_failed = args.live_mode == "required" and live_status != "passed"
    print(
        "policy_evidence_package_storage verification complete: "
        f"gates_passed={len(report['storage_gates']) - len(failures)}/{len(report['storage_gates'])} "
        f"live_status={live_status}"
    )
    if failures:
        print(f"failed_gates={','.join(failures)}")
        return 1
    if live_required_failed:
        print("failed_live_probe=required_mode")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
