from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "backend" / "scripts" / "verification" / "verify_live_reader_economic_source_probe.py"
spec = spec_from_file_location("verify_live_reader_economic_source_probe", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _fixture_case(case_id: str) -> dict:
    fixture = module._load_json(module.DEFAULT_REPLAY_FIXTURE)
    for case in fixture["cases"]:
        if case["case_id"] == case_id:
            return case
    raise AssertionError(f"missing replay case {case_id}")


def _classify_from_case(case_id: str) -> dict:
    case = _fixture_case(case_id)
    return module.classify_case(
        case_id=case["case_id"],
        label=case["label"],
        source_family=case["source_family"],
        url=case["url"],
        reader_payload=case["reader_payload"],
        fetch_error=case.get("fetch_error", ""),
    )


def test_legistar_case_is_qualitative_only_due_to_missing_numeric_parameters():
    result = _classify_from_case("sanjose_legistar_cost_of_residential_development")
    assert result["reader_success"] is True
    assert result["economics_topic_signal"] is True
    assert result["numeric_parameter_signal"] is False
    assert result["decision_grade_candidate"] is False
    assert result["blocking_gate"] == "parameterization_sufficiency"


def test_records_pdf_navigation_case_fails_reader_source_quality():
    result = _classify_from_case("sanjose_records_contract_pdf_con667337_002")
    assert result["reader_success"] is True
    assert result["likely_portal_or_navigation"] is True
    assert result["decision_grade_candidate"] is False
    assert result["blocking_gate"] == "reader_source_quality"


def test_portal_listing_case_fails_reader_source_quality():
    result = _classify_from_case("sanjose_housing_council_memos_portal")
    assert result["likely_portal_or_navigation"] is True
    assert result["decision_grade_candidate"] is False
    assert result["blocking_gate"] == "reader_source_quality"


def test_replay_mode_runs_and_produces_three_cases():
    config = module.ProbeConfig(
        mode=module.MODE_REPLAY,
        replay_fixture=module.DEFAULT_REPLAY_FIXTURE,
        out_json=Path("/tmp/live-reader-probe-test.json"),
        out_md=Path("/tmp/live-reader-probe-test.md"),
        save_live_replay=None,
    )
    report = module.asyncio.run(module._run(config))
    assert report["mode"] == module.MODE_REPLAY
    assert report["summary"]["total_cases"] == 3
    assert report["summary"]["decision_grade_candidate_cases"] == 0


def test_parser_default_does_not_write_live_replay_fixture():
    parser = module._build_parser()
    args = parser.parse_args([])
    assert args.save_live_replay is None


def test_levine_act_500_boilerplate_is_not_numeric_parameter_signal():
    payload = {
        "reader_result": {
            "content": (
                "Cost of residential development policy memo for housing fee framework. "
                "Levine Act notice: no officer shall participate if campaign contributions exceed $500. "
                "The memo states analysis is qualitative and does not provide quantitative scenario estimates."
            )
        }
    }
    result = module.classify_case(
        case_id="levine_boilerplate_case",
        label="Levine boilerplate case",
        source_family="official_meeting_detail",
        url="https://sanjose.legistar.com/MeetingDetail.aspx?ID=1",
        reader_payload=payload,
        fetch_error="",
    )
    assert result["reader_success"] is True
    assert result["economics_topic_signal"] is True
    assert result["numeric_parameter_signal"] is False
    assert result["decision_grade_candidate"] is False
    assert result["blocking_gate"] == "parameterization_sufficiency"


def test_real_economic_amount_with_context_still_counts_as_parameter_signal():
    payload = {
        "reader_result": {
            "content": (
                "Budget memo recommends appropriating $2.5 million from the housing fund. "
                "Estimated annual cost is $400,000 and projected revenue impact is 3.2%."
            )
        }
    }
    result = module.classify_case(
        case_id="economic_amount_case",
        label="Economic amount case",
        source_family="official_memo",
        url="https://example.org/memo",
        reader_payload=payload,
        fetch_error="",
    )
    assert result["numeric_parameter_signal"] is True
