from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = (
    ROOT
    / "backend"
    / "scripts"
    / "verification"
    / "verify_scrape_structured_integration_poc.py"
)
spec = spec_from_file_location("verify_scrape_structured_integration_poc", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_replay_contract_has_required_envelope_fields():
    config = module.VerifierConfig(
        mode="replay",
        out_json=Path("/tmp/scrape-structured-integration-test.json"),
        out_md=Path("/tmp/scrape-structured-integration-test.md"),
        self_check=False,
    )
    report = module._run(config)
    assert report["envelopes"]
    errors = module._validate_report(report)
    assert errors == []


def test_integration_proves_cross_lane_dedupe_and_provider_roles():
    config = module.VerifierConfig(
        mode="replay",
        out_json=Path("/tmp/scrape-structured-integration-test2.json"),
        out_md=Path("/tmp/scrape-structured-integration-test2.md"),
        self_check=False,
    )
    report = module._run(config)
    summary = report["summary"]
    assert summary["integrated_dedupe_groups_count"] >= 1
    roles = report["provider_role_recommendation"]["lane_roles"]
    role_map = {item["provider"]: item["role"] for item in roles}
    assert role_map["private_searxng"] == "primary_scrape_search_lane"
    assert role_map["tavily"] == "hot_fallback"
    assert role_map["exa"] == "bakeoff_eval_only"


def test_impact_mode_to_mechanism_mapping_covers_required_modes():
    mapping = module._impact_mode_mapping()
    map_dict = {item["impact_mode"]: item["mechanism_family"] for item in mapping}
    assert map_dict["direct_fiscal"] == "direct_fiscal"
    assert map_dict["compliance_cost"] == "compliance_cost"
    assert map_dict["pass_through_incidence"] == "fee_or_tax_pass_through"
    assert map_dict["adoption_take_up"] == "adoption_take_up"
    assert map_dict["qualitative_only"] is None
