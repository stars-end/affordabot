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
                        "run_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                        "job_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
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
                        "run_id": "01J9KJ5G15T1VA7T6F0Y8PSXG3",
                        "job_id": "01J9KJ5G15T1VA7T6F0Y8PSXG3",
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
        windmill_run_id="01J9KJ5J3YEN2T2A8V3W8Y1D63",
        windmill_job_id="01J9KJ5J3YEN2T2A8V3W8Y1D63",
        windmill_flow_path="f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
        blocker_class=None,
        blocker_detail=None,
        command_client="backend_endpoint",
        command_attempted="windmill-cli flow run ...",
        flow_response_status="succeeded",
        backend_scope_status="succeeded_with_alerts",
        idempotency_key="bd-3wefe.13.4.4:lgm-001:1",
        run_id_source="flow_run_output",
        job_id_source="flow_run_output",
        job_lookup_trace=("flow_run_output:windmill_run_id", "flow_run_output:windmill_job_id"),
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
        idempotency_key="bd-3wefe.13.4.4:lgm-001:2",
        run_id_source=None,
        job_id_source=None,
        job_lookup_trace=("job_list_all[0]:count=0",),
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


def test_build_report_keeps_failed_flow_blocked_even_with_job_refs():
    matrix = _matrix_fixture()
    baseline_rows = verify_module._build_baseline_rows(matrix)
    blocked_attempt = verify_module.LiveAttempt(
        corpus_row_id="lgm-001",
        status="blocked",
        orchestration_mode="blocked",
        windmill_run_id="01J9KJ5J3YEN2T2A8V3W8Y1D63",
        windmill_job_id="01J9KJ5J3YEN2T2A8V3W8Y1D63",
        windmill_flow_path="f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
        blocker_class="backend_scope_not_succeeded",
        blocker_detail="flow_status=failed backend_scope_status=None",
        command_client="backend_endpoint",
        command_attempted="windmill-cli flow run ... -s",
        flow_response_status="failed",
        backend_scope_status=None,
        idempotency_key="bd-3wefe.13.4.4:lgm-001:3",
        run_id_source="job_list_all:recent_flow_job",
        job_id_source="job_list_all:recent_flow_job",
        job_lookup_trace=("job_list_all[0]:recent_flow_job",),
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
        command_log=["windmill-cli flow run ... -s"],
        surface_blocker=None,
    )

    assert report["post_metrics"]["blocker_rows"][0]["blocker_class"] == (
        "backend_scope_not_succeeded"
    )
    assert report["c13_verdict_candidate"] == "not_proven_blocked"


def test_extract_flow_refs_prefers_authoritative_values():
    flow_result = {
        "status": "succeeded",
        "id": "01J9KJ62MTR1T06NMD5BJCTQ74",
        "job": {
            "id": "01J9KJ62MTR1T06NMD5BJCTQ74",
        },
    }
    run_id, job_id = verify_module._extract_flow_refs(
        flow_result,
        idempotency_key="bd-3wefe.13.4.4:lgm-001:1",
    )
    assert run_id == "01J9KJ62MTR1T06NMD5BJCTQ74"
    assert job_id == "01J9KJ62MTR1T06NMD5BJCTQ74"


def test_extract_flow_refs_rejects_idempotency_and_seeded_placeholders():
    idempotency_key = "bd-3wefe.13.4.4:lgm-007:20260417082402"
    flow_result = {
        "id": idempotency_key,
        "windmill_run_id": "wm::lgm-007",
        "job": {"id": "wm-job::lgm-007"},
    }
    run_id, job_id = verify_module._extract_flow_refs(
        flow_result,
        idempotency_key=idempotency_key,
    )
    assert run_id is None
    assert job_id is None


def test_find_job_for_idempotency_matches_nested_payload_strings():
    idempotency_key = "bd-3wefe.13.4.4:lgm-007:20260417082402"
    jobs = [
        {"id": "01bad", "args": {"idempotency_key": "other"}},
        {
            "id": "01good",
            "result": {"lineage": {"attempt_key": idempotency_key}},
        },
    ]
    matched = verify_module._find_job_for_idempotency(jobs, idempotency_key)
    assert matched is not None
    assert matched["id"] == "01good"


def test_build_report_fail_closes_seeded_placeholder_refs():
    matrix = _matrix_fixture()
    matrix["rows"][1]["infrastructure_status"]["windmill_refs"]["run_id"] = "wm::seeded"
    matrix["rows"][1]["infrastructure_status"]["windmill_refs"]["job_id"] = "wm-job::seeded"
    baseline_rows = verify_module._build_baseline_rows(matrix)
    report = verify_module._build_report(
        matrix=matrix,
        scorecard=None,
        baseline_rows=baseline_rows,
        merged_rows=baseline_rows,
        attempts=[],
        flow_path="f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
        command_client="backend_endpoint",
        command_log=[],
        surface_blocker=None,
    )

    assert "lgm-002" in report["post_metrics"]["seeded_placeholder_rows"]
    assert "lgm-002" in report["post_metrics"]["missing_live_refs_rows"]
    assert report["c13_verdict_candidate"] == "not_proven_unverified_live_refs"
