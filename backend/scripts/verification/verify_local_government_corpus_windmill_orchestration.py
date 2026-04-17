#!/usr/bin/env python3
"""Verify/fail-close local-government corpus Windmill orchestration coverage."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MATRIX_PATH = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "local_government_corpus_matrix.json"
)
DEFAULT_SCORECARD_PATH = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "local_government_corpus_scorecard.json"
)
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "local_government_corpus_windmill_orchestration.json"
)
DEFAULT_WINDMILL_FLOW_PATH = "f/affordabot/pipeline_daily_refresh_domain_boundary__flow"
DEFAULT_WINDMILL_SCRIPT_PATH = "f/affordabot/pipeline_daily_refresh_domain_boundary"
DEFAULT_WINDMILL_WORKSPACE = "affordabot"
FEATURE_KEY = "bd-3wefe.13.4.4"
CONTRACT_VERSION = "2026-04-17.windmill-domain.v2"


@dataclass(frozen=True)
class WindmillContext:
    workspace: str
    flow_path: str
    script_path: str
    config_dir: str


@dataclass(frozen=True)
class LiveAttempt:
    corpus_row_id: str
    status: str
    orchestration_mode: str
    windmill_run_id: str | None
    windmill_job_id: str | None
    windmill_flow_path: str | None
    blocker_class: str | None
    blocker_detail: str | None
    command_client: str
    command_attempted: str
    flow_response_status: str | None
    backend_scope_status: str | None
    idempotency_key: str
    run_id_source: str | None
    job_id_source: str | None
    job_lookup_trace: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "corpus_row_id": self.corpus_row_id,
            "status": self.status,
            "orchestration_mode": self.orchestration_mode,
            "windmill_run_id": self.windmill_run_id,
            "windmill_job_id": self.windmill_job_id,
            "windmill_flow_path": self.windmill_flow_path,
            "blocker_class": self.blocker_class,
            "blocker_detail": self.blocker_detail,
            "command_client": self.command_client,
            "command_attempted": self.command_attempted,
            "flow_response_status": self.flow_response_status,
            "backend_scope_status": self.backend_scope_status,
            "idempotency_key": self.idempotency_key,
            "run_id_source": self.run_id_source,
            "job_id_source": self.job_id_source,
            "job_lookup_trace": list(self.job_lookup_trace),
        }


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _matrix_digest(matrix: dict[str, Any]) -> str:
    payload = json.dumps(matrix, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_last_json_object(text: str) -> dict[str, Any]:
    raw_text = text.strip()
    if raw_text:
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
    for line in reversed(text.splitlines()):
        raw = line.strip()
        if not raw.startswith("{"):
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _walk_strings(payload: Any) -> list[str]:
    values: list[str] = []
    if isinstance(payload, dict):
        for value in payload.values():
            values.extend(_walk_strings(value))
    elif isinstance(payload, list):
        for value in payload:
            values.extend(_walk_strings(value))
    elif isinstance(payload, str):
        values.append(payload)
    return values


def _contains_string(payload: Any, needle: str) -> bool:
    return any(needle in item for item in _walk_strings(payload))


def _is_seeded_windmill_ref(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    raw = value.strip()
    return raw.startswith("wm::") or raw.startswith("wm-job::")


def _authoritative_windmill_ref(value: Any, *, idempotency_key: str) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw == idempotency_key:
        return None
    if raw == "not_found":
        return None
    if _is_seeded_windmill_ref(raw):
        return None
    return raw


def _first_scope_result(flow_result: dict[str, Any]) -> dict[str, Any]:
    per_scope = flow_result.get("per_scope_pipeline")
    if isinstance(per_scope, list) and per_scope and isinstance(per_scope[0], dict):
        return per_scope[0]
    return {}


def _extract_flow_response_status(flow_result: dict[str, Any]) -> str | None:
    status = flow_result.get("status")
    return str(status) if status is not None else None


def _extract_backend_scope_status(flow_result: dict[str, Any]) -> str | None:
    scope = _first_scope_result(flow_result)
    backend = scope.get("backend_response")
    if isinstance(backend, dict) and backend.get("status"):
        return str(backend["status"])
    run_scope = (scope.get("steps") or {}).get("run_scope_pipeline")
    if isinstance(run_scope, dict) and run_scope.get("status"):
        return str(run_scope["status"])
    return None


def _extract_flow_refs(flow_result: dict[str, Any], *, idempotency_key: str) -> tuple[str | None, str | None]:
    run_candidates: list[Any] = [
        flow_result.get("windmill_run_id"),
        flow_result.get("flow_job_id"),
        flow_result.get("run_id"),
        flow_result.get("id"),
    ]
    job_candidates: list[Any] = [
        flow_result.get("windmill_job_id"),
        flow_result.get("job_id"),
    ]
    for container_key in ("job", "flow_job", "flow_run"):
        container = flow_result.get(container_key)
        if isinstance(container, dict):
            run_candidates.extend(
                [container.get("windmill_run_id"), container.get("flow_job_id"), container.get("run_id"), container.get("id")]
            )
            job_candidates.extend([container.get("windmill_job_id"), container.get("job_id"), container.get("id")])

    scope = _first_scope_result(flow_result)
    run_scope = (scope.get("steps") or {}).get("run_scope_pipeline")
    if isinstance(run_scope, dict):
        run_candidates.extend(
            [run_scope.get("windmill_run_id"), run_scope.get("flow_job_id"), run_scope.get("run_id"), run_scope.get("id")]
        )
        job_candidates.extend([run_scope.get("windmill_job_id"), run_scope.get("job_id"), run_scope.get("id")])

    run_id = next(
        (
            ref
            for ref in (
                _authoritative_windmill_ref(candidate, idempotency_key=idempotency_key) for candidate in run_candidates
            )
            if ref
        ),
        None,
    )
    job_id = next(
        (
            ref
            for ref in (
                _authoritative_windmill_ref(candidate, idempotency_key=idempotency_key) for candidate in job_candidates
            )
            if ref
        ),
        None,
    )
    return run_id, job_id


def _job_matches_idempotency(job: dict[str, Any], idempotency_key: str) -> bool:
    args = job.get("args")
    if isinstance(args, dict):
        raw = args.get("idempotency_key")
        if isinstance(raw, str) and (raw == idempotency_key or raw.startswith(f"{idempotency_key}::")):
            return True
    return _contains_string(job, idempotency_key)


def _find_job_for_idempotency(jobs: list[dict[str, Any]], idempotency_key: str) -> dict[str, Any] | None:
    for job in jobs:
        if _job_matches_idempotency(job, idempotency_key):
            return job
    return None


def _find_recent_flow_job(jobs: list[dict[str, Any]], *, flow_path: str, run_started_at: datetime) -> dict[str, Any] | None:
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if job.get("script_path") != flow_path:
            continue
        job_kind = job.get("job_kind")
        if isinstance(job_kind, str) and job_kind and job_kind != "flow":
            continue
        created_at = _parse_dt(job.get("created_at"))
        if not created_at:
            continue
        if created_at < run_started_at:
            continue
        candidates.append((created_at, job))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _normalize_jurisdiction(row: dict[str, Any]) -> str:
    jurisdiction = row.get("jurisdiction")
    if not isinstance(jurisdiction, dict):
        return str(row.get("jurisdiction_id") or "unknown")
    name = str(jurisdiction.get("name") or "").strip()
    state = str(jurisdiction.get("state") or "").strip()
    if name and state:
        return f"{name} {state}"
    if name:
        return name
    return str(jurisdiction.get("id") or "unknown")


def _safe_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


def _get_cached_secret(secret_ref: str) -> str:
    proc = _run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail; "
                "source \"$HOME/agent-skills/scripts/lib/dx-auth.sh\"; "
                f'DX_AUTH_CACHE_ONLY=1 dx_auth_read_secret_cached "{secret_ref}"'
            ),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cached secret unavailable: {secret_ref}")
    value = proc.stdout.strip()
    if not value:
        raise RuntimeError(f"cached secret empty: {secret_ref}")
    return value


def _wmill(config_dir: str, workspace: str, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        "npx",
        "--yes",
        "windmill-cli",
        *args,
        "--workspace",
        workspace,
        "--config-dir",
        config_dir,
    ]
    return _run(cmd, check=False)


@contextmanager
def _windmill_context(*, workspace: str, flow_path: str, script_path: str) -> Any:
    with tempfile.TemporaryDirectory(prefix="lgm-c13-wmill-") as config_dir:
        token = _get_cached_secret("op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN")
        login_url = _get_cached_secret("op://dev/Agent-Secrets-Production/WINDMILL_DEV_LOGIN_URL")
        base_url = login_url.removesuffix("/user/login").rstrip("/")
        if not base_url:
            raise RuntimeError("invalid WINDMILL_DEV_LOGIN_URL shape")

        add_proc = _run(
            [
                "npx",
                "--yes",
                "windmill-cli",
                "workspace",
                "add",
                workspace,
                workspace,
                base_url,
                "--token",
                token,
                "--config-dir",
                config_dir,
            ],
            check=False,
        )
        if add_proc.returncode != 0:
            raise RuntimeError("windmill workspace add failed")

        list_proc = _run(
            [
                "npx",
                "--yes",
                "windmill-cli",
                "workspace",
                "list",
                "--config-dir",
                config_dir,
            ],
            check=False,
        )
        if list_proc.returncode != 0:
            raise RuntimeError("windmill workspace list failed")

        flow_proc = _wmill(config_dir, workspace, "flow", "get", flow_path, "--json")
        if flow_proc.returncode != 0:
            stderr = flow_proc.stderr or flow_proc.stdout
            if "Flow not found" in stderr:
                raise RuntimeError("windmill flow not deployed")
            raise RuntimeError("windmill flow get failed")

        yield WindmillContext(workspace=workspace, flow_path=flow_path, script_path=script_path, config_dir=config_dir)


def _build_mode_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"windmill_live": 0, "mixed": 0, "cli_only": 0, "blocked": 0}
    for row in rows:
        mode = str(row.get("orchestration_mode") or "")
        if mode in counts:
            counts[mode] += 1
    return counts


def _build_baseline_rows(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    corpus_rows = [
        row
        for row in matrix.get("rows", [])
        if isinstance(row, dict) and row.get("row_type") == "corpus_package"
    ]
    baseline: list[dict[str, Any]] = []
    for row in corpus_rows:
        infra = row.get("infrastructure_status") if isinstance(row, dict) else {}
        if not isinstance(infra, dict):
            infra = {}
        refs = infra.get("windmill_refs")
        if not isinstance(refs, dict):
            refs = {}
        baseline.append(
            {
                "corpus_row_id": str(row.get("corpus_row_id") or "unknown"),
                "package_id": str(row.get("package_id") or ""),
                "jurisdiction_id": str((row.get("jurisdiction") or {}).get("id") or ""),
                "policy_family": str(row.get("policy_family") or ""),
                "baseline_mode": str(infra.get("orchestration_mode") or "cli_only"),
                "orchestration_mode": str(infra.get("orchestration_mode") or "cli_only"),
                "windmill_flow_path": refs.get("flow_id"),
                "windmill_run_id": refs.get("run_id"),
                "windmill_job_id": refs.get("job_id"),
                "row_status": "carried_forward_from_matrix",
                "blocker_class": None,
                "blocker_detail": None,
                "flow_response_status": None,
                "backend_scope_status": None,
                "command_client": None,
                "command_attempted": None,
                "idempotency_key": None,
                "run_id_source": None,
                "job_id_source": None,
                "job_lookup_trace": [],
            }
        )
    return baseline


def _live_attempt_for_row(
    *,
    row: dict[str, Any],
    context: WindmillContext,
    command_client: str,
    backend_timeout_seconds: int,
) -> LiveAttempt:
    corpus_row_id = str(row.get("corpus_row_id") or "unknown")
    jurisdiction = _normalize_jurisdiction(row)
    source_family = str(row.get("policy_family") or "unknown")
    query_families = row.get("query_families")
    if not isinstance(query_families, list):
        query_families = []
    search_query = str(query_families[0] if query_families else f"{jurisdiction} {source_family} policy")
    analysis_question = (
        "Validate local-government policy evidence orchestration for corpus gate C13 and preserve run/job refs."
    )
    idempotency_key = f"{FEATURE_KEY}:{corpus_row_id}:{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    payload = {
        "idempotency_key": idempotency_key,
        "mode": "manual",
        "jurisdictions": [jurisdiction],
        "source_families": [source_family],
        "scope_parallelism": 1,
        "search_query": search_query,
        "analysis_question": analysis_question,
        "stale_status": "fresh",
        "command_client": command_client,
        "backend_endpoint_timeout_seconds": backend_timeout_seconds,
    }
    command_attempted = (
        "windmill-cli flow run "
        f"{context.flow_path} -s -d '{_safe_json(payload)}'"
    )
    run_started_at = datetime.now(UTC)
    run_proc = _wmill(
        context.config_dir,
        context.workspace,
        "flow",
        "run",
        context.flow_path,
        "-s",
        "-d",
        _safe_json(payload),
    )
    if run_proc.returncode != 0:
        stderr = (run_proc.stderr or run_proc.stdout).strip()
        blocker_class = "windmill_flow_run_failed"
        if "backend_endpoint_missing_configuration" in stderr:
            blocker_class = "backend_endpoint_not_configured"
        elif "backend_endpoint_http_error" in stderr:
            blocker_class = "backend_endpoint_http_error"
        return LiveAttempt(
            corpus_row_id=corpus_row_id,
            status="blocked",
            orchestration_mode="blocked",
            windmill_run_id=None,
            windmill_job_id=None,
            windmill_flow_path=context.flow_path,
            blocker_class=blocker_class,
            blocker_detail=stderr[-500:] if stderr else "flow run returned non-zero",
            command_client=command_client,
            command_attempted=command_attempted,
            flow_response_status=None,
            backend_scope_status=None,
            idempotency_key=idempotency_key,
            run_id_source=None,
            job_id_source=None,
            job_lookup_trace=(),
        )

    flow_result = _extract_last_json_object(run_proc.stdout.strip())
    flow_status = _extract_flow_response_status(flow_result)
    backend_scope_status = _extract_backend_scope_status(flow_result)
    run_id, job_id = _extract_flow_refs(flow_result, idempotency_key=idempotency_key)
    run_id_source = "flow_run_output" if run_id else None
    job_id_source = "flow_run_output" if job_id else None

    lookup_trace: list[str] = []
    if run_id:
        lookup_trace.append("flow_run_output:windmill_run_id")
    if job_id:
        lookup_trace.append("flow_run_output:windmill_job_id")

    for attempt_idx in range(10):
        jobs: list[dict[str, Any]] = []
        job_proc = _wmill(
            context.config_dir,
            context.workspace,
            "job",
            "list",
            "--all",
            "--limit",
            "300",
            "--json",
        )
        if job_proc.returncode == 0:
            try:
                parsed = json.loads(job_proc.stdout or "[]")
            except json.JSONDecodeError:
                parsed = []
            if isinstance(parsed, list):
                jobs = [job for job in parsed if isinstance(job, dict)]
            lookup_trace.append(f"job_list_all[{attempt_idx}]:count={len(jobs)}")
            matched_job = _find_job_for_idempotency(jobs, idempotency_key)
            if matched_job:
                candidate = _authoritative_windmill_ref(matched_job.get("id"), idempotency_key=idempotency_key)
                if candidate:
                    job_id = candidate
                    job_id_source = "job_list_all:idempotency_match"
                    lookup_trace.append(f"job_list_all[{attempt_idx}]:idempotency_match")
                if not run_id and candidate:
                    run_id = candidate
                    run_id_source = "job_list_all:idempotency_match"
                    lookup_trace.append(f"job_list_all[{attempt_idx}]:run_id_from_job_id")

            if not job_id and attempt_idx in {0, 3, 6, 9}:
                script_proc = _wmill(
                    context.config_dir,
                    context.workspace,
                    "job",
                    "list",
                    "--script-path",
                    context.script_path,
                    "--all",
                    "--limit",
                    "120",
                    "--json",
                )
                if script_proc.returncode == 0:
                    try:
                        parsed_script = json.loads(script_proc.stdout or "[]")
                    except json.JSONDecodeError:
                        parsed_script = []
                    script_jobs: list[dict[str, Any]] = []
                    if isinstance(parsed_script, list):
                        script_jobs = [job for job in parsed_script if isinstance(job, dict)]
                    lookup_trace.append(f"job_list_script_path[{attempt_idx}]:count={len(script_jobs)}")
                    matched_script_job = _find_job_for_idempotency(script_jobs, idempotency_key)
                    if matched_script_job:
                        candidate = _authoritative_windmill_ref(
                            matched_script_job.get("id"), idempotency_key=idempotency_key
                        )
                        if candidate:
                            job_id = candidate
                            job_id_source = "job_list_script_path:idempotency_match"
                            lookup_trace.append(f"job_list_script_path[{attempt_idx}]:idempotency_match")
                            if not run_id:
                                run_id = candidate
                                run_id_source = "job_list_script_path:idempotency_match"
                                lookup_trace.append(f"job_list_script_path[{attempt_idx}]:run_id_from_job_id")
                else:
                    lookup_trace.append(f"job_list_script_path[{attempt_idx}]:non_zero")

            if not job_id:
                recent_job = _find_recent_flow_job(jobs, flow_path=context.flow_path, run_started_at=run_started_at)
                if recent_job:
                    candidate = _authoritative_windmill_ref(recent_job.get("id"), idempotency_key=idempotency_key)
                    if candidate:
                        job_id = candidate
                        job_id_source = "job_list_all:recent_flow_job"
                        lookup_trace.append(f"job_list_all[{attempt_idx}]:recent_flow_job")
                        if not run_id:
                            run_id = candidate
                            run_id_source = "job_list_all:recent_flow_job"
                            lookup_trace.append(f"job_list_all[{attempt_idx}]:run_id_from_recent_flow_job")
        else:
            lookup_trace.append(f"job_list_all[{attempt_idx}]:non_zero")

        if run_id and job_id:
            break
        time.sleep(1.0)

    flow_blocked_or_failed = flow_status in {"failed", "blocked"}
    proven = bool(run_id and job_id and not flow_blocked_or_failed)
    if proven:
        mode = "windmill_live" if command_client == "backend_endpoint" else "mixed"
        return LiveAttempt(
            corpus_row_id=corpus_row_id,
            status="proven",
            orchestration_mode=mode,
            windmill_run_id=run_id,
            windmill_job_id=job_id,
            windmill_flow_path=context.flow_path,
            blocker_class=None,
            blocker_detail=None,
            command_client=command_client,
            command_attempted=command_attempted,
            flow_response_status=flow_status,
            backend_scope_status=backend_scope_status,
            idempotency_key=idempotency_key,
            run_id_source=run_id_source,
            job_id_source=job_id_source,
            job_lookup_trace=tuple(lookup_trace),
        )

    blocker_class = "windmill_refs_incomplete"
    blocker_detail = (
        "run did not return both authoritative windmill_run_id and windmill_job_id; "
        f"lookup_trace={'; '.join(lookup_trace[-6:]) if lookup_trace else 'none'}"
    )
    if flow_blocked_or_failed:
        blocker_class = "backend_scope_not_succeeded"
        blocker_detail = (
            f"flow_status={flow_status} backend_scope_status={backend_scope_status}; "
            f"run_id_source={run_id_source or 'missing'} job_id_source={job_id_source or 'missing'}"
        )
    return LiveAttempt(
        corpus_row_id=corpus_row_id,
        status="blocked",
        orchestration_mode="blocked",
        windmill_run_id=run_id,
        windmill_job_id=job_id,
        windmill_flow_path=context.flow_path,
        blocker_class=blocker_class,
        blocker_detail=blocker_detail,
        command_client=command_client,
        command_attempted=command_attempted,
        flow_response_status=flow_status,
        backend_scope_status=backend_scope_status,
        idempotency_key=idempotency_key,
        run_id_source=run_id_source,
        job_id_source=job_id_source,
        job_lookup_trace=tuple(lookup_trace),
    )


def _merge_rows_with_attempts(
    baseline_rows: list[dict[str, Any]],
    attempts: dict[str, LiveAttempt],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for row in baseline_rows:
        corpus_row_id = row["corpus_row_id"]
        attempt = attempts.get(corpus_row_id)
        if not attempt:
            merged.append(row)
            continue
        merged.append(
            {
                **row,
                "orchestration_mode": attempt.orchestration_mode,
                "windmill_flow_path": attempt.windmill_flow_path,
                "windmill_run_id": attempt.windmill_run_id,
                "windmill_job_id": attempt.windmill_job_id,
                "row_status": attempt.status,
                "blocker_class": attempt.blocker_class,
                "blocker_detail": attempt.blocker_detail,
                "flow_response_status": attempt.flow_response_status,
                "backend_scope_status": attempt.backend_scope_status,
                "command_client": attempt.command_client,
                "command_attempted": attempt.command_attempted,
                "idempotency_key": attempt.idempotency_key,
                "run_id_source": attempt.run_id_source,
                "job_id_source": attempt.job_id_source,
                "job_lookup_trace": list(attempt.job_lookup_trace),
            }
        )
    return merged


def _build_report(
    *,
    matrix: dict[str, Any],
    scorecard: dict[str, Any] | None,
    baseline_rows: list[dict[str, Any]],
    merged_rows: list[dict[str, Any]],
    attempts: list[LiveAttempt],
    flow_path: str,
    command_client: str,
    command_log: list[str],
    surface_blocker: dict[str, Any] | None,
) -> dict[str, Any]:
    baseline_counts = _build_mode_counts(baseline_rows)
    post_counts = _build_mode_counts(merged_rows)
    total_rows = len(merged_rows)
    baseline_cli_share = round((baseline_counts["cli_only"] / total_rows), 4) if total_rows else 0.0
    post_cli_share = round((post_counts["cli_only"] / total_rows), 4) if total_rows else 0.0

    seeded_placeholder_rows = [
        row["corpus_row_id"]
        for row in merged_rows
        if row.get("orchestration_mode") in {"windmill_live", "mixed"} and (
            _is_seeded_windmill_ref(row.get("windmill_run_id"))
            or _is_seeded_windmill_ref(row.get("windmill_job_id"))
        )
    ]
    missing_live_refs_rows = [
        row["corpus_row_id"]
        for row in merged_rows
        if row.get("orchestration_mode") in {"windmill_live", "mixed"}
        and (
            not row.get("windmill_flow_path")
            or not row.get("windmill_run_id")
            or not row.get("windmill_job_id")
            or _is_seeded_windmill_ref(row.get("windmill_run_id"))
            or _is_seeded_windmill_ref(row.get("windmill_job_id"))
        )
    ]
    blocker_rows = [
        {
            "corpus_row_id": row["corpus_row_id"],
            "package_id": row.get("package_id"),
            "blocker_class": row.get("blocker_class"),
            "blocker_detail": row.get("blocker_detail"),
        }
        for row in merged_rows
        if row.get("orchestration_mode") == "blocked" or row.get("blocker_class")
    ]
    live_exercised = any(attempt.status in {"proven", "blocked"} for attempt in attempts)
    if post_cli_share <= 0.1 and not missing_live_refs_rows and not blocker_rows:
        verdict = "pass_candidate"
        next_action = (
            "Integrate this artifact into C13 scoring input and regenerate the corpus scorecard."
        )
    elif blocker_rows:
        verdict = "not_proven_blocked"
        next_action = (
            "Clear blocker rows (auth/deploy/runtime) and re-run this verifier with backend_endpoint mode."
        )
    elif missing_live_refs_rows:
        verdict = "not_proven_unverified_live_refs"
        next_action = (
            "Replace seeded/placeholder refs with live-proven Windmill run/job ids for all windmill_live and mixed rows."
        )
    else:
        verdict = "not_proven_cli_only_share_above_cap"
        next_action = "Run additional cli_only rows through live Windmill orchestration until cli_only_share <= 0.10."

    scorecard_c13 = (((scorecard or {}).get("gates") or {}).get("C13") or {}) if isinstance(scorecard, dict) else {}
    scorecard_c13_metrics = scorecard_c13.get("metrics") if isinstance(scorecard_c13, dict) else {}
    scorecard_reference = None
    if isinstance(scorecard_c13, dict) and isinstance(scorecard_c13_metrics, dict):
        scorecard_reference = {
            "generated_at": (scorecard or {}).get("generated_at"),
            "c13_status": scorecard_c13.get("status"),
            "c13_reason": scorecard_c13.get("reason"),
            "c13_cli_only_share": scorecard_c13_metrics.get("cli_only_share"),
            "c13_row_count": scorecard_c13_metrics.get("row_count"),
            "c13_mode_counts": scorecard_c13_metrics.get("mode_counts"),
            "c13_blockers": scorecard_c13.get("blockers"),
        }

    return {
        "feature_key": FEATURE_KEY,
        "generated_at": _iso_now(),
        "corpus_matrix_digest": _matrix_digest(matrix),
        "scorecard_reference": scorecard_reference,
        "windmill_flow_path": flow_path,
        "command_client": command_client,
        "live_windmill_exercised": live_exercised,
        "baseline_metrics": {
            "row_count": total_rows,
            "mode_counts": baseline_counts,
            "cli_only_share": baseline_cli_share,
        },
        "post_metrics": {
            "row_count": total_rows,
            "mode_counts": post_counts,
            "cli_only_share": post_cli_share,
            "missing_live_refs_rows": missing_live_refs_rows,
            "seeded_placeholder_rows": seeded_placeholder_rows,
            "blocker_rows": blocker_rows,
        },
        "rows": merged_rows,
        "attempts": [attempt.to_json() for attempt in attempts],
        "commands_attempted": command_log,
        "surface_blocker": surface_blocker,
        "c13_verdict_candidate": verdict,
        "recommended_next_action": next_action,
    }


def run(
    *,
    matrix_path: Path,
    scorecard_path: Path | None,
    output_path: Path,
    workspace: str,
    flow_path: str,
    script_path: str,
    command_client: str,
    backend_timeout_seconds: int,
    max_cli_only_rows: int,
    skip_live: bool,
) -> dict[str, Any]:
    matrix = _load_json(matrix_path)
    scorecard = None
    if scorecard_path and scorecard_path.exists():
        scorecard = _load_json(scorecard_path)
    baseline_rows = _build_baseline_rows(matrix)
    target_rows = [
        row
        for row in baseline_rows
        if row.get("baseline_mode") == "cli_only"
    ][: max(0, max_cli_only_rows)]
    row_index = {row["corpus_row_id"]: row for row in baseline_rows}

    attempts: list[LiveAttempt] = []
    command_log: list[str] = []
    surface_blocker: dict[str, Any] | None = None

    if not skip_live and target_rows:
        try:
            with _windmill_context(workspace=workspace, flow_path=flow_path, script_path=script_path) as context:
                for target in target_rows:
                    source_row = next(
                        (
                            row
                            for row in matrix.get("rows", [])
                            if isinstance(row, dict) and row.get("corpus_row_id") == target["corpus_row_id"]
                        ),
                        row_index[target["corpus_row_id"]],
                    )
                    attempt = _live_attempt_for_row(
                        row=source_row,
                        context=context,
                        command_client=command_client,
                        backend_timeout_seconds=backend_timeout_seconds,
                    )
                    attempts.append(attempt)
                    command_log.append(attempt.command_attempted)
        except RuntimeError as exc:
            surface_blocker = {
                "blocker_class": "windmill_surface_unavailable",
                "detail": str(exc),
                "target_cli_only_rows": [row["corpus_row_id"] for row in target_rows],
            }
            for target in target_rows:
                attempts.append(
                    LiveAttempt(
                        corpus_row_id=target["corpus_row_id"],
                        status="blocked",
                        orchestration_mode="blocked",
                        windmill_run_id=None,
                        windmill_job_id=None,
                        windmill_flow_path=flow_path,
                        blocker_class="windmill_surface_unavailable",
                        blocker_detail=str(exc),
                        command_client=command_client,
                        command_attempted="windmill-cli workspace/flow preflight",
                        flow_response_status=None,
                        backend_scope_status=None,
                        idempotency_key=f"{FEATURE_KEY}:{target['corpus_row_id']}:surface-blocked",
                        run_id_source=None,
                        job_id_source=None,
                        job_lookup_trace=(),
                    )
                )
    elif skip_live:
        surface_blocker = {
            "blocker_class": "live_skipped_by_flag",
            "detail": "--skip-live requested",
            "target_cli_only_rows": [row["corpus_row_id"] for row in target_rows],
        }

    attempts_by_row = {attempt.corpus_row_id: attempt for attempt in attempts}
    merged_rows = _merge_rows_with_attempts(baseline_rows, attempts_by_row)
    report = _build_report(
        matrix=matrix,
        scorecard=scorecard,
        baseline_rows=baseline_rows,
        merged_rows=merged_rows,
        attempts=attempts,
        flow_path=flow_path,
        command_client=command_client,
        command_log=command_log,
        surface_blocker=surface_blocker,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-path", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--scorecard-path", type=Path, default=DEFAULT_SCORECARD_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--workspace", default=DEFAULT_WINDMILL_WORKSPACE)
    parser.add_argument("--flow-path", default=DEFAULT_WINDMILL_FLOW_PATH)
    parser.add_argument("--script-path", default=DEFAULT_WINDMILL_SCRIPT_PATH)
    parser.add_argument(
        "--command-client",
        default="backend_endpoint",
        choices=["backend_endpoint", "stub", "domain_package"],
    )
    parser.add_argument("--backend-timeout-seconds", type=int, default=180)
    parser.add_argument("--max-cli-only-rows", type=int, default=4)
    parser.add_argument("--skip-live", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run(
        matrix_path=args.matrix_path,
        scorecard_path=args.scorecard_path,
        output_path=args.out,
        workspace=args.workspace,
        flow_path=args.flow_path,
        script_path=args.script_path,
        command_client=args.command_client,
        backend_timeout_seconds=max(1, int(args.backend_timeout_seconds)),
        max_cli_only_rows=max(0, int(args.max_cli_only_rows)),
        skip_live=bool(args.skip_live),
    )
    print(
        "local_government_corpus_windmill_orchestration complete: "
        f"baseline_cli_only_share={report['baseline_metrics']['cli_only_share']} "
        f"post_cli_only_share={report['post_metrics']['cli_only_share']} "
        f"verdict={report['c13_verdict_candidate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
