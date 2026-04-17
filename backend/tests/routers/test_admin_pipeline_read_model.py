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
                "llm_narrative_proof": {
                    "proof_status": "not_proven",
                    "blocker": "canonical_llm_run_id_unverified_from_package_payload",
                },
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
    assert data["source_quality"]["status"] == "not_proven"
    assert data["source_quality"]["reason"] == "source_quality_metrics_missing"
    assert data["source_quality"]["selection_quality_status"] == "not_proven"
    assert "data_moat_status" in data
    assert "data_moat_value" in data
    assert data["data_moat_status"]["status"] in {
        "decision_grade_data_moat",
        "evidence_ready_with_gaps",
        "fail",
    }
    assert data["data_moat_value"]["status"] in {
        "stored_policy_evidence",
        "economic_handoff_candidate",
        "economic_analysis_ready",
        "stored_not_economic",
        "not_stored_policy_evidence",
    }
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
    assert "economic_handoff_quality" in data
    assert "mechanism_candidates" in data
    assert "parameter_inventory" in data
    assert "missing_parameters" in data
    assert "assumption_needs" in data
    assert "secondary_research_needs" in data
    assert "unsupported_claim_risks" in data
    assert "recommended_next_action" in data
    assert data["economic_handoff_quality"]["status"] in {
        "analysis_ready",
        "analysis_ready_with_gaps",
        "not_analysis_ready",
    }
    assert data["recommended_next_action"] in {
        "run_direct_analysis",
        "run_secondary_research",
        "qualitative_summary_only",
        "improve_data_moat_sources",
        "ingest_official_attachments",
        "parse_official_attachment_pdfs",
        "reject",
    }
    assert data["manual_audit_scaffold"]["status"] == "required"


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
    assert data["economic_handoff_quality"]["status"] == "not_analysis_ready"
    if data["economic_analysis_status"]["status"] == "fail_closed":
        assert data["economic_handoff_quality"]["fail_closed_specific"] is True
        assert data["recommended_next_action"] == "reject"
    else:
        assert data["economic_handoff_quality"]["reason_code"] in {
            "secondary_research_contract_required",
            "pass_through_incidence_assumptions_missing",
            "unsupported_claim_risk_high",
        }


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
                    "run_id": "run-live-q4",
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


def test_policy_evidence_analysis_status_surfaces_selected_artifact_quality_metrics(client, mock_db):
    package = _case_package("direct_cost_case")
    source_quality_metrics = {
        "top_n_window": 5,
        "top_n_official_recall_count": 5,
        "top_n_artifact_recall_count": 2,
        "selected_artifact_family": "official_page",
        "reader_substance_observed": True,
        "secondary_numeric_rescue_detected": True,
        "secondary_numeric_parameter_count": 2,
        "selected_candidate": {
            "url": "https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee",
            "provider": "private_searxng",
            "rank": 1,
            "selection_reason": "materialized_raw_scrape",
            "artifact_grade": False,
            "official_domain": True,
            "artifact_family": "official_page",
        },
        "provider_summary": {
            "primary_provider": "private_searxng",
            "provider_error_count": 1,
            "quality_failure_count": 0,
        },
        "provider_results": {
            "private_searxng": {
                "status": "succeeded",
                "reason_code": "materialized_raw_scrape",
                "candidates": [
                    {
                        "url": "https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee",
                        "rank": 1,
                        "artifact_grade": False,
                        "official_domain": True,
                    },
                    {
                        "url": "https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6",
                        "rank": 2,
                        "artifact_grade": True,
                        "official_domain": True,
                    },
                ],
            }
        },
    }
    mock_db._fetchrow.side_effect = [
        {
            "id": "run-q5",
            "bill_id": "SJ-2026-CLF",
            "jurisdiction": "San Jose CA",
            "status": "completed",
            "error": None,
            "models": {},
            "trigger_source": "windmill",
            "windmill_run_id": "wm-run-q5",
            "started_at": "2026-04-16T05:00:00Z",
            "completed_at": "2026-04-16T05:05:00Z",
            "result": {
                "policy_evidence_package": package,
                "rows": [
                    {
                        "field": "commercial_linkage_fee_rate_usd_per_sqft",
                        "raw_value": "Residential Care $ 18.706.00",
                        "normalized_value": None,
                        "value": None,
                        "source_family": "resolution",
                        "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                        "source_ref": "legistar::matter::7526::attachment::301",
                        "source_locator": "attachment_probe:301",
                        "provenance_lane": "structured_attachment_probe",
                        "attachment_id": "301",
                        "attachment_title": "Resolution No. 80069",
                        "ambiguity_flag": True,
                        "ambiguity_reason": "currency_format_anomaly",
                        "currency_sanity": "invalid",
                        "unit_sanity": "valid",
                    }
                ],
                "analysis": {"summary": "Narrative generated from selected artifact."},
            },
        },
        {
            "id": "pkg-row-q5",
            "package_id": package["package_id"],
            "package_payload": {
                **package,
                "gate_projection": {
                    **package["gate_projection"],
                    "canonical_pipeline_run_id": "run-q5",
                    "canonical_pipeline_step_id": "analysis-q5",
                    "canonical_breakdown_ref": "analysis:analysis-q5",
                },
                "run_context": {
                    "backend_run_id": "run-q5",
                    "windmill_run_id": "wm-run-q5",
                    "windmill_job_id": "run_scope_pipeline:0:run_scope_pipeline",
                    "windmill_workspace": "affordabot",
                    "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                    "policy_lineage": {
                        "attachment_state": {
                            "attachment_economic_row_count": 0,
                        }
                    },
                    "source_quality_metrics": source_quality_metrics,
                    "source_reconciliation": {
                        "true_structured_row_count": 0,
                        "missing_true_structured_corroboration_count": 2,
                    },
                },
            },
            "artifact_readback_status": "proven",
            "fail_closed": False,
            "gate_state": "qualitative_only",
            "created_at": "2026-04-16T05:00:00Z",
            "updated_at": "2026-04-16T05:05:00Z",
        },
    ]

    client.set_auth("admin")
    response = client.get(
        f"/api/admin/pipeline/policy-evidence/packages/{package['package_id']}/analysis-status?run_id=run-q5"
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["source_quality"]["status"] == "captured"
    assert data["source_quality"]["selected_artifact_family"] == "official_page"
    assert data["source_quality"]["top_n_artifact_recall_count"] == 2
    assert data["source_quality"]["secondary_numeric_rescue_detected"] is True
    assert data["source_quality"]["selected_candidate_rank"] == 1
    assert data["source_quality"]["selection_quality_status"] == "fail"
    moat = data["data_moat_status"]
    assert moat["runtime_ready"] is True
    assert moat["source_quality_ready"] is False
    assert moat["structured_depth_ready"] is False
    assert moat["source_selection_blocker"] is True
    assert moat["source_selection_reason"] == "official_page_selected_while_artifact_candidates_exist"
    assert moat["true_structured_row_count"] == 0
    assert moat["missing_true_structured_corroboration_count"] == 2
    assert moat["official_attachment_row_count"] == 0
    assert moat["row_family_depth"]["true_structured"]["satisfies_depth"] is False
    assert moat["row_family_depth"]["official_attachment"]["satisfies_depth"] is False
    assert moat["row_family_depth"]["secondary_search"]["satisfies_depth"] is False
    assert data["source_quality"]["row_family_depth"]["official_attachment"]["row_count"] == 0
    assert data["source_quality"]["structured_depth_ready"] is False
    moat_value = data["data_moat_value"]
    assert moat_value["status"] in {
        "stored_policy_evidence",
        "economic_handoff_candidate",
        "economic_analysis_ready",
        "stored_not_economic",
        "not_stored_policy_evidence",
    }
    assert moat_value["stored_policy_evidence"] is True
    assert moat_value["economic_analysis_ready"] is False
    assert data["recommended_next_action"] == "ingest_official_attachments"


def test_policy_evidence_analysis_status_identity_blocker_fails_data_moat_and_handoff(client, mock_db):
    package = _case_package("direct_cost_case")
    source_quality_metrics = {
        "top_n_window": 5,
        "top_n_official_recall_count": 3,
        "top_n_artifact_recall_count": 1,
        "selected_artifact_family": "artifact",
        "reader_substance_observed": True,
        "selected_candidate": {
            "url": "https://www.hcd.ca.gov/housing-elements/docs/los%20altos_5th_draft011415.pdf",
            "provider": "private_searxng",
            "rank": 1,
            "selection_reason": "materialized_raw_scrape",
            "artifact_grade": True,
            "official_domain": True,
            "artifact_family": "artifact",
        },
        "policy_identity_ready": False,
        "jurisdiction_identity_ready": False,
        "identity_blocker_code": "jurisdiction_identity_mismatch",
        "identity_blocker_reason": "Selected source points to Los Altos, not San Jose CLF policy lineage.",
        "provider_summary": {
            "primary_provider": "private_searxng",
            "provider_error_count": 0,
            "quality_failure_count": 0,
        },
        "provider_results": {
            "private_searxng": {
                "status": "succeeded",
                "reason_code": "materialized_raw_scrape",
                "candidates": [
                    {
                        "url": "https://www.hcd.ca.gov/housing-elements/docs/los%20altos_5th_draft011415.pdf",
                        "rank": 1,
                        "artifact_grade": True,
                        "official_domain": True,
                    }
                ],
            }
        },
    }
    mock_db._fetchrow.side_effect = [
        {
            "id": "run-q6",
            "bill_id": "SJ-2026-CLF",
            "jurisdiction": "San Jose CA",
            "status": "completed",
            "error": None,
            "models": {},
            "trigger_source": "windmill",
            "windmill_run_id": "wm-run-q6",
            "started_at": "2026-04-16T06:00:00Z",
            "completed_at": "2026-04-16T06:05:00Z",
            "result": {
                "policy_evidence_package": package,
                "rows": [
                    {
                        "field": "commercial_linkage_fee_rate_usd_per_sqft",
                        "raw_value": "Residential Care $ 18.706.00",
                        "normalized_value": None,
                        "value": None,
                        "source_family": "resolution",
                        "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                        "source_ref": "legistar::matter::7526::attachment::301",
                        "source_locator": "attachment_probe:301",
                        "provenance_lane": "structured_attachment_probe",
                        "attachment_id": "301",
                        "attachment_title": "Resolution No. 80069",
                        "ambiguity_flag": True,
                        "ambiguity_reason": "currency_format_anomaly",
                        "currency_sanity": "invalid",
                        "unit_sanity": "valid",
                    }
                ],
                "analysis": {"summary": "Narrative generated from selected artifact."},
            },
        },
        {
            "id": "pkg-row-q6",
            "package_id": package["package_id"],
            "package_payload": {
                **package,
                "gate_projection": {
                    **package["gate_projection"],
                    "canonical_pipeline_run_id": "run-q6",
                    "canonical_pipeline_step_id": "analysis-q6",
                    "canonical_breakdown_ref": "analysis:analysis-q6",
                },
                "run_context": {
                    "backend_run_id": "run-q6",
                    "windmill_run_id": "wm-run-q6",
                    "windmill_job_id": "run_scope_pipeline:0:run_scope_pipeline",
                    "windmill_workspace": "affordabot",
                    "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                    "source_quality_metrics": source_quality_metrics,
                    "source_reconciliation": {
                        "true_structured_row_count": 1,
                        "missing_true_structured_corroboration_count": 0,
                    },
                },
            },
            "artifact_readback_status": "proven",
            "fail_closed": False,
            "gate_state": "qualitative_only",
            "created_at": "2026-04-16T06:00:00Z",
            "updated_at": "2026-04-16T06:05:00Z",
        },
    ]

    client.set_auth("admin")
    response = client.get(
        f"/api/admin/pipeline/policy-evidence/packages/{package['package_id']}/analysis-status?run_id=run-q6"
    )
    assert response.status_code == 200, response.text
    data = response.json()

    source_quality = data["source_quality"]
    assert source_quality["selection_quality_status"] == "fail"
    assert source_quality["selection_quality_reason"] == "jurisdiction_identity_mismatch"
    assert source_quality["identity_ready"] is False
    assert source_quality["identity_blocker_code"] == "jurisdiction_identity_mismatch"
    assert source_quality["identity_recommended_action"] == "repair_source_identity"

    moat = data["data_moat_status"]
    assert moat["runtime_ready"] is True
    assert moat["structured_depth_ready"] is True
    assert moat["source_quality_ready"] is False
    assert moat["identity_ready"] is False
    assert moat["identity_blocker_code"] == "jurisdiction_identity_mismatch"
    assert moat["identity_recommended_action"] == "repair_source_identity"
    assert moat["recommended_next_action"] == "repair_source_identity"

    handoff = data["economic_handoff_quality"]
    assert handoff["status"] == "not_analysis_ready"
    assert handoff["reason_code"] == "jurisdiction_identity_mismatch"
    assert handoff["source_identity_blocker"] is True
    assert data["recommended_next_action"] == "repair_source_identity"


def test_policy_evidence_analysis_status_official_attachment_rows_satisfy_depth_family(client, mock_db):
    package = _case_package("direct_cost_case")
    source_quality_metrics = {
        "top_n_window": 5,
        "top_n_official_recall_count": 3,
        "top_n_artifact_recall_count": 1,
        "selected_artifact_family": "official_page",
        "selection_quality_status": "fail",
        "selection_quality_reason": "no_artifact_candidate_passed_quality_gate",
        "policy_identity_ready": True,
        "jurisdiction_identity_ready": True,
        "selected_candidate": {
            "url": "https://www.sanjoseca.gov/Home/Components/News/News/1683/4765",
            "provider": "private_searxng",
            "rank": 1,
            "artifact_family": "official_page",
        },
    }
    mock_db._fetchrow.side_effect = [
        {
            "id": "run-q7",
            "bill_id": "SJ-2026-CLF",
            "jurisdiction": "San Jose CA",
            "status": "completed",
            "error": None,
            "models": {},
            "trigger_source": "windmill",
            "windmill_run_id": "wm-run-q7",
            "started_at": "2026-04-16T07:00:00Z",
            "completed_at": "2026-04-16T07:05:00Z",
            "result": {
                "policy_evidence_package": package,
                "rows": [
                    {
                        "field": "commercial_linkage_fee_rate_usd_per_sqft",
                        "raw_value": "Residential Care $ 18.706.00",
                        "normalized_value": None,
                        "value": None,
                        "source_family": "resolution",
                        "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                        "source_ref": "legistar::matter::7526::attachment::301",
                        "source_locator": "attachment_probe:301",
                        "provenance_lane": "structured_attachment_probe",
                        "attachment_id": "301",
                        "attachment_title": "Resolution No. 80069",
                        "ambiguity_flag": True,
                        "ambiguity_reason": "currency_format_anomaly",
                        "currency_sanity": "invalid",
                        "unit_sanity": "valid",
                    }
                ],
                "analysis": {"summary": "Narrative generated from selected artifact."},
            },
        },
        {
            "id": "pkg-row-q7",
            "package_id": package["package_id"],
            "package_payload": {
                **package,
                "gate_projection": {
                    **package["gate_projection"],
                    "canonical_pipeline_run_id": "run-q7",
                    "canonical_pipeline_step_id": "analysis-q7",
                    "canonical_breakdown_ref": "analysis:analysis-q7",
                },
                "run_context": {
                    "backend_run_id": "run-q7",
                    "windmill_run_id": "wm-run-q7",
                    "windmill_job_id": "run_scope_pipeline:0:run_scope_pipeline",
                    "windmill_workspace": "affordabot",
                    "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                    "policy_lineage": {
                        "related_attachment_refs": [
                            {
                                "attachment_id": "301",
                                "title": "Resolution No. 80069",
                                "url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                                "source_family": "resolution",
                            }
                        ],
                        "attachment_state": {
                            "attachment_ref_count": 1,
                            "attachment_probe_count": 2,
                            "attachment_ingested_count": 1,
                            "attachment_economic_row_count": 2,
                        },
                        "attachment_content_probes": [
                            {
                                "attachment_id": "301",
                                "title": "Resolution No. 80069",
                                "source_family": "resolution",
                                "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120.pdf",
                                "status": "ingested_excerpt",
                                "read_status": "read_text",
                                "failure_class": None,
                                "content_ingested": True,
                                "economic_row_count": 2,
                            },
                            {
                                "attachment_id": "302",
                                "title": "Memo",
                                "source_family": "memorandum",
                                "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758121.pdf",
                                "status": "binary_pdf_unparsed",
                                "read_status": "binary_unparsed",
                                "failure_class": "binary_pdf_unparsed",
                                "content_ingested": False,
                                "economic_row_count": 0,
                            },
                        ],
                    },
                    "source_quality_metrics": source_quality_metrics,
                    "source_reconciliation": {
                        "true_structured_row_count": 0,
                        "missing_true_structured_corroboration_count": 0,
                        "secondary_snippet_row_count": 3,
                    },
                },
            },
            "artifact_readback_status": "proven",
            "fail_closed": False,
            "gate_state": "qualitative_only",
            "created_at": "2026-04-16T07:00:00Z",
            "updated_at": "2026-04-16T07:05:00Z",
        },
    ]

    client.set_auth("admin")
    response = client.get(
        f"/api/admin/pipeline/policy-evidence/packages/{package['package_id']}/analysis-status?run_id=run-q7"
    )
    assert response.status_code == 200, response.text
    data = response.json()
    moat = data["data_moat_status"]
    assert moat["structured_depth_ready"] is True
    assert moat["true_structured_depth_ready"] is False
    assert moat["official_attachment_depth_ready"] is True
    assert moat["official_attachment_row_count"] == 2
    assert moat["attachment_ref_count"] == 1
    assert moat["attachment_probe_count"] == 2
    assert moat["attachment_content_ingested_count"] == 1
    assert moat["official_attachment_refs_present"] is True
    assert moat["official_pdf_text_extracted"] is True
    assert moat["official_attachment_rows_emitted"] is True
    assert moat["official_attachment_failure_counts"]["binary_pdf_unparsed"] == 1
    assert moat["official_attachment_parse_anomaly_count"] == 1
    assert moat["official_attachment_parse_anomalies"][0]["raw_value"] == "Residential Care $ 18.706.00"
    assert moat["secondary_search_row_count"] == 3
    assert moat["row_family_depth"]["official_attachment"]["satisfies_depth"] is True
    assert moat["row_family_depth"]["secondary_search"]["satisfies_depth"] is False
    assert moat["structured_depth_satisfied_by"] == ["official_attachment"]
    assert data["source_quality"]["row_family_depth"]["official_attachment"]["row_count"] == 2
    assert data["source_quality"]["structured_depth_ready"] is True
    assert data["source_quality"]["official_attachment_refs_present"] is True
    assert data["source_quality"]["official_pdf_text_extracted"] is True
    assert data["source_quality"]["official_attachment_rows_emitted"] is True


def test_policy_evidence_analysis_status_cycle_34_attachment_failure_surfaces_parse_action(client, mock_db):
    package = _case_package("direct_cost_case")
    source_quality_metrics = {
        "selected_artifact_family": "official_page",
        "top_n_artifact_recall_count": 0,
        "policy_identity_ready": True,
        "jurisdiction_identity_ready": True,
        "selected_candidate": {
            "url": "https://www.sanjoseca.gov/Home/Components/News/News/1683/4765",
            "provider": "private_searxng",
            "rank": 1,
            "artifact_family": "official_page",
        },
    }
    mock_db._fetchrow.side_effect = [
        {
            "id": "run-q8",
            "bill_id": "SJ-2026-CLF",
            "jurisdiction": "San Jose CA",
            "status": "completed",
            "error": None,
            "models": {},
            "trigger_source": "windmill",
            "windmill_run_id": "wm-run-q8",
            "started_at": "2026-04-16T08:00:00Z",
            "completed_at": "2026-04-16T08:05:00Z",
            "result": {
                "policy_evidence_package": package,
                "rows": [],
                "analysis": {"summary": "Narrative generated from selected artifact."},
            },
        },
        {
            "id": "pkg-row-q8",
            "package_id": package["package_id"],
            "package_payload": {
                **package,
                "gate_projection": {
                    **package["gate_projection"],
                    "canonical_pipeline_run_id": "run-q8",
                    "canonical_pipeline_step_id": "analysis-q8",
                    "canonical_breakdown_ref": "analysis:analysis-q8",
                },
                "run_context": {
                    "backend_run_id": "run-q8",
                    "windmill_run_id": "wm-run-q8",
                    "windmill_job_id": "run_scope_pipeline:0:run_scope_pipeline",
                    "windmill_workspace": "affordabot",
                    "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                    "policy_lineage": {
                        "related_attachment_refs": [
                            {
                                "attachment_id": "301",
                                "title": "Resolution No. 80069",
                                "url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                                "source_family": "resolution",
                            },
                            {
                                "attachment_id": "302",
                                "title": "Third-party memo",
                                "url": "https://example.com/memo.pdf",
                                "source_family": "memorandum",
                            },
                        ],
                        "attachment_state": {
                            "attachment_ref_count": 2,
                            "attachment_probe_count": 3,
                            "attachment_ingested_count": 0,
                            "attachment_economic_row_count": 0,
                        },
                        "attachment_content_probes": [
                            {
                                "attachment_id": "301",
                                "title": "Resolution No. 80069",
                                "source_family": "resolution",
                                "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                                "status": "binary_pdf_unparsed",
                                "read_status": "binary_unparsed",
                                "failure_class": "binary_pdf_unparsed",
                                "content_ingested": False,
                                "economic_row_count": 0,
                            },
                            {
                                "attachment_id": "302",
                                "title": "Third-party memo",
                                "source_family": "memorandum",
                                "source_url": "https://example.com/memo.pdf",
                                "status": "skipped_non_official_attachment",
                                "read_status": "not_read",
                                "failure_class": "non_official_attachment",
                                "content_ingested": False,
                                "economic_row_count": 0,
                            },
                            {
                                "attachment_id": "303",
                                "title": "Nexus Addendum",
                                "source_family": "nexus_study",
                                "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758999",
                                "status": "fetch_failed",
                                "read_status": "fetch_failed",
                                "failure_class": "attachment_fetch_failed",
                                "content_ingested": False,
                                "economic_row_count": 0,
                            },
                        ],
                    },
                    "source_quality_metrics": source_quality_metrics,
                    "source_reconciliation": {
                        "true_structured_row_count": 0,
                        "missing_true_structured_corroboration_count": 0,
                        "secondary_snippet_row_count": 1,
                        "official_attachment_row_count": 0,
                    },
                },
            },
            "artifact_readback_status": "proven",
            "fail_closed": False,
            "gate_state": "qualitative_only",
            "created_at": "2026-04-16T08:00:00Z",
            "updated_at": "2026-04-16T08:05:00Z",
        },
    ]

    client.set_auth("admin")
    response = client.get(
        f"/api/admin/pipeline/policy-evidence/packages/{package['package_id']}/analysis-status?run_id=run-q8"
    )
    assert response.status_code == 200, response.text
    data = response.json()
    moat = data["data_moat_status"]
    assert moat["status"] == "fail"
    assert moat["official_attachment_refs_present"] is True
    assert moat["official_pdf_text_extracted"] is False
    assert moat["official_attachment_rows_emitted"] is False
    assert moat["attachment_ref_count"] == 2
    assert moat["attachment_probe_count"] == 3
    assert moat["attachment_content_ingested_count"] == 0
    assert moat["attachment_economic_row_count"] == 0
    assert moat["official_attachment_failure_counts"]["non_official_attachment"] == 1
    assert moat["official_attachment_failure_counts"]["binary_pdf_unparsed"] == 1
    assert moat["official_attachment_failure_counts"]["fetch_failed"] == 1
    assert data["source_quality"]["official_attachment_refs_present"] is True
    assert data["source_quality"]["official_pdf_text_extracted"] is False
    assert data["recommended_next_action"] == "parse_official_attachment_pdfs"


def test_policy_evidence_analysis_status_cycle_38_surfaces_row_quality_gap_signals(client, mock_db):
    package = _case_package("direct_cost_case")
    source_quality_metrics = {
        "selected_artifact_family": "official_page",
        "top_n_artifact_recall_count": 0,
        "policy_identity_ready": True,
        "jurisdiction_identity_ready": True,
        "selected_candidate": {
            "url": "https://www.sanjoseca.gov/Home/Components/News/News/1683/4765",
            "provider": "private_searxng",
            "rank": 1,
            "artifact_family": "official_page",
        },
    }
    mock_db._fetchrow.side_effect = [
        {
            "id": "run-q38",
            "bill_id": "SJ-2026-CLF",
            "jurisdiction": "San Jose CA",
            "status": "completed",
            "error": None,
            "models": {},
            "trigger_source": "windmill",
            "windmill_run_id": "wm-run-q38",
            "started_at": "2026-04-16T09:00:00Z",
            "completed_at": "2026-04-16T09:05:00Z",
            "result": {
                "policy_evidence_package": package,
                "rows": [
                    {
                        "field": "commercial_linkage_fee_rate_usd_per_sqft",
                        "normalized_value": 18.7,
                        "value": 18.7,
                        "locator_quality": "table_row_chunk_locator",
                        "source_family": "resolution",
                        "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                        "source_ref": "legistar::matter::7526::attachment::301",
                        "source_locator": "attachment_probe:301:1:fee_table_row",
                        "provenance_lane": "structured_attachment_probe",
                        "attachment_id": "301",
                    },
                    {
                        "field": "commercial_linkage_fee_rate_usd_per_sqft",
                        "normalized_value": None,
                        "value": None,
                        "ambiguity_flag": True,
                        "ambiguity_reason": "currency_format_anomaly",
                        "currency_sanity": "invalid",
                        "unit_sanity": "valid",
                        "locator_quality": "chunk_locator_only",
                        "source_family": "resolution",
                        "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                        "source_ref": "legistar::matter::7526::attachment::301",
                        "source_locator": "attachment_probe:301:2:fee_table_row",
                        "provenance_lane": "structured_attachment_probe",
                        "attachment_id": "301",
                    },
                    {
                        "field": "commercial_linkage_fee_rate_usd_per_sqft",
                        "normalized_value": None,
                        "value": None,
                        "row_status": "rejected",
                        "locator_quality": "locator_not_available",
                        "source_family": "resolution",
                        "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                        "source_ref": "legistar::matter::7526::attachment::301",
                        "source_locator": "attachment_probe:301:3:fee_table_row",
                        "provenance_lane": "structured_attachment_probe",
                        "attachment_id": "301",
                    },
                ],
                "analysis": {"summary": "Narrative generated from selected artifact."},
            },
        },
        {
            "id": "pkg-row-q38",
            "package_id": package["package_id"],
            "package_payload": {
                **package,
                "gate_projection": {
                    **package["gate_projection"],
                    "canonical_pipeline_run_id": "run-q38",
                    "canonical_pipeline_step_id": "analysis-q38",
                    "canonical_breakdown_ref": "analysis:analysis-q38",
                },
                "run_context": {
                    "backend_run_id": "run-q38",
                    "windmill_run_id": "wm-run-q38",
                    "windmill_job_id": "run_scope_pipeline:0:run_scope_pipeline",
                    "windmill_workspace": "affordabot",
                    "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                    "source_quality_metrics": source_quality_metrics,
                    "source_reconciliation": {
                        "true_structured_row_count": 0,
                        "missing_true_structured_corroboration_count": 0,
                        "official_attachment_row_count": 3,
                    },
                    "policy_lineage": {
                        "related_attachment_refs": [
                            {
                                "attachment_id": "301",
                                "title": "Resolution No. 80069",
                                "url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120",
                                "source_family": "resolution",
                            }
                        ],
                        "attachment_state": {
                            "attachment_ref_count": 1,
                            "attachment_probe_count": 2,
                            "attachment_ingested_count": 1,
                            "attachment_economic_row_count": 3,
                        },
                        "attachment_content_probes": [
                            {
                                "attachment_id": "301",
                                "title": "Resolution No. 80069",
                                "source_family": "resolution",
                                "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758120.pdf",
                                "status": "ingested_excerpt",
                                "read_status": "read_text",
                                "failure_class": None,
                                "content_ingested": True,
                                "economic_row_count": 3,
                            },
                            {
                                "attachment_id": "302",
                                "title": "Memo",
                                "source_family": "memorandum",
                                "source_url": "https://sanjoseca.legistar.com/View.ashx?M=F&ID=8758121.pdf",
                                "status": "binary_pdf_unparsed",
                                "read_status": "binary_unparsed",
                                "failure_class": "binary_pdf_unparsed",
                                "content_ingested": False,
                                "economic_row_count": 0,
                            },
                        ],
                    },
                },
            },
            "artifact_readback_status": "proven",
            "fail_closed": False,
            "gate_state": "qualitative_only",
            "created_at": "2026-04-16T09:00:00Z",
            "updated_at": "2026-04-16T09:05:00Z",
        },
    ]

    client.set_auth("admin")
    response = client.get(
        f"/api/admin/pipeline/policy-evidence/packages/{package['package_id']}/analysis-status?run_id=run-q38"
    )
    assert response.status_code == 200, response.text
    data = response.json()
    moat = data["data_moat_status"]
    assert moat["status"] == "evidence_ready_with_gaps"
    assert moat["official_attachment_depth_ready"] is True
    assert moat["official_attachment_depth_clean"] is False
    assert moat["row_quality_gate_status"] == "fail"
    assert moat["row_quality_gap"] is True
    assert moat["row_quality_weak_row_count"] == 2
    assert moat["row_quality_rejected_or_ambiguous_count"] == 2
    assert moat["row_quality_locator_quality_distribution"] == {
        "chunk_locator_only": 1,
        "locator_not_available": 1,
        "table_row_chunk_locator": 1,
    }
    assert moat["attachment_parse_failure_count"] >= 1
    assert moat["economic_handoff_blocked_by_row_quality"] is True
    assert moat["economic_handoff_blocked_by"] == "row_quality"
    assert moat["decision_grade_blocked_by"] == "row_quality_gap"
    assert (
        moat["row_family_depth"]["official_attachment"]["status"]
        == "satisfied_with_row_quality_gaps"
    )
    assert data["economic_handoff_quality"]["status"] == "analysis_ready_with_gaps"
    assert data["economic_handoff_quality"]["reason_code"] == "row_quality_gap_non_decision_grade"
    assert (
        data["economic_handoff_quality"]["quantification_paths"]["direct_project_fee_exposure"]["status"]
        == "not_analysis_ready"
    )
    assert (
        data["economic_handoff_quality"]["quantification_paths"]["household_cost_of_living"]["status"]
        == "not_analysis_ready"
    )
    assert data["gates"]["economic_analysis_readiness"]["row_quality_gate_status"] == "fail"
    assert data["source_quality"]["row_quality_weak_row_count"] == 2
    assert data["recommended_next_action"] != "run_direct_analysis"
