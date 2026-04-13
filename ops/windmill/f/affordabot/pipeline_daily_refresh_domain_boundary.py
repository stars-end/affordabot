"""Windmill script surface for Path B orchestration skeleton.

This file intentionally models orchestration behavior only:
- build scope matrix (jurisdiction x source family)
- invoke coarse domain commands via stubs (live-safe default)
- branch on freshness status (blocked vs usable)
- aggregate run summary + failure handler surface

No direct product writes are performed here.

Notes:
- `command_client=domain_package` is repo-local execution that depends on the
  affordabot backend package being present on disk.
- `command_client=backend_endpoint` is explicit opt-in and fail-closed when
  endpoint URL/auth are missing or invalid.
- Windmill-hosted runtime should stay on `command_client=stub` by default.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


CONTRACT_VERSION = "2026-04-13.windmill-domain.v1"
USABLE_STATUSES = {"fresh", "stale_but_usable", "empty_but_usable"}
BLOCKED_STATUSES = {"stale_blocked", "empty_blocked"}
ALLOWED_COMMAND_CLIENTS = {"stub", "domain_package", "backend_endpoint"}
BACKEND_ENDPOINT_CONNECT_TIMEOUT_SECONDS = 5
BACKEND_ENDPOINT_READ_TIMEOUT_SECONDS = 30
BACKEND_RUN_SCOPE_PATH = "/cron/pipeline/domain/run-scope"


def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _normalize_backend_endpoint_url(endpoint_url: str) -> str:
    candidate = endpoint_url.rstrip("/")
    if not candidate:
        return ""
    if candidate.endswith(BACKEND_RUN_SCOPE_PATH):
        return candidate
    return f"{candidate}{BACKEND_RUN_SCOPE_PATH}"


def _envelope(
    *,
    step: str,
    contract_version: str,
    architecture_path: str,
    windmill_workspace: str,
    windmill_flow_path: str,
    windmill_run_id: str,
    windmill_job_id: str,
    idempotency_key: str,
    scope_item: Dict[str, str],
    scope_index: int,
    mode: str,
) -> Dict[str, Any]:
    jurisdiction = scope_item.get("jurisdiction", "")
    source_family = scope_item.get("source_family", "")
    scope_key = f"{jurisdiction}|{source_family}|{scope_index}"
    return {
        "contract_version": contract_version,
        "architecture_path": architecture_path,
        "orchestrator": "windmill",
        "windmill_workspace": windmill_workspace,
        "windmill_flow_path": windmill_flow_path,
        "windmill_run_id": windmill_run_id,
        "windmill_job_id": windmill_job_id,
        "windmill_step_id": step,
        "idempotency_key": idempotency_key,
        "jurisdiction_id": jurisdiction,
        "jurisdiction_name": jurisdiction,
        "source_family": source_family,
        "scope_index": scope_index,
        "scope_key": scope_key,
        "mode": mode,
    }


def _invoke_command_stub(
    *,
    command: str,
    envelope: Dict[str, Any],
    stale_status: str,
    previous_step_output: Optional[Dict[str, Any]],
    search_query: Optional[str],
    analysis_question: Optional[str],
) -> Dict[str, Any]:
    if command == "search_materialize":
        return {
            "status": "fresh",
            "snapshot_id": f"snapshot-{_stable_hash(envelope['scope_key'])}",
            "result_count": 2,
            "query": search_query,
            "envelope": envelope,
            "invoked_command": command,
        }

    if command == "freshness_gate":
        if stale_status not in USABLE_STATUSES | BLOCKED_STATUSES:
            return {
                "status": "source_error",
                "error": "invalid_stale_status",
                "envelope": envelope,
                "invoked_command": command,
            }
        return {
            "status": stale_status,
            "age_seconds": 3600,
            "envelope": envelope,
            "invoked_command": command,
        }

    if command == "read_fetch":
        if not previous_step_output:
            return {
                "status": "reader_error",
                "error": "missing_freshness_gate_output",
                "envelope": envelope,
                "invoked_command": command,
            }
        return {
            "status": "fresh",
            "canonical_document_key": f"doc-{_stable_hash(envelope['scope_key'])}",
            "reader_record_id": f"reader-{_stable_hash(envelope['windmill_run_id'])}",
            "envelope": envelope,
            "invoked_command": command,
        }

    if command == "index":
        if not previous_step_output:
            return {
                "status": "storage_error",
                "error": "missing_read_fetch_output",
                "envelope": envelope,
                "invoked_command": command,
            }
        return {
            "status": "fresh",
            "chunks_total": 5,
            "chunks_created": 5,
            "envelope": envelope,
            "invoked_command": command,
        }

    if command == "analyze":
        if not previous_step_output:
            return {
                "status": "analysis_error",
                "error": "missing_index_output",
                "envelope": envelope,
                "invoked_command": command,
            }
        return {
            "status": "fresh",
            "analysis_id": f"analysis-{_stable_hash(envelope['idempotency_key'])}",
            "question": analysis_question,
            "envelope": envelope,
            "invoked_command": command,
        }

    if command == "summarize_run":
        terminal_status = previous_step_output.get("status") if previous_step_output else "source_error"
        flow_status = "blocked" if terminal_status in BLOCKED_STATUSES else "succeeded"
        if terminal_status not in USABLE_STATUSES | BLOCKED_STATUSES | {"fresh", "succeeded"}:
            flow_status = "failed"
        return {
            "status": flow_status,
            "terminal_step_status": terminal_status,
            "summary": "Path B orchestration skeleton. Product writes belong to affordabot commands.",
            "envelope": envelope,
            "invoked_command": command,
        }

    return {
        "status": "source_error",
        "error": f"unsupported_command:{command}",
        "envelope": envelope,
        "invoked_command": command,
    }


def _invoke_scope_backend_endpoint(
    *,
    envelope: Dict[str, Any],
    stale_status: str,
    search_query: Optional[str],
    analysis_question: Optional[str],
    backend_endpoint_url: Optional[str],
    backend_endpoint_auth_token: Optional[str],
    backend_endpoint_timeout_seconds: int,
) -> Dict[str, Any]:
    endpoint_url = _normalize_backend_endpoint_url((backend_endpoint_url or "").strip())
    auth_token = (backend_endpoint_auth_token or "").strip()
    if not endpoint_url:
        return {
            "status": "failed",
            "error": "backend_endpoint_missing_configuration",
            "error_details": {"missing": ["backend_endpoint_url"]},
            "envelope": envelope,
            "invoked_command": "run_scope_pipeline",
        }
    if not auth_token:
        return {
            "status": "failed",
            "error": "backend_endpoint_missing_configuration",
            "error_details": {"missing": ["backend_endpoint_auth_token"]},
            "envelope": envelope,
            "invoked_command": "run_scope_pipeline",
        }

    request_payload = {
        "contract_version": envelope["contract_version"],
        "idempotency_key": envelope["idempotency_key"],
        "jurisdiction": envelope["jurisdiction_id"],
        "source_family": envelope["source_family"],
        "stale_status": stale_status,
        "windmill_workspace": envelope["windmill_workspace"],
        "windmill_flow_path": envelope["windmill_flow_path"],
        "windmill_run_id": envelope["windmill_run_id"],
        "windmill_job_id": envelope["windmill_job_id"],
        "search_query": search_query,
        "analysis_question": analysis_question,
    }
    request_headers = {
        "Authorization": f"Bearer {auth_token}",
        "X-PR-CRON-SECRET": auth_token,
        "X-PR-CRON-SOURCE": envelope["windmill_flow_path"],
        "Content-Type": "application/json",
    }

    timeout_seconds = max(1, int(backend_endpoint_timeout_seconds))
    timeout_tuple = (BACKEND_ENDPOINT_CONNECT_TIMEOUT_SECONDS, timeout_seconds)

    try:
        response = requests.post(
            endpoint_url,
            json=request_payload,
            headers=request_headers,
            timeout=timeout_tuple,
        )
    except requests.RequestException as exc:
        return {
            "status": "failed",
            "error": "backend_endpoint_request_error",
            "error_details": {"detail": str(exc), "endpoint_url": endpoint_url},
            "envelope": envelope,
            "invoked_command": "run_scope_pipeline",
        }

    response_payload: Dict[str, Any] | Any
    try:
        response_payload = response.json()
    except ValueError:
        response_payload = {"raw_text": response.text}

    if response.status_code >= 400:
        return {
            "status": "failed",
            "error": "backend_endpoint_http_error",
            "error_details": {
                "http_status": response.status_code,
                "endpoint_url": endpoint_url,
                "response": response_payload,
            },
            "envelope": envelope,
            "invoked_command": "run_scope_pipeline",
        }

    if not isinstance(response_payload, dict):
        return {
            "status": "failed",
            "error": "backend_endpoint_invalid_response",
            "error_details": {
                "detail": "response payload is not an object",
                "endpoint_url": endpoint_url,
                "response_excerpt": json.dumps(response_payload)[:400],
            },
            "envelope": envelope,
            "invoked_command": "run_scope_pipeline",
        }
    if not response_payload.get("status"):
        return {
            "status": "failed",
            "error": "backend_endpoint_invalid_response",
            "error_details": {
                "detail": "missing required status in backend response",
                "endpoint_url": endpoint_url,
                "response": response_payload,
            },
            "envelope": envelope,
            "invoked_command": "run_scope_pipeline",
        }
    return response_payload


def _build_scope_matrix(jurisdictions: List[str], source_families: List[str]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for jurisdiction in jurisdictions:
        for source_family in source_families:
            items.append(
                {
                    "jurisdiction": jurisdiction,
                    "source_family": source_family,
                    "scope_key": f"{jurisdiction.lower()}::{source_family.lower()}",
                }
            )
    return {
        "status": "ready",
        "scope_items": items,
        "scope_count": len(items),
    }


def _run_scope_pipeline(
    *,
    contract_version: str,
    architecture_path: str,
    windmill_workspace: str,
    windmill_flow_path: str,
    windmill_run_id: str,
    windmill_job_id: str,
    idempotency_key: str,
    mode: str,
    scope_item: Dict[str, str],
    scope_index: int,
    stale_status: str,
    search_query: Optional[str],
    analysis_question: Optional[str],
    command_client: str,
    backend_endpoint_url: Optional[str],
    backend_endpoint_auth_token: Optional[str],
    backend_endpoint_timeout_seconds: int,
) -> Dict[str, Any]:
    steps: Dict[str, Dict[str, Any]] = {}

    if command_client == "backend_endpoint":
        env = _envelope(
            step="run_scope_pipeline",
            contract_version=contract_version,
            architecture_path=architecture_path,
            windmill_workspace=windmill_workspace,
            windmill_flow_path=windmill_flow_path,
            windmill_run_id=windmill_run_id,
            windmill_job_id=f"{windmill_job_id}:{scope_index}:run_scope_pipeline",
            idempotency_key=idempotency_key,
            scope_item=scope_item,
            scope_index=scope_index,
            mode=mode,
        )
        backend_response = _invoke_scope_backend_endpoint(
            envelope=env,
            stale_status=stale_status,
            search_query=search_query,
            analysis_question=analysis_question,
            backend_endpoint_url=backend_endpoint_url,
            backend_endpoint_auth_token=backend_endpoint_auth_token,
            backend_endpoint_timeout_seconds=backend_endpoint_timeout_seconds,
        )
        if backend_response.get("error"):
            return {
                "scope_item": scope_item,
                "scope_index": scope_index,
                "status": "failed",
                "steps": {"run_scope_pipeline": backend_response},
                "alert": f"backend_endpoint:{backend_response.get('error')}",
            }

        backend_steps = backend_response.get("steps")
        if not isinstance(backend_steps, dict):
            invalid = {
                "status": "failed",
                "error": "backend_endpoint_invalid_response",
                "error_details": {"detail": "missing required steps object"},
                "envelope": env,
                "invoked_command": "run_scope_pipeline",
            }
            return {
                "scope_item": scope_item,
                "scope_index": scope_index,
                "status": "failed",
                "steps": {"run_scope_pipeline": invalid},
                "alert": "backend_endpoint:backend_endpoint_invalid_response",
            }

        backend_status = backend_response.get("status", "failed")
        if backend_status in {"succeeded", "succeeded_with_alerts"}:
            scope_status = "succeeded"
        elif backend_status == "blocked":
            scope_status = "blocked"
        else:
            scope_status = "failed"
        backend_alerts = backend_response.get("alerts") or []
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": scope_status,
            "steps": backend_steps,
            "alert": ";".join(str(alert) for alert in backend_alerts),
            "backend_response": {
                "status": backend_status,
                "decision_reason": backend_response.get("decision_reason"),
                "storage_mode": backend_response.get("storage_mode"),
                "missing_runtime_adapters": backend_response.get("missing_runtime_adapters", []),
                "refs": backend_response.get("refs", {}),
            },
        }

    def run_step(command: str, previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        env = _envelope(
            step=command,
            contract_version=contract_version,
            architecture_path=architecture_path,
            windmill_workspace=windmill_workspace,
            windmill_flow_path=windmill_flow_path,
            windmill_run_id=windmill_run_id,
            windmill_job_id=f"{windmill_job_id}:{scope_index}:{command}",
            idempotency_key=idempotency_key,
            scope_item=scope_item,
            scope_index=scope_index,
            mode=mode,
        )
        return _invoke_command_stub(
            command=command,
            envelope=env,
            stale_status=stale_status,
            previous_step_output=previous,
            search_query=search_query,
            analysis_question=analysis_question,
        )

    steps["search_materialize"] = run_step("search_materialize")
    steps["freshness_gate"] = run_step("freshness_gate", previous=steps["search_materialize"])
    freshness_status = steps["freshness_gate"].get("status", "source_error")

    if freshness_status in BLOCKED_STATUSES:
        steps["summarize_run"] = run_step("summarize_run", previous=steps["freshness_gate"])
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": "blocked",
            "steps": steps,
            "alert": f"freshness_gate:{freshness_status}",
        }

    if freshness_status not in USABLE_STATUSES:
        steps["summarize_run"] = run_step("summarize_run", previous=steps["freshness_gate"])
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": "failed",
            "steps": steps,
            "alert": f"freshness_gate:{freshness_status}",
        }

    steps["read_fetch"] = run_step("read_fetch", previous=steps["freshness_gate"])
    if steps["read_fetch"].get("status") != "fresh":
        steps["summarize_run"] = run_step("summarize_run", previous=steps["read_fetch"])
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": "failed",
            "steps": steps,
            "alert": f"read_fetch:{steps['read_fetch'].get('status')}",
        }

    steps["index"] = run_step("index", previous=steps["read_fetch"])
    if steps["index"].get("status") != "fresh":
        steps["summarize_run"] = run_step("summarize_run", previous=steps["index"])
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": "failed",
            "steps": steps,
            "alert": f"index:{steps['index'].get('status')}",
        }

    steps["analyze"] = run_step("analyze", previous=steps["index"])
    steps["summarize_run"] = run_step("summarize_run", previous=steps["analyze"])
    return {
        "scope_item": scope_item,
        "scope_index": scope_index,
        "status": "succeeded" if steps["analyze"].get("status") == "fresh" else "failed",
        "steps": steps,
        "alert": "",
    }


def _load_domain_package() -> Any:
    repo_root = Path(__file__).resolve().parents[4]
    backend_dir = repo_root / "backend"
    backend_dir_text = str(backend_dir)
    if backend_dir_text not in sys.path:
        sys.path.insert(0, backend_dir_text)

    from services.pipeline.domain import (  # noqa: PLC0415
        CommandEnvelope,
        FreshnessPolicy,
        InMemoryAnalyzer,
        InMemoryArtifactStore,
        InMemoryDomainState,
        InMemoryReaderProvider,
        InMemorySearchProvider,
        InMemoryVectorStore,
        PipelineDomainCommands,
        SearchResultItem,
        WindmillMetadata,
    )

    return {
        "CommandEnvelope": CommandEnvelope,
        "FreshnessPolicy": FreshnessPolicy,
        "InMemoryAnalyzer": InMemoryAnalyzer,
        "InMemoryArtifactStore": InMemoryArtifactStore,
        "InMemoryDomainState": InMemoryDomainState,
        "InMemoryReaderProvider": InMemoryReaderProvider,
        "InMemorySearchProvider": InMemorySearchProvider,
        "InMemoryVectorStore": InMemoryVectorStore,
        "PipelineDomainCommands": PipelineDomainCommands,
        "SearchResultItem": SearchResultItem,
        "WindmillMetadata": WindmillMetadata,
    }


def _build_domain_service(
    *,
    domain_state: Any | None,
    scope_item: Dict[str, str],
    search_query: str | None,
) -> tuple[Any, Any]:
    domain = _load_domain_package()
    state = domain_state or domain["InMemoryDomainState"]()

    default_url = (
        "https://www.sanjoseca.gov/your-government/departments-offices/"
        "city-clerk/city-council-meeting-minutes"
    )
    title = f"{scope_item.get('jurisdiction', 'Unknown')} Meeting Minutes"
    snippet = search_query or "Local meeting minutes and agenda updates."
    search_results = [
        domain["SearchResultItem"](
            url=default_url,
            title=title,
            snippet=snippet,
        )
    ]

    service = domain["PipelineDomainCommands"](
        state=state,
        search_provider=domain["InMemorySearchProvider"](results=search_results),
        reader_provider=domain["InMemoryReaderProvider"](),
        artifact_store=domain["InMemoryArtifactStore"](state),
        vector_store=domain["InMemoryVectorStore"](state),
        analyzer=domain["InMemoryAnalyzer"](),
    )
    return state, service


def _apply_staleness_override(
    *,
    stale_status: str,
    state: Any,
    snapshot_id: str,
    scope_key: str,
) -> Any | None:
    now = state.now
    latest_success = None
    if stale_status == "stale_but_usable":
        state.search_snapshots[snapshot_id]["captured_at"] = (now - timedelta(hours=36)).isoformat()
        latest_success = now
    elif stale_status == "stale_blocked":
        state.search_snapshots[snapshot_id]["captured_at"] = (now - timedelta(hours=120)).isoformat()
        latest_success = now
    elif stale_status == "empty_but_usable":
        state.search_snapshots[snapshot_id]["results"] = []
        latest_success = now
    elif stale_status == "empty_blocked":
        state.search_snapshots[snapshot_id]["results"] = []
        latest_success = None
    if latest_success is not None:
        state.previous_success_by_scope[scope_key] = latest_success
    return latest_success


def _run_scope_pipeline_domain_package(
    *,
    contract_version: str,
    windmill_workspace: str,
    windmill_flow_path: str,
    windmill_run_id: str,
    windmill_job_id: str,
    idempotency_key: str,
    scope_item: Dict[str, str],
    scope_index: int,
    stale_status: str,
    search_query: str | None,
    analysis_question: str | None,
    domain_state: Any | None,
) -> Dict[str, Any]:
    state, service = _build_domain_service(
        domain_state=domain_state,
        scope_item=scope_item,
        search_query=search_query,
    )
    domain = _load_domain_package()
    policy = domain["FreshnessPolicy"](
        fresh_hours=24,
        stale_usable_ceiling_hours=72,
        fail_closed_ceiling_hours=168,
    )

    scope_key = f"{scope_item.get('jurisdiction', '')}|{scope_item.get('source_family', '')}"
    steps: Dict[str, Dict[str, Any]] = {}
    envelopes: Dict[str, Dict[str, Any]] = {}

    def make_envelope(command: str, step_idx: int) -> Any:
        env = _envelope(
            step=command,
            contract_version=contract_version,
            architecture_path="affordabot_domain_boundary",
            windmill_workspace=windmill_workspace,
            windmill_flow_path=windmill_flow_path,
            windmill_run_id=windmill_run_id,
            windmill_job_id=f"{windmill_job_id}:{scope_index}:{step_idx}",
            idempotency_key=f"{idempotency_key}:{command}",
            scope_item=scope_item,
            scope_index=scope_index,
            mode="domain_package",
        )
        envelopes[command] = env
        return domain["CommandEnvelope"](
            command=command,
            jurisdiction_id=env["jurisdiction_id"],
            source_family=env["source_family"],
            idempotency_key=env["idempotency_key"],
            contract_version=env["contract_version"],
            windmill=domain["WindmillMetadata"](
                run_id=env["windmill_run_id"],
                job_id=env["windmill_job_id"],
                workspace=env["windmill_workspace"],
                flow_path=env["windmill_flow_path"],
            ),
        )

    def store_step(command: str, response: Any) -> None:
        payload = response.to_dict()
        payload["envelope"] = envelopes[command]
        payload["invoked_command"] = command
        steps[command] = payload

    search_env = make_envelope("search_materialize", 1)
    search = service.search_materialize(
        envelope=search_env,
        query=search_query or "San Jose meeting minutes",
    )
    store_step("search_materialize", search)
    snapshot_id = str(search.refs.get("search_snapshot_id", ""))
    latest_success = _apply_staleness_override(
        stale_status=stale_status,
        state=state,
        snapshot_id=snapshot_id,
        scope_key=scope_key,
    )

    freshness_env = make_envelope("freshness_gate", 2)
    freshness = service.freshness_gate(
        envelope=freshness_env,
        snapshot_id=snapshot_id,
        policy=policy,
        latest_success_at=latest_success,
    )
    store_step("freshness_gate", freshness)

    if freshness.decision_reason in BLOCKED_STATUSES:
        summarize_env = make_envelope("summarize_run", 6)
        summary = service.summarize_run(
            envelope=summarize_env,
            command_responses=[search, freshness],
        )
        store_step("summarize_run", summary)
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": "blocked",
            "steps": steps,
            "alert": f"freshness_gate:{freshness.decision_reason}",
            "domain_state": state,
        }

    if freshness.status.startswith("failed"):
        summarize_env = make_envelope("summarize_run", 6)
        summary = service.summarize_run(
            envelope=summarize_env,
            command_responses=[search, freshness],
        )
        store_step("summarize_run", summary)
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": "failed",
            "steps": steps,
            "alert": f"freshness_gate:{freshness.decision_reason}",
            "domain_state": state,
        }

    read_env = make_envelope("read_fetch", 3)
    read = service.read_fetch(
        envelope=read_env,
        snapshot_id=snapshot_id,
    )
    store_step("read_fetch", read)
    if read.status != "succeeded":
        summarize_env = make_envelope("summarize_run", 6)
        summary = service.summarize_run(
            envelope=summarize_env,
            command_responses=[search, freshness, read],
        )
        store_step("summarize_run", summary)
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": "failed",
            "steps": steps,
            "alert": f"read_fetch:{read.decision_reason}",
            "domain_state": state,
        }

    index_env = make_envelope("index", 4)
    index = service.index(
        envelope=index_env,
        raw_scrape_ids=list(read.refs.get("raw_scrape_ids", [])),
    )
    store_step("index", index)
    if index.status.startswith("failed") or index.status == "blocked":
        summarize_env = make_envelope("summarize_run", 6)
        summary = service.summarize_run(
            envelope=summarize_env,
            command_responses=[search, freshness, read, index],
        )
        store_step("summarize_run", summary)
        return {
            "scope_item": scope_item,
            "scope_index": scope_index,
            "status": "failed",
            "steps": steps,
            "alert": f"index:{index.decision_reason}",
            "domain_state": state,
        }

    analyze_env = make_envelope("analyze", 5)
    analyze = service.analyze(
        envelope=analyze_env,
        question=analysis_question or "Summarize meeting minutes",
        jurisdiction_id=scope_item.get("jurisdiction", ""),
        source_family=scope_item.get("source_family", ""),
    )
    store_step("analyze", analyze)

    summarize_env = make_envelope("summarize_run", 6)
    summary = service.summarize_run(
        envelope=summarize_env,
        command_responses=[search, freshness, read, index, analyze],
    )
    store_step("summarize_run", summary)

    run_status = "succeeded"
    if summary.status in {"failed_retryable", "failed_terminal"}:
        run_status = "failed"
    elif summary.status == "blocked":
        run_status = "blocked"
    return {
        "scope_item": scope_item,
        "scope_index": scope_index,
        "status": run_status,
        "steps": steps,
        "alert": "" if run_status == "succeeded" else f"summarize_run:{summary.status}",
        "domain_state": state,
    }


def _run_local_integration_harness(
    *,
    contract_version: str,
    windmill_workspace: str,
    windmill_flow_path: str,
    windmill_run_id: str,
    windmill_job_id: str,
    idempotency_key: str,
    scope_item: Dict[str, str],
    search_query: str | None,
    analysis_question: str | None,
) -> Dict[str, Any]:
    first = _run_scope_pipeline_domain_package(
        contract_version=contract_version,
        windmill_workspace=windmill_workspace,
        windmill_flow_path=windmill_flow_path,
        windmill_run_id=windmill_run_id,
        windmill_job_id=windmill_job_id,
        idempotency_key=idempotency_key,
        scope_item=scope_item,
        scope_index=0,
        stale_status="fresh",
        search_query=search_query,
        analysis_question=analysis_question,
        domain_state=None,
    )
    rerun = _run_scope_pipeline_domain_package(
        contract_version=contract_version,
        windmill_workspace=windmill_workspace,
        windmill_flow_path=windmill_flow_path,
        windmill_run_id=windmill_run_id,
        windmill_job_id=windmill_job_id,
        idempotency_key=idempotency_key,
        scope_item=scope_item,
        scope_index=0,
        stale_status="fresh",
        search_query=search_query,
        analysis_question=analysis_question,
        domain_state=first["domain_state"],
    )
    blocked = _run_scope_pipeline_domain_package(
        contract_version=contract_version,
        windmill_workspace=windmill_workspace,
        windmill_flow_path=windmill_flow_path,
        windmill_run_id=windmill_run_id,
        windmill_job_id=windmill_job_id,
        idempotency_key=f"{idempotency_key}:blocked",
        scope_item=scope_item,
        scope_index=1,
        stale_status="stale_blocked",
        search_query=search_query,
        analysis_question=analysis_question,
        domain_state=first["domain_state"],
    )

    first_index = first["steps"]["index"]
    rerun_index = rerun["steps"]["index"]
    evidence = {
        "happy_status": first["status"],
        "rerun_status": rerun["status"],
        "stale_blocked_status": blocked["status"],
        "rerun_index_idempotent_reuse": bool(rerun_index["details"].get("idempotent_reuse")),
        "rerun_chunk_count_stable": first_index["counts"].get("chunks") == rerun_index["counts"].get("chunks"),
        "stale_blocked_short_circuit": "read_fetch" not in blocked["steps"],
        "windmill_refs_propagated": all(
            step["refs"].get("windmill_run_id") == windmill_run_id
            for step in first["steps"].values()
        ),
    }
    for result in (first, rerun, blocked):
        result.pop("domain_state", None)
    return {
        "status": "succeeded" if all(v for v in evidence.values()) else "failed",
        "scope_item": scope_item,
        "scenarios": {
            "happy_first": first,
            "happy_rerun": rerun,
            "stale_blocked": blocked,
        },
        "evidence": evidence,
    }


def _aggregate_scope_results(scope_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(scope_results)
    blocked = sum(1 for result in scope_results if result.get("status") == "blocked")
    failed = sum(1 for result in scope_results if result.get("status") == "failed")
    succeeded = sum(1 for result in scope_results if result.get("status") == "succeeded")
    alerts = [result["alert"] for result in scope_results if result.get("alert")]
    run_status = "failed" if failed > 0 or blocked > 0 else "succeeded"
    return {
        "status": run_status,
        "scope_total": total,
        "scope_succeeded": succeeded,
        "scope_blocked": blocked,
        "scope_failed": failed,
        "alerts": alerts,
        "scope_results": scope_results,
    }


def main(
    step: str,
    contract_version: str = CONTRACT_VERSION,
    architecture_path: str = "affordabot_domain_boundary",
    windmill_workspace: str = "affordabot",
    windmill_flow_path: str = "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
    windmill_run_id: str = "windmill-run-id",
    windmill_job_id: str = "windmill-job-id",
    idempotency_key: str = "run:2026-04-13",
    mode: str = "scheduled",
    jurisdictions: Optional[List[str]] = None,
    source_families: Optional[List[str]] = None,
    scope_item: Optional[Dict[str, str]] = None,
    scope_index: int = 0,
    stale_status: str = "fresh",
    search_query: Optional[str] = None,
    analysis_question: Optional[str] = None,
    previous_step_output: Optional[Dict[str, Any]] = None,
    scope_results: Optional[List[Dict[str, Any]]] = None,
    command_client: str = "stub",
    backend_endpoint_url: Optional[str] = None,
    backend_endpoint_auth_token: Optional[str] = None,
    backend_endpoint_timeout_seconds: int = BACKEND_ENDPOINT_READ_TIMEOUT_SECONDS,
    domain_state: Any | None = None,
) -> Dict[str, Any]:
    contract_version = contract_version or CONTRACT_VERSION
    architecture_path = architecture_path or "affordabot_domain_boundary"
    windmill_workspace = windmill_workspace or "affordabot"
    windmill_flow_path = windmill_flow_path or "f/affordabot/pipeline_daily_refresh_domain_boundary__flow"
    windmill_run_id = windmill_run_id or idempotency_key or "windmill-run-id"
    windmill_job_id = windmill_job_id or step
    idempotency_key = idempotency_key or "run:2026-04-13"
    mode = mode or "scheduled"
    stale_status = stale_status or "fresh"
    command_client = command_client or "stub"
    backend_endpoint_url = backend_endpoint_url or ""
    backend_endpoint_auth_token = backend_endpoint_auth_token or ""
    backend_endpoint_timeout_seconds = int(backend_endpoint_timeout_seconds or BACKEND_ENDPOINT_READ_TIMEOUT_SECONDS)
    jurisdictions = jurisdictions or ["San Jose CA"]
    source_families = source_families or ["meeting_minutes"]

    if command_client not in ALLOWED_COMMAND_CLIENTS:
        return {
            "status": "failed",
            "error": f"unsupported_command_client:{command_client}",
            "allowed_command_clients": sorted(ALLOWED_COMMAND_CLIENTS),
        }

    if step == "build_scope_matrix":
        return _build_scope_matrix(jurisdictions, source_families)

    if step == "run_scope_pipeline":
        if not scope_item:
            return {"status": "failed", "error": "missing_scope_item"}
        if command_client == "domain_package":
            try:
                return _run_scope_pipeline_domain_package(
                    contract_version=contract_version,
                    windmill_workspace=windmill_workspace,
                    windmill_flow_path=windmill_flow_path,
                    windmill_run_id=windmill_run_id,
                    windmill_job_id=windmill_job_id,
                    idempotency_key=idempotency_key,
                    scope_item=scope_item,
                    scope_index=scope_index,
                    stale_status=stale_status,
                    search_query=search_query,
                    analysis_question=analysis_question,
                    domain_state=domain_state,
                )
            except (ImportError, ModuleNotFoundError, FileNotFoundError) as exc:
                return {
                    "status": "failed",
                    "error": "domain_package_unavailable",
                    "command_client": command_client,
                    "detail": str(exc),
                }
        return _run_scope_pipeline(
            contract_version=contract_version,
            architecture_path=architecture_path,
            windmill_workspace=windmill_workspace,
            windmill_flow_path=windmill_flow_path,
            windmill_run_id=windmill_run_id,
            windmill_job_id=windmill_job_id,
            idempotency_key=idempotency_key,
            mode=mode,
            scope_item=scope_item,
            scope_index=scope_index,
            stale_status=stale_status,
            search_query=search_query,
            analysis_question=analysis_question,
            command_client=command_client,
            backend_endpoint_url=backend_endpoint_url,
            backend_endpoint_auth_token=backend_endpoint_auth_token,
            backend_endpoint_timeout_seconds=backend_endpoint_timeout_seconds,
        )

    if step == "run_local_integration_harness":
        if not scope_item:
            scope_item = {"jurisdiction": jurisdictions[0], "source_family": source_families[0]}
        return _run_local_integration_harness(
            contract_version=contract_version,
            windmill_workspace=windmill_workspace,
            windmill_flow_path=windmill_flow_path,
            windmill_run_id=windmill_run_id,
            windmill_job_id=windmill_job_id,
            idempotency_key=idempotency_key,
            scope_item=scope_item,
            search_query=search_query,
            analysis_question=analysis_question,
        )

    if step == "aggregate_run_summary":
        return _aggregate_scope_results(scope_results or [])

    if step == "failure_handler":
        return {
            "status": "failed",
            "summary": "Windmill failure handler for Path B orchestration skeleton.",
            "last_step": previous_step_output,
            "windmill_run_id": windmill_run_id,
            "windmill_job_id": windmill_job_id,
            "contract_version": contract_version,
        }

    return {"status": "source_error", "error": f"unsupported_step:{step}"}
