#!/usr/bin/env python3
"""Verify/fail-close local-government corpus Windmill orchestration coverage."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
try:
    from datetime import UTC, datetime
except ImportError:  # pragma: no cover - Python < 3.11 compatibility
    from datetime import datetime, timezone

    UTC = timezone.utc
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
FEATURE_KEY = "bd-3wefe.13.4.6"
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
    backend_failure_detail: dict[str, Any] | None = None
    backend_failure_codes: tuple[str, ...] = ()
    windmill_step_statuses: dict[str, str] | None = None
    scope_id: str | None = None
    recommended_next_action: str | None = None

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
            "backend_failure_detail": self.backend_failure_detail,
            "backend_failure_codes": list(self.backend_failure_codes),
            "windmill_step_statuses": self.windmill_step_statuses,
            "scope_id": self.scope_id,
            "recommended_next_action": self.recommended_next_action,
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


def _normalize_step_statuses(payload: Any) -> dict[str, str]:
    statuses: dict[str, str] = {}
    if not isinstance(payload, dict):
        return statuses
    for raw_step, raw_step_payload in payload.items():
        if not isinstance(raw_step_payload, dict):
            continue
        status = raw_step_payload.get("status")
        if status is None:
            continue
        step = str(raw_step).strip()
        if not step:
            continue
        statuses[step] = str(status)
    return statuses


def _first_value_for_key(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload.get(key)
        for value in payload.values():
            found = _first_value_for_key(value, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _first_value_for_key(value, key)
            if found is not None:
                return found
    return None


def _first_nonempty_string_for_keys(payloads: list[Any], keys: list[str]) -> str | None:
    for payload in payloads:
        for key in keys:
            raw = _first_value_for_key(payload, key)
            if isinstance(raw, str):
                value = raw.strip()
                if value:
                    return value
    return None


def _first_int_for_keys(payloads: list[Any], keys: list[str]) -> int | None:
    for payload in payloads:
        for key in keys:
            raw = _first_value_for_key(payload, key)
            if isinstance(raw, bool):
                continue
            if isinstance(raw, int):
                return raw
            if isinstance(raw, str) and raw.strip().isdigit():
                return int(raw.strip())
    return None


def _collect_backend_failure_codes(payload: Any) -> tuple[str, ...]:
    codes: list[str] = []
    seen: set[str] = set()

    def _add_code(raw: Any) -> None:
        if not isinstance(raw, str):
            return
        code = raw.strip()
        if not code:
            return
        if code in seen:
            return
        seen.add(code)
        codes.append(code)

    def _visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in {
                    "failure_code",
                    "failure_codes",
                    "runtime_failure_codes",
                    "reason_code",
                    "error",
                    "blocking_gate",
                    "decision_reason",
                    "retry_class",
                }:
                    if isinstance(nested, list):
                        for item in nested:
                            _add_code(item)
                    else:
                        _add_code(nested)
                _visit(nested)
            return
        if isinstance(value, list):
            for nested in value:
                _visit(nested)

    _visit(payload)
    return tuple(codes)


def _default_failure_next_action(failure_domain: str) -> str:
    if failure_domain == "product_data_unsupported":
        return "Gather missing authoritative policy evidence for this scope and re-run the backend endpoint flow."
    if failure_domain == "infra_or_runtime":
        return "Repair backend_endpoint/Windmill runtime failure, then re-run the same scope idempotency key."
    if failure_domain == "windmill_cli_status_only":
        return "Windmill CLI exposed only failed/succeeded status; inspect run/job logs in Windmill UI and re-run."
    return "Inspect backend scope failure payload/logs for this run/job and re-run after the blocking cause is addressed."


def _classify_backend_failure(
    *,
    failure_codes: tuple[str, ...],
    exception_text: str | None,
    failing_step: str | None,
    backend_scope_status: str | None,
    response_http_status: int | None,
    has_step_statuses: bool,
) -> str:
    corpus = " ".join(
        part
        for part in (
            " ".join(failure_codes),
            exception_text or "",
            failing_step or "",
            backend_scope_status or "",
        )
        if part
    ).lower()
    if not corpus and response_http_status is None and not has_step_statuses:
        return "windmill_cli_status_only"

    product_markers = (
        "unsupported",
        "parameter_missing",
        "parameter_unverifiable",
        "no_quant_support_path",
        "insufficient_evidence",
        "blocking_gate_present",
        "qualitative_only",
        "policy_evidence_fail_closed",
        "package_not_ready_for_economic_handoff",
        "stale_blocked",
        "empty_blocked",
    )
    infra_markers = (
        "backend_endpoint_http_error",
        "backend_endpoint_request_error",
        "backend_endpoint_missing_configuration",
        "backend_endpoint_invalid_response",
        "timeout",
        "connection",
        "request error",
        "service unavailable",
        "unauthorized",
        "forbidden",
        "traceback",
        "exception",
        "module_not_found",
    )

    product_hit = any(marker in corpus for marker in product_markers)
    infra_hit = any(marker in corpus for marker in infra_markers) or (
        response_http_status is not None and response_http_status >= 400
    )

    if product_hit and not infra_hit:
        return "product_data_unsupported"
    if infra_hit:
        return "infra_or_runtime"
    return "unknown"


def _extract_backend_failure_evidence(
    *,
    flow_result: dict[str, Any],
    backend_scope_status: str | None,
    job_detail: dict[str, Any] | None,
) -> dict[str, Any]:
    scope = _first_scope_result(flow_result)
    backend_response = scope.get("backend_response") if isinstance(scope.get("backend_response"), dict) else {}
    scope_steps = _normalize_step_statuses(scope.get("steps"))
    backend_steps = _normalize_step_statuses(backend_response.get("steps"))
    step_statuses = {**scope_steps, **backend_steps}

    failing_step = next(
        (
            step
            for step, status in step_statuses.items()
            if status not in {"succeeded", "succeeded_with_alerts", "fresh", "ready", "pass", "none"}
        ),
        None,
    )
    payloads: list[Any] = [scope, backend_response, flow_result]
    if isinstance(job_detail, dict):
        payloads.append(job_detail)

    failure_codes = _collect_backend_failure_codes(payloads)
    scope_id = _first_nonempty_string_for_keys(
        payloads,
        [
            "scope_idempotency_key",
            "scope_id",
            "scope_key",
        ],
    )
    recommended_next_action = _first_nonempty_string_for_keys(payloads, ["recommended_next_action"])
    exception_text = _first_nonempty_string_for_keys(
        payloads,
        ["exception", "traceback", "detail", "error"],
    )
    response_http_status = _first_int_for_keys(payloads, ["http_status", "status_code"])
    response_status = _first_nonempty_string_for_keys(
        [backend_response, scope, flow_result],
        ["status", "flow_response_status"],
    )
    failing_module = _first_nonempty_string_for_keys(
        payloads,
        ["module", "module_id", "step", "step_id", "invoked_command"],
    )
    failure_domain = _classify_backend_failure(
        failure_codes=failure_codes,
        exception_text=exception_text,
        failing_step=failing_step,
        backend_scope_status=backend_scope_status,
        response_http_status=response_http_status,
        has_step_statuses=bool(step_statuses),
    )
    if not recommended_next_action:
        recommended_next_action = _default_failure_next_action(failure_domain)

    failure_detail: dict[str, Any] = {
        "failure_domain": failure_domain,
        "response_status": response_status,
        "response_http_status": response_http_status,
        "scope_id": scope_id,
        "failing_step": failing_step,
        "failing_module": failing_module,
        "exception_text": exception_text,
    }
    if failure_domain == "windmill_cli_status_only":
        failure_detail["detail"] = "Windmill CLI returned failed/succeeded status without backend failure detail."
    return {
        "backend_failure_detail": failure_detail,
        "backend_failure_codes": failure_codes,
        "windmill_step_statuses": step_statuses or None,
        "scope_id": scope_id,
        "recommended_next_action": recommended_next_action,
    }


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
                "backend_failure_detail": None,
                "backend_failure_codes": [],
                "windmill_step_statuses": None,
                "scope_id": None,
                "recommended_next_action": None,
            }
        )
    return baseline


def _has_authoritative_live_refs(*, run_id: Any, job_id: Any) -> bool:
    if not isinstance(run_id, str) or not run_id.strip():
        return False
    if not isinstance(job_id, str) or not job_id.strip():
        return False
    if _is_seeded_windmill_ref(run_id) or _is_seeded_windmill_ref(job_id):
        return False
    return True


def _row_is_proven(row: dict[str, Any]) -> bool:
    if str(row.get("row_status") or "") != "proven":
        return False
    return _has_authoritative_live_refs(
        run_id=row.get("windmill_run_id"),
        job_id=row.get("windmill_job_id"),
    )


def _load_existing_report(output_path: Path) -> dict[str, Any] | None:
    if not output_path.exists():
        return None
    existing = _load_json(output_path)
    if not isinstance(existing, dict):
        return None
    return existing


def _index_proven_rows(existing_report: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(existing_report, dict):
        return {}
    proven_by_id: dict[str, dict[str, Any]] = {}
    for row in existing_report.get("rows", []):
        if not isinstance(row, dict):
            continue
        corpus_row_id = str(row.get("corpus_row_id") or "").strip()
        if not corpus_row_id:
            continue
        if _row_is_proven(row):
            proven_by_id[corpus_row_id] = row
    return proven_by_id


def _select_target_rows(
    *,
    baseline_rows: list[dict[str, Any]],
    max_cli_only_rows: int,
    target_row_ids: list[str],
    skip_proven_output_rows: bool,
    existing_proven_row_ids: set[str],
) -> list[dict[str, Any]]:
    row_index = {row["corpus_row_id"]: row for row in baseline_rows}
    if target_row_ids:
        deduped_ids: list[str] = []
        seen: set[str] = set()
        for raw_row_id in target_row_ids:
            row_id = str(raw_row_id).strip()
            if not row_id or row_id in seen:
                continue
            seen.add(row_id)
            deduped_ids.append(row_id)
        missing = [row_id for row_id in deduped_ids if row_id not in row_index]
        if missing:
            missing_display = ", ".join(sorted(missing))
            raise ValueError(f"Unknown --target-row-id value(s): {missing_display}")
        return [row_index[row_id] for row_id in deduped_ids]

    targets = [row for row in baseline_rows if row.get("baseline_mode") == "cli_only"]
    if skip_proven_output_rows:
        targets = [row for row in targets if row["corpus_row_id"] not in existing_proven_row_ids]
    return targets[: max(0, max_cli_only_rows)]


def _carry_forward_proven_row(
    *,
    baseline_row: dict[str, Any],
    existing_row: dict[str, Any],
) -> dict[str, Any]:
    lookup_trace = existing_row.get("job_lookup_trace")
    if not isinstance(lookup_trace, list):
        lookup_trace = []
    return {
        **baseline_row,
        "orchestration_mode": str(existing_row.get("orchestration_mode") or baseline_row.get("orchestration_mode") or ""),
        "windmill_flow_path": existing_row.get("windmill_flow_path") or baseline_row.get("windmill_flow_path"),
        "windmill_run_id": existing_row.get("windmill_run_id"),
        "windmill_job_id": existing_row.get("windmill_job_id"),
        "row_status": "proven",
        "blocker_class": None,
        "blocker_detail": None,
        "flow_response_status": existing_row.get("flow_response_status"),
        "backend_scope_status": existing_row.get("backend_scope_status"),
        "command_client": existing_row.get("command_client"),
        "command_attempted": existing_row.get("command_attempted"),
        "idempotency_key": existing_row.get("idempotency_key"),
        "run_id_source": existing_row.get("run_id_source"),
        "job_id_source": existing_row.get("job_id_source"),
        "job_lookup_trace": lookup_trace,
        "backend_failure_detail": existing_row.get("backend_failure_detail"),
        "backend_failure_codes": existing_row.get("backend_failure_codes"),
        "windmill_step_statuses": existing_row.get("windmill_step_statuses"),
        "scope_id": existing_row.get("scope_id"),
        "recommended_next_action": existing_row.get("recommended_next_action"),
    }


def _index_proven_attempts(existing_report: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(existing_report, dict):
        return {}
    proven_attempts: dict[str, dict[str, Any]] = {}
    for attempt in existing_report.get("attempts", []):
        if not isinstance(attempt, dict):
            continue
        if str(attempt.get("status") or "") != "proven":
            continue
        corpus_row_id = str(attempt.get("corpus_row_id") or "").strip()
        if not corpus_row_id:
            continue
        if not _has_authoritative_live_refs(
            run_id=attempt.get("windmill_run_id"),
            job_id=attempt.get("windmill_job_id"),
        ):
            continue
        lookup_trace = attempt.get("job_lookup_trace")
        if not isinstance(lookup_trace, list):
            lookup_trace = []
        proven_attempts[corpus_row_id] = {
            "corpus_row_id": corpus_row_id,
            "status": "proven",
            "orchestration_mode": attempt.get("orchestration_mode"),
            "windmill_run_id": attempt.get("windmill_run_id"),
            "windmill_job_id": attempt.get("windmill_job_id"),
            "windmill_flow_path": attempt.get("windmill_flow_path"),
            "blocker_class": attempt.get("blocker_class"),
            "blocker_detail": attempt.get("blocker_detail"),
            "command_client": attempt.get("command_client"),
            "command_attempted": attempt.get("command_attempted"),
            "flow_response_status": attempt.get("flow_response_status"),
            "backend_scope_status": attempt.get("backend_scope_status"),
            "idempotency_key": attempt.get("idempotency_key"),
            "run_id_source": attempt.get("run_id_source"),
            "job_id_source": attempt.get("job_id_source"),
            "job_lookup_trace": lookup_trace,
            "backend_failure_detail": attempt.get("backend_failure_detail"),
            "backend_failure_codes": attempt.get("backend_failure_codes"),
            "windmill_step_statuses": attempt.get("windmill_step_statuses"),
            "scope_id": attempt.get("scope_id"),
            "recommended_next_action": attempt.get("recommended_next_action"),
        }
    return proven_attempts


def _merge_attempt_payloads(
    *,
    existing_proven_attempts: dict[str, dict[str, Any]],
    new_attempts: list[LiveAttempt],
) -> list[dict[str, Any]]:
    ordered: list[str] = []
    merged: dict[str, dict[str, Any]] = {}

    for corpus_row_id, payload in existing_proven_attempts.items():
        ordered.append(corpus_row_id)
        merged[corpus_row_id] = payload

    for attempt in new_attempts:
        corpus_row_id = attempt.corpus_row_id
        if corpus_row_id not in merged:
            ordered.append(corpus_row_id)
        merged[corpus_row_id] = attempt.to_json()

    return [merged[row_id] for row_id in ordered]


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
        failure_domain = "infra_or_runtime"
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
            backend_failure_detail={
                "failure_domain": failure_domain,
                "response_status": None,
                "response_http_status": None,
                "scope_id": None,
                "failing_step": "flow_run",
                "failing_module": "windmill-cli flow run",
                "exception_text": stderr[-500:] if stderr else None,
            },
            backend_failure_codes=(blocker_class,),
            windmill_step_statuses=None,
            scope_id=None,
            recommended_next_action=_default_failure_next_action(failure_domain),
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
    matched_job_for_failure: dict[str, Any] | None = None

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
                matched_job_for_failure = matched_job
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
                    matched_job_for_failure = recent_job
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
    job_detail: dict[str, Any] | None = None
    if flow_blocked_or_failed and (job_id or run_id):
        job_get_target = job_id or run_id
        job_get_proc = _wmill(
            context.config_dir,
            context.workspace,
            "job",
            "get",
            str(job_get_target),
            "--json",
        )
        if job_get_proc.returncode == 0:
            try:
                parsed_job = json.loads(job_get_proc.stdout or "{}")
            except json.JSONDecodeError:
                parsed_job = {}
            if isinstance(parsed_job, dict):
                job_detail = parsed_job
                lookup_trace.append("job_get:hydrated")
        else:
            lookup_trace.append("job_get:non_zero")
    if not job_detail and isinstance(matched_job_for_failure, dict):
        job_detail = matched_job_for_failure

    failure_evidence: dict[str, Any] = {}
    if flow_blocked_or_failed:
        failure_evidence = _extract_backend_failure_evidence(
            flow_result=flow_result,
            backend_scope_status=backend_scope_status,
            job_detail=job_detail,
        )

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
        failure_detail_payload = failure_evidence.get("backend_failure_detail") or {}
        failure_domain = failure_detail_payload.get("failure_domain")
        failing_step = failure_detail_payload.get("failing_step")
        failure_codes = failure_evidence.get("backend_failure_codes") or ()
        failure_codes_display = ",".join(str(code) for code in failure_codes[:4]) if failure_codes else "none"
        blocker_detail = (
            f"flow_status={flow_status} backend_scope_status={backend_scope_status}; "
            f"failure_domain={failure_domain or 'unknown'} failing_step={failing_step or 'unknown'} "
            f"failure_codes={failure_codes_display}; "
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
        backend_failure_detail=failure_evidence.get("backend_failure_detail"),
        backend_failure_codes=tuple(failure_evidence.get("backend_failure_codes") or ()),
        windmill_step_statuses=failure_evidence.get("windmill_step_statuses"),
        scope_id=failure_evidence.get("scope_id"),
        recommended_next_action=failure_evidence.get("recommended_next_action"),
    )


def _merge_rows_with_attempts(
    baseline_rows: list[dict[str, Any]],
    attempts: dict[str, LiveAttempt],
    *,
    existing_proven_rows: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    carried_forward = existing_proven_rows or {}
    for row in baseline_rows:
        corpus_row_id = row["corpus_row_id"]
        attempt = attempts.get(corpus_row_id)
        if not attempt:
            prior = carried_forward.get(corpus_row_id)
            if prior:
                merged.append(_carry_forward_proven_row(baseline_row=row, existing_row=prior))
                continue
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
                "backend_failure_detail": attempt.backend_failure_detail,
                "backend_failure_codes": list(attempt.backend_failure_codes),
                "windmill_step_statuses": attempt.windmill_step_statuses,
                "scope_id": attempt.scope_id,
                "recommended_next_action": attempt.recommended_next_action,
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
    attempts_payload: list[dict[str, Any]] | None = None,
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
            "backend_failure_codes": row.get("backend_failure_codes"),
            "scope_id": row.get("scope_id"),
            "recommended_next_action": row.get("recommended_next_action"),
        }
        for row in merged_rows
        if row.get("orchestration_mode") == "blocked" or row.get("blocker_class")
    ]
    materialized_attempts = (
        attempts_payload
        if isinstance(attempts_payload, list)
        else [attempt.to_json() for attempt in attempts]
    )
    live_exercised = any(attempt.status in {"proven", "blocked"} for attempt in attempts)
    if not live_exercised:
        live_exercised = any(
            str(attempt.get("status") or "") in {"proven", "blocked"}
            for attempt in materialized_attempts
            if isinstance(attempt, dict)
        )
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
        "attempts": materialized_attempts,
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
    target_row_ids: list[str] | None = None,
    skip_proven_output_rows: bool = True,
) -> dict[str, Any]:
    matrix = _load_json(matrix_path)
    scorecard = None
    if scorecard_path and scorecard_path.exists():
        scorecard = _load_json(scorecard_path)
    existing_report = _load_existing_report(output_path)
    existing_proven_rows = _index_proven_rows(existing_report)
    existing_proven_attempts = _index_proven_attempts(existing_report)

    baseline_rows = _build_baseline_rows(matrix)
    target_rows = _select_target_rows(
        baseline_rows=baseline_rows,
        max_cli_only_rows=max_cli_only_rows,
        target_row_ids=list(target_row_ids or []),
        skip_proven_output_rows=bool(skip_proven_output_rows),
        existing_proven_row_ids=set(existing_proven_rows),
    )
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
    merged_rows = _merge_rows_with_attempts(
        baseline_rows,
        attempts_by_row,
        existing_proven_rows=existing_proven_rows,
    )
    attempts_payload = _merge_attempt_payloads(
        existing_proven_attempts=existing_proven_attempts,
        new_attempts=attempts,
    )
    report = _build_report(
        matrix=matrix,
        scorecard=scorecard,
        baseline_rows=baseline_rows,
        merged_rows=merged_rows,
        attempts=attempts,
        attempts_payload=attempts_payload,
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
    parser.add_argument(
        "--target-row-id",
        action="append",
        default=[],
        help="Target a specific corpus_row_id. Repeat this flag to target multiple rows.",
    )
    parser.add_argument(
        "--skip-proven-output-rows",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip cli_only rows already proven in the existing --out artifact.",
    )
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
        target_row_ids=list(args.target_row_id or []),
        skip_proven_output_rows=bool(args.skip_proven_output_rows),
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
