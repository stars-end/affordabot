#!/usr/bin/env python3
"""Live storage/readback verifier for policy-evidence quality spine (bd-3wefe.13)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.storage.s3_storage import S3Storage  # noqa: E402


DEFAULT_RUNTIME_EVIDENCE = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "data_runtime_evidence.json"
)
DEFAULT_WINDMILL_EVIDENCE = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "quality_spine_live_windmill_domain_run.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "quality_spine_live_storage_probe.json"
)


GateStatus = str


@dataclass(frozen=True)
class StorageProbeInputs:
    package_id: str
    canonical_document_key: str
    backend_run_id: str | None
    windmill_job_id: str | None
    idempotency_key: str | None
    artifact_refs: list[str]
    pgvector_truth_role: str


class DbProbe(Protocol):
    def policy_package_linkage(
        self, *, package_id: str, backend_run_id: str | None
    ) -> tuple[GateStatus, str, dict[str, Any]]:
        ...

    def pipeline_run_exists(self, *, run_id: str) -> bool:
        ...

    def pipeline_steps(self, *, run_id: str) -> list[dict[str, Any]]:
        ...

    def runs_by_idempotency(self, *, idempotency_key: str) -> int:
        ...

    def document_chunk_stats(self, *, document_id: str) -> tuple[int, int]:
        ...


class ArtifactReadbackProbe(Protocol):
    def read_bytes(self, *, ref: str) -> tuple[bool, str]:
        ...


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def _extract_artifact_refs(payload: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()

    def _push(value: Any) -> None:
        if not isinstance(value, str):
            return
        normalized = value.strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        refs.append(normalized)

    def _from_steps(steps: Any) -> None:
        if not isinstance(steps, dict):
            return
        summarize_run = steps.get("summarize_run")
        if isinstance(summarize_run, dict):
            summarize_refs = summarize_run.get("refs")
            if isinstance(summarize_refs, dict):
                _push(summarize_refs.get("reader_artifact_uri"))
                _push(summarize_refs.get("package_artifact_uri"))
            summarize_details = summarize_run.get("details")
            if isinstance(summarize_details, dict):
                policy_pkg = summarize_details.get("policy_evidence_package")
                if isinstance(policy_pkg, dict):
                    pkg_refs = policy_pkg.get("refs")
                    if isinstance(pkg_refs, dict):
                        _push(pkg_refs.get("reader_artifact_uri"))
                        _push(pkg_refs.get("package_artifact_uri"))
        read_fetch = steps.get("read_fetch")
        if not isinstance(read_fetch, dict):
            return
        artifact_refs = read_fetch.get("artifact_refs")
        if isinstance(artifact_refs, list):
            for item in artifact_refs:
                _push(item)
        refs_obj = read_fetch.get("refs")
        if isinstance(refs_obj, dict):
            nested = refs_obj.get("artifact_refs")
            if isinstance(nested, list):
                for item in nested:
                    _push(item)

    _from_steps(payload.get("steps"))

    result_payload = payload.get("result_payload")
    if isinstance(result_payload, dict):
        scope_results = result_payload.get("scope_results")
        if isinstance(scope_results, list):
            for scope in scope_results:
                if not isinstance(scope, dict):
                    continue
                steps = scope.get("steps")
                if isinstance(steps, dict):
                    _from_steps(steps)

    return refs


def _extract_backend_run_id(payload: dict[str, Any]) -> str | None:
    scope = _extract_scope_result(payload)
    if isinstance(scope, dict):
        summarize_run = (scope.get("steps") or {}).get("summarize_run")
        if isinstance(summarize_run, dict):
            refs = summarize_run.get("refs")
            if isinstance(refs, dict):
                for key in ("backend_run_id", "run_id"):
                    run_id = refs.get(key)
                    if isinstance(run_id, str) and run_id.strip():
                        return run_id.strip()

    direct = payload.get("backend_run_id")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    result_payload = payload.get("result_payload")
    if not isinstance(result_payload, dict):
        return None
    scope_results = result_payload.get("scope_results")
    if not isinstance(scope_results, list):
        return None
    for scope in scope_results:
        if not isinstance(scope, dict):
            continue
        backend_response = scope.get("backend_response")
        if not isinstance(backend_response, dict):
            continue
        refs = backend_response.get("refs")
        if not isinstance(refs, dict):
            continue
        run_id = refs.get("run_id")
        if isinstance(run_id, str) and run_id.strip():
            return run_id.strip()
    return None


def _extract_scope_result(payload: dict[str, Any]) -> dict[str, Any] | None:
    result_payload = payload.get("result_payload")
    if not isinstance(result_payload, dict):
        return None
    scope_results = result_payload.get("scope_results")
    if not isinstance(scope_results, list):
        return None
    for scope in scope_results:
        if isinstance(scope, dict):
            return scope
    return None


def _extract_policy_refs(payload: dict[str, Any]) -> dict[str, Any]:
    scope = _extract_scope_result(payload)
    if not isinstance(scope, dict):
        return {}
    steps = scope.get("steps")
    if not isinstance(steps, dict):
        return {}
    summarize_run = steps.get("summarize_run")
    if not isinstance(summarize_run, dict):
        return {}
    refs = summarize_run.get("refs")
    if isinstance(refs, dict):
        return refs
    details = summarize_run.get("details")
    if not isinstance(details, dict):
        return {}
    package = details.get("policy_evidence_package")
    if not isinstance(package, dict):
        return {}
    package_refs = package.get("refs")
    return package_refs if isinstance(package_refs, dict) else {}


def _extract_idempotency_key(payload: dict[str, Any]) -> str | None:
    direct = payload.get("idempotency_key")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    manual_run = payload.get("manual_run")
    if isinstance(manual_run, dict):
        value = manual_run.get("idempotency_key")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_windmill_job_id(payload: dict[str, Any]) -> str | None:
    manual_run = payload.get("manual_run")
    if isinstance(manual_run, dict):
        value = manual_run.get("windmill_job_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    refs = _extract_policy_refs(payload)
    value = refs.get("windmill_job_id") if isinstance(refs, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _extract_pgvector_truth_role(runtime_payload: dict[str, Any] | None, windmill_payload: dict[str, Any]) -> str:
    if isinstance(runtime_payload, dict):
        package = runtime_payload.get("vertical_package_payload")
        if isinstance(package, dict):
            refs = package.get("storage_refs")
            if isinstance(refs, list):
                for item in refs:
                    if not isinstance(item, dict):
                        continue
                    if str(item.get("storage_system") or "") == "pgvector":
                        role = str(item.get("truth_role") or "").strip()
                        if role:
                            return role

    scope = _extract_scope_result(windmill_payload)
    if isinstance(scope, dict):
        steps = scope.get("steps")
        if isinstance(steps, dict):
            summarize_run = steps.get("summarize_run")
            if isinstance(summarize_run, dict):
                details = summarize_run.get("details")
                if isinstance(details, dict):
                    package = details.get("policy_evidence_package")
                    if isinstance(package, dict):
                        storage_result = package.get("storage_result")
                        if isinstance(storage_result, dict):
                            role = str(storage_result.get("pgvector_truth_role") or "").strip()
                            if role:
                                return role

    return "unknown"


def _extract_package_id_and_document_key(
    runtime_payload: dict[str, Any] | None, windmill_payload: dict[str, Any]
) -> tuple[str, str]:
    if isinstance(runtime_payload, dict):
        package = runtime_payload.get("vertical_package_payload")
        if isinstance(package, dict):
            package_id = str(package.get("package_id") or "")
            canonical_document_key = str(package.get("canonical_document_key") or "")
            if package_id or canonical_document_key:
                return package_id, canonical_document_key

    refs = _extract_policy_refs(windmill_payload)
    if isinstance(refs, dict):
        return (
            str(refs.get("package_id") or ""),
            str(refs.get("canonical_document_key") or ""),
        )

    return "", ""


def load_inputs(*, runtime_path: Path | None, windmill_path: Path) -> StorageProbeInputs:
    runtime_payload = _load_json(runtime_path) if runtime_path and runtime_path.exists() else None
    windmill_payload = _load_json(windmill_path)
    package_id, canonical_document_key = _extract_package_id_and_document_key(
        runtime_payload=runtime_payload,
        windmill_payload=windmill_payload,
    )
    return StorageProbeInputs(
        package_id=package_id,
        canonical_document_key=canonical_document_key,
        backend_run_id=_extract_backend_run_id(windmill_payload),
        windmill_job_id=_extract_windmill_job_id(windmill_payload),
        idempotency_key=_extract_idempotency_key(windmill_payload),
        artifact_refs=_extract_artifact_refs(windmill_payload),
        pgvector_truth_role=_extract_pgvector_truth_role(runtime_payload, windmill_payload),
    )


def _gate(status: GateStatus, details: str, **extra: Any) -> dict[str, Any]:
    payload = {"status": status, "details": details}
    payload.update(extra)
    return payload


def _classify_overall(core_gates: dict[str, dict[str, Any]]) -> tuple[GateStatus, str]:
    statuses = [str(core_gates[key]["status"]) for key in sorted(core_gates.keys())]
    if any(status == "fail" for status in statuses):
        return "fail", "one_or_more_storage_gates_failed"
    if all(status == "pass" for status in statuses):
        return "pass", "all_storage_gates_passed"
    return "not_proven", "one_or_more_storage_gates_not_proven"


def _extract_document_id(steps: list[dict[str, Any]]) -> str | None:
    for step in steps:
        refs = step.get("refs")
        if not isinstance(refs, dict):
            continue
        document_id = refs.get("document_id")
        if document_id:
            return str(document_id)
    return None


class PsycopgDbProbe:
    def __init__(self, *, database_url: str) -> None:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        self._psycopg2 = psycopg2
        self._RealDictCursor = RealDictCursor
        self._database_url = database_url

    def _connect(self):
        return self._psycopg2.connect(self._database_url)

    def _table_exists(self, table_name: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
                row = cur.fetchone()
        return bool(row and row[0])

    def _policy_package_row(self, *, package_id: str) -> dict[str, Any] | None:
        if not self._table_exists("policy_evidence_packages"):
            return None
        query = (
            "SELECT id, package_id, package_payload "
            "FROM public.policy_evidence_packages "
            "WHERE package_id = %s "
            "ORDER BY updated_at DESC NULLS LAST "
            "LIMIT 1"
        )
        with self._connect() as conn:
            with conn.cursor(cursor_factory=self._RealDictCursor) as cur:
                cur.execute(query, (package_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def policy_package_linkage(
        self, *, package_id: str, backend_run_id: str | None
    ) -> tuple[GateStatus, str, dict[str, Any]]:
        if not self._table_exists("policy_evidence_packages"):
            return (
                "not_proven",
                "policy_evidence_packages_table_missing",
                {"table_exists": False},
            )
        row = self._policy_package_row(package_id=package_id)
        if not row:
            return (
                "not_proven",
                "policy_evidence_package_row_missing_for_package_id",
                {"table_exists": True, "package_id": package_id},
            )
        payload = row.get("package_payload")
        if not isinstance(payload, dict):
            payload = {}
        run_context = payload.get("run_context")
        if not isinstance(run_context, dict):
            run_context = {}
        linked_backend_run_id = run_context.get("backend_run_id") or payload.get(
            "backend_run_id"
        )
        if backend_run_id and str(linked_backend_run_id or "") == backend_run_id:
            return (
                "pass",
                "package_row_linked_to_backend_run_id",
                {"table_exists": True, "record_id": str(row["id"])},
            )
        return (
            "not_proven",
            "package_row_exists_but_backend_run_linkage_missing",
            {
                "table_exists": True,
                "record_id": str(row["id"]),
                "expected_backend_run_id": backend_run_id,
                "linked_backend_run_id": linked_backend_run_id,
            },
        )

    def pipeline_run_exists(self, *, run_id: str) -> bool:
        query = "SELECT id FROM public.pipeline_runs WHERE id::text = %s LIMIT 1"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (run_id,))
                row = cur.fetchone()
        return bool(row)

    def pipeline_steps(self, *, run_id: str) -> list[dict[str, Any]]:
        query = (
            "SELECT command, status, refs "
            "FROM public.pipeline_steps "
            "WHERE run_id::text = %s "
            "ORDER BY step_number ASC, created_at ASC"
        )
        with self._connect() as conn:
            with conn.cursor(cursor_factory=self._RealDictCursor) as cur:
                cur.execute(query, (run_id,))
                rows = cur.fetchall()
        return [dict(row) for row in rows]

    def runs_by_idempotency(self, *, idempotency_key: str) -> int:
        query = "SELECT COUNT(*)::int AS count FROM public.pipeline_runs WHERE idempotency_key = %s"
        with self._connect() as conn:
            with conn.cursor(cursor_factory=self._RealDictCursor) as cur:
                cur.execute(query, (idempotency_key,))
                row = cur.fetchone()
        return int((row or {}).get("count") or 0)

    def document_chunk_stats(self, *, document_id: str) -> tuple[int, int]:
        query = (
            "SELECT "
            "COUNT(*)::int AS total, "
            "COUNT(*) FILTER (WHERE embedding IS NOT NULL)::int AS with_embedding "
            "FROM public.document_chunks "
            "WHERE document_id::text = %s"
        )
        with self._connect() as conn:
            with conn.cursor(cursor_factory=self._RealDictCursor) as cur:
                cur.execute(query, (document_id,))
                row = cur.fetchone()
        row = dict(row or {})
        return int(row.get("total") or 0), int(row.get("with_embedding") or 0)


class MinioReadbackProbe:
    def __init__(self, *, storage: S3Storage) -> None:
        self.storage = storage
        self.last_error: str | None = None

    @staticmethod
    def _to_key(ref: str, *, expected_bucket: str) -> tuple[str | None, str]:
        if ref.startswith("minio://"):
            parsed = urlparse(ref)
            if parsed.scheme != "minio":
                return None, "unsupported_uri_scheme"
            bucket = parsed.netloc
            if bucket != expected_bucket:
                return None, "bucket_mismatch"
            return parsed.path.lstrip("/"), "ok"
        if ref.startswith("artifacts/"):
            return ref, "ok"
        return None, "unsupported_ref_format"

    def read_bytes(self, *, ref: str) -> tuple[bool, str]:
        key, reason = self._to_key(ref, expected_bucket=self.storage.bucket)
        if not key:
            return False, reason
        import asyncio

        try:
            data = asyncio.run(self.storage.download(path=key))
        except Exception as exc:  # noqa: BLE001
            self.last_error = type(exc).__name__
            return False, f"download_error:{type(exc).__name__}"
        if not data:
            return False, "empty_object"
        return True, f"bytes={len(data)}"


def evaluate_storage_proof(
    *,
    inputs: StorageProbeInputs,
    live_mode: str,
    db_probe: DbProbe | None,
    artifact_probe: ArtifactReadbackProbe | None,
) -> dict[str, Any]:
    core_gates: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []
    supporting: dict[str, Any] = {
        "artifact_refs_count": len(inputs.artifact_refs),
        "package_id": inputs.package_id,
        "backend_run_id": inputs.backend_run_id,
        "windmill_job_id": inputs.windmill_job_id,
    }

    if not inputs.package_id:
        core_gates["postgres_package_row"] = _gate("fail", "package_id_missing_in_runtime_artifact")
        blockers.append("package_id_missing")
    elif live_mode == "off":
        core_gates["postgres_package_row"] = _gate(
            "not_proven",
            "offline_mode_no_live_postgres_probe",
            missing="exact_policy_evidence_package_row_linked_to_backend_run",
        )
    elif db_probe is None:
        core_gates["postgres_package_row"] = _gate(
            "not_proven",
            "database_probe_unavailable",
            missing="exact_policy_evidence_package_row_linked_to_backend_run",
            requirements="DATABASE_URL_or_psycopg2",
        )
    else:
        status, details, evidence = db_probe.policy_package_linkage(
            package_id=inputs.package_id,
            backend_run_id=inputs.backend_run_id,
        )
        core_gates["postgres_package_row"] = _gate(status, details, evidence=evidence)
        if status != "pass":
            blockers.append("postgres_package_row_not_linked")

    if not inputs.artifact_refs:
        core_gates["minio_object_readback"] = _gate("not_proven", "artifact_refs_missing_for_live_run")
        blockers.append("artifact_refs_missing")
    elif live_mode == "off":
        core_gates["minio_object_readback"] = _gate(
            "not_proven",
            "offline_mode_no_live_minio_probe",
            missing="live_minio_readback_for_current_refs",
        )
    elif artifact_probe is None:
        core_gates["minio_object_readback"] = _gate(
            "not_proven",
            "artifact_probe_unavailable",
            missing="MINIO_env_or_client_init",
        )
    else:
        failures: list[dict[str, str]] = []
        passes = 0
        for ref in inputs.artifact_refs:
            ok, note = artifact_probe.read_bytes(ref=ref)
            if ok:
                passes += 1
            else:
                failures.append({"ref": ref, "reason": note})
        if failures:
            core_gates["minio_object_readback"] = _gate(
                "fail",
                "one_or_more_artifact_readbacks_failed",
                passed=passes,
                failed=len(failures),
                failures=failures,
            )
            blockers.append("minio_readback_failed")
        else:
            core_gates["minio_object_readback"] = _gate(
                "pass",
                "all_artifact_refs_read_back",
                passed=passes,
            )

    if inputs.pgvector_truth_role and inputs.pgvector_truth_role != "derived_index":
        core_gates["pgvector_derivation"] = _gate(
            "fail",
            "pgvector_truth_role_violation",
            truth_role=inputs.pgvector_truth_role,
        )
        blockers.append("pgvector_truth_role_violation")
    elif live_mode == "off":
        core_gates["pgvector_derivation"] = _gate(
            "not_proven",
            "offline_mode_no_live_document_chunks_probe",
            truth_role=inputs.pgvector_truth_role or "unknown",
        )
    elif db_probe is None:
        core_gates["pgvector_derivation"] = _gate(
            "not_proven",
            "database_probe_unavailable",
            truth_role=inputs.pgvector_truth_role or "unknown",
        )
    elif not inputs.backend_run_id or not db_probe.pipeline_run_exists(run_id=inputs.backend_run_id):
        core_gates["pgvector_derivation"] = _gate(
            "not_proven",
            "backend_run_missing_in_pipeline_runs",
        )
        blockers.append("backend_run_missing")
    else:
        steps = db_probe.pipeline_steps(run_id=inputs.backend_run_id)
        document_id = _extract_document_id(steps)
        if not document_id:
            core_gates["pgvector_derivation"] = _gate(
                "not_proven",
                "document_id_missing_from_pipeline_step_refs",
            )
            blockers.append("document_id_missing")
        else:
            total, with_embedding = db_probe.document_chunk_stats(document_id=document_id)
            if total <= 0:
                core_gates["pgvector_derivation"] = _gate(
                    "fail",
                    "document_chunks_missing_for_document_id",
                    document_id=document_id,
                    total_chunks=total,
                    with_embedding=with_embedding,
                    truth_role=inputs.pgvector_truth_role or "unknown",
                )
                blockers.append("document_chunks_missing")
            elif with_embedding <= 0:
                core_gates["pgvector_derivation"] = _gate(
                    "not_proven",
                    "document_chunks_present_but_embeddings_missing",
                    document_id=document_id,
                    total_chunks=total,
                    with_embedding=with_embedding,
                    truth_role=inputs.pgvector_truth_role or "unknown",
                )
                blockers.append("embeddings_missing")
            else:
                core_gates["pgvector_derivation"] = _gate(
                    "pass",
                    "document_chunks_and_embeddings_present_with_derived_index_truth_role",
                    document_id=document_id,
                    total_chunks=total,
                    with_embedding=with_embedding,
                    truth_role=inputs.pgvector_truth_role or "unknown",
                )

    if live_mode == "off":
        core_gates["atomicity_or_replay"] = _gate(
            "not_proven",
            "offline_mode_no_live_replay_probe",
            missing="pipeline_runs_idempotency_observation",
        )
    elif db_probe is None:
        core_gates["atomicity_or_replay"] = _gate(
            "not_proven",
            "database_probe_unavailable",
            missing="DATABASE_URL_or_psycopg2",
        )
    elif not inputs.backend_run_id:
        core_gates["atomicity_or_replay"] = _gate("not_proven", "backend_run_id_missing")
        blockers.append("backend_run_id_missing")
    elif not db_probe.pipeline_run_exists(run_id=inputs.backend_run_id):
        core_gates["atomicity_or_replay"] = _gate(
            "not_proven",
            "backend_run_missing_in_pipeline_runs",
        )
        blockers.append("backend_run_missing")
    else:
        runs_for_idempotency = (
            db_probe.runs_by_idempotency(idempotency_key=inputs.idempotency_key)
            if inputs.idempotency_key
            else 0
        )
        steps = db_probe.pipeline_steps(run_id=inputs.backend_run_id)
        statuses = {str(step.get("status") or "") for step in steps}
        failed_statuses = statuses.intersection({"failed_terminal", "failed_retryable"})
        if failed_statuses:
            core_gates["atomicity_or_replay"] = _gate(
                "fail",
                "run_contains_failed_steps",
                failed_statuses=sorted(failed_statuses),
                runs_for_idempotency=runs_for_idempotency,
            )
            blockers.append("failed_steps_present")
        else:
            core_gates["atomicity_or_replay"] = _gate(
                "pass",
                "pipeline_run_is_terminal_without_failed_steps",
                runs_for_idempotency=runs_for_idempotency,
                idempotent_replay_observed=runs_for_idempotency > 1,
            )

    overall_status, overall_details = _classify_overall(core_gates)
    gates = dict(core_gates)
    gates["storage/read-back"] = _gate(overall_status, overall_details)
    if overall_status == "fail":
        blocker = "storage_gate_failed"
    elif overall_status == "not_proven":
        blocker = "missing_exact_policy_package_linkage_or_live_readback"
    else:
        blocker = None
    return {
        "generated_at": _utc_now(),
        "feature_key": "bd-3wefe.13",
        "status": overall_status,
        "blocker": blocker,
        "details": overall_details,
        "inputs": {
            "package_id": inputs.package_id,
            "canonical_document_key": inputs.canonical_document_key,
            "backend_run_id": inputs.backend_run_id,
            "windmill_job_id": inputs.windmill_job_id,
            "idempotency_key": inputs.idempotency_key,
            "artifact_refs": inputs.artifact_refs,
            "pgvector_truth_role": inputs.pgvector_truth_role,
        },
        "gates": gates,
        "supporting_signals": supporting,
        "missing_or_failed_signals": sorted(set(blockers)),
    }


def _env_present(name: str) -> bool:
    return bool(str(os.getenv(name, "")).strip())


def _is_local_live_auto_mode(*, live_mode: str) -> bool:
    return live_mode == "auto" and not _env_present("RAILWAY_ENVIRONMENT_ID")


def _database_url_for_live_probe(*, live_mode: str) -> str | None:
    # `railway run` executes locally with Railway metadata/env injected, so the
    # private DATABASE_URL host is still not resolvable from the agent machine.
    # Prefer the public URL whenever Railway exposes it; in-container probes can
    # also use the public URL safely.
    if live_mode == "auto" and _env_present("DATABASE_URL_PUBLIC"):
        return str(os.environ["DATABASE_URL_PUBLIC"])
    if _env_present("DATABASE_URL"):
        return str(os.environ["DATABASE_URL"])
    return None


def _normalize_minio_endpoint_for_sdk(raw: str) -> str:
    candidate = str(raw or "").strip()
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    if parsed.scheme:
        host = parsed.netloc.strip()
        return host
    if "/" in candidate:
        return candidate.split("/", 1)[0].strip()
    return candidate


def _build_live_probes(*, live_mode: str) -> tuple[DbProbe | None, ArtifactReadbackProbe | None]:
    if live_mode == "off":
        return None, None

    db_probe: DbProbe | None = None
    artifact_probe: ArtifactReadbackProbe | None = None

    database_url = _database_url_for_live_probe(live_mode=live_mode)
    if database_url:
        try:
            db_probe = PsycopgDbProbe(database_url=database_url)
        except Exception:  # noqa: BLE001
            db_probe = None

    minio_auth_and_bucket = (
        _env_present("MINIO_URL"),
        _env_present("MINIO_ACCESS_KEY"),
        _env_present("MINIO_SECRET_KEY"),
        _env_present("MINIO_BUCKET"),
    )
    has_any_endpoint = any(
        (
            _env_present("MINIO_URL"),
            _env_present("MINIO_URL_PUBLIC"),
            _env_present("RAILWAY_SERVICE_BUCKET_URL"),
            _env_present("S3_ENDPOINT"),
        )
    )
    if all(minio_auth_and_bucket[1:]) and has_any_endpoint:
        try:
            endpoint = _normalize_minio_endpoint_for_sdk(str(os.getenv("MINIO_URL", "")))
            storage_kwargs: dict[str, Any] = dict(
                access_key=str(os.environ["MINIO_ACCESS_KEY"]),
                secret_key=str(os.environ["MINIO_SECRET_KEY"]),
                bucket=str(os.environ["MINIO_BUCKET"]),
                secure=str(os.getenv("MINIO_SECURE", "false")).lower() == "true",
            )
            # When Railway exposes a public bucket URL, let S3Storage choose it
            # via its env-based resolver instead of forcing the private
            # bucket.railway.internal endpoint into a local probe.
            if endpoint and not _env_present("RAILWAY_SERVICE_BUCKET_URL"):
                storage_kwargs["endpoint"] = endpoint
            storage = S3Storage(**storage_kwargs)
            if storage.client is not None:
                artifact_probe = MinioReadbackProbe(storage=storage)
        except Exception:  # noqa: BLE001
            artifact_probe = None
    return db_probe, artifact_probe


def run(
    *,
    runtime_path: Path | None,
    windmill_path: Path,
    out_path: Path,
    live_mode: str,
) -> dict[str, Any]:
    inputs = load_inputs(runtime_path=runtime_path, windmill_path=windmill_path)
    db_probe, artifact_probe = _build_live_probes(live_mode=live_mode)
    report = evaluate_storage_proof(
        inputs=inputs,
        live_mode=live_mode,
        db_probe=db_probe,
        artifact_probe=artifact_probe,
    )
    report["probe_mode"] = "live" if live_mode != "off" else "offline"
    report["inputs_artifacts"] = {
        "runtime": _repo_rel(runtime_path) if runtime_path else None,
        "windmill": _repo_rel(windmill_path),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=None)
    parser.add_argument("--windmill", type=Path, default=DEFAULT_WINDMILL_EVIDENCE)
    parser.add_argument(
        "--live-cycle-artifact",
        type=Path,
        default=None,
        help="Use live cycle JSON as the primary evidence source for package/run/artifact refs.",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--live-mode",
        choices=("off", "auto"),
        default="off",
        help="off=deterministic evidence classification only; auto=attempt live probes from env",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_path = args.runtime
    windmill_path = args.windmill
    if args.live_cycle_artifact:
        windmill_path = args.live_cycle_artifact
    elif runtime_path is None and DEFAULT_RUNTIME_EVIDENCE.exists():
        runtime_path = DEFAULT_RUNTIME_EVIDENCE

    report = run(
        runtime_path=runtime_path,
        windmill_path=windmill_path,
        out_path=args.out,
        live_mode=args.live_mode,
    )
    print(
        "policy_evidence_quality_spine_live_storage verification complete: "
        f"status={report['status']} "
        f"blocker={report.get('blocker') or 'none'}"
    )
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
