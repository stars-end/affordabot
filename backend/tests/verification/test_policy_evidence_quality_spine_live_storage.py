from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


def _load_module():
    root = Path(__file__).resolve().parents[3]
    script_path = (
        root
        / "backend"
        / "scripts"
        / "verification"
        / "verify_policy_evidence_quality_spine_live_storage.py"
    )
    spec = importlib.util.spec_from_file_location("quality_spine_live_storage", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load quality spine live storage module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeDbProbe:
    def __init__(
        self,
        *,
        linkage_status: str = "pass",
        linkage_detail: str = "ok",
        run_exists: bool = True,
        steps: list[dict[str, Any]] | None = None,
        idempotency_runs: int = 1,
        chunks_total: int = 4,
        chunks_with_embedding: int = 4,
    ) -> None:
        self._linkage_status = linkage_status
        self._linkage_detail = linkage_detail
        self._run_exists = run_exists
        self._steps = steps or [
            {
                "command": "index",
                "status": "succeeded",
                "refs": {"document_id": "doc-1"},
            }
        ]
        self._idempotency_runs = idempotency_runs
        self._chunks_total = chunks_total
        self._chunks_with_embedding = chunks_with_embedding

    def policy_package_linkage(self, *, package_id: str, backend_run_id: str | None):
        evidence = {"package_id": package_id, "backend_run_id": backend_run_id}
        return self._linkage_status, self._linkage_detail, evidence

    def pipeline_run_exists(self, *, run_id: str) -> bool:
        return self._run_exists

    def pipeline_steps(self, *, run_id: str) -> list[dict[str, Any]]:
        return list(self._steps)

    def runs_by_idempotency(self, *, idempotency_key: str) -> int:
        return self._idempotency_runs

    def document_chunk_stats(self, *, document_id: str) -> tuple[int, int]:
        return self._chunks_total, self._chunks_with_embedding


class _FakeArtifactProbe:
    def __init__(self, *, failures: dict[str, str] | None = None) -> None:
        self.failures = failures or {}

    def read_bytes(self, *, ref: str) -> tuple[bool, str]:
        if ref in self.failures:
            return False, self.failures[ref]
        return True, "bytes=128"


def _inputs(module):
    return module.StorageProbeInputs(
        package_id="pkg-sj-parking-minimum-amendment",
        canonical_document_key="san_jose_ca::sj-parking-minimum-amendment",
        backend_run_id="run-1",
        windmill_job_id="job-1",
        idempotency_key="idem-1",
        artifact_refs=["artifacts/test-object.md"],
        pgvector_truth_role="derived_index",
    )


def test_load_inputs_extracts_nested_backend_run_id_and_artifact_refs(tmp_path) -> None:
    module = _load_module()
    runtime = {
        "vertical_package_payload": {
            "package_id": "pkg-1",
            "canonical_document_key": "san_jose_ca::case-1",
            "storage_refs": [
                {
                    "storage_system": "pgvector",
                    "truth_role": "derived_index",
                }
            ],
        }
    }
    windmill = {
        "manual_run": {
            "windmill_job_id": "019d94d2-81ef-1117-0353-4c40719876ed",
        },
        "result_payload": {
            "scope_results": [
                {
                    "backend_response": {
                        "refs": {
                            "run_id": "6695fe26-eaaf-47d1-9100-7eb861a7aa2f",
                        }
                    },
                    "steps": {
                        "read_fetch": {
                            "refs": {
                                "artifact_refs": ["artifacts/live/reader_output.md"],
                            }
                        }
                    },
                }
            ]
        },
    }
    runtime_path = tmp_path / "runtime.json"
    windmill_path = tmp_path / "windmill.json"
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    windmill_path.write_text(json.dumps(windmill), encoding="utf-8")

    inputs = module.load_inputs(runtime_path=runtime_path, windmill_path=windmill_path)
    assert inputs.package_id == "pkg-1"
    assert inputs.backend_run_id == "6695fe26-eaaf-47d1-9100-7eb861a7aa2f"
    assert inputs.artifact_refs == ["artifacts/live/reader_output.md"]
    assert inputs.pgvector_truth_role == "derived_index"


def test_load_inputs_from_live_cycle_without_runtime_extracts_package_and_refs(tmp_path) -> None:
    module = _load_module()
    windmill = {
        "manual_run": {
            "windmill_job_id": "job-4",
            "idempotency_key": "idem-4",
        },
        "result_payload": {
            "scope_results": [
                {
                    "steps": {
                        "summarize_run": {
                            "refs": {
                                "backend_run_id": "run-4",
                                "package_id": "pkg-4",
                                "canonical_document_key": "v2|jurisdiction=san-jose-ca|family=meeting_minutes",
                                "reader_artifact_uri": "minio://affordabot-artifacts/artifacts/reader-4.md",
                                "package_artifact_uri": "minio://affordabot-artifacts/policy-evidence/packages/pkg-4.json",
                            },
                            "details": {
                                "policy_evidence_package": {
                                    "storage_result": {
                                        "artifact_write_status": "succeeded",
                                        "artifact_readback_status": "proven",
                                        "pgvector_truth_role": "derived_index",
                                    }
                                }
                            },
                        }
                    }
                }
            ]
        },
    }
    windmill_path = tmp_path / "cycle4.json"
    windmill_path.write_text(json.dumps(windmill), encoding="utf-8")

    inputs = module.load_inputs(runtime_path=None, windmill_path=windmill_path)
    assert inputs.package_id == "pkg-4"
    assert inputs.canonical_document_key == "v2|jurisdiction=san-jose-ca|family=meeting_minutes"
    assert inputs.backend_run_id == "run-4"
    assert inputs.windmill_job_id == "job-4"
    assert inputs.idempotency_key == "idem-4"
    assert inputs.artifact_refs == [
        "minio://affordabot-artifacts/artifacts/reader-4.md",
        "minio://affordabot-artifacts/policy-evidence/packages/pkg-4.json",
    ]
    assert inputs.pgvector_truth_role == "derived_index"


def test_offline_mode_never_fakes_live_storage_pass() -> None:
    module = _load_module()
    report = module.evaluate_storage_proof(
        inputs=_inputs(module),
        live_mode="off",
        db_probe=None,
        artifact_probe=None,
    )

    assert report["status"] == "not_proven"
    assert report["gates"]["postgres_package_row"]["status"] == "not_proven"
    assert report["gates"]["minio_object_readback"]["status"] == "not_proven"
    assert report["gates"]["pgvector_derivation"]["status"] == "not_proven"
    assert report["gates"]["atomicity_or_replay"]["status"] == "not_proven"


def test_access_denied_fails_minio_gate_and_never_passes_overall() -> None:
    module = _load_module()
    db = _FakeDbProbe()
    artifact = _FakeArtifactProbe(failures={"artifacts/test-object.md": "download_error:AccessDenied"})

    report = module.evaluate_storage_proof(
        inputs=_inputs(module),
        live_mode="auto",
        db_probe=db,
        artifact_probe=artifact,
    )

    assert report["gates"]["minio_object_readback"]["status"] == "fail"
    assert report["status"] in {"fail", "not_proven"}
    assert report["status"] != "pass"


def test_missing_exact_package_linkage_is_not_proven() -> None:
    module = _load_module()
    db = _FakeDbProbe(
        linkage_status="not_proven",
        linkage_detail="package_row_exists_but_backend_run_linkage_missing",
    )
    artifact = _FakeArtifactProbe()

    report = module.evaluate_storage_proof(
        inputs=_inputs(module),
        live_mode="auto",
        db_probe=db,
        artifact_probe=artifact,
    )

    assert report["gates"]["postgres_package_row"]["status"] == "not_proven"
    assert report["status"] == "not_proven"


def test_fake_success_path_passes_all_storage_gates() -> None:
    module = _load_module()
    db = _FakeDbProbe(
        linkage_status="pass",
        linkage_detail="package_row_linked_to_backend_run_id",
        run_exists=True,
        idempotency_runs=2,
        chunks_total=10,
        chunks_with_embedding=10,
        steps=[
            {"command": "read_fetch", "status": "succeeded", "refs": {"document_id": "doc-1"}},
            {"command": "index", "status": "succeeded", "refs": {"document_id": "doc-1"}},
            {"command": "analyze", "status": "succeeded", "refs": {}},
        ],
    )
    artifact = _FakeArtifactProbe()

    report = module.evaluate_storage_proof(
        inputs=_inputs(module),
        live_mode="auto",
        db_probe=db,
        artifact_probe=artifact,
    )

    assert report["gates"]["postgres_package_row"]["status"] == "pass"
    assert report["gates"]["minio_object_readback"]["status"] == "pass"
    assert report["gates"]["pgvector_derivation"]["status"] == "pass"
    assert report["gates"]["atomicity_or_replay"]["status"] == "pass"
    assert report["status"] == "pass"


def test_build_live_probes_prefers_database_url_public_for_local_auto(monkeypatch) -> None:
    module = _load_module()
    captured: dict[str, Any] = {}

    class _FakeDb:
        def __init__(self, *, database_url: str) -> None:
            captured["database_url"] = database_url

    monkeypatch.setattr(module, "PsycopgDbProbe", _FakeDb)
    monkeypatch.setenv("DATABASE_URL", "postgresql://pgvector.railway.internal:5432/app")
    monkeypatch.setenv("DATABASE_URL_PUBLIC", "postgresql://public-host:5432/app")
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_ID", raising=False)
    monkeypatch.delenv("MINIO_URL", raising=False)
    monkeypatch.delenv("MINIO_URL_PUBLIC", raising=False)
    monkeypatch.delenv("RAILWAY_SERVICE_BUCKET_URL", raising=False)
    monkeypatch.delenv("S3_ENDPOINT", raising=False)
    monkeypatch.delenv("MINIO_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MINIO_SECRET_KEY", raising=False)
    monkeypatch.delenv("MINIO_BUCKET", raising=False)

    db_probe, artifact_probe = module._build_live_probes(live_mode="auto")
    assert db_probe is not None
    assert artifact_probe is None
    assert captured["database_url"] == "postgresql://public-host:5432/app"


def test_build_live_probes_normalizes_minio_endpoint(monkeypatch) -> None:
    module = _load_module()
    captured: dict[str, Any] = {}

    class _FakeStorage:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)
            self.client = object()

    monkeypatch.setattr(module, "S3Storage", _FakeStorage)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_PUBLIC", raising=False)
    monkeypatch.setenv("MINIO_URL", "http://bucket.railway.internal:9000/path")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "k")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("MINIO_BUCKET", "b")
    monkeypatch.setenv("MINIO_SECURE", "false")

    _db_probe, artifact_probe = module._build_live_probes(live_mode="auto")
    assert artifact_probe is not None
    assert captured["endpoint"] == "bucket.railway.internal:9000"


def test_build_live_probes_falls_back_to_default_storage_env_init(monkeypatch) -> None:
    module = _load_module()
    captured: dict[str, Any] = {}

    class _FakeStorage:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)
            self.client = object()

    monkeypatch.setattr(module, "S3Storage", _FakeStorage)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_PUBLIC", raising=False)
    monkeypatch.setenv("MINIO_URL", "http:///")
    monkeypatch.setenv("MINIO_URL_PUBLIC", "https://bucket-public.up.railway.app/")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "k")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("MINIO_BUCKET", "b")
    monkeypatch.setenv("MINIO_SECURE", "true")

    _db_probe, artifact_probe = module._build_live_probes(live_mode="auto")
    assert artifact_probe is not None
    assert "endpoint" not in captured
