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


def test_backend_endpoint_default_timeout_covers_live_reader_analysis_window():
    flow_text = FLOW_PATH.read_text()

    assert module.BACKEND_ENDPOINT_READ_TIMEOUT_SECONDS == 600
    assert "backend_endpoint_timeout_seconds:" in flow_text
    assert "default: 600" in flow_text


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


def test_scope_pipeline_domain_package_happy_path_and_windmill_refs():
    result = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:domain-package-happy",
        windmill_run_id="run:domain-package-happy",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        scope_index=0,
        stale_status="fresh",
        search_query="San Jose housing minutes",
        analysis_question="Summarize housing items",
        command_client="domain_package",
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
    for step in result["steps"].values():
        refs = step.get("refs", {})
        assert refs["windmill_run_id"] == "run:domain-package-happy"
        assert refs["windmill_job_id"].startswith("windmill-job-id:0:")
    assert result["steps"]["freshness_gate"]["decision_reason"] == "fresh"


def test_scope_pipeline_domain_package_stale_but_usable_completes_with_alerts():
    result = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:domain-package-stale-usable",
        windmill_run_id="run:domain-package-stale-usable",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        scope_index=0,
        stale_status="stale_but_usable",
        search_query="San Jose housing minutes",
        analysis_question="Summarize housing items",
        command_client="domain_package",
    )

    assert result["status"] == "succeeded"
    assert result["steps"]["freshness_gate"]["status"] == "succeeded_with_alerts"
    assert result["steps"]["freshness_gate"]["decision_reason"] == "stale_but_usable"
    assert "source_search_failed_using_last_success" in result["steps"]["freshness_gate"]["alerts"]


def test_scope_pipeline_domain_package_stale_blocked_short_circuits():
    result = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:domain-package-stale-blocked",
        windmill_run_id="run:domain-package-stale-blocked",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        scope_index=0,
        stale_status="stale_blocked",
        search_query="San Jose housing minutes",
        analysis_question="Summarize housing items",
        command_client="domain_package",
    )

    assert result["status"] == "blocked"
    assert "read_fetch" not in result["steps"]
    assert "index" not in result["steps"]
    assert "analyze" not in result["steps"]
    assert result["steps"]["freshness_gate"]["decision_reason"] == "stale_blocked"
    assert result["steps"]["summarize_run"]["status"] == "blocked"


def test_domain_package_rerun_reuses_idempotency_when_state_is_passed():
    first = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:domain-package-rerun",
        windmill_run_id="run:domain-package-rerun",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        scope_index=0,
        stale_status="fresh",
        search_query="San Jose housing minutes",
        analysis_question="Summarize housing items",
        command_client="domain_package",
    )
    second = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:domain-package-rerun",
        windmill_run_id="run:domain-package-rerun",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        scope_index=0,
        stale_status="fresh",
        search_query="San Jose housing minutes",
        analysis_question="Summarize housing items",
        command_client="domain_package",
        domain_state=first["domain_state"],
    )

    assert first["status"] == "succeeded"
    assert second["status"] == "succeeded"
    assert second["steps"]["search_materialize"]["details"]["idempotent_reuse"] is True
    assert second["steps"]["index"]["details"]["idempotent_reuse"] is True
    assert (
        first["steps"]["summarize_run"]["refs"]["run_id"]
        == second["steps"]["summarize_run"]["refs"]["run_id"]
    )


def test_windmill_null_optional_inputs_coalesce_for_domain_package_mode():
    result = module.main(
        step="run_scope_pipeline",
        contract_version=None,
        architecture_path=None,
        windmill_workspace=None,
        windmill_flow_path=None,
        windmill_run_id=None,
        windmill_job_id=None,
        idempotency_key="run:domain-package-null-coalesce",
        mode=None,
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        scope_index=0,
        stale_status=None,
        search_query="query",
        analysis_question="question",
        command_client="domain_package",
    )

    search_step = result["steps"]["search_materialize"]
    assert search_step["contract_version"] == "2026-04-13.windmill-domain.v1"
    assert search_step["refs"]["windmill_run_id"] == "run:domain-package-null-coalesce"
    assert search_step["refs"]["windmill_job_id"] == "run_scope_pipeline:0:1"


def test_unsupported_command_client_returns_failed_contract():
    result = module.main(
        step="run_scope_pipeline",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        command_client="invalid_client",
    )
    assert result["status"] == "failed"
    assert result["error"] == "unsupported_command_client:invalid_client"


def test_flow_schema_defaults_to_stub_command_client_for_live_safety():
    text = FLOW_PATH.read_text(encoding="utf-8")
    assert "command_client:" in text
    assert "default: stub" in text
    assert "- backend_endpoint" in text


def test_domain_package_import_failure_returns_contract_error(monkeypatch):
    def _boom(**kwargs):  # noqa: ARG001
        raise ModuleNotFoundError("services.pipeline.domain")

    monkeypatch.setattr(module, "_run_scope_pipeline_domain_package", _boom)
    result = module.main(
        step="run_scope_pipeline",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        command_client="domain_package",
    )
    assert result["status"] == "failed"
    assert result["error"] == "domain_package_unavailable"
    assert result["command_client"] == "domain_package"


def test_backend_endpoint_mode_fails_closed_when_url_missing():
    result = module.main(
        step="run_scope_pipeline",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        command_client="backend_endpoint",
        backend_endpoint_auth_token="token-123",
    )

    assert result["status"] == "failed"
    assert result["alert"] == "backend_endpoint:backend_endpoint_missing_configuration"
    run_step = result["steps"]["run_scope_pipeline"]
    assert run_step["error"] == "backend_endpoint_missing_configuration"
    assert run_step["error_details"]["missing"] == ["backend_endpoint_url"]


def test_backend_endpoint_mode_fails_closed_when_auth_missing():
    result = module.main(
        step="run_scope_pipeline",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        command_client="backend_endpoint",
        backend_endpoint_url="https://backend.example/cron/pipeline/domain/run-scope",
    )

    assert result["status"] == "failed"
    assert result["alert"] == "backend_endpoint:backend_endpoint_missing_configuration"
    run_step = result["steps"]["run_scope_pipeline"]
    assert run_step["error"] == "backend_endpoint_missing_configuration"
    assert run_step["error_details"]["missing"] == ["backend_endpoint_auth_token"]


def test_backend_endpoint_mode_maps_http_error_to_contract_failure(monkeypatch):
    class _FakeResponse:
        status_code = 503

        @staticmethod
        def json():
            return {"status": "failed", "error": "upstream_unavailable"}

        text = '{"status":"failed","error":"upstream_unavailable"}'

    def _fake_post(*args, **kwargs):  # noqa: ARG001
        return _FakeResponse()

    monkeypatch.setattr(module.requests, "post", _fake_post)
    result = module.main(
        step="run_scope_pipeline",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        command_client="backend_endpoint",
        backend_endpoint_url="https://backend.example/cron/pipeline/domain/run-scope",
        backend_endpoint_auth_token="token-123",
    )

    assert result["status"] == "failed"
    run_step = result["steps"]["run_scope_pipeline"]
    assert run_step["error"] == "backend_endpoint_http_error"
    assert run_step["error_details"]["http_status"] == 503


def test_backend_endpoint_mode_passthrough_success_payload(monkeypatch):
    captured: list[dict[str, object]] = []

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "status": "succeeded",
                "decision_reason": "scope_completed",
                "idempotency_key": "run:backend-endpoint-pass",
                "scope_idempotency_key": "run:backend-endpoint-pass::scope",
                "windmill_run_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                "windmill_run_id_reported": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                "windmill_run_id_source": "windmill_flow_input",
                "windmill_run_id_missing_reason": None,
                "windmill_job_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                "windmill_job_id_reported": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                "windmill_job_id_source": "windmill_flow_input",
                "windmill_job_id_missing_reason": None,
                "orchestration_refs": {
                    "idempotency_key": "run:backend-endpoint-pass",
                    "scope_idempotency_key": "run:backend-endpoint-pass::scope",
                    "windmill_run_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                    "windmill_job_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                    "windmill_job_id_source": "windmill_flow_input",
                },
                "alerts": [],
                "steps": {
                    "search_materialize": {"status": "succeeded"},
                    "freshness_gate": {"status": "succeeded", "decision_reason": "fresh"},
                    "read_fetch": {"status": "succeeded"},
                    "index": {"status": "succeeded"},
                    "analyze": {"status": "succeeded"},
                    "summarize_run": {"status": "succeeded"},
                },
                "storage_mode": "in_memory_domain_ports",
                "missing_runtime_adapters": ["postgres_pipeline_state_store_adapter"],
            }

        text = '{"status":"succeeded"}'

    def _fake_post(url, json, headers, timeout):  # noqa: ANN001
        captured.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return _FakeResponse()

    monkeypatch.setattr(module.requests, "post", _fake_post)
    result = module.main(
        step="run_scope_pipeline",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        command_client="backend_endpoint",
        backend_endpoint_url="https://backend.example/cron/pipeline/domain/run-scope",
        backend_endpoint_auth_token="token-123",
    )

    assert result["status"] == "succeeded"
    assert result["backend_response"]["storage_mode"] == "in_memory_domain_ports"
    assert result["backend_response"]["idempotency_key"] == "run:backend-endpoint-pass"
    assert result["backend_response"]["scope_idempotency_key"] == "run:backend-endpoint-pass::scope"
    assert result["backend_response"]["orchestration_refs"]["windmill_job_id"] == "01J9KJ5FK0XQ7CG1WM89AZ6RY4"
    assert "search_materialize" in result["steps"]
    assert captured
    first_call = captured[0]
    assert first_call["url"] == "https://backend.example/cron/pipeline/domain/run-scope"
    request_body = first_call["json"]
    assert isinstance(request_body, dict)
    assert request_body["jurisdiction"] == "San Jose CA"
    assert request_body["source_family"] == "meeting_minutes"
    assert request_body["windmill_workspace"] == "affordabot"
    assert first_call["headers"]["Authorization"] == "Bearer token-123"
    assert first_call["headers"]["X-PR-CRON-SOURCE"] == "f/affordabot/pipeline_daily_refresh_domain_boundary__flow"


def test_backend_endpoint_mode_passes_fail_closed_job_id_contract(monkeypatch):
    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "status": "succeeded_with_alerts",
                "decision_reason": "scope_completed_with_alerts",
                "idempotency_key": "run:backend-endpoint-missing-job",
                "scope_idempotency_key": "run:backend-endpoint-missing-job::scope",
                "windmill_run_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                "windmill_run_id_reported": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                "windmill_run_id_source": "windmill_flow_input",
                "windmill_run_id_missing_reason": None,
                "windmill_job_id": None,
                "windmill_job_id_reported": "run_scope_pipeline:0:run_scope_pipeline",
                "windmill_job_id_source": "windmill_flow_input_unverified",
                "windmill_job_id_missing_reason": "windmill_job_id_step_placeholder",
                "orchestration_refs": {
                    "idempotency_key": "run:backend-endpoint-missing-job",
                    "scope_idempotency_key": "run:backend-endpoint-missing-job::scope",
                    "windmill_run_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                    "windmill_job_id": None,
                    "windmill_job_id_reported": "run_scope_pipeline:0:run_scope_pipeline",
                    "windmill_job_id_source": "windmill_flow_input_unverified",
                    "windmill_job_id_missing_reason": "windmill_job_id_step_placeholder",
                },
                "alerts": ["windmill_job_id_not_authoritative"],
                "steps": {
                    "search_materialize": {"status": "succeeded"},
                    "freshness_gate": {"status": "succeeded", "decision_reason": "fresh"},
                    "summarize_run": {"status": "succeeded_with_alerts"},
                },
                "storage_mode": "railway_runtime",
                "missing_runtime_adapters": [],
                "refs": {"windmill_run_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4"},
            }

        text = '{"status":"succeeded_with_alerts"}'

    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: _FakeResponse())  # noqa: ARG005
    result = module.main(
        step="run_scope_pipeline",
        scope_item={"jurisdiction": "San Jose CA", "source_family": "meeting_minutes"},
        command_client="backend_endpoint",
        backend_endpoint_url="https://backend.example/cron/pipeline/domain/run-scope",
        backend_endpoint_auth_token="token-123",
    )

    assert result["status"] == "succeeded"
    backend_response = result["backend_response"]
    assert backend_response["idempotency_key"] == "run:backend-endpoint-missing-job"
    assert backend_response["scope_idempotency_key"] == "run:backend-endpoint-missing-job::scope"
    assert backend_response["windmill_job_id"] is None
    assert backend_response["windmill_job_id_source"] == "windmill_flow_input_unverified"
    assert backend_response["windmill_job_id_missing_reason"] == "windmill_job_id_step_placeholder"
    assert backend_response["orchestration_refs"]["windmill_job_id"] is None


def test_backend_endpoint_mode_preserves_typed_timeout_reason(monkeypatch):
    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "status": "failed_retryable",
                "decision_reason": "scope_timeout",
                "idempotency_key": "run:backend-endpoint-portland",
                "scope_idempotency_key": "run:backend-endpoint-portland::scope",
                "windmill_run_id": "wm-run-portland",
                "windmill_run_id_reported": "wm-run-portland",
                "windmill_run_id_source": "windmill_flow_input",
                "windmill_run_id_missing_reason": None,
                "windmill_job_id": "wm-job-portland",
                "windmill_job_id_reported": "wm-job-portland",
                "windmill_job_id_source": "windmill_flow_input",
                "windmill_job_id_missing_reason": None,
                "orchestration_refs": {
                    "idempotency_key": "run:backend-endpoint-portland",
                    "scope_idempotency_key": "run:backend-endpoint-portland::scope",
                    "windmill_run_id": "wm-run-portland",
                    "windmill_job_id": "wm-job-portland",
                },
                "alerts": ["search_provider_timeout"],
                "steps": {
                    "search_materialize": {
                        "status": "failed_retryable",
                        "decision_reason": "search_provider_timeout",
                    },
                    "summarize_run": {"status": "failed_retryable"},
                },
                "storage_mode": "railway_runtime",
                "missing_runtime_adapters": [],
                "refs": {
                    "fail_closed_reasons": [
                        "search_materialize:search_provider_timeout",
                    ]
                },
            }

        text = '{"status":"failed_retryable"}'

    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: _FakeResponse())  # noqa: ARG005
    result = module.main(
        step="run_scope_pipeline",
        scope_item={"jurisdiction": "Portland OR", "source_family": "short_term_rental"},
        command_client="backend_endpoint",
        backend_endpoint_url="https://backend.example/cron/pipeline/domain/run-scope",
        backend_endpoint_auth_token="token-123",
    )

    assert result["status"] == "failed"
    assert result["steps"]["search_materialize"]["decision_reason"] == "search_provider_timeout"
    assert "search_provider_timeout" in result["alert"]
    assert (
        "search_materialize:search_provider_timeout"
        in result["backend_response"]["refs"]["fail_closed_reasons"]
    )
