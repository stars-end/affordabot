from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "backend" / "scripts" / "verification" / "verify_economic_readiness_overlay.py"
spec = spec_from_file_location("verify_economic_readiness_overlay", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_overlay_report_fails_closed_for_current_live_sanjose_artifact():
    config = module.VerifierConfig(
        live_report_path=module.DEFAULT_LIVE_REPORT,
        bakeoff_report_path=module.DEFAULT_BAKEOFF_REPORT,
        gate_fixture_path=module.DEFAULT_MATRIX_FIXTURE,
        out_json=Path("/tmp/economic-readiness-overlay-test.json"),
        out_md=Path("/tmp/economic-readiness-overlay-test.md"),
    )
    report = module._run(config)

    assert report["decision_grade_for_numeric_economic_analysis"] is False
    assert report["final_verdict"] == module.FINAL_VERDICT_QUAL_ONLY_FAIL_CLOSED
    assert report["blocking_gate"] == "economic_evidence_card_sufficiency"
    assert report["gate_results"]["search_provider_source_quality"]["passed"] is True
    assert report["gate_results"]["reader_substrate_quality"]["passed"] is True
    assert report["gate_results"]["economic_evidence_card_sufficiency"]["passed"] is False
    assert report["inputs"]["live_report_path"] == (
        "docs/poc/windmill-domain-boundary-integration/artifacts/sanjose_live_gate_report.json"
    )


def test_overlay_report_gate_order_is_stable():
    assert module.GATE_ORDER == (
        "search_provider_source_quality",
        "reader_substrate_quality",
        "economic_evidence_card_sufficiency",
        "parameterization_sufficiency",
        "assumption_sufficiency",
        "deterministic_quantification_readiness",
        "llm_explanation_support",
    )
