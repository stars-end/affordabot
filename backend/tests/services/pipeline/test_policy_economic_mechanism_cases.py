from __future__ import annotations

from services.pipeline.policy_economic_mechanism_cases import (
    PolicyEconomicMechanismCaseService,
)
from services.pipeline.policy_evidence_package_storage import (
    InMemoryArtifactProbe,
    InMemoryArtifactWriter,
    InMemoryPolicyEvidencePackageStore,
    PolicyEvidencePackageStorageService,
)
from services.pipeline.policy_evidence_package_sufficiency import (
    PolicyEvidencePackageSufficiencyService,
)


def _case(bundle: dict, case_id: str) -> dict:
    for case in bundle["cases"]:
        if case["case_id"] == case_id:
            return case
    raise AssertionError(f"missing case_id={case_id}")


def test_bundle_has_direct_indirect_secondary_and_control_cases() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()

    case_ids = {case["case_id"] for case in bundle["cases"]}
    assert case_ids == {
        "direct_cost_case",
        "indirect_pass_through_case",
        "secondary_research_required_case",
        "unsupported_fail_closed_control",
    }
    assert bundle["feature_key"] == "bd-3wefe.6"


def test_direct_case_includes_graph_parameters_bounds_and_deterministic_conclusion() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    direct = _case(bundle, "direct_cost_case")

    assert direct["quantification_plausible"] is True
    assert direct["scenario_range"] is not None
    assert direct["scenario_range"]["low"] <= direct["scenario_range"]["base"] <= direct["scenario_range"]["high"]
    assert direct["parameter_table"]
    assert direct["mechanism_graph"]["nodes"]
    assert direct["mechanism_graph"]["edges"]
    assert direct["deterministic_conclusion"].startswith("[Deterministic POC]")
    assert direct["primary_package"]["economic_handoff_ready"] is True


def test_indirect_case_requires_assumption_card_and_quant_usage() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    indirect = _case(bundle, "indirect_pass_through_case")

    assert indirect["quantification_plausible"] is True
    assert indirect["assumption_cards"], "indirect case must include explicit assumption card"
    package = indirect["primary_package"]
    assert package["assumption_usage"], "indirect case must include assumption usage"
    assert package["economic_handoff_ready"] is True
    assert package["gate_projection"]["runtime_sufficiency_state"] == "quantified"


def test_secondary_case_uses_second_package_not_hidden_context() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    secondary = _case(bundle, "secondary_research_required_case")

    primary = secondary["primary_package"]
    secondary_package = secondary["secondary_package"]
    assert primary["economic_handoff_ready"] is False
    assert "blocking_gate_present" in primary["insufficiency_reasons"]
    assert secondary_package is not None
    assert secondary_package["economic_handoff_ready"] is True
    assert secondary["scenario_range"] is not None
    assert secondary["deterministic_conclusion"].startswith("[Deterministic POC]")


def test_unsupported_control_fails_closed_with_rejection_reason() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    control = _case(bundle, "unsupported_fail_closed_control")

    assert control["quantification_plausible"] is False
    assert control["scenario_range"] is None
    assert control["unsupported_claim_rejection"] is not None
    assert control["unsupported_claim_rejection"]["failure_code"] == "parameter_unverifiable"
    package = control["primary_package"]
    assert package["economic_handoff_ready"] is False
    assert package["gate_report"]["verdict"] == "fail_closed"
    assert package["gate_report"]["blocking_gate"] == "parameterization"


def test_mechanism_packages_roundtrip_through_storage_and_sufficiency() -> None:
    bundle = PolicyEconomicMechanismCaseService().build_case_bundle()
    observed: dict[tuple[str, str], tuple[str, bool]] = {}

    for case in bundle["cases"]:
        for label in ("primary_package", "secondary_package"):
            package = case.get(label)
            if package is None:
                continue
            known_uris = {f"minio://policy-evidence/packages/{package['package_id']}.json"}
            for ref in package.get("storage_refs", []):
                if ref.get("storage_system") == "minio":
                    known_uris.add(ref.get("uri") or ref.get("reference_id"))
            store = InMemoryPolicyEvidencePackageStore()
            storage = PolicyEvidencePackageStorageService(
                store=store,
                artifact_writer=InMemoryArtifactWriter(),
                artifact_probe=InMemoryArtifactProbe(known_uris=known_uris),
            )
            idempotency_key = f"test::{case['case_id']}::{label}"
            storage_result = storage.persist(package_payload=package, idempotency_key=idempotency_key)
            assert storage_result.stored is True
            record = store.get_by_idempotency(idempotency_key=idempotency_key)
            assert record is not None
            sufficiency = PolicyEvidencePackageSufficiencyService().evaluate(record=record)
            observed[(case["case_id"], label)] = (
                sufficiency.readiness_level.value,
                sufficiency.passed,
            )

    assert observed[("direct_cost_case", "primary_package")] == ("economic_handoff_ready", True)
    assert observed[("indirect_pass_through_case", "primary_package")] == ("economic_handoff_ready", True)
    assert observed[("secondary_research_required_case", "primary_package")] == ("qualitative_only", True)
    assert observed[("secondary_research_required_case", "secondary_package")] == ("economic_handoff_ready", True)
    assert observed[("unsupported_fail_closed_control", "primary_package")] == ("fail_closed", False)
