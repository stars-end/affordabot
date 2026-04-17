from __future__ import annotations

from copy import deepcopy

from services.pipeline.local_government_corpus_benchmark import (
    LocalGovernmentCorpusBenchmarkService,
    build_local_government_corpus_matrix_seed,
)


def test_seed_matrix_has_required_scope_axes_and_expansion_backlog() -> None:
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

    assert matrix["seed_mode"] == "seed_with_expansion_backlog"
    assert matrix["corpus_readiness_target"] == "corpus_ready_with_gaps"
    assert len(matrix["expansion_backlog"]) >= 1
    assert len(jurisdictions) >= 6
    assert len(non_ca) >= 2
    assert len(policy_families) >= 8
    assert len(source_families) >= 5
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
    assert scorecard["gates"]["C0"]["status"] == "not_proven"
    assert scorecard["corpus_state"] == "corpus_ready_with_gaps"


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
                "true_structured": False,
                "depth": "metadata",
                "live_proven": True,
            }
        ]
        row["structured_cell_status"] = "covered"
    scorecard = service.evaluate(matrix=mutated)

    assert scorecard["gates"]["C2"]["status"] == "fail"
    assert (
        "true_structured_family_count_below_2" in scorecard["gates"]["C2"]["blockers"]
    )


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
