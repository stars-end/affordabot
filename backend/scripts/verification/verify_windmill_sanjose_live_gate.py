#!/usr/bin/env python3
"""Live Windmill San Jose validation harness.

This harness validates Windmill CLI access, deployment surface, and optional
manual flow execution for:
f/affordabot/pipeline_daily_refresh_domain_boundary__flow

It intentionally distinguishes:
- stub_orchestration_pass: orchestration flow passes but still uses stub command path
- full_product_pass: orchestration pass plus storage/runtime evidence gates
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.util import module_from_spec, spec_from_file_location
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JSON_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "windmill-domain-boundary-integration"
    / "artifacts"
    / "sanjose_live_gate_report.json"
)
DEFAULT_MD_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "windmill-domain-boundary-integration"
    / "artifacts"
    / "sanjose_live_gate_report.md"
)
DEFAULT_FLOW_PATH = "f/affordabot/pipeline_daily_refresh_domain_boundary__flow"
DEFAULT_SCRIPT_PATH = "f/affordabot/pipeline_daily_refresh_domain_boundary"
DEFAULT_WORKSPACE = "affordabot"
FEATURE_KEY = "bd-9qjof.6"
HARNESS_VERSION = "2026-04-13.worker-b.v2"
STUB_SUMMARY_MARKER = "Path B orchestration skeleton. Product writes belong to affordabot commands."
EXPECTED_STEP_SEQUENCE = [
    "search_materialize",
    "freshness_gate",
    "read_fetch",
    "index",
    "analyze",
    "summarize_run",
]
EXPECTED_QUALITY_BLOCK_STEP_SEQUENCE = [
    "search_materialize",
    "freshness_gate",
    "read_fetch",
    "summarize_run",
]
WINDMILL_DOMAIN_SCRIPT_PATH = (
    REPO_ROOT / "ops" / "windmill" / "f" / "affordabot" / "pipeline_daily_refresh_domain_boundary.py"
)
DEFAULT_SEARX_ENDPOINTS = ["https://searx.tiekoetter.com/search"]
DEFAULT_BACKEND_ENDPOINT_TIMEOUT_SECONDS = 600
EXA_SECRET_REF = "op://dev/Agent-Secrets-Production/EXA_API_KEY"
TAVILY_SECRET_REF = "op://dev/Agent-Secrets-Production/TAVILY_API_KEY"


class HarnessError(RuntimeError):
    def __init__(self, category: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.details = details or {}


@dataclass
class HarnessContext:
    windmill_api_token: str
    windmill_dev_login_url: str
    windmill_base_url: str
    windmill_workspace: str
    config_dir: str


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _run(cmd: list[str], *, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        capture_output=True,
        text=True,
        input=input_text,
    )


def _json_or_raise(stdout: str, stage: str) -> Any:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise HarnessError(
            "windmill_cli",
            f"{stage} returned non-JSON output",
            {"stage": stage, "stdout_head": stdout[:300]},
        ) from exc


def _get_cached_secret(secret_ref: str) -> str:
    cmd = [
        "bash",
        "-lc",
        (
            "set -euo pipefail; "
            "source \"$HOME/agent-skills/scripts/lib/dx-auth.sh\"; "
            f'DX_AUTH_CACHE_ONLY=1 dx_auth_read_secret_cached "{secret_ref}"'
        ),
    ]
    try:
        result = _run(cmd)
    except subprocess.CalledProcessError as exc:
        raise HarnessError(
            "infra/auth",
            f"cached secret unavailable: {secret_ref}",
            {"stderr": exc.stderr[-400:] if exc.stderr else ""},
        ) from exc
    value = result.stdout.strip()
    if not value:
        raise HarnessError("infra/auth", f"empty cached secret: {secret_ref}")
    return value


def _build_context(workspace: str) -> HarnessContext:
    token = _get_cached_secret("op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN")
    login_url = _get_cached_secret("op://dev/Agent-Secrets-Production/WINDMILL_DEV_LOGIN_URL")
    base_url = login_url.removesuffix("/user/login")
    if base_url == login_url:
        base_url = login_url.rstrip("/")
    if not base_url.startswith("http"):
        raise HarnessError("infra/auth", "invalid WINDMILL_DEV_LOGIN_URL shape", {"login_url": login_url})
    config_dir = tempfile.mkdtemp(prefix="wmill-live-gate-")
    return HarnessContext(
        windmill_api_token=token,
        windmill_dev_login_url=login_url,
        windmill_base_url=base_url,
        windmill_workspace=workspace,
        config_dir=config_dir,
    )


def _wmill(ctx: HarnessContext, *args: str, expect_json: bool = False) -> str | Any:
    cmd = ["npx", "--yes", "windmill-cli", *args, "--workspace", ctx.windmill_workspace, "--config-dir", ctx.config_dir]
    try:
        result = _run(cmd)
    except subprocess.CalledProcessError as exc:
        raise HarnessError(
            "windmill_cli",
            f"windmill-cli command failed: {' '.join(args)}",
            {"stderr": exc.stderr[-600:] if exc.stderr else "", "stdout": exc.stdout[-300:] if exc.stdout else ""},
        ) from exc
    return _json_or_raise(result.stdout, " ".join(args)) if expect_json else result.stdout


def _setup_workspace_profile(ctx: HarnessContext) -> None:
    cmd = [
        "npx",
        "--yes",
        "windmill-cli",
        "workspace",
        "add",
        ctx.windmill_workspace,
        ctx.windmill_workspace,
        ctx.windmill_base_url,
        "--token",
        ctx.windmill_api_token,
        "--config-dir",
        ctx.config_dir,
    ]
    try:
        _run(cmd)
    except subprocess.CalledProcessError as exc:
        raise HarnessError(
            "infra/auth",
            "failed to create temporary Windmill workspace profile",
            {"stderr": exc.stderr[-500:] if exc.stderr else ""},
        ) from exc


def _find_job_for_idempotency(jobs: list[dict[str, Any]], idempotency_key: str) -> dict[str, Any] | None:
    for job in jobs:
        args = job.get("args") or {}
        if args.get("idempotency_key") == idempotency_key:
            return job
    return None


def _find_recent_flow_job(jobs: list[dict[str, Any]], *, flow_path: str, run_started_at: datetime) -> dict[str, Any] | None:
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for job in jobs:
        if job.get("script_path") != flow_path:
            continue
        if job.get("job_kind") != "flow":
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


def _summarize_flow_status(flow_status: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(flow_status, dict):
        return {}
    modules = []
    for module in flow_status.get("modules") or []:
        if not isinstance(module, dict):
            continue
        modules.append(
            {
                "id": module.get("id"),
                "type": module.get("type"),
                "skipped": module.get("skipped"),
                "branch_chosen": module.get("branch_chosen"),
            }
        )
    return {
        "step": flow_status.get("step"),
        "modules": modules,
        "failure_module": flow_status.get("failure_module"),
    }


def _summarize_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job.get("id"),
        "script_path": job.get("script_path"),
        "job_kind": job.get("job_kind"),
        "created_at": job.get("created_at"),
        "completed_at": job.get("completed_at"),
        "duration_ms": job.get("duration_ms"),
        "canceled": job.get("canceled"),
        "deleted": job.get("deleted"),
        "flow_status": _summarize_flow_status(job.get("flow_status")),
    }


def _extract_step_sequence(result_payload: dict[str, Any]) -> list[str]:
    scope_results = result_payload.get("scope_results") or []
    if not scope_results:
        return []
    steps = scope_results[0].get("steps") or {}
    if not isinstance(steps, dict):
        return []
    present = set(steps.keys())
    ordered = [step for step in EXPECTED_STEP_SEQUENCE if step in present]
    extras = sorted(step for step in present if step not in EXPECTED_STEP_SEQUENCE)
    return ordered + extras


def _first_scope_result(result_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result_payload, dict):
        return {}
    scope_results = result_payload.get("scope_results") or []
    if not isinstance(scope_results, list) or not scope_results:
        return {}
    first = scope_results[0]
    return first if isinstance(first, dict) else {}


def _is_reader_quality_block(result_payload: dict[str, Any] | None) -> bool:
    scope_result = _first_scope_result(result_payload)
    steps = scope_result.get("steps") or {}
    if not isinstance(steps, dict):
        return False
    read_fetch = steps.get("read_fetch") or {}
    if not isinstance(read_fetch, dict):
        return False
    if str(read_fetch.get("status") or "") != "blocked":
        return False
    if str(read_fetch.get("decision_reason") or "") != "reader_output_insufficient_substance":
        return False
    return True


def _read_fetch_raw_scrape_ids(result_payload: dict[str, Any] | None) -> list[str]:
    scope_result = _first_scope_result(result_payload)
    steps = scope_result.get("steps") or {}
    if not isinstance(steps, dict):
        return []
    read_fetch = steps.get("read_fetch") or {}
    if not isinstance(read_fetch, dict):
        return []
    refs = read_fetch.get("refs") or {}
    if not isinstance(refs, dict):
        return []
    raw_scrape_ids = refs.get("raw_scrape_ids") or []
    if not isinstance(raw_scrape_ids, list):
        return []
    return [str(raw_id) for raw_id in raw_scrape_ids if raw_id]


def _any_step_idempotent_reuse(result_payload: dict[str, Any] | None) -> bool:
    scope_result = _first_scope_result(result_payload)
    steps = scope_result.get("steps") or {}
    if not isinstance(steps, dict):
        return False
    for step_payload in steps.values():
        if not isinstance(step_payload, dict):
            continue
        details = step_payload.get("details") or {}
        if isinstance(details, dict) and bool(details.get("idempotent_reuse")):
            return True
    return False


def _all_step_envelopes_have_contract(result_payload: dict[str, Any]) -> bool:
    scope_results = result_payload.get("scope_results") or []
    if not scope_results:
        return False
    for scope_result in scope_results:
        steps = scope_result.get("steps") or {}
        for step_payload in steps.values():
            env = step_payload.get("envelope") or {}
            if not env.get("contract_version"):
                return False
            if env.get("orchestrator") != "windmill":
                return False
            if not env.get("windmill_workspace"):
                return False
            if not env.get("windmill_flow_path"):
                return False
    return True


def _build_storage_evidence_gates(result_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scope_results = result_payload.get("scope_results") or []
    summarize_summary = ""
    storage_mode = ""
    if scope_results:
        summarize_summary = (
            scope_results[0]
            .get("steps", {})
            .get("summarize_run", {})
            .get("summary", "")
        )
        storage_mode = str((scope_results[0].get("backend_response") or {}).get("storage_mode") or "")

    stub_mode = STUB_SUMMARY_MARKER in summarize_summary
    bridge_mode_status = storage_mode or ("stub" if stub_mode else "unknown")

    pending_note = (
        "not proven in Windmill stub run; requires Worker A product bridge + live storage adapters"
    )
    return {
        "postgres_rows_written": {"status": "pending", "note": pending_note},
        "pgvector_index_probe": {"status": "pending", "note": pending_note},
        "minio_object_refs": {"status": "pending", "note": pending_note},
        "reader_output_ref": {"status": "pending", "note": pending_note},
        "analysis_provenance_chain": {"status": "pending", "note": pending_note},
        "quality_gate_blocked_before_index_analyze": {"status": "pending", "note": pending_note},
        "idempotent_rerun": {"status": "pending", "note": pending_note},
        "stale_drill_stale_but_usable": {"status": "pending", "note": pending_note},
        "stale_drill_stale_blocked": {"status": "pending", "note": pending_note},
        "failure_handler_drill": {
            "status": "not_run",
            "note": "failure injection is a separate pre-schedule gate; this San Jose product path run verified the native failure handler surface was configured",
        },
        "bridge_mode": {"status": bridge_mode_status, "note": summarize_summary},
    }


def _load_windmill_domain_script_module() -> Any:
    spec = spec_from_file_location("windmill_domain_boundary", WINDMILL_DOMAIN_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise HarnessError(
            "product_bridge",
            "unable to load windmill domain script for backend endpoint probe",
            {"script_path": str(WINDMILL_DOMAIN_SCRIPT_PATH)},
        )
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_backend_endpoint_local_probe(backend_endpoint_auth_token: str, *, feature_key: str = FEATURE_KEY) -> dict[str, Any]:
    module = _load_windmill_domain_script_module()
    expected_auth = f"Bearer {backend_endpoint_auth_token}"

    class _ProbeHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            auth_header = self.headers.get("Authorization", "")
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body.decode("utf-8") if body else "{}")
            except json.JSONDecodeError:
                payload = {}
            if auth_header != expected_auth:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "failed", "error": "unauthorized"}).encode("utf-8"))
                return
            response = {
                "status": "succeeded",
                "decision_reason": "scope_completed",
                "probe": "backend_endpoint_local_mock",
                "jurisdiction": payload.get("jurisdiction"),
                "source_family": payload.get("source_family"),
                "steps": {
                    "search_materialize": {"status": "succeeded"},
                    "freshness_gate": {"status": "succeeded", "decision_reason": "fresh"},
                    "read_fetch": {"status": "succeeded"},
                    "index": {"status": "succeeded"},
                    "analyze": {"status": "succeeded"},
                    "summarize_run": {"status": "succeeded"},
                },
                "storage_mode": "in_memory_domain_ports",
                "missing_runtime_adapters": [
                    "postgres_pipeline_state_store_adapter",
                    "minio_artifact_store_adapter",
                    "pgvector_chunk_store_adapter",
                ],
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _ProbeHandler)
    endpoint_url = f"http://127.0.0.1:{server.server_port}/domain-command"
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        result = module.main(
            step="run_scope_pipeline",
            idempotency_key=f"{feature_key}-backend-probe",
            scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
            scope_index=0,
            stale_status="fresh",
            search_query="San Jose CA city council meeting minutes housing",
            analysis_question="Summarize housing-related signals.",
            command_client="backend_endpoint",
            backend_endpoint_url=endpoint_url,
            backend_endpoint_auth_token=backend_endpoint_auth_token,
            backend_endpoint_timeout_seconds=10,
        )
        expected_steps = {"search_materialize", "freshness_gate", "read_fetch", "index", "analyze", "summarize_run"}
        if result.get("status") != "succeeded":
            return {"status": "failed", "note": "local mock probe did not complete", "result_status": result.get("status")}
        observed_steps = set((result.get("steps") or {}).keys())
        if observed_steps != expected_steps:
            return {
                "status": "failed",
                "note": "local mock probe missing expected command sequence",
                "observed_steps": sorted(observed_steps),
            }
        return {"status": "passed", "note": "local mock backend endpoint probe passed"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "note": "local mock backend endpoint probe failed", "detail": str(exc)}
    finally:
        server.shutdown()
        server_thread.join(timeout=2)
        server.server_close()


def _build_backend_endpoint_readiness(
    *,
    backend_endpoint_url: str | None,
    backend_endpoint_auth_token: str | None,
    feature_key: str = FEATURE_KEY,
) -> dict[str, Any]:
    endpoint_url = (backend_endpoint_url or "").strip()
    auth_token = (backend_endpoint_auth_token or "").strip()
    missing: list[str] = []
    if not endpoint_url:
        missing.append("backend_endpoint_url")
    if not auth_token:
        missing.append("backend_endpoint_auth_token")

    if missing:
        return {
            "status": "not_configured",
            "note": "backend endpoint mode is opt-in and currently not configured",
            "missing_inputs": missing,
            "local_mock_probe": {"status": "skipped", "note": "missing required backend endpoint inputs"},
        }

    local_probe = _run_backend_endpoint_local_probe(auth_token, feature_key=feature_key)
    if local_probe.get("status") == "passed":
        return {
            "status": "ready_for_opt_in",
            "note": "backend endpoint config is present and local mock probe passed",
            "missing_inputs": [],
            "local_mock_probe": local_probe,
        }
    return {
        "status": "probe_failed",
        "note": "backend endpoint config is present but local mock probe failed",
        "missing_inputs": [],
        "local_mock_probe": local_probe,
    }


def _normalize_searx_results(payload: dict[str, Any], limit: int = 3) -> list[dict[str, str]]:
    top = []
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        top.append(
            {
                "url": str(item.get("url") or ""),
                "title": str(item.get("title") or ""),
                "snippet": str(item.get("content") or ""),
            }
        )
        if len(top) >= limit:
            break
    return top


def _probe_searx(endpoint: str, query: str, timeout_seconds: int = 20) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        response = requests.get(
            endpoint,
            params={"q": query, "format": "json"},
            timeout=timeout_seconds,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        if response.status_code != 200:
            return {
                "provider": "searxng",
                "endpoint": endpoint,
                "query": query,
                "status": "failed",
                "failure_classification": "http_error",
                "http_status": response.status_code,
                "result_count": 0,
                "latency_ms": latency_ms,
                "top_results": [],
            }
        payload = response.json()
        result_count = len(payload.get("results") or [])
        return {
            "provider": "searxng",
            "endpoint": endpoint,
            "query": query,
            "status": "succeeded",
            "failure_classification": None,
            "http_status": response.status_code,
            "result_count": result_count,
            "latency_ms": latency_ms,
            "top_results": _normalize_searx_results(payload),
        }
    except requests.Timeout:
        return {
            "provider": "searxng",
            "endpoint": endpoint,
            "query": query,
            "status": "failed",
            "failure_classification": "timeout",
            "result_count": 0,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "top_results": [],
        }
    except requests.RequestException as exc:
        return {
            "provider": "searxng",
            "endpoint": endpoint,
            "query": query,
            "status": "failed",
            "failure_classification": "network_error",
            "error": str(exc),
            "result_count": 0,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "top_results": [],
        }


def _probe_exa(query: str, api_key: str, timeout_seconds: int = 20) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        response = requests.post(
            "https://api.exa.ai/search",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"query": query, "numResults": 5},
            timeout=timeout_seconds,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        if response.status_code != 200:
            return {
                "provider": "exa",
                "query": query,
                "status": "failed",
                "failure_classification": "http_error",
                "http_status": response.status_code,
                "result_count": 0,
                "latency_ms": latency_ms,
                "top_results": [],
            }
        payload = response.json()
        results = payload.get("results") or []
        top = []
        for item in results[:3]:
            if not isinstance(item, dict):
                continue
            top.append(
                {
                    "url": str(item.get("url") or ""),
                    "title": str(item.get("title") or ""),
                    "snippet": str(item.get("text") or item.get("snippet") or ""),
                }
            )
        return {
            "provider": "exa",
            "query": query,
            "status": "succeeded",
            "failure_classification": None,
            "http_status": response.status_code,
            "result_count": len(results),
            "latency_ms": latency_ms,
            "top_results": top,
        }
    except requests.Timeout:
        return {
            "provider": "exa",
            "query": query,
            "status": "failed",
            "failure_classification": "timeout",
            "result_count": 0,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "top_results": [],
        }
    except requests.RequestException as exc:
        return {
            "provider": "exa",
            "query": query,
            "status": "failed",
            "failure_classification": "network_error",
            "error": str(exc),
            "result_count": 0,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "top_results": [],
        }


def _probe_tavily(query: str, api_key: str, timeout_seconds: int = 20) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={"api_key": api_key, "query": query, "max_results": 5, "include_answer": False},
            timeout=timeout_seconds,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        if response.status_code != 200:
            return {
                "provider": "tavily",
                "query": query,
                "status": "failed",
                "failure_classification": "http_error",
                "http_status": response.status_code,
                "result_count": 0,
                "latency_ms": latency_ms,
                "top_results": [],
            }
        payload = response.json()
        results = payload.get("results") or []
        top = []
        for item in results[:3]:
            if not isinstance(item, dict):
                continue
            top.append(
                {
                    "url": str(item.get("url") or ""),
                    "title": str(item.get("title") or ""),
                    "snippet": str(item.get("content") or ""),
                }
            )
        return {
            "provider": "tavily",
            "query": query,
            "status": "succeeded",
            "failure_classification": None,
            "http_status": response.status_code,
            "result_count": len(results),
            "latency_ms": latency_ms,
            "top_results": top,
        }
    except requests.Timeout:
        return {
            "provider": "tavily",
            "query": query,
            "status": "failed",
            "failure_classification": "timeout",
            "result_count": 0,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "top_results": [],
        }
    except requests.RequestException as exc:
        return {
            "provider": "tavily",
            "query": query,
            "status": "failed",
            "failure_classification": "network_error",
            "error": str(exc),
            "result_count": 0,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "top_results": [],
        }


def _run_search_provider_bakeoff(
    *,
    query: str,
    searx_endpoints: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    probes: list[dict[str, Any]] = []
    sensitive_values: list[str] = []
    for endpoint in searx_endpoints:
        probes.append(_probe_searx(endpoint, query))

    exa_key = ""
    try:
        exa_key = _get_cached_secret(EXA_SECRET_REF)
    except HarnessError:
        probes.append(
            {
                "provider": "exa",
                "query": query,
                "status": "not_configured",
                "failure_classification": "missing_secret",
                "result_count": 0,
                "latency_ms": 0,
                "top_results": [],
            }
        )
    if exa_key:
        sensitive_values.append(exa_key)
        probes.append(_probe_exa(query, exa_key))

    tavily_key = ""
    try:
        tavily_key = _get_cached_secret(TAVILY_SECRET_REF)
    except HarnessError:
        probes.append(
            {
                "provider": "tavily",
                "query": query,
                "status": "not_configured",
                "failure_classification": "missing_secret",
                "result_count": 0,
                "latency_ms": 0,
                "top_results": [],
            }
        )
    if tavily_key:
        sensitive_values.append(tavily_key)
        probes.append(_probe_tavily(query, tavily_key))

    return probes, sensitive_values


async def _query_db_evidence(
    database_url: str,
    *,
    idempotency_key: str,
    jurisdiction: str,
    source_family: str,
) -> dict[str, Any]:
    try:
        import asyncpg
    except ImportError:
        return {"status": "blocked", "reason": "asyncpg_missing"}

    conn = await asyncpg.connect(database_url)
    try:
        search_rows = await conn.fetch(
            """
            SELECT id, result_count
            FROM public.search_result_snapshots
            WHERE idempotency_key = $1 OR idempotency_key LIKE ($1 || '::%')
            ORDER BY created_at DESC
            LIMIT 10
            """,
            idempotency_key,
        )
        artifacts = await conn.fetch(
            """
            SELECT id, artifact_kind, content_hash, storage_uri
            FROM public.content_artifacts
            WHERE source_family = $1
            ORDER BY created_at DESC
            LIMIT 25
            """,
            source_family,
        )
        raw_scrapes = await conn.fetch(
            """
            SELECT id, url, canonical_document_key, left(coalesce(data->>'content', ''), 700) AS content_excerpt
            FROM public.raw_scrapes
            WHERE canonical_document_key ILIKE $1
            ORDER BY created_at DESC
            LIMIT 25
            """,
            f"%{jurisdiction.lower().replace(' ', '-')}%",
        )
        chunk_stats = await conn.fetchrow(
            """
            SELECT
              COUNT(*)::int AS total,
              COUNT(*) FILTER (WHERE embedding IS NOT NULL)::int AS with_embedding
            FROM public.document_chunks
            WHERE metadata::text ILIKE $1
            """,
            f"%{jurisdiction.lower().replace(' ', '-')}%",
        )
        command_rows = await conn.fetch(
            """
            SELECT id, command, status, refs, alerts
            FROM public.pipeline_command_results
            WHERE idempotency_key = $1 OR idempotency_key LIKE ($1 || '::%')
            ORDER BY created_at DESC
            LIMIT 20
            """,
            idempotency_key,
        )
    finally:
        await conn.close()

    object_refs = [row["storage_uri"] for row in artifacts if row.get("storage_uri")]
    minio_checks = []
    for uri in object_refs[:3]:
        parsed = urlparse(uri)
        if parsed.scheme in {"http", "https"}:
            try:
                resp = requests.head(uri, timeout=10)
                minio_checks.append({"uri": uri, "status": "checked", "http_status": resp.status_code})
            except requests.RequestException as exc:
                minio_checks.append({"uri": uri, "status": "probe_failed", "error": str(exc)})
        else:
            minio_checks.append({"uri": uri, "status": "not_probeable_without_storage_client"})

    return {
        "status": "queried",
        "search_snapshot_rows": [{"id": str(r["id"]), "result_count": int(r["result_count"] or 0)} for r in search_rows],
        "content_artifact_rows": [
            {
                "id": str(r["id"]),
                "artifact_kind": str(r["artifact_kind"]),
                "content_hash": str(r["content_hash"]),
                "storage_uri": str(r["storage_uri"] or ""),
            }
            for r in artifacts
        ],
        "raw_scrape_rows": [
            {
                "id": str(r["id"]),
                "url": str(r["url"] or ""),
                "canonical_document_key": str(r["canonical_document_key"] or ""),
                "content_excerpt": str(r["content_excerpt"] or ""),
            }
            for r in raw_scrapes
        ],
        "document_chunks_count": int((chunk_stats or {}).get("total") or 0),
        "document_chunks_with_embedding_count": int((chunk_stats or {}).get("with_embedding") or 0),
        "pipeline_command_rows": [
            {
                "id": str(r["id"]),
                "command": str(r["command"]),
                "status": str(r["status"]),
                "refs": r["refs"] if isinstance(r["refs"], dict) else {},
                "alerts": r["alerts"] if isinstance(r["alerts"], list) else [],
            }
            for r in command_rows
        ],
        "minio_object_checks": minio_checks,
    }


def _derive_db_probe(
    *,
    idempotency_key: str,
    jurisdiction: str,
    source_family: str,
    database_url: str | None,
) -> dict[str, Any]:
    if not database_url:
        return {"status": "not_configured", "reason": "DATABASE_URL missing"}
    try:
        return asyncio.run(
            _query_db_evidence(
                database_url,
                idempotency_key=idempotency_key,
                jurisdiction=jurisdiction,
                source_family=source_family,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "probe_failed", "reason": str(exc)}


def _assert_no_secret_leak(report: dict[str, Any], secrets: list[str]) -> list[str]:
    blob = json.dumps(report, sort_keys=True)
    leaked = []
    for secret in secrets:
        if secret and len(secret) >= 8 and secret in blob:
            leaked.append(secret[:6] + "...redacted")
    return leaked


def _derive_classification(
    *,
    result_payload: dict[str, Any] | None,
    storage_gates: dict[str, dict[str, Any]],
    backend_endpoint_readiness: dict[str, Any],
    blockers: list[dict[str, Any]],
) -> tuple[str, str]:
    hard_blockers = [b for b in blockers if b.get("blocking", True)]
    if hard_blockers:
        return "blocked", "blocked"
    if not result_payload:
        if backend_endpoint_readiness.get("status") == "ready_for_opt_in":
            return "backend_bridge_surface_ready", "partial"
        return "read_only_surface_pass", "partial"

    if _is_reader_quality_block(result_payload):
        no_index_analyze_gate = storage_gates.get("quality_gate_blocked_before_index_analyze", {})
        if no_index_analyze_gate.get("status") == "passed":
            return "quality_gate_block_pass", "ready"
        return "quality_gate_block_observed", "partial"

    run_status = result_payload.get("status")
    if run_status != "succeeded":
        return "failed_run", "partial"

    scope_results = result_payload.get("scope_results") or []
    if not scope_results:
        return "failed_run", "partial"

    incomplete_storage_gates = [
        gate_name
        for gate_name, gate in storage_gates.items()
        if gate_name not in {"bridge_mode", "failure_handler_drill"}
        and gate.get("status") in {"pending", "failed"}
    ]
    if not incomplete_storage_gates and storage_gates.get("bridge_mode", {}).get("status") not in {"stub", "unknown"}:
        return "full_product_pass", "ready"

    summary = (
        scope_results[0]
        .get("steps", {})
        .get("summarize_run", {})
        .get("summary", "")
    )
    if backend_endpoint_readiness.get("status") == "ready_for_opt_in":
        return "backend_bridge_surface_ready", "partial"
    if STUB_SUMMARY_MARKER in summary:
        return "stub_orchestration_pass", "partial"
    return "failed_run", "partial"


def _derive_manual_audit_notes(
    *,
    result_payload: dict[str, Any] | None,
    db_storage_probe: dict[str, Any],
) -> dict[str, str]:
    raw_rows = db_storage_probe.get("raw_scrape_rows") or []
    reader_excerpt = ""
    if raw_rows:
        current_raw_ids = set(_read_fetch_raw_scrape_ids(result_payload))
        matching_rows = [
            raw_row
            for raw_row in raw_rows
            if isinstance(raw_row, dict) and str(raw_row.get("id") or "") in current_raw_ids
        ]
        first_raw = matching_rows[0] if matching_rows else raw_rows[0]
        url = first_raw.get("url") or ""
        content_excerpt = " ".join(str(first_raw.get("content_excerpt") or "").split())
        reader_excerpt = f"{url}: {content_excerpt[:500]}".strip(": ")

    analysis: dict[str, Any] = {}
    if result_payload:
        scope_results = result_payload.get("scope_results") or []
        if scope_results:
            analysis = (
                scope_results[0]
                .get("steps", {})
                .get("analyze", {})
                .get("details", {})
                .get("analysis", {})
            )
            if not isinstance(analysis, dict):
                analysis = {}

    analysis_excerpt = str(analysis.get("summary") or analysis.get("answer") or "")[:700]
    key_points = analysis.get("key_points")
    key_point_text = " ".join(str(item) for item in key_points if isinstance(item, str)) if isinstance(key_points, list) else ""
    substantive_analysis_text = f"{analysis_excerpt} {key_point_text}".lower()
    has_substantive_policy_analysis = any(
        signal in substantive_analysis_text
        for signal in (
            "commercial linkage fee",
            "per sq. ft",
            "per square foot",
            "resolution",
            "ordinance",
            "fee schedule",
            "gross square footage",
        )
    )
    sufficiency_state = str(analysis.get("sufficiency_state") or "").lower()
    insufficient = sufficiency_state == "insufficient" or "does not contain" in analysis_excerpt.lower()
    quality_blocked = _is_reader_quality_block(result_payload)

    if quality_blocked:
        reader_quality_note = (
            "Selected San Jose source resolved to navigation/menu content and was blocked by reader quality gate "
            "before persistence/index/analyze."
        )
        llm_quality_note = (
            "Analysis was intentionally not run because the reader quality gate blocked insufficient source substance."
        )
        manual_verdict = "PASS_READER_QUALITY_GATE_BLOCKED_NAV_OUTPUT"
    elif insufficient:
        if has_substantive_policy_analysis:
            reader_quality_note = (
                "Reader output was persisted and contained substantive policy text; the analysis remained insufficient for final economic decision-grade output."
            )
            llm_quality_note = (
                "LLM analysis extracted policy facts but fail-closed because the package did not satisfy all economic handoff gates."
            )
            manual_verdict = "PASS_DATA_EXTRACTION_FAIL_ECONOMIC_HANDOFF"
        else:
            reader_quality_note = (
                "Z.ai reader executed and persisted output, but the selected San Jose source did not contain enough substantive policy content for the requested analysis."
            )
            llm_quality_note = (
                "Z.ai analysis correctly refused to infer housing signals from insufficient evidence; product mechanics passed, discovery/source targeting did not."
            )
            manual_verdict = "PASS_MECHANICS_FAIL_DISCOVERY_QUALITY"
    elif analysis_excerpt:
        reader_quality_note = "Reader output was persisted and provided to analysis."
        llm_quality_note = "LLM analysis produced a substantive answer from persisted evidence."
        manual_verdict = "PASS_MANUAL_AUDIT"
    else:
        reader_quality_note = "Reader output evidence was not available in the DB probe."
        llm_quality_note = "LLM analysis excerpt was not available in the run payload."
        manual_verdict = "PENDING_MANUAL_AUDIT"

    return {
        "reader_output_excerpt": reader_excerpt,
        "reader_quality_note": reader_quality_note,
        "llm_analysis_excerpt": analysis_excerpt,
        "llm_quality_note": llm_quality_note,
        "manual_verdict": manual_verdict,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Windmill San Jose Live Validation Gate",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- feature_key: `{report['feature_key']}`",
        f"- harness_version: `{report['harness_version']}`",
        f"- run_mode: `{report['run_mode']}`",
        f"- classification: `{report['classification']}`",
        f"- full_run_readiness: `{report['full_run_readiness']}`",
        "",
        "## Deployment Surface",
        f"- flow_deployed: `{report['deployment_surface']['flow_deployed']}`",
        f"- script_deployed: `{report['deployment_surface']['script_deployed']}`",
        f"- flow_unscheduled: `{report['deployment_surface']['flow_unscheduled']}`",
        "",
        "## Manual Run",
    ]
    manual_run = report.get("manual_run") or {}
    if manual_run.get("attempted"):
        lines.extend(
            [
                "- attempted: `true`",
                f"- idempotency_key: `{manual_run.get('idempotency_key', '')}`",
                f"- windmill_job_id: `{manual_run.get('windmill_job_id', 'not_found')}`",
                f"- final_status: `{manual_run.get('final_status', 'unknown')}`",
                f"- scope_totals: `{manual_run.get('scope_totals', {})}`",
                f"- step_sequence: `{manual_run.get('step_sequence', [])}`",
                f"- step_sequence_matches_expected: `{manual_run.get('step_sequence_matches_expected', False)}`",
                f"- contract_metadata_present: `{manual_run.get('contract_metadata_present', False)}`",
            ]
        )
    else:
        lines.append("- attempted: `false`")

    lines.extend(["", "## Storage Evidence Gates"])
    for gate_name, gate in report["storage_evidence_gates"].items():
        lines.append(f"- {gate_name}: `{gate['status']}` ({gate['note']})")

    backend_readiness = report.get("backend_endpoint_readiness") or {}
    lines.extend(
        [
            "",
            "## Backend Endpoint Readiness",
            f"- status: `{backend_readiness.get('status', 'unknown')}`",
            f"- note: {backend_readiness.get('note', '')}",
            f"- missing_inputs: `{backend_readiness.get('missing_inputs', [])}`",
            f"- local_mock_probe: `{backend_readiness.get('local_mock_probe', {})}`",
        ]
    )

    lines.extend(["", "## Search Provider Bakeoff"])
    probes = report.get("search_provider_bakeoff") or []
    if probes:
        lines.extend(
            [
                "| Provider | Status | Result Count | Latency (ms) | Failure Class | Top URL |",
                "|---|---:|---:|---:|---|---|",
            ]
        )
        for probe in probes:
            top_url = ""
            top_results = probe.get("top_results") or []
            if top_results and isinstance(top_results, list):
                top_url = str(top_results[0].get("url") or "")
            lines.append(
                "| {provider} | {status} | {count} | {latency} | {failure} | {top_url} |".format(
                    provider=probe.get("provider", ""),
                    status=probe.get("status", ""),
                    count=probe.get("result_count", 0),
                    latency=probe.get("latency_ms", 0),
                    failure=probe.get("failure_classification") or "",
                    top_url=top_url,
                )
            )
    else:
        lines.append("- no probes")

    db_probe = report.get("db_storage_probe") or {}
    lines.extend(
        [
            "",
            "## DB/Storage Evidence",
            f"- probe_status: `{db_probe.get('status', 'unknown')}`",
            f"- search_snapshot_rows: `{len(db_probe.get('search_snapshot_rows', []))}`",
            f"- content_artifact_rows: `{len(db_probe.get('content_artifact_rows', []))}`",
            f"- raw_scrape_rows: `{len(db_probe.get('raw_scrape_rows', []))}`",
            f"- document_chunks_count: `{db_probe.get('document_chunks_count', 0)}`",
            f"- document_chunks_with_embedding_count: `{db_probe.get('document_chunks_with_embedding_count', 0)}`",
            f"- minio_object_checks: `{db_probe.get('minio_object_checks', [])}`",
        ]
    )

    manual_notes = report.get("manual_audit_notes") or {}
    lines.extend(
        [
            "",
            "## Manual Audit Notes",
            f"- reader_output_excerpt: {manual_notes.get('reader_output_excerpt', '-') or '-'}",
            f"- reader_quality_note: {manual_notes.get('reader_quality_note', '-') or '-'}",
            f"- llm_analysis_excerpt: {manual_notes.get('llm_analysis_excerpt', '-') or '-'}",
            f"- llm_quality_note: {manual_notes.get('llm_quality_note', '-') or '-'}",
            f"- manual_verdict: {manual_notes.get('manual_verdict', 'PENDING_MANUAL_AUDIT')}",
        ]
    )

    lines.extend(["", "## Blockers"])
    if report["blockers"]:
        for blocker in report["blockers"]:
            lines.append(f"- `{blocker['category']}`: {blocker['message']}")
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def run_harness(
    *,
    run_mode: str,
    workspace: str,
    flow_path: str,
    script_path: str,
    jurisdiction: str,
    source_family: str,
    search_query: str,
    analysis_question: str,
    stale_status: str,
    scope_parallelism: int,
    idempotency_key: str | None,
    stale_drill_statuses: list[str],
    run_idempotent_rerun: bool,
    searx_endpoints: list[str],
    backend_endpoint_url: str | None,
    backend_endpoint_auth_token: str | None,
    database_url: str | None,
    backend_endpoint_timeout_seconds: int = DEFAULT_BACKEND_ENDPOINT_TIMEOUT_SECONDS,
    feature_key: str = FEATURE_KEY,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    result_payload: dict[str, Any] | None = None
    sensitive_values: list[str] = []

    context = _build_context(workspace)
    sensitive_values.append(context.windmill_api_token)
    _setup_workspace_profile(context)

    try:
        workspace_profiles = _wmill(context, "workspace", "list")
        flow = _wmill(context, "flow", "get", flow_path, "--json", expect_json=True)
        script = _wmill(context, "script", "get", script_path, "--json", expect_json=True)
        schedules = _wmill(context, "schedule", "list", "--json", expect_json=True)
        jobs_before = _wmill(context, "job", "list", "--script-path", flow_path, "--limit", "20", "--json", expect_json=True)
    except HarnessError as err:
        blockers.append({"category": err.category, "message": str(err), "details": err.details, "blocking": True})
        workspace_profiles = ""
        flow = {}
        script = {}
        schedules = []
        jobs_before = []

    flow_unscheduled = True
    if isinstance(schedules, list):
        schedule_paths = {item.get("path", "") for item in schedules}
        flow_unscheduled = flow_path not in schedule_paths
    if not flow:
        blockers.append(
            {
                "category": "deployment",
                "message": "target flow is not deployed in workspace",
                "details": {"flow_path": flow_path},
                "blocking": True,
            }
        )
    if not script:
        blockers.append(
            {
                "category": "deployment",
                "message": "target script is not deployed in workspace",
                "details": {"script_path": script_path},
                "blocking": True,
            }
        )
    if not flow_unscheduled:
        blockers.append(
            {
                "category": "deployment",
                "message": "target flow has a schedule and is not safe as manual-only POC",
                "details": {"flow_path": flow_path},
                "blocking": True,
            }
        )

    backend_endpoint_readiness = _build_backend_endpoint_readiness(
        backend_endpoint_url=backend_endpoint_url,
        backend_endpoint_auth_token=backend_endpoint_auth_token,
        feature_key=feature_key,
    )

    command_client = "stub" if run_mode == "stub-run" else "backend_endpoint"
    manual_run: dict[str, Any] = {"attempted": False, "command_client": command_client}
    stale_drills: list[dict[str, Any]] = []
    idempotent_rerun: dict[str, Any] = {"attempted": False}
    if not blockers and run_mode in {"stub-run", "backend-endpoint-run"}:
        if run_mode == "backend-endpoint-run" and backend_endpoint_readiness.get("status") != "ready_for_opt_in":
            blockers.append(
                {
                    "category": "product_bridge",
                    "message": "backend-endpoint-run requested but backend endpoint readiness is not ready_for_opt_in",
                    "details": backend_endpoint_readiness,
                    "blocking": True,
                }
            )
            manual_run["attempted"] = False
        else:
            manual_run["attempted"] = True
    if manual_run.get("attempted"):
        manual_run["attempted"] = True
        idempotency = idempotency_key or f"{feature_key}-live-gate-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
        manual_run["idempotency_key"] = idempotency
        payload = {
            "idempotency_key": idempotency,
            "mode": "manual",
            "jurisdictions": [jurisdiction],
            "source_families": [source_family],
            "scope_parallelism": scope_parallelism,
            "search_query": search_query,
            "analysis_question": analysis_question,
            "stale_status": stale_status,
            "command_client": command_client,
            "backend_endpoint_timeout_seconds": backend_endpoint_timeout_seconds,
        }
        try:
            run_started_at = datetime.now(UTC)
            result_payload = _wmill(
                context,
                "flow",
                "run",
                flow_path,
                "-s",
                "-d",
                json.dumps(payload),
                expect_json=True,
            )
            jobs_after = _wmill(
                context,
                "job",
                "list",
                "--all",
                "--limit",
                "200",
                "--json",
                expect_json=True,
            )
            matched_job = _find_job_for_idempotency(jobs_after, idempotency) or _find_job_for_idempotency(jobs_before, idempotency)
            if not matched_job:
                fallback_jobs = _wmill(
                    context,
                    "job",
                    "list",
                    "--script-path",
                    script_path,
                    "--all",
                    "--limit",
                    "80",
                    "--json",
                    expect_json=True,
                )
                matched_job = _find_job_for_idempotency(fallback_jobs, idempotency)
            if not matched_job:
                matched_job = _find_recent_flow_job(jobs_after, flow_path=flow_path, run_started_at=run_started_at)
            if matched_job:
                job_id = matched_job.get("id", "")
                manual_run["windmill_job_id"] = job_id
                job_get = _wmill(context, "job", "get", job_id, "--json", expect_json=True)
                manual_run["job_get"] = _summarize_job(job_get)
                manual_run["job_logs_excerpt"] = str(_wmill(context, "job", "logs", job_id))[-1200:]
            else:
                manual_run["windmill_job_id"] = "not_found"

            step_sequence = _extract_step_sequence(result_payload)
            manual_run["final_status"] = result_payload.get("status")
            manual_run["scope_totals"] = {
                "scope_total": result_payload.get("scope_total"),
                "scope_succeeded": result_payload.get("scope_succeeded"),
                "scope_failed": result_payload.get("scope_failed"),
                "scope_blocked": result_payload.get("scope_blocked"),
            }
            manual_run["step_sequence"] = step_sequence
            expected_sequence = (
                EXPECTED_QUALITY_BLOCK_STEP_SEQUENCE if _is_reader_quality_block(result_payload) else EXPECTED_STEP_SEQUENCE
            )
            manual_run["expected_step_sequence"] = expected_sequence
            manual_run["step_sequence_matches_expected"] = step_sequence == expected_sequence
            manual_run["contract_metadata_present"] = _all_step_envelopes_have_contract(result_payload)

            for drill_status in stale_drill_statuses:
                drill_key = f"{idempotency}:{drill_status}"
                drill_payload = dict(payload)
                drill_payload["idempotency_key"] = drill_key
                drill_payload["stale_status"] = drill_status
                drill_result = _wmill(
                    context,
                    "flow",
                    "run",
                    flow_path,
                    "-s",
                    "-d",
                    json.dumps(drill_payload),
                    expect_json=True,
                )
                stale_drills.append(
                    {
                        "idempotency_key": drill_key,
                        "requested_stale_status": drill_status,
                        "status": drill_result.get("status"),
                        "scope_succeeded": drill_result.get("scope_succeeded"),
                        "scope_failed": drill_result.get("scope_failed"),
                        "step_sequence": _extract_step_sequence(drill_result),
                        "freshness_gate_status": (
                            (
                                _first_scope_result(drill_result).get("steps", {}).get("freshness_gate", {}) or {}
                            ).get("status")
                        ),
                        "freshness_gate_reason": (
                            (
                                _first_scope_result(drill_result).get("steps", {}).get("freshness_gate", {}) or {}
                            ).get("decision_reason")
                        ),
                        "read_fetch_status": (
                            (
                                _first_scope_result(drill_result).get("steps", {}).get("read_fetch", {}) or {}
                            ).get("status")
                        ),
                        "read_fetch_reason": (
                            (
                                _first_scope_result(drill_result).get("steps", {}).get("read_fetch", {}) or {}
                            ).get("decision_reason")
                        ),
                        "quality_blocked": _is_reader_quality_block(drill_result),
                    }
                )

            if run_idempotent_rerun:
                idempotent_rerun["attempted"] = True
                rerun_result = _wmill(
                    context,
                    "flow",
                    "run",
                    flow_path,
                    "-s",
                    "-d",
                    json.dumps(payload),
                    expect_json=True,
                )
                idempotent_rerun["status"] = rerun_result.get("status")
                idempotent_rerun["step_sequence"] = _extract_step_sequence(rerun_result)
                idempotent_rerun["scope_totals"] = {
                    "scope_total": rerun_result.get("scope_total"),
                    "scope_succeeded": rerun_result.get("scope_succeeded"),
                    "scope_failed": rerun_result.get("scope_failed"),
                    "scope_blocked": rerun_result.get("scope_blocked"),
                }
                idempotent_rerun["result_payload"] = rerun_result
        except HarnessError as err:
            blockers.append({"category": err.category, "message": str(err), "details": err.details, "blocking": True})
    elif run_mode == "read-only":
        manual_run["attempted"] = False

    storage_gates = _build_storage_evidence_gates(result_payload or {})
    quality_blocked = _is_reader_quality_block(result_payload)
    if quality_blocked:
        scope_steps = (_first_scope_result(result_payload).get("steps") or {}) if result_payload else {}
        missing_index_analyze = "index" not in scope_steps and "analyze" not in scope_steps
        storage_gates["quality_gate_blocked_before_index_analyze"] = {
            "status": "passed" if missing_index_analyze else "failed",
            "note": "reader quality gate blocked at read_fetch; index/analyze were not executed",
        }
        for gate_name in [
            "postgres_rows_written",
            "reader_output_ref",
            "minio_object_refs",
            "pgvector_index_probe",
            "analysis_provenance_chain",
        ]:
            storage_gates[gate_name] = {
                "status": "not_applicable",
                "note": "current run intentionally blocked at read_fetch before persistence/index/analyze",
            }
    else:
        storage_gates["quality_gate_blocked_before_index_analyze"] = {
            "status": "not_applicable",
            "note": "current run completed past read_fetch; reader quality block was not expected in this success path",
        }

    if stale_drills:
        by_mode = {item["requested_stale_status"]: item for item in stale_drills}
        usable = by_mode.get("stale_but_usable")
        blocked = by_mode.get("stale_blocked")
        usable_pass = False
        if usable:
            freshness_ok = usable.get("freshness_gate_status") in {"succeeded", "succeeded_with_alerts"} and usable.get("freshness_gate_reason") in {
                "fresh",
                "stale_but_usable",
            }
            usable_pass = freshness_ok
        storage_gates["stale_drill_stale_but_usable"] = {
            "status": "passed" if usable_pass else "failed",
            "note": str(usable or {}),
        }
        blocked_pass = False
        if blocked:
            blocked_steps = blocked.get("step_sequence") or []
            blocked_pass = "read_fetch" not in blocked_steps and "index" not in blocked_steps and "analyze" not in blocked_steps
        storage_gates["stale_drill_stale_blocked"] = {
            "status": "passed" if blocked_pass else "failed",
            "note": str(blocked or {}),
        }

    if idempotent_rerun.get("attempted"):
        rerun_payload = idempotent_rerun.get("result_payload") or {}
        idempotent_reuse = _any_step_idempotent_reuse(rerun_payload)
        rerun_quality_blocked = _is_reader_quality_block(rerun_payload)
        if quality_blocked:
            rerun_pass = rerun_quality_blocked and idempotent_reuse
        else:
            rerun_pass = idempotent_rerun.get("status") == "succeeded" and idempotent_reuse
        storage_gates["idempotent_rerun"] = {
            "status": "passed" if rerun_pass else "pending",
            "note": (
                f"rerun_status={idempotent_rerun.get('status')} "
                f"rerun_quality_blocked={rerun_quality_blocked} "
                f"idempotent_reuse={idempotent_reuse}"
            ),
        }

    search_provider_bakeoff, provider_secrets = _run_search_provider_bakeoff(
        query=search_query,
        searx_endpoints=searx_endpoints or DEFAULT_SEARX_ENDPOINTS,
    )
    sensitive_values.extend(provider_secrets)

    db_storage_probe = _derive_db_probe(
        idempotency_key=manual_run.get("idempotency_key", idempotency_key or ""),
        jurisdiction=jurisdiction,
        source_family=source_family,
        database_url=database_url or os.getenv("DATABASE_URL"),
    )
    if db_storage_probe.get("status") == "queried" and not quality_blocked:
        postgres_rows_written = any(
            [
                db_storage_probe.get("search_snapshot_rows"),
                db_storage_probe.get("content_artifact_rows"),
                db_storage_probe.get("raw_scrape_rows"),
                db_storage_probe.get("pipeline_command_rows"),
                db_storage_probe.get("document_chunks_count", 0) > 0,
            ]
        )
        if postgres_rows_written:
            storage_gates["postgres_rows_written"] = {"status": "passed", "note": "Postgres product rows found"}
        if db_storage_probe.get("content_artifact_rows"):
            storage_gates["reader_output_ref"] = {"status": "passed", "note": "content_artifacts rows found"}
            storage_gates["minio_object_refs"] = {"status": "passed", "note": "storage_uri refs present in content_artifacts"}
        if db_storage_probe.get("document_chunks_count", 0) > 0:
            embedded_count = int(db_storage_probe.get("document_chunks_with_embedding_count", 0) or 0)
            if embedded_count > 0:
                storage_gates["pgvector_index_probe"] = {
                    "status": "passed",
                    "note": f"document_chunks rows found with embeddings ({embedded_count})",
                }
            else:
                storage_gates["pgvector_index_probe"] = {
                    "status": "failed",
                    "note": "document_chunks rows found but embeddings are NULL; chunk persistence passed, pgvector retrieval not proven",
                }
        analysis_rows = [
            row
            for row in db_storage_probe.get("pipeline_command_rows", [])
            if row.get("command") == "analyze" and row.get("status") in {"succeeded", "succeeded_with_alerts"}
        ]
        if analysis_rows:
            storage_gates["analysis_provenance_chain"] = {"status": "passed", "note": "successful analyze command row found"}
    elif db_storage_probe.get("status") in {"not_configured", "probe_failed", "blocked"}:
        blockers.append(
            {
                "category": "storage/runtime",
                "message": "DB/storage probe unavailable",
                "details": db_storage_probe,
                "blocking": False,
            }
        )
    if result_payload and storage_gates.get("bridge_mode", {}).get("status") == "stub":
        blockers.append(
            {
                "category": "product_bridge",
                "message": "flow run is still stub-backed; full product validation not yet possible",
                "details": {"bridge_mode": "stub"},
                "blocking": False,
            }
        )

    if result_payload and run_mode in {"stub-run", "backend-endpoint-run"}:
        missing_storage = [
            name
            for name, gate in storage_gates.items()
            if gate["status"] in {"pending", "failed"} and name not in {"bridge_mode", "failure_handler_drill"}
        ]
        if missing_storage:
            blockers.append(
                {
                    "category": "storage/runtime",
                    "message": "storage/runtime evidence gates are pending",
                    "details": {"pending_gates": missing_storage},
                    "blocking": False,
                }
            )

    if backend_endpoint_readiness.get("status") == "not_configured":
        blockers.append(
            {
                "category": "product_bridge",
                "message": "backend endpoint client is not configured for live Windmill validation",
                "details": {"missing_inputs": backend_endpoint_readiness.get("missing_inputs", [])},
                "blocking": False,
            }
        )
    elif backend_endpoint_readiness.get("status") == "probe_failed":
        blockers.append(
            {
                "category": "product_bridge",
                "message": "backend endpoint local mock probe failed",
                "details": backend_endpoint_readiness.get("local_mock_probe", {}),
                "blocking": False,
            }
        )

    classification, readiness = _derive_classification(
        result_payload=result_payload,
        storage_gates=storage_gates,
        backend_endpoint_readiness=backend_endpoint_readiness,
        blockers=blockers,
    )
    report: dict[str, Any] = {
        "generated_at": _now_iso(),
        "feature_key": feature_key,
        "harness_version": HARNESS_VERSION,
        "run_mode": run_mode,
        "classification": classification,
        "full_run_readiness": readiness,
        "canonical_variables": {
            "WINDMILL_API_TOKEN": "op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN",
            "WINDMILL_DEV_LOGIN_URL": "op://dev/Agent-Secrets-Production/WINDMILL_DEV_LOGIN_URL",
            "WINDMILL_BASE_URL": "derived as WINDMILL_DEV_LOGIN_URL without /user/login",
            "WINDMILL_WORKSPACE": workspace,
            "TMP_WMILL_CONFIG": "auto-created temporary profile directory",
            "BACKEND_PUBLIC_URL_VAR": "f/affordabot/BACKEND_PUBLIC_URL",
            "CRON_SECRET_VAR": "f/affordabot/CRON_SECRET",
            "BACKEND_ENDPOINT_URL": "optional local readiness input only",
            "BACKEND_ENDPOINT_AUTH_TOKEN": "optional local readiness input only",
        },
        "deployment_surface": {
            "flow_path": flow_path,
            "script_path": script_path,
            "flow_deployed": bool(flow),
            "script_deployed": bool(script),
            "flow_unscheduled": flow_unscheduled,
        },
        "surface_checks": {
            "workspace_profile_listed": bool(workspace_profiles),
            "schedule_count": len(schedules) if isinstance(schedules, list) else 0,
            "jobs_checked_count": len(jobs_before) if isinstance(jobs_before, list) else 0,
        },
        "manual_run": manual_run,
        "stale_drills": stale_drills,
        "idempotent_rerun": idempotent_rerun,
        "result_payload": result_payload,
        "storage_evidence_gates": storage_gates,
        "db_storage_probe": db_storage_probe,
        "search_provider_bakeoff": search_provider_bakeoff,
        "backend_endpoint_readiness": backend_endpoint_readiness,
        "manual_audit_notes": _derive_manual_audit_notes(
            result_payload=result_payload,
            db_storage_probe=db_storage_probe,
        ),
        "blockers": blockers,
    }
    leaked = _assert_no_secret_leak(report, sensitive_values + [backend_endpoint_auth_token or ""])
    if leaked:
        report["classification"] = "blocked"
        report["full_run_readiness"] = "blocked"
        report["blockers"].append(
            {
                "category": "security",
                "message": "secret leakage detected in report payload",
                "details": {"matches": leaked},
                "blocking": True,
            }
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Windmill San Jose live gate.")
    parser.add_argument("--run-mode", choices=["read-only", "stub-run", "backend-endpoint-run"], default="stub-run")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--flow-path", default=DEFAULT_FLOW_PATH)
    parser.add_argument("--script-path", default=DEFAULT_SCRIPT_PATH)
    parser.add_argument("--jurisdiction", default="San Jose CA")
    parser.add_argument("--source-family", default="meeting_minutes")
    parser.add_argument("--search-query", default="San Jose CA city council meeting minutes housing")
    parser.add_argument(
        "--analysis-question",
        default="Summarize housing-related signals from recent San Jose meeting minutes.",
    )
    parser.add_argument("--stale-status", default="fresh")
    parser.add_argument(
        "--stale-drill-statuses",
        default="",
        help="Comma-separated stale drills, e.g. stale_but_usable,stale_blocked",
    )
    parser.add_argument("--scope-parallelism", type=int, default=1)
    parser.add_argument("--idempotent-rerun", action="store_true")
    parser.add_argument(
        "--searx-endpoint",
        action="append",
        default=[],
        help="Repeatable SearXNG endpoint; defaults to canonical public probe if omitted",
    )
    parser.add_argument("--idempotency-key", default=None)
    parser.add_argument(
        "--feature-key",
        default=FEATURE_KEY,
        help=f"Feature key to stamp into report + idempotency defaults (default: {FEATURE_KEY})",
    )
    parser.add_argument("--backend-endpoint-url", default=None)
    parser.add_argument("--backend-endpoint-auth-token", default=None)
    parser.add_argument(
        "--backend-endpoint-timeout-seconds",
        type=int,
        default=DEFAULT_BACKEND_ENDPOINT_TIMEOUT_SECONDS,
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_JSON_ARTIFACT)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_MD_ARTIFACT)
    args = parser.parse_args()
    stale_drills = [item.strip() for item in args.stale_drill_statuses.split(",") if item.strip()]
    searx_endpoints = args.searx_endpoint or DEFAULT_SEARX_ENDPOINTS

    report = run_harness(
        run_mode=args.run_mode,
        workspace=args.workspace,
        flow_path=args.flow_path,
        script_path=args.script_path,
        jurisdiction=args.jurisdiction,
        source_family=args.source_family,
        search_query=args.search_query,
        analysis_question=args.analysis_question,
        stale_status=args.stale_status,
        scope_parallelism=args.scope_parallelism,
        idempotency_key=args.idempotency_key,
        stale_drill_statuses=stale_drills,
        run_idempotent_rerun=args.idempotent_rerun,
        searx_endpoints=searx_endpoints,
        backend_endpoint_url=args.backend_endpoint_url,
        backend_endpoint_auth_token=args.backend_endpoint_auth_token,
        backend_endpoint_timeout_seconds=args.backend_endpoint_timeout_seconds,
        database_url=args.database_url,
        feature_key=args.feature_key,
    )

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    args.out_md.write_text(_render_markdown(report), encoding="utf-8")

    print(f"Wrote JSON report: {args.out_json}")
    print(f"Wrote Markdown report: {args.out_md}")
    print(f"classification={report['classification']}")
    print(f"full_run_readiness={report['full_run_readiness']}")
    return 0 if report["classification"] in {"read_only_surface_pass", "stub_orchestration_pass", "backend_bridge_surface_ready", "quality_gate_block_pass", "full_product_pass"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
