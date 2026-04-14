from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "backend" / "scripts" / "verification" / "verify_economic_evidence_gate_matrix.py"
spec = spec_from_file_location("verify_economic_evidence_gate_matrix", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _fixture_case(case_id: str) -> dict:
    fixture = module._load_json(module.DEFAULT_FIXTURE_PATH)
    for case in fixture["cases"]:
        if case["case_id"] == case_id:
            return case
    raise AssertionError(f"missing fixture case {case_id}")


def test_positive_quantification_case_passes_all_gates():
    case = _fixture_case("direct_fiscal_positive_city_staff_report")
    result = module._evaluate_case(case, stop_after_index=None)
    assert result["final_verdict"] == module.FINAL_VERDICT_QUANTIFIED_PASS
    assert result["blocking_gate"] == ""
    assert all(result["gate_results"][gate]["status"] == "pass" for gate in module.GATE_ORDER)
    assert result["formula_ids"] == ["direct_fiscal_bounds_v1"]


def test_local_minutes_control_fails_closed_at_parameterization():
    case = _fixture_case("local_minutes_control_fail_closed_no_numeric_basis")
    result = module._evaluate_case(case, stop_after_index=None)
    assert result["final_verdict"] == module.FINAL_VERDICT_QUAL_ONLY_FAIL_CLOSED
    assert result["blocking_gate"] == "parameterization"
    assert result["gate_results"]["search_recall"]["status"] == "pass"
    assert result["gate_results"]["evidence_cards"]["status"] == "pass"
    assert result["gate_results"]["parameterization"]["status"] == "fail"
    assert result["gate_results"]["assumption_selection"]["status"] == "skipped_due_to_blocking_gate"


def test_provider_failure_is_attributed_to_search_recall():
    case = _fixture_case("provider_failure_no_artifact_candidates")
    result = module._evaluate_case(case, stop_after_index=None)
    assert result["final_verdict"] == module.FINAL_VERDICT_QUAL_ONLY_FAIL_CLOSED
    assert result["blocking_gate"] == "search_recall"
    assert result["gate_results"]["search_recall"]["status"] == "fail"
    assert result["gate_results"]["reader_substance"]["status"] == "skipped_due_to_blocking_gate"


def test_llm_unsupported_claims_fail_after_quantification():
    case = _fixture_case("llm_explanation_failure_unsupported_claims")
    result = module._evaluate_case(case, stop_after_index=None)
    assert result["gate_results"]["quantification"]["status"] == "pass"
    assert result["gate_results"]["llm_explanation"]["status"] == "fail"
    assert result["blocking_gate"] == "llm_explanation"
    assert result["final_verdict"] == module.FINAL_VERDICT_QUAL_ONLY_LLM_BLOCKED
    assert result["unsupported_claim_count"] > 0


def test_run_strict_expected_has_no_failures():
    config = module.VerifierConfig(
        fixture_path=module.DEFAULT_FIXTURE_PATH,
        out_json=Path("/tmp/econ-gates-test.json"),
        out_md=Path("/tmp/econ-gates-test.md"),
        stop_after=None,
        provider_filter=None,
        strict_expected=True,
    )
    report = module._run(config)
    assert "expectation_failures" not in report
    assert report["summary"]["total_cases"] >= 5


def test_pass_through_fixture_is_registry_aligned():
    case = _fixture_case("pass_through_positive_declared_assumption")
    cards = case["gate_inputs"]["assumption_selection"]["cards"]
    assert len(cards) == 1
    assumption = cards[0]
    assert assumption["low"] == 0.5
    assert assumption["central"] == 0.68
    assert assumption["high"] == 0.89
    assert (
        assumption["source_url"]
        == "https://www.philadelphiafed.org/-/media/frbp/assets/consumer-finance/discussion-papers/dp24-01.pdf"
    )
    assert assumption["applicability"] == "housing,rental_market,local_tax_or_fee"
