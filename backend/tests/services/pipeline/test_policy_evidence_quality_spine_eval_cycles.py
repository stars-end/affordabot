from __future__ import annotations

from pathlib import Path

from scripts.verification.verify_policy_evidence_quality_spine_eval_cycles import (
    build_eval_cycles_report,
)


def _scorecard_fixture() -> dict:
    return {
        "matrix_attempt": {
            "attempt_id": "bd-3wefe.17-cycle-1",
            "retry_round": 1,
            "targeted_tweak": "gate_controller_contract_v2",
        },
        "vertical_package": {
            "package_id": "pkg-sj-parking-minimum-amendment",
        },
        "taxonomy": {
            "scraped/search": {"status": "pass", "details": "ok"},
            "reader": {"status": "pass", "details": "ok"},
            "structured-source": {"status": "pass", "details": "ok"},
            "sufficiency gate": {"status": "pass", "details": "ready"},
            "economic reasoning": {"status": "pass", "details": "ready"},
            "LLM narrative": {"status": "not_proven", "details": "canonical run id missing"},
        },
    }


def _cycle_fixture() -> dict:
    return {
        "manual_run": {
            "windmill_job_id": "019d94d2-81ef-1117-0353-4c40719876ed",
            "final_status": "succeeded",
        },
        "result_payload": {
            "scope_results": [
                {
                    "backend_response": {
                        "refs": {
                            "run_id": "6695fe26-eaaf-47d1-9100-7eb861a7aa2f",
                        }
                    },
                    "scope_item": {
                        "source_family": "meeting_minutes",
                    },
                    "steps": {
                        "read_fetch": {
                            "details": {
                                "candidate_audit": [
                                    {
                                        "outcome": "materialized_raw_scrape",
                                        "url": "https://sanjose.legistar.com/View.ashx?M=A&ID=1345653",
                                    }
                                ]
                            },
                            "refs": {
                                "artifact_refs": [
                                    "artifacts/live/reader_output.md",
                                ]
                            },
                        },
                        "summarize_run": {
                            "refs": {
                                "package_id": "pkg-live-1",
                                "package_artifact_uri": "minio://affordabot-artifacts/policy-evidence/packages/pkg-live-1.json",
                            },
                            "details": {
                                "policy_evidence_package": {
                                    "storage_result": {
                                        "artifact_write_status": "succeeded",
                                        "artifact_readback_status": "proven",
                                        "pgvector_truth_role": "derived_index",
                                    },
                                    "package_payload": {
                                        "run_context": {
                                            "mechanism_family_hint": "fee_or_tax_pass_through",
                                            "impact_mode_hint": "pass_through_incidence",
                                            "secondary_research_needed": True,
                                        }
                                    },
                                }
                            },
                        },
                    },
                }
            ]
        },
    }


def _storage_probe_fixture() -> dict:
    return {
        "gates": {
            "postgres_package_row": {
                "status": "pass",
                "details": "package_row_linked_to_backend_run_id",
            },
            "minio_object_readback": {
                "status": "pass",
                "details": "all_artifact_refs_read_back",
            },
            "pgvector_derivation": {
                "status": "pass",
                "details": "document_chunks_and_embeddings_present_with_derived_index_truth_role",
                "total_chunks": 42,
                "with_embedding": 42,
            },
        }
    }


def _economic_status_fixture() -> dict:
    return {
        "endpoint_ok": True,
        "analysis_status": "secondary_research_needed",
        "decision_grade_verdict": "not_decision_grade",
        "canonical_pipeline_run_id": "run-llm-1",
        "canonical_pipeline_step_id": "step-llm-1",
    }


def test_eval_cycle_report_supports_v2_gate_contract_and_thirty_cycles() -> None:
    report = build_eval_cycles_report(
        scorecard=_scorecard_fixture(),
        retry_ledger=None,
        live_storage_probe=_storage_probe_fixture(),
        live_cycle=_cycle_fixture(),
        economic_status=_economic_status_fixture(),
        max_cycles=30,
        deploy_sha="6d3e711af5da02b1ae96f0d11bcb22090daee111",
    )

    assert report["gate_contract_version"] == "v2"
    assert report["max_cycles"] == 30
    assert len(report["cycle_ledger"]) == 30
    assert set(report["gates"].keys()) == {
        "D1",
        "D2",
        "D3",
        "D4",
        "D5",
        "D6",
        "E1",
        "E2",
        "E3",
        "E4",
        "E5",
        "E6",
        "M1",
        "M2",
        "M3",
    }


def test_completion_guard_blocks_documentation_only_cycle() -> None:
    report = build_eval_cycles_report(
        scorecard=_scorecard_fixture(),
        retry_ledger=None,
        live_storage_probe=None,
        live_cycle=None,
        cycle_metadata={
            1: {
                "cycle_number": 1,
                "targeted_tweak": "notes_only",
                "inputs": {"jurisdiction": "San Jose CA"},
                "commands_executed": [],
                "code_config_tweaks": [],
                "artifacts": ["docs/poc/policy-evidence-quality-spine/cycle_notes_only.md"],
            }
        },
        economic_status=None,
        max_cycles=3,
        deploy_sha=None,
    )

    cycle_1 = report["cycle_ledger"][0]
    assert cycle_1["status"] == "guard_blocked"
    assert cycle_1["verdict"] in {"partial", "fail"}


def test_completion_guard_allows_cycle_with_fix_attempt() -> None:
    report = build_eval_cycles_report(
        scorecard=_scorecard_fixture(),
        retry_ledger=None,
        live_storage_probe=None,
        live_cycle=None,
        cycle_metadata={
            1: {
                "cycle_number": 1,
                "targeted_tweak": "attempted_fix",
                "inputs": {"jurisdiction": "San Jose CA"},
                "commands_executed": ["poetry run python scripts/verification/verify_policy_evidence_quality_spine_eval_cycles.py --max-cycles 30"],
                "code_config_tweaks": ["add_d1_to_d6_gate_contract"],
                "artifacts": ["docs/poc/policy-evidence-quality-spine/cycle_attempted_fix.md"],
            }
        },
        economic_status=None,
        max_cycles=3,
        deploy_sha=None,
    )

    cycle_1 = report["cycle_ledger"][0]
    assert cycle_1["status"] == "completed"
    assert cycle_1["stop_continue_decision"].startswith("continue_")


def test_manual_audit_gate_paths_flip_m_gates_to_pass(tmp_path: Path) -> None:
    data_path = tmp_path / "manual_data_audit.md"
    econ_path = tmp_path / "manual_economic_audit.md"
    decision_path = tmp_path / "manual_gate_decision.md"
    data_path.write_text("# data", encoding="utf-8")
    econ_path.write_text("# economics", encoding="utf-8")
    decision_path.write_text("# decision", encoding="utf-8")

    report = build_eval_cycles_report(
        scorecard=_scorecard_fixture(),
        retry_ledger=None,
        live_storage_probe=_storage_probe_fixture(),
        live_cycle=_cycle_fixture(),
        economic_status=_economic_status_fixture(),
        max_cycles=2,
        deploy_sha=None,
        manual_data_audit_path=data_path,
        manual_economic_audit_path=econ_path,
        manual_gate_decision_path=decision_path,
    )

    assert report["gates"]["M1"]["status"] == "pass"
    assert report["gates"]["M2"]["status"] == "pass"
    assert report["gates"]["M3"]["status"] == "pass"
