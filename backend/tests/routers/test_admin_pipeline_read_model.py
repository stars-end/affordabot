import os
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest

from main import app
from routers.admin import get_db
from services.pipeline.policy_economic_mechanism_cases import (
    PolicyEconomicMechanismCaseService,
)
from services.pipeline.domain.constants import CONTRACT_VERSION


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.connect = AsyncMock()
    db.close = AsyncMock()
    db._fetch = AsyncMock()
    db._fetchrow = AsyncMock()
    return db


@pytest.fixture
def client(mock_db):
    UNIT_TEST_SECRET = "unit-test-secret"

    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("main.db", mock_db):
        prev_env = os.environ.get("RAILWAY_ENVIRONMENT_NAME")
        prev_secret = os.environ.get("TEST_AUTH_BYPASS_SECRET")
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = "dev"
        os.environ["TEST_AUTH_BYPASS_SECRET"] = UNIT_TEST_SECRET
        try:
            with TestClient(app, base_url="http://localhost") as c:
                def set_auth(role: str = "admin"):
                    import base64
                    import hashlib
                    import hmac
                    import json
                    import time

                    payload = {
                        "sub": f"test_{role}",
                        "role": role,
                        "email": f"test_{role}@example.com",
                        "exp": int(time.time()) + 3600,
                    }
                    payload_json = json.dumps(payload, separators=(",", ":"))
                    payload_b64 = (
                        base64.urlsafe_b64encode(payload_json.encode())
                        .decode()
                        .rstrip("=")
                    )
                    msg = f"v1.{payload_b64}"
                    sig = hmac.new(
                        UNIT_TEST_SECRET.encode(), msg.encode(), hashlib.sha256
                    ).digest()
                    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
                    token = f"{msg}.{sig_b64}"
                    c.cookies.set("x-test-user", token)

                c.set_auth = set_auth
                yield c
        finally:
            if prev_env is None:
                os.environ.pop("RAILWAY_ENVIRONMENT_NAME", None)
            else:
                os.environ["RAILWAY_ENVIRONMENT_NAME"] = prev_env
            if prev_secret is None:
                os.environ.pop("TEST_AUTH_BYPASS_SECRET", None)
            else:
                os.environ["TEST_AUTH_BYPASS_SECRET"] = prev_secret

    app.dependency_overrides = {}


def test_get_pipeline_jurisdiction_status_shape(client, mock_db):
    mock_db._fetchrow.side_effect = [
        {"id": "jur-1", "name": "San Jose CA", "type": "CITY"},
        {
            "id": "run-1",
            "jurisdiction": "San Jose CA",
            "status": "completed",
            "started_at": "2026-04-13T01:00:00Z",
            "completed_at": "2026-04-13T01:05:00Z",
            "error": None,
            "windmill_run_id": "wm-run-1",
            "result": {
                "freshness": {
                    "status": "stale_but_usable",
                    "alerts": ["source_search_failed_using_last_success"],
                },
                "search_results_count": 2,
                "raw_scrapes_count": 1,
                "artifact_count": 1,
                "rag_chunks_retrieved": 4,
                "analysis": {"summary": "ok"},
                "validated_evidence_count": 4,
                "sufficiency_state": "qualitative_only",
                "alerts": ["source_search_failed_using_last_success"],
            },
        },
        {"completed_at": "2026-04-13T01:05:00Z"},
    ]
    client.set_auth("admin")
    response = client.get("/api/admin/pipeline/jurisdictions/jur-1/status")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["jurisdiction_id"] == "jur-1"
    assert data["source_family"] == "meeting_minutes"
    assert data["latest_pipeline_run_id"] == "run-1"
    assert data["operator_links"]["pipeline_run_id"] == "run-1"
    assert data["pipeline_status"] == "stale_but_usable"
    assert data["freshness"]["stale_usable_ceiling_hours"] == 72
    assert data["counts"]["chunks"] == 4
    assert data["latest_analysis"]["status"] == "ready"
    first_query = mock_db._fetchrow.call_args_list[1]
    assert first_query.args[3] == "meeting_minutes"


def test_get_pipeline_run_detail_shape(client, mock_db):
    mock_db._fetchrow.return_value = {
        "id": "run-2",
        "bill_id": "SB-1",
        "jurisdiction": "San Jose CA",
        "status": "completed",
        "started_at": "2026-04-13T02:00:00Z",
        "completed_at": "2026-04-13T02:01:00Z",
        "error": None,
        "models": {"analysis": "zai"},
        "trigger_source": "windmill",
        "windmill_workspace": "affordabot",
        "windmill_run_id": "wm-run-2",
        "source_family": "meeting_minutes",
        "result": {
            "search_results_count": 3,
            "raw_scrapes_count": 2,
            "artifact_count": 2,
            "rag_chunks_retrieved": 5,
            "analysis": {"summary": "ready"},
            "validated_evidence_count": 5,
        },
    }
    client.set_auth("admin")
    response = client.get("/api/admin/pipeline/runs/run-2")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["run_id"] == "run-2"
    assert data["pipeline_run_id"] == "run-2"
    assert data["counts"]["search_results"] == 3
    assert data["latest_analysis"]["evidence_count"] == 5
    assert data["operator_links"]["windmill_run_url"].endswith("/wm-run-2")


def test_get_pipeline_run_steps_shape(client, mock_db):
    mock_db._fetchrow.return_value = {
        "id": "run-2",
        "bill_id": "SB-1",
        "jurisdiction": "San Jose CA",
        "status": "completed",
        "started_at": "2026-04-13T02:00:00Z",
        "completed_at": "2026-04-13T02:01:00Z",
        "error": None,
        "models": {"analysis": "zai"},
        "trigger_source": "windmill",
        "windmill_workspace": "affordabot",
        "windmill_run_id": "wm-run-2",
        "source_family": "meeting_minutes",
        "result": {},
    }
    mock_db._fetch.return_value = [
        {
            "id": "step-1",
            "run_id": "run-2",
            "step_number": 1,
            "step_name": "search_materialize",
            "status": "succeeded",
            "duration_ms": 42,
            "input_context": {"q": "san jose meeting minutes"},
            "output_result": {
                "command": "search_materialize",
                "decision_reason": "fresh_snapshot_materialized",
                "retry_class": "none",
                "counts": {"search_results": 2},
                "refs": {"search_snapshot_id": "snap-1"},
            },
            "model_config": {},
            "created_at": "2026-04-13T02:00:10Z",
        },
    ]
    client.set_auth("admin")
    response = client.get("/api/admin/pipeline/runs/run-2/steps")
    assert response.status_code == 200
    data = response.json()
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["run_id"] == "run-2"
    assert data["pipeline_run_id"] == "run-2"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["command"] == "search_materialize"
    assert data["steps"][0]["refs"]["search_snapshot_id"] == "snap-1"


def test_get_pipeline_run_evidence_shape(client, mock_db):
    mock_db._fetchrow.return_value = {
        "id": "run-3",
        "bill_id": "SB-1",
        "jurisdiction": "San Jose CA",
        "status": "completed",
        "started_at": "2026-04-13T02:00:00Z",
        "completed_at": "2026-04-13T02:01:00Z",
        "error": None,
        "models": {"analysis": "zai"},
        "trigger_source": "windmill",
        "windmill_workspace": "affordabot",
        "windmill_run_id": "wm-run-3",
        "source_family": "meeting_minutes",
        "result": {
            "analysis": {
                "citations": [
                    {"type": "chunk", "label": "City Agenda Packet", "source_ref": "raw-1"}
                ]
            }
        },
    }
    client.set_auth("admin")
    response = client.get("/api/admin/pipeline/runs/run-3/evidence")
    assert response.status_code == 200
    data = response.json()
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["evidence_count"] == 1
    assert data["items"][0]["label"] == "City Agenda Packet"


def test_get_pipeline_run_steps_rejects_non_run_uuid_query_key(client, mock_db):
    # get_pipeline_run is strict id lookup; bill/manual keys should not resolve here.
    mock_db._fetchrow.return_value = None
    client.set_auth("admin")
    response = client.get("/api/admin/pipeline/runs/SR-2026-001/steps")
    assert response.status_code == 404
    assert response.json()["detail"] == "Pipeline run not found"
    mock_db._fetch.assert_not_called()


def test_post_pipeline_jurisdiction_refresh_shape(client, mock_db):
    mock_db._fetchrow.return_value = {
        "id": "jur-7",
        "name": "San Jose CA",
        "type": "CITY",
    }
    client.set_auth("admin")
    response = client.post("/api/admin/pipeline/jurisdictions/jur-7/refresh")
    assert response.status_code == 200
    data = response.json()
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["status"] == "accepted"
    assert data["decision_reason"] == "manual_refresh_queued"
    assert data["jurisdiction_id"] == "jur-7"


def _case_package(case_id: str) -> dict:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    for case in bundle["cases"]:
        if case["case_id"] == case_id:
            return case["primary_package"]
    raise AssertionError(f"missing case_id={case_id}")


def test_policy_evidence_analysis_status_surfaces_provenance_and_not_proven_gates(
    client, mock_db
):
    package = _case_package("direct_cost_case")
    mock_db._fetchrow.side_effect = [
        {
            "id": "run-q1",
            "bill_id": "SR-2026-001",
            "jurisdiction": "San Jose CA",
            "status": "completed",
            "error": None,
            "models": {},
            "trigger_source": "windmill",
            "windmill_run_id": "wm-run-q1",
            "started_at": "2026-04-15T01:00:00Z",
            "completed_at": "2026-04-15T01:02:00Z",
            "result": {
                "policy_evidence_package": package,
                "rows": [],
                "orchestration_proof": {},
                "llm_narrative_proof": {},
                "storage_proof": {},
            },
        },
        {
            "id": "pkg-row-q1",
            "package_id": package["package_id"],
            "package_payload": {**package, "run_context": {"backend_run_id": "run-q1"}},
            "artifact_readback_status": "proven",
            "fail_closed": False,
            "gate_state": "quantified",
            "created_at": "2026-04-15T01:00:00Z",
            "updated_at": "2026-04-15T01:02:00Z",
        },
    ]

    client.set_auth("admin")
    response = client.get(
        f"/api/admin/pipeline/policy-evidence/packages/{package['package_id']}/analysis-status?run_id=run-q1"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["package_id"] == package["package_id"]
    assert data["backend_run_id"] == "run-q1"
    assert data["provenance"]["canonical_document_key"] == package["canonical_document_key"]
    assert "scraped" in data["provenance"]["source_lanes"]
    assert "structured" in data["provenance"]["source_lanes"]
    assert data["provenance"]["scraped_sources"], "expected scraped provenance rows"
    assert data["provenance"]["structured_sources"], "expected structured provenance rows"
    assert data["gates"]["storage/read-back"]["status"] == "pass"
    assert data["gates"]["Windmill/orchestration"]["status"] == "not_proven"
    assert data["gates"]["LLM narrative"]["status"] == "not_proven"
    assert data["economic_analysis_status"]["status"] in {
        "secondary_research_needed",
        "qualitative_only",
        "decision_grade",
    }
    assert data["economic_output"]["status"] in {"ready", "not_proven"}
    if data["economic_output"]["status"] != "ready":
        assert data["economic_output"]["user_facing_conclusion"] is None
    assert "parameter_readiness" in data["economic_readiness"]
    assert "unsupported_claim_rejection" in data["economic_readiness"]


def test_policy_evidence_analysis_status_fail_closed_case_blocks_quantified_conclusion(
    client, mock_db
):
    package = _case_package("secondary_research_required_case")
    mock_db._fetchrow.side_effect = [
        {
            "id": "run-q3",
            "bill_id": "SR-2026-001",
            "jurisdiction": "San Jose CA",
            "status": "completed",
            "error": None,
            "models": {},
            "trigger_source": "windmill",
            "windmill_run_id": "wm-run-q3",
            "started_at": "2026-04-15T03:00:00Z",
            "completed_at": "2026-04-15T03:02:00Z",
            "result": {"policy_evidence_package": package},
        },
        {
            "id": "pkg-row-q3",
            "package_id": package["package_id"],
            "package_payload": {
                **package,
                "run_context": {"backend_run_id": "run-q3"},
            },
            "artifact_readback_status": "missing",
            "fail_closed": True,
            "gate_state": "insufficient_evidence",
            "created_at": "2026-04-15T03:00:00Z",
            "updated_at": "2026-04-15T03:02:00Z",
        },
    ]

    client.set_auth("admin")
    response = client.get(
        f"/api/admin/pipeline/policy-evidence/packages/{package['package_id']}/analysis-status?run_id=run-q3"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["backend_run_id"] == "run-q3"
    assert data["economic_analysis_status"]["status"] in {
        "fail_closed",
        "secondary_research_needed",
        "qualitative_only",
    }
    assert data["economic_output"]["status"] == "not_proven"
    assert data["economic_output"]["decision_grade_verdict"] == "not_decision_grade"
    assert data["economic_output"]["user_facing_conclusion"] is None


def test_policy_evidence_analysis_status_rejects_missing_package_in_run(client, mock_db):
    package = _case_package("direct_cost_case")
    mock_db._fetchrow.return_value = {
        "id": "run-q2",
        "bill_id": "SR-2026-001",
        "jurisdiction": "San Jose CA",
        "status": "completed",
        "error": None,
        "models": {},
        "trigger_source": "windmill",
        "windmill_run_id": "wm-run-q2",
        "result": {
            "policy_evidence_package": package,
        },
    }

    client.set_auth("admin")
    response = client.get(
        "/api/admin/pipeline/policy-evidence/packages/pkg-does-not-exist/analysis-status?run_id=run-q2"
    )
    assert response.status_code == 404


def test_policy_evidence_analysis_status_hydrates_live_run_context_proofs(client, mock_db):
    package = _case_package("indirect_pass_through_case")
    scraped = dict(package["scraped_sources"][0])
    scraped["reader_substance_passed"] = False
    package = {
        **package,
        "scraped_sources": [scraped],
    }
    mock_db._fetchrow.side_effect = [
        {
            "id": "run-live-q4",
            "bill_id": "SJ-2026-AHIF",
            "jurisdiction": "San Jose CA",
            "status": "completed",
            "error": None,
            "models": {},
            "trigger_source": "windmill",
            "windmill_run_id": "wm-live-q4",
            "started_at": "2026-04-16T01:00:00Z",
            "completed_at": "2026-04-16T01:03:00Z",
            "result": {
                "policy_evidence_package": package,
                "analysis": {
                    "summary": "Narrative generated from selected artifact.",
                },
                "rows": [],
                "orchestration_proof": {},
                "llm_narrative_proof": {},
                "storage_proof": {},
            },
        },
        {
            "id": "pkg-row-live-q4",
            "package_id": package["package_id"],
            "package_payload": {
                **package,
                "gate_projection": {
                    **package["gate_projection"],
                    "canonical_pipeline_run_id": "run-live-q4",
                    "canonical_pipeline_step_id": "analysis-q4",
                    "canonical_breakdown_ref": "analysis:analysis-q4",
                },
                "run_context": {
                    "backend_run_id": "run-live-q4",
                    "windmill_run_id": "wm-live-q4",
                    "windmill_job_id": "run_scope_pipeline:0:run_scope_pipeline",
                    "windmill_workspace": "affordabot",
                    "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                    "reader_artifact_uri": "minio://affordabot-artifacts/artifacts/live/reader_output.md",
                },
            },
            "artifact_readback_status": "proven",
            "fail_closed": False,
            "gate_state": "qualitative_only",
            "created_at": "2026-04-16T01:00:00Z",
            "updated_at": "2026-04-16T01:03:00Z",
        },
    ]

    client.set_auth("admin")
    response = client.get(
        f"/api/admin/pipeline/policy-evidence/packages/{package['package_id']}/analysis-status?run_id=run-live-q4"
    )
    assert response.status_code == 200, response.text
    data = response.json()
    scraped_row = data["provenance"]["scraped_sources"][0]
    assert scraped_row["reader_substance_observed"] is False
    assert scraped_row["reader_substance_passed"] is True
    assert scraped_row["reader_provenance_hydrated"] is True
    assert data["gates"]["storage/read-back"]["status"] == "pass"
    assert data["gates"]["Windmill/orchestration"]["status"] == "pass"
    assert "scope job id only" in data["gates"]["Windmill/orchestration"]["reason"]
    windmill_ref_keys = {ref["key"] for ref in data["gates"]["Windmill/orchestration"]["refs"]}
    assert "windmill_scope_job_id" in windmill_ref_keys
    assert data["gates"]["LLM narrative"]["status"] == "pass"
    assert data["canonical_analysis_binding"]["status"] == "bound"
    assert data["canonical_analysis_binding"]["package_projection"] == {
        "canonical_pipeline_run_id": "run-live-q4",
        "canonical_pipeline_step_id": "analysis-q4",
    }
    if "missing_evidence" in data["economic_output"]:
        assert all(
            not str(item).startswith("reader:")
            for item in data["economic_output"]["missing_evidence"]
        )
