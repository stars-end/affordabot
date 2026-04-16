from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WINDMILL_DIR = ROOT / "ops" / "windmill" / "f" / "affordabot"
SCRIPT_PATH = WINDMILL_DIR / "policy_evidence_package_orchestration.py"
FLOW_PATH = WINDMILL_DIR / "policy_evidence_package_orchestration__flow" / "flow.yaml"

spec = spec_from_file_location("windmill_policy_evidence_package", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_scope_pipeline_happy_path_preserves_required_refs():
    result = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:bd-3wefe.12:happy",
        windmill_run_id="wm-run-happy",
        windmill_job_id="wm-job-happy",
        jurisdiction="San Jose CA",
        query_family="meeting_minutes",
        package_id="pkg-happy",
        package_readiness_status="ready",
        gate_status="quantified",
    )

    assert result["status"] == "succeeded"
    assert result["package_id"] == "pkg-happy"
    assert result["package_readiness_status"] == "ready"
    assert result["gate_status"] == "quantified"
    assert set(result["steps"].keys()) == {
        "fetch_scraped_candidates",
        "fetch_structured_candidates",
        "build_policy_evidence_package",
        "persist_readback_boundary",
        "evaluate_package_readiness",
        "summarize_orchestration",
    }

    for step_name, payload in result["steps"].items():
        refs = payload["refs"]
        assert refs["windmill_run_id"] == "wm-run-happy"
        assert refs["windmill_step_id"] == step_name
        assert refs["idempotency_key"] == "run:bd-3wefe.12:happy"
        assert payload["command_id"].startswith("cmd-")
        assert payload["decision_reason"]
        assert payload["retry_class"]

    storage_refs = result["storage_refs"]
    assert "postgres_package_row" in storage_refs
    assert "minio_package_artifact" in storage_refs
    assert "pgvector_chunk_projection" in storage_refs


def test_scope_pipeline_blocked_on_package_readiness_gate():
    result = module.main(
        step="run_scope_pipeline",
        idempotency_key="run:bd-3wefe.12:blocked",
        package_id="pkg-blocked",
        package_readiness_status="blocked",
        gate_status="insufficient_evidence",
    )

    assert result["status"] == "blocked"
    assert result["package_id"] == "pkg-blocked"
    assert result["package_readiness_status"] == "blocked"
    assert result["decision_reason"] == "package_not_ready_for_economic_handoff"
    assert result["retry_class"] == "retry_after_new_evidence"
    assert result["steps"]["evaluate_package_readiness"]["status"] == "blocked"


def test_unsupported_command_client_fails_closed():
    result = module.main(
        step="run_scope_pipeline",
        command_client="unsupported",
    )
    assert result["status"] == "failed"
    assert result["error"] == "unsupported_command_client:unsupported"


def test_flow_schema_defaults_to_stub_command_client_for_live_safety():
    text = FLOW_PATH.read_text(encoding="utf-8")
    assert "command_client:" in text
    assert "default: stub" in text
    assert "- backend_endpoint" in text


def test_backend_endpoint_mode_fails_closed_when_url_missing():
    result = module.main(
        step="run_scope_pipeline",
        command_client="backend_endpoint",
        backend_endpoint_auth_token="token-123",
    )

    assert result["status"] == "failed"
    run_step = result["steps"]["fetch_scraped_candidates"]
    assert run_step["error"] == "backend_endpoint_missing_configuration"
    assert run_step["error_details"]["missing"] == ["backend_endpoint_url"]


def test_backend_endpoint_mode_fails_closed_when_auth_missing():
    result = module.main(
        step="run_scope_pipeline",
        command_client="backend_endpoint",
        backend_endpoint_url="https://backend.example",
    )

    assert result["status"] == "failed"
    run_step = result["steps"]["fetch_scraped_candidates"]
    assert run_step["error"] == "backend_endpoint_missing_configuration"
    assert run_step["error_details"]["missing"] == ["backend_endpoint_auth_token"]


def test_backend_endpoint_mode_passthrough_success_payload(monkeypatch):
    captured: list[dict[str, object]] = []

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"status": "succeeded", "decision_reason": "backend_scope_completed"}

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
        command_client="backend_endpoint",
        backend_endpoint_url="https://backend.example",
        backend_endpoint_auth_token="token-123",
    )

    assert result["status"] == "succeeded"
    assert captured
    first_call = captured[0]
    assert first_call["url"] == "https://backend.example/cron/pipeline/policy-evidence/command"
    request_body = first_call["json"]
    assert isinstance(request_body, dict)
    assert request_body["command_name"] == "fetch_scraped_candidates"
    assert request_body["jurisdiction"] == "San Jose CA"
    assert request_body["query_family"] == "meeting_minutes"
    assert first_call["headers"]["Authorization"] == "Bearer token-123"
    assert first_call["headers"]["X-PR-CRON-SOURCE"] == "f/affordabot/policy_evidence_package_orchestration__flow"


def test_flow_contract_includes_required_modules_and_branch():
    flow_text = FLOW_PATH.read_text(encoding="utf-8")
    for required in [
        "run_scope_pipeline",
        "readiness_branch",
        "branchone",
    ]:
        assert required in flow_text

    script_text = SCRIPT_PATH.read_text(encoding="utf-8")
    for required in [
        "fetch_scraped_candidates",
        "fetch_structured_candidates",
        "build_policy_evidence_package",
        "persist_readback_boundary",
        "evaluate_package_readiness",
    ]:
        assert required in script_text


def test_windmill_assets_do_not_embed_product_business_logic():
    text = SCRIPT_PATH.read_text(encoding="utf-8") + "\n" + FLOW_PATH.read_text(encoding="utf-8")
    forbidden_terms = [
        "elasticity",
        "pass_through",
        "econometric",
        "assumption_registry",
        "wavez",
        "source-ranking",
        "sqlalchemy",
        "insert into",
        "minio_client",
        "pgvector_client",
    ]
    for term in forbidden_terms:
        assert term not in text.lower()
