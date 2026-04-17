from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = (
    ROOT
    / "backend"
    / "scripts"
    / "verification"
    / "verify_local_government_corpus_windmill_orchestration.py"
)

spec = spec_from_file_location(
    "verify_local_government_corpus_windmill_orchestration",
    SCRIPT_PATH,
)
verify_module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = verify_module
spec.loader.exec_module(verify_module)


def _matrix_fixture() -> dict[str, object]:
    return {
        "benchmark_id": "local_government_data_moat_benchmark_v0",
        "rows": [
            {
                "row_type": "corpus_package",
                "corpus_row_id": "lgm-001",
                "package_id": "pkg::lgm-001",
                "jurisdiction": {"id": "a", "name": "A", "state": "CA"},
                "policy_family": "parking_policy",
                "infrastructure_status": {
                    "orchestration_mode": "cli_only",
                    "windmill_refs": None,
                },
            },
            {
                "row_type": "corpus_package",
                "corpus_row_id": "lgm-002",
                "package_id": "pkg::lgm-002",
                "jurisdiction": {"id": "b", "name": "B", "state": "CA"},
                "policy_family": "housing_permits",
                "infrastructure_status": {
                    "orchestration_mode": "windmill_live",
                    "windmill_refs": {
                        "flow_id": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                        "run_id": "wm::2",
                        "job_id": "job::2",
                    },
                },
            },
            {
                "row_type": "corpus_package",
                "corpus_row_id": "lgm-003",
                "package_id": "pkg::lgm-003",
                "jurisdiction": {"id": "c", "name": "C", "state": "CA"},
                "policy_family": "code_enforcement",
                "infrastructure_status": {
                    "orchestration_mode": "mixed",
                    "windmill_refs": {
                        "flow_id": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                        "run_id": "wm::3",
                        "job_id": "job::3",
                    },
                },
            },
        ],
    }


def test_build_report_pass_candidate_when_cli_only_is_eliminated():
    matrix = _matrix_fixture()
    baseline_rows = verify_module._build_baseline_rows(matrix)
    attempt = verify_module.LiveAttempt(
        corpus_row_id="lgm-001",
        status="proven",
        orchestration_mode="windmill_live",
        windmill_run_id="wm::live-001",
        windmill_job_id="job::live-001",
        windmill_flow_path="f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
        blocker_class=None,
        blocker_detail=None,
        command_client="backend_endpoint",
        command_attempted="windmill-cli flow run ...",
        flow_response_status="succeeded",
        backend_scope_status="succeeded_with_alerts",
        idempotency_key="bd-3wefe.13.4.3:lgm-001:1",
    )

    merged = verify_module._merge_rows_with_attempts(
        baseline_rows,
        {"lgm-001": attempt},
    )
    report = verify_module._build_report(
        matrix=matrix,
        scorecard=None,
        baseline_rows=baseline_rows,
        merged_rows=merged,
        attempts=[attempt],
        flow_path="f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
        command_client="backend_endpoint",
        command_log=["windmill-cli flow run ..."],
        surface_blocker=None,
    )

    assert report["baseline_metrics"]["cli_only_share"] == 0.3333
    assert report["post_metrics"]["cli_only_share"] == 0.0
    assert report["post_metrics"]["missing_live_refs_rows"] == []
    assert report["post_metrics"]["blocker_rows"] == []
    assert report["c13_verdict_candidate"] == "pass_candidate"


def test_build_report_fail_closes_blocked_rows():
    matrix = _matrix_fixture()
    baseline_rows = verify_module._build_baseline_rows(matrix)
    blocked_attempt = verify_module.LiveAttempt(
        corpus_row_id="lgm-001",
        status="blocked",
        orchestration_mode="blocked",
        windmill_run_id=None,
        windmill_job_id=None,
        windmill_flow_path="f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
        blocker_class="backend_endpoint_not_configured",
        blocker_detail="missing BACKEND_PUBLIC_URL",
        command_client="backend_endpoint",
        command_attempted="windmill-cli flow run ...",
        flow_response_status="failed",
        backend_scope_status="failed",
        idempotency_key="bd-3wefe.13.4.3:lgm-001:2",
    )
    merged = verify_module._merge_rows_with_attempts(
        baseline_rows,
        {"lgm-001": blocked_attempt},
    )
    report = verify_module._build_report(
        matrix=matrix,
        scorecard=None,
        baseline_rows=baseline_rows,
        merged_rows=merged,
        attempts=[blocked_attempt],
        flow_path="f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
        command_client="backend_endpoint",
        command_log=["windmill-cli flow run ..."],
        surface_blocker={"blocker_class": "windmill_surface_unavailable"},
    )

    assert report["post_metrics"]["mode_counts"]["blocked"] == 1
    assert report["post_metrics"]["blocker_rows"][0]["corpus_row_id"] == "lgm-001"
    assert report["c13_verdict_candidate"] == "not_proven_blocked"
