from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from datetime import UTC, datetime
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "backend" / "scripts" / "verification" / "verify_windmill_sanjose_live_gate.py"

spec = spec_from_file_location("verify_windmill_sanjose_live_gate", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _stub_scope_result(summary_text: str) -> dict:
    return {
        "scope_results": [
            {
                "steps": {
                    "search_materialize": {
                        "envelope": {
                            "contract_version": "2026-04-13.windmill-domain.v1",
                            "orchestrator": "windmill",
                            "windmill_workspace": "affordabot",
                            "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                        }
                    },
                    "freshness_gate": {
                        "envelope": {
                            "contract_version": "2026-04-13.windmill-domain.v1",
                            "orchestrator": "windmill",
                            "windmill_workspace": "affordabot",
                            "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                        }
                    },
                    "read_fetch": {
                        "envelope": {
                            "contract_version": "2026-04-13.windmill-domain.v1",
                            "orchestrator": "windmill",
                            "windmill_workspace": "affordabot",
                            "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                        }
                    },
                    "index": {
                        "envelope": {
                            "contract_version": "2026-04-13.windmill-domain.v1",
                            "orchestrator": "windmill",
                            "windmill_workspace": "affordabot",
                            "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                        }
                    },
                    "analyze": {
                        "envelope": {
                            "contract_version": "2026-04-13.windmill-domain.v1",
                            "orchestrator": "windmill",
                            "windmill_workspace": "affordabot",
                            "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                        }
                    },
                    "summarize_run": {
                        "summary": summary_text,
                        "envelope": {
                            "contract_version": "2026-04-13.windmill-domain.v1",
                            "orchestrator": "windmill",
                            "windmill_workspace": "affordabot",
                            "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                        },
                    },
                }
            }
        ]
    }


def test_extract_step_sequence_preserves_expected_command_order():
    result_payload = _stub_scope_result("stub")
    assert module._extract_step_sequence(result_payload) == [
        "search_materialize",
        "freshness_gate",
        "read_fetch",
        "index",
        "analyze",
        "summarize_run",
    ]


def test_contract_presence_check_requires_envelope_fields():
    result_payload = _stub_scope_result("stub")
    assert module._all_step_envelopes_have_contract(result_payload) is True

    broken = _stub_scope_result("stub")
    del broken["scope_results"][0]["steps"]["index"]["envelope"]["contract_version"]
    assert module._all_step_envelopes_have_contract(broken) is False


def test_storage_gates_mark_stub_bridge_mode_when_stub_summary_present():
    result_payload = _stub_scope_result(module.STUB_SUMMARY_MARKER)
    gates = module._build_storage_evidence_gates(result_payload)
    assert gates["bridge_mode"]["status"] == "stub"
    assert "Worker A product bridge" in gates["postgres_rows_written"]["note"]


def test_classification_is_stub_orchestration_pass_without_blockers():
    result_payload = _stub_scope_result(module.STUB_SUMMARY_MARKER)
    result_payload["status"] = "succeeded"
    classification, readiness = module._derive_classification(
        result_payload=result_payload,
        storage_gates=module._build_storage_evidence_gates(result_payload),
        backend_endpoint_readiness={"status": "not_configured"},
        blockers=[],
    )
    assert classification == "stub_orchestration_pass"
    assert readiness == "partial"


def test_classification_is_backend_bridge_surface_ready_when_probe_ready():
    result_payload = _stub_scope_result(module.STUB_SUMMARY_MARKER)
    result_payload["status"] = "succeeded"
    classification, readiness = module._derive_classification(
        result_payload=result_payload,
        storage_gates=module._build_storage_evidence_gates(result_payload),
        backend_endpoint_readiness={"status": "ready_for_opt_in"},
        blockers=[],
    )
    assert classification == "backend_bridge_surface_ready"
    assert readiness == "partial"


def test_backend_endpoint_readiness_marks_not_configured_when_inputs_missing():
    readiness = module._build_backend_endpoint_readiness(
        backend_endpoint_url=None,
        backend_endpoint_auth_token=None,
    )
    assert readiness["status"] == "not_configured"
    assert "backend_endpoint_url" in readiness["missing_inputs"]
    assert "backend_endpoint_auth_token" in readiness["missing_inputs"]


def test_backend_endpoint_readiness_marks_ready_when_local_probe_passes(monkeypatch):
    monkeypatch.setattr(
        module,
        "_run_backend_endpoint_local_probe",
        lambda _: {"status": "passed", "note": "ok"},
    )
    readiness = module._build_backend_endpoint_readiness(
        backend_endpoint_url="https://backend.example/cron/pipeline/domain/run-scope",
        backend_endpoint_auth_token="token-123",
    )
    assert readiness["status"] == "ready_for_opt_in"
    assert readiness["local_mock_probe"]["status"] == "passed"


def test_job_lookup_uses_idempotency_key():
    jobs = [
        {"id": "a", "args": {"idempotency_key": "run:old"}},
        {"id": "b", "args": {"idempotency_key": "run:new"}},
    ]
    matched = module._find_job_for_idempotency(jobs, "run:new")
    assert matched is not None
    assert matched["id"] == "b"


def test_recent_flow_job_lookup_selects_latest_after_run_start():
    run_started_at = datetime(2026, 4, 13, 16, 40, tzinfo=UTC)
    jobs = [
        {
            "id": "old",
            "script_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
            "job_kind": "flow",
            "created_at": "2026-04-13T16:39:00Z",
        },
        {
            "id": "newest",
            "script_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
            "job_kind": "flow",
            "created_at": "2026-04-13T16:41:00Z",
        },
        {
            "id": "other",
            "script_path": "f/affordabot/universal_harvester",
            "job_kind": "flow",
            "created_at": "2026-04-13T16:50:00Z",
        },
    ]

    matched = module._find_recent_flow_job(
        jobs,
        flow_path="f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
        run_started_at=run_started_at,
    )
    assert matched is not None
    assert matched["id"] == "newest"


def test_search_provider_bakeoff_marks_paid_providers_not_configured(monkeypatch):
    monkeypatch.setattr(
        module,
        "_probe_searx",
        lambda endpoint, query, timeout_seconds=20: {
            "provider": "searxng",
            "endpoint": endpoint,
            "query": query,
            "status": "succeeded",
            "failure_classification": None,
            "result_count": 1,
            "latency_ms": 5,
            "top_results": [{"url": "https://example.com", "title": "x", "snippet": "y"}],
        },
    )

    def _missing_secret(_ref):
        raise module.HarnessError("infra/auth", "missing")

    monkeypatch.setattr(module, "_get_cached_secret", _missing_secret)
    probes, sensitive = module._run_search_provider_bakeoff(
        query="san jose housing",
        searx_endpoints=["https://searx.example/search"],
    )
    assert sensitive == []
    by_provider = {item["provider"]: item for item in probes}
    assert by_provider["searxng"]["status"] == "succeeded"
    assert by_provider["exa"]["status"] == "not_configured"
    assert by_provider["tavily"]["status"] == "not_configured"


def test_secret_leak_detector_flags_token_presence():
    report = {"a": "ok", "b": "token-1234567890"}
    leaked = module._assert_no_secret_leak(report, ["token-1234567890"])
    assert leaked == ["token-...redacted"]


def test_db_probe_not_configured_without_database_url(monkeypatch):
    probe = module._derive_db_probe(
        idempotency_key="run:1",
        jurisdiction="San Jose CA",
        source_family="meeting_minutes",
        database_url=None,
    )
    assert probe["status"] == "not_configured"


def test_render_markdown_includes_provider_and_manual_sections():
    report = {
        "generated_at": "2026-04-13T00:00:00Z",
        "feature_key": "bd-9qjof.6",
        "harness_version": "x",
        "run_mode": "stub-run",
        "classification": "stub_orchestration_pass",
        "full_run_readiness": "partial",
        "deployment_surface": {"flow_deployed": True, "script_deployed": True, "flow_unscheduled": True},
        "manual_run": {"attempted": False},
        "storage_evidence_gates": {"bridge_mode": {"status": "stub", "note": "stub"}},
        "backend_endpoint_readiness": {"status": "not_configured", "note": "", "missing_inputs": [], "local_mock_probe": {}},
        "search_provider_bakeoff": [
            {"provider": "searxng", "status": "succeeded", "result_count": 2, "latency_ms": 12, "failure_classification": None, "top_results": [{"url": "https://example.com"}]}
        ],
        "db_storage_probe": {
            "status": "queried",
            "search_snapshot_rows": [],
            "content_artifact_rows": [],
            "raw_scrape_rows": [],
            "document_chunks_count": 0,
            "minio_object_checks": [],
        },
        "manual_audit_notes": {
            "reader_output_excerpt": "",
            "reader_quality_note": "",
            "llm_analysis_excerpt": "",
            "llm_quality_note": "",
            "manual_verdict": "PENDING_MANUAL_AUDIT",
        },
        "blockers": [],
    }
    md = module._render_markdown(report)
    assert "## Search Provider Bakeoff" in md
    assert "## DB/Storage Evidence" in md
    assert "## Manual Audit Notes" in md


def test_run_harness_keeps_stub_path_and_skips_db_without_env(monkeypatch):
    monkeypatch.setattr(module, "_build_context", lambda workspace: module.HarnessContext("tok", "https://wm/user/login", "https://wm", workspace, "/tmp/w"))
    monkeypatch.setattr(module, "_setup_workspace_profile", lambda ctx: None)

    run_calls = {"count": 0}

    def fake_wmill(ctx, *args, expect_json=False):
        key = " ".join(args[:2])
        if key == "workspace list":
            return "profile"
        if key == "flow get":
            return {"path": "flow"}
        if key == "script get":
            return {"path": "script"}
        if key == "schedule list":
            return []
        if key == "job list":
            return []
        if key == "flow run":
            run_calls["count"] += 1
            if run_calls["count"] == 2:
                blocked_payload = _stub_scope_result(module.STUB_SUMMARY_MARKER)
                blocked_payload["scope_results"][0]["steps"] = {
                    "search_materialize": blocked_payload["scope_results"][0]["steps"]["search_materialize"],
                    "freshness_gate": blocked_payload["scope_results"][0]["steps"]["freshness_gate"],
                    "summarize_run": blocked_payload["scope_results"][0]["steps"]["summarize_run"],
                }
                return blocked_payload | {
                    "status": "failed",
                    "scope_total": 1,
                    "scope_succeeded": 0,
                    "scope_failed": 0,
                    "scope_blocked": 1,
                }
            return _stub_scope_result(module.STUB_SUMMARY_MARKER) | {
                "status": "succeeded",
                "scope_total": 1,
                "scope_succeeded": 1,
                "scope_failed": 0,
                "scope_blocked": 0,
            }
        return ""

    monkeypatch.setattr(module, "_wmill", fake_wmill)
    monkeypatch.setattr(module, "_run_search_provider_bakeoff", lambda **kwargs: ([], []))
    monkeypatch.setenv("DATABASE_URL", "")
    report = module.run_harness(
        run_mode="stub-run",
        workspace="affordabot",
        flow_path="f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
        script_path="f/affordabot/pipeline_daily_refresh_domain_boundary",
        jurisdiction="San Jose CA",
        source_family="meeting_minutes",
        search_query="q",
        analysis_question="a",
        stale_status="fresh",
        scope_parallelism=1,
        idempotency_key="run:test",
        stale_drill_statuses=["stale_blocked"],
        run_idempotent_rerun=False,
        searx_endpoints=["https://searx.example/search"],
        backend_endpoint_url=None,
        backend_endpoint_auth_token=None,
        database_url=None,
    )
    assert report["run_mode"] == "stub-run"
    assert report["manual_run"]["attempted"] is True
    assert report["db_storage_probe"]["status"] == "not_configured"
    assert report["storage_evidence_gates"]["stale_drill_stale_blocked"]["status"] == "passed"
