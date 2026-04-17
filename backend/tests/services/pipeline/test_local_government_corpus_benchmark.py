from __future__ import annotations

from copy import deepcopy

from services.pipeline.local_government_corpus_benchmark import (
    LocalGovernmentCorpusBenchmarkService,
    build_local_government_corpus_matrix_seed,
)


def test_seed_matrix_has_decision_grade_scope_axes() -> None:
    matrix = build_local_government_corpus_matrix_seed()
    rows = [row for row in matrix["rows"] if row.get("row_type") == "corpus_package"]

    jurisdictions = {row["jurisdiction"]["id"] for row in rows}
    non_ca = {
        row["jurisdiction"]["id"]
        for row in rows
        if row["jurisdiction"]["state"] != "CA"
    }
    policy_families = {row["policy_family"] for row in rows}
    source_families = {
        row["selected_primary_source"]["source_family"]
        for row in rows
        if row.get("selected_primary_source")
    }
    for row in rows:
        for observation in row.get("structured_source_observations", []):
            source_families.add(observation["source_family"])

    max_jurisdiction_count = max(
        sum(1 for row in rows if row["jurisdiction"]["id"] == jurisdiction)
        for jurisdiction in jurisdictions
    )
    stored_or_qualitative_rows = [
        row
        for row in rows
        if row["classification"]["data_moat_package_classification"]
        in {"stored_not_economic", "qualitative_only"}
    ]

    assert matrix["seed_mode"] == "expanded_generator_cycle_45"
    assert matrix["corpus_readiness_target"] == "corpus_ready_with_gaps"
    assert len(matrix["expansion_backlog"]) >= 1
    assert 75 <= len(rows) <= 120
    assert len(jurisdictions) >= 6
    assert len(non_ca) >= 2
    assert len(policy_families) >= 8
    assert len(source_families) >= 5
    assert max_jurisdiction_count / len(rows) <= 0.4
    assert len(stored_or_qualitative_rows) / len(rows) >= 0.1
    assert any(row["evaluation_split"] == "tuning" for row in rows)
    assert any(row["evaluation_split"] == "blind_evaluation" for row in rows)
    assert all(row.get("known_policy_reference_id") for row in rows)


def test_seed_scorecard_encodes_c0_to_c14_without_false_pass() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    scorecard = service.evaluate(matrix=matrix)

    gate_ids = set(scorecard["gates"].keys())
    assert {
        "C0",
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
        "C6",
        "C7",
        "C8",
        "C9",
        "C9a",
        "C10",
        "C11",
        "C12",
        "C13",
        "C14",
    }.issubset(gate_ids)
    assert scorecard["gates"]["C0"]["status"] == "pass"
    assert scorecard["gates"]["C1"]["status"] == "pass"
    assert scorecard["gates"]["C2"]["status"] == "pass"
    assert scorecard["gates"]["C13"]["status"] == "not_proven"
    assert (
        "windmill_refs_seeded_not_live_proven"
        in scorecard["gates"]["C13"]["blockers"]
    )
    assert scorecard["gates"]["C14"]["status"] == "pass"
    assert scorecard["corpus_state"] == "corpus_ready_with_gaps"


def test_live_proven_windmill_refs_satisfy_c13() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    rows = [row for row in matrix["rows"] if row.get("row_type") == "corpus_package"]

    for row in rows:
        infra = row.get("infrastructure_status")
        if not isinstance(infra, dict):
            continue
        refs = infra.get("windmill_refs")
        if not isinstance(refs, dict):
            continue
        refs["run_id"] = f"live-run::{row['corpus_row_id']}"
        refs["job_id"] = f"live-job::{row['corpus_row_id']}"
        refs["proof_status"] = "live_proven"
        refs["proof_source"] = "windmill_cli_live"

    scorecard = service.evaluate(matrix=matrix)
    assert scorecard["gates"]["C13"]["status"] == "pass"


def test_seeded_windmill_refs_fail_c13_for_decision_grade_target() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    matrix["corpus_readiness_target"] = "decision_grade_corpus"

    scorecard = service.evaluate(matrix=matrix)
    assert scorecard["gates"]["C13"]["status"] == "not_proven"
    assert (
        "windmill_refs_seeded_not_live_proven"
        in scorecard["gates"]["C13"]["blockers"]
    )


def test_c13_artifact_overlay_blocked_row_stays_not_proven() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    baseline = service.evaluate(matrix=matrix)
    rows = [row for row in matrix["rows"] if row.get("row_type") == "corpus_package"]
    blocked_target = next(
        row
        for row in rows
        if (row.get("infrastructure_status") or {}).get("orchestration_mode")
        == "cli_only"
    )
    blocked_row_id = blocked_target["corpus_row_id"]

    artifact = {
        "rows": [
            {
                "corpus_row_id": blocked_row_id,
                "row_status": "blocked",
                "orchestration_mode": "blocked",
                "blocker_class": "windmill_refs_incomplete",
                "windmill_run_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                "windmill_job_id": None,
            }
        ]
    }
    scorecard = service.evaluate(
        matrix=matrix,
        windmill_orchestration_artifact=artifact,
    )

    assert scorecard["gates"]["C13"]["status"] == "not_proven"
    assert (
        scorecard["gates"]["C13"]["metrics"]["mode_counts"]["cli_only"]
        == baseline["gates"]["C13"]["metrics"]["mode_counts"]["cli_only"]
    )
    assert (
        "windmill_refs_seeded_not_live_proven"
        in scorecard["gates"]["C13"]["blockers"]
    )


def test_c13_artifact_overlay_proven_row_upgrades_single_row() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    baseline = service.evaluate(matrix=matrix)
    rows = [row for row in matrix["rows"] if row.get("row_type") == "corpus_package"]
    proven_target = next(
        row
        for row in rows
        if (row.get("infrastructure_status") or {}).get("orchestration_mode")
        in {"windmill_live", "mixed"}
    )
    proven_row_id = proven_target["corpus_row_id"]

    artifact = {
        "rows": [
            {
                "corpus_row_id": proven_row_id,
                "row_status": "proven",
                "orchestration_mode": "windmill_live",
                "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                "windmill_run_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
                "windmill_job_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
            }
        ]
    }
    scorecard = service.evaluate(
        matrix=matrix,
        windmill_orchestration_artifact=artifact,
    )

    assert scorecard["gates"]["C13"]["status"] == "not_proven"
    assert (
        scorecard["gates"]["C13"]["metrics"]["seeded_not_live_proven_rows"]
        == baseline["gates"]["C13"]["metrics"]["seeded_not_live_proven_rows"] - 1
    )
    assert (
        "windmill_refs_seeded_not_live_proven"
        in scorecard["gates"]["C13"]["blockers"]
    )


def test_c13_artifact_overlay_can_satisfy_c13_with_live_proven_refs() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    rows = [row for row in matrix["rows"] if row.get("row_type") == "corpus_package"]
    artifact_rows = []
    for row in rows:
        mode = (row.get("infrastructure_status") or {}).get("orchestration_mode")
        if mode not in {"windmill_live", "mixed"}:
            continue
        row_id = str(row["corpus_row_id"])
        artifact_rows.append(
            {
                "corpus_row_id": row_id,
                "row_status": "proven",
                "orchestration_mode": mode,
                "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
                "windmill_run_id": f"live-run-{row_id}",
                "windmill_job_id": f"live-job-{row_id}",
            }
        )
    artifact = {"rows": artifact_rows}

    scorecard = service.evaluate(
        matrix=matrix,
        windmill_orchestration_artifact=artifact,
    )
    assert scorecard["gates"]["C13"]["status"] == "pass"


def test_decision_grade_c13_requires_proof_for_all_live_and_mixed_rows() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    matrix["corpus_readiness_target"] = "decision_grade_corpus"
    rows = [row for row in matrix["rows"] if row.get("row_type") == "corpus_package"]
    single_live_row = next(
        row
        for row in rows
        if (row.get("infrastructure_status") or {}).get("orchestration_mode")
        in {"windmill_live", "mixed"}
    )
    row_overlay = {
        str(single_live_row["corpus_row_id"]): {
            "orchestration_mode": "windmill_live",
            "flow_id": "f/affordabot/pipeline_daily_refresh_domain_boundary__flow",
            "run_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
            "job_id": "01J9KJ5FK0XQ7CG1WM89AZ6RY4",
            "proof_status": "live_proven",
            "proof_source": "windmill_row_overlay",
        }
    }

    scorecard = service.evaluate(
        matrix=matrix,
        windmill_row_proof_overlay=row_overlay,
    )
    assert scorecard["gates"]["C13"]["status"] == "not_proven"
    assert (
        "windmill_refs_seeded_not_live_proven"
        in scorecard["gates"]["C13"]["blockers"]
    )


def test_san_jose_only_matrix_fails_c0() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    matrix["rows"] = [
        row
        for row in matrix["rows"]
        if row.get("row_type") == "corpus_package"
        and row.get("jurisdiction", {}).get("id") == "san_jose_ca"
    ]
    scorecard = service.evaluate(matrix=matrix)
    assert scorecard["gates"]["C0"]["status"] == "fail"
    assert "san_jose_only" in scorecard["gates"]["C0"]["blockers"]


def test_insufficient_package_count_without_backlog_fails_c0() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    mutated = deepcopy(matrix)
    package_rows = [
        row for row in mutated["rows"] if row.get("row_type") == "corpus_package"
    ]
    mutated["rows"] = package_rows[:74]
    mutated["expansion_backlog"] = []
    mutated["corpus_readiness_target"] = "decision_grade_corpus"

    scorecard = service.evaluate(matrix=mutated)
    assert scorecard["gates"]["C0"]["status"] == "fail"
    assert "package_count_below_75" in scorecard["gates"]["C0"]["blockers"]


def test_external_primary_over_cap_fails_c1() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    mutated = deepcopy(matrix)
    rows = [row for row in mutated["rows"] if row.get("row_type") == "corpus_package"]
    for row in rows[:4]:
        row["selected_primary_source"]["source_officialness"] = "external_advocacy"
        row["selected_primary_source"]["primary_evidence_allowed"] = True
        row["classification"]["data_moat_package_classification"] = (
            "economic_handoff_candidate"
        )
        row["provider_usage"]["tavily_primary_selected"] = True
    scorecard = service.evaluate(matrix=mutated)

    assert scorecard["gates"]["C1"]["status"] == "fail"
    assert (
        "tavily_exa_primary_selected_in_audited_sample"
        in scorecard["gates"]["C1"]["blockers"]
    )


def test_tavily_exa_primary_over_5_percent_corpus_cap_fails_c1() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    mutated = deepcopy(matrix)
    rows = [row for row in mutated["rows"] if row.get("row_type") == "corpus_package"]
    for row in rows[:6]:
        row["provider_usage"]["tavily_primary_selected"] = True
        row["provider_usage"]["exa_primary_selected"] = False
        row["manual_audit"]["sampled"] = False

    scorecard = service.evaluate(matrix=mutated)
    assert scorecard["gates"]["C1"]["status"] == "fail"
    assert "tavily_exa_primary_over_5_percent_corpus_cap" in scorecard["gates"]["C1"]["blockers"]


def test_shallow_legistar_only_structured_fails_c2() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    mutated = deepcopy(matrix)
    for row in mutated["rows"]:
        if row.get("row_type") != "corpus_package":
            continue
        row["structured_source_observations"] = [
            {
                "source_family": "agenda_meeting_api",
                "true_structured": True,
                "depth": "meeting_metadata",
                "live_proven": True,
            }
        ]
        row["structured_cell_status"] = "covered"
    scorecard = service.evaluate(matrix=mutated)

    assert scorecard["gates"]["C2"]["status"] == "fail"
    assert "shallow_legistar_only_structured_depth" in scorecard["gates"]["C2"]["blockers"]


def test_missing_c3_d11_mapping_fails_c3() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    mutated = deepcopy(matrix)
    first = next(
        row for row in mutated["rows"] if row.get("row_type") == "corpus_package"
    )
    first["classification"]["data_moat_package_classification"] = (
        "economic_analysis_ready"
    )
    first["classification"]["d11_handoff_quality"] = "not_analysis_ready"
    first["classification"]["d11_reason"] = "incompatible for analysis-ready class"

    scorecard = service.evaluate(matrix=mutated)
    assert scorecard["gates"]["C3"]["status"] == "fail"
    assert "c3_d11_mapping_mismatch" in scorecard["gates"]["C3"]["blockers"]


def test_missing_taxonomy_schema_product_surface_fails_relevant_gates() -> None:
    service = LocalGovernmentCorpusBenchmarkService()
    matrix = build_local_government_corpus_matrix_seed()
    mutated = deepcopy(matrix)
    mutated.pop("taxonomy_version", None)
    mutated.pop("schema_contract", None)
    mutated.pop("product_surface", None)

    scorecard = service.evaluate(matrix=mutated)
    assert scorecard["gates"]["C6"]["status"] == "fail"
    assert scorecard["gates"]["C9a"]["status"] == "fail"
    assert scorecard["gates"]["C11"]["status"] == "fail"
