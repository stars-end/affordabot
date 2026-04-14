from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = (
    ROOT
    / "backend"
    / "scripts"
    / "verification"
    / "verify_structured_economic_handoff_poc.py"
)
spec = spec_from_file_location("verify_structured_economic_handoff_poc", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_replay_contract_has_required_gates_for_all_cases():
    config = module.VerifierConfig(
        mode="replay",
        out_json=Path("/tmp/structured-economic-handoff-report-test.json"),
        out_md=Path("/tmp/structured-economic-handoff-report-test.md"),
        self_check=False,
    )
    report = module._run(config)
    assert len(report["cases"]) >= 2
    for case in report["cases"]:
        assert list(case["gate_results"].keys()) == list(module.GATE_ORDER)
    assert module._validate_report_contract(report) == []


def test_replay_contains_quantified_pass_and_fail_closed_case():
    config = module.VerifierConfig(
        mode="replay",
        out_json=Path("/tmp/structured-economic-handoff-report-test2.json"),
        out_md=Path("/tmp/structured-economic-handoff-report-test2.md"),
        self_check=False,
    )
    report = module._run(config)
    verdicts = {case["case_id"]: case["final_verdict"] for case in report["cases"]}
    assert verdicts["case_direct_fiscal_quantified_pass"] == "quantified_pass"
    assert verdicts["case_local_control_fail_closed_insufficient"] == "fail_closed"
    blocking_gate = {
        case["case_id"]: case["blocking_gate"] for case in report["cases"]
    }
    assert blocking_gate["case_local_control_fail_closed_insufficient"] == "parameterization"
    assert report["summary"]["architecture_option_recommendation"] == "option_a"


def test_contract_validator_rejects_missing_case_structure():
    bad_report = {
        "feature_key": "x",
        "poc_version": "x",
        "mode": "replay",
        "generated_at": "x",
        "cases": [{"case_id": "only-one", "gate_results": {}}],
        "summary": {"architecture_option_recommendation": "option_z"},
        "code_path_citations": [],
        "recommended_extensions": [],
    }
    errors = module._validate_report_contract(bad_report)
    assert "cases_contract_requires_at_least_two_cases" in errors
    assert "invalid_architecture_option_recommendation" in errors
