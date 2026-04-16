from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VERIFY_SCRIPT_PATH = (
    ROOT
    / "backend"
    / "scripts"
    / "verification"
    / "verify_policy_evidence_package_windmill_orchestration.py"
)

spec = spec_from_file_location("verify_policy_evidence_package_windmill_orchestration", VERIFY_SCRIPT_PATH)
verify_module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(verify_module)


def _local_payload() -> dict[str, object]:
    return {
        "stub_happy": {
            "status": "succeeded",
            "package_id": "pkg-happy",
            "package_readiness_status": "ready",
            "gate_status": "quantified",
            "decision_reason": "ok",
            "retry_class": "none",
            "storage_refs": {"postgres_package_row": "row-1"},
        },
        "stub_blocked": {
            "status": "blocked",
            "package_id": "pkg-blocked",
            "package_readiness_status": "blocked",
            "gate_status": "insufficient_evidence",
            "decision_reason": "blocked",
            "retry_class": "retry_after_new_evidence",
        },
        "backend_endpoint_happy": {
            "status": "succeeded",
            "command_client": "backend_endpoint",
            "package_id": "pkg-happy",
            "gate_status": "quantified",
            "decision_reason": "ok",
        },
        "backend_endpoint_events": [{"command_name": "fetch_scraped_candidates"}],
    }


def _live_payload() -> dict[str, object]:
    return {
        "live_status": "passed_stub_flow_run",
        "commands": ["windmill-cli flow run ..."],
        "return_code": 0,
        "stdout_redacted": True,
        "stderr_redacted": False,
        "stub_run_result": {"status": "succeeded"},
        "blocker": None,
    }


def test_backend_route_contract_snapshot_detects_policy_endpoint_mismatch():
    snapshot = verify_module._backend_route_contract_snapshot()

    assert snapshot["policy_evidence_backend_path"] == "/cron/pipeline/policy-evidence/command"
    assert snapshot["domain_boundary_backend_path"] == "/cron/pipeline/domain/run-scope"
    assert snapshot["domain_boundary_backend_route_present"] is True
    assert snapshot["policy_evidence_backend_route_present"] is False
    assert snapshot["route_mismatch"] is True
    assert snapshot["authoritative_live_evidence_idempotency_key"] == "bd-3wefe.13-live-domain-backend-2026-04-15-r1"
    assert snapshot["authoritative_live_evidence_status"] == "succeeded_with_alerts"


def test_build_report_fails_closed_when_policy_endpoint_route_missing():
    report = verify_module._build_report(_local_payload(), _live_payload())

    assert report["local_status"] == "passed"
    assert report["live_surface_probe"]["live_status"] == "passed_stub_flow_run"
    assert report["live_status"] == "blocked_backend_endpoint_route_mismatch"
    assert report["contract_alignment"]["route_mismatch"] is True
    assert report["contract_alignment"]["authoritative_live_product_flow"].endswith(
        "pipeline_daily_refresh_domain_boundary__flow"
    )
    assert report["authoritative_live_evidence"]["status"] == "succeeded_with_alerts"
    assert "proof-with-warning" in "\n".join(report["open_gaps"])
