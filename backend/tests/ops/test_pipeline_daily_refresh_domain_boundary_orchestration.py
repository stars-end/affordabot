from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WINDMILL_DIR = ROOT / "ops" / "windmill" / "f" / "affordabot"
SCRIPT_PATH = WINDMILL_DIR / "pipeline_daily_refresh_domain_boundary.py"
FLOW_PATH = WINDMILL_DIR / "pipeline_daily_refresh_domain_boundary__flow" / "flow.yaml"


spec = spec_from_file_location("windmill_domain_boundary", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_scope_pipeline_happy_path_passes_windmill_envelope_between_steps():
    result = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:2026-04-13",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        scope_index=0,
        stale_status="fresh",
        search_query="San Jose housing minutes",
        analysis_question="Summarize housing items",
    )

    assert result["status"] == "succeeded"
    assert set(result["steps"].keys()) == {
        "search_materialize",
        "freshness_gate",
        "read_fetch",
        "index",
        "analyze",
        "summarize_run",
    }
    for step_name, payload in result["steps"].items():
        assert payload["envelope"]["contract_version"] == "2026-04-13.windmill-domain.v1"
        assert payload["envelope"]["orchestrator"] == "windmill"
        assert payload["envelope"]["windmill_workspace"] == "affordabot"
        assert payload["envelope"]["windmill_step_id"] == step_name
        assert payload["envelope"]["jurisdiction_id"] == "San Jose CA"
        assert payload["envelope"]["jurisdiction_name"] == "San Jose CA"
        assert payload["invoked_command"] in {
            "search_materialize",
            "freshness_gate",
            "read_fetch",
            "index",
            "analyze",
            "summarize_run",
        }


def test_scope_pipeline_stale_blocked_short_circuits_to_summary():
    result = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:2026-04-13",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        scope_index=0,
        stale_status="stale_blocked",
        search_query="San Jose housing minutes",
        analysis_question="Summarize housing items",
    )

    assert result["status"] == "blocked"
    assert "read_fetch" not in result["steps"]
    assert "index" not in result["steps"]
    assert "analyze" not in result["steps"]
    assert result["steps"]["freshness_gate"]["status"] == "stale_blocked"
    assert result["steps"]["summarize_run"]["status"] == "blocked"


def test_run_summary_aggregates_fanout_scope_results():
    scope_matrix = module.main(
        step="build_scope_matrix",
        jurisdictions=["San Jose CA", "Santa Clara County CA"],
        source_families=["meeting_minutes"],
    )
    assert scope_matrix["scope_count"] == 2

    first_scope = module.main(
        step="run_scope_pipeline",
        scope_item=scope_matrix["scope_items"][0],
        scope_index=0,
        stale_status="fresh",
        search_query="query",
        analysis_question="question",
    )
    second_scope = module.main(
        step="run_scope_pipeline",
        scope_item=scope_matrix["scope_items"][1],
        scope_index=1,
        stale_status="stale_blocked",
        search_query="query",
        analysis_question="question",
    )

    summary = module.main(
        step="aggregate_run_summary",
        scope_results=[first_scope, second_scope],
    )

    assert summary["scope_total"] == 2
    assert summary["scope_succeeded"] == 1
    assert summary["scope_blocked"] == 1
    assert summary["scope_failed"] == 0
    assert summary["status"] == "failed"
    assert "freshness_gate:stale_blocked" in summary["alerts"]


def test_windmill_null_optional_inputs_coalesce_to_contract_defaults():
    result = module.main(
        step="run_scope_pipeline",
        contract_version=None,
        architecture_path=None,
        windmill_workspace=None,
        windmill_flow_path=None,
        windmill_run_id=None,
        windmill_job_id=None,
        idempotency_key="run:null-coalesce",
        mode=None,
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        scope_index=0,
        stale_status=None,
        search_query="query",
        analysis_question="question",
    )

    envelope = result["steps"]["search_materialize"]["envelope"]
    assert envelope["contract_version"] == "2026-04-13.windmill-domain.v1"
    assert envelope["architecture_path"] == "affordabot_domain_boundary"
    assert envelope["windmill_workspace"] == "affordabot"
    assert envelope["windmill_flow_path"] == "f/affordabot/pipeline_daily_refresh_domain_boundary__flow"
    assert envelope["windmill_run_id"] == "run:null-coalesce"
    assert envelope["windmill_job_id"] == "run_scope_pipeline:0:search_materialize"
    assert envelope["mode"] == "scheduled"


def test_windmill_assets_reference_coarse_command_stubs_not_storage_apis():
    text = SCRIPT_PATH.read_text(encoding="utf-8") + "\n" + FLOW_PATH.read_text(encoding="utf-8")
    forbidden_terms = [
        "sqlalchemy",
        "psycopg",
        "postgres_client",
        "local_pgvector",
        "s3_storage",
        "minio",
        "insert into",
    ]
    for term in forbidden_terms:
        assert term not in text.lower()

    for required in [
        "search_materialize",
        "freshness_gate",
        "read_fetch",
        "index",
        "analyze",
        "summarize_run",
        "forloopflow",
        "branchone",
        "failure_module",
    ]:
        assert required in text
