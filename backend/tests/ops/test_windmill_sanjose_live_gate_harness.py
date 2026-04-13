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
