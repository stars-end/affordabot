from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "backend" / "scripts" / "verification" / "verify_structured_source_lane_poc.py"
spec = spec_from_file_location("verify_structured_source_lane_poc", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_replay_fixture_has_expected_probes():
    fixture = module._load_json(module.DEFAULT_REPLAY_FIXTURE)
    probes = fixture["probes"]
    assert set(probes.keys()) == {"leginfo", "legistar", "arcgis"}
    assert probes["legistar"]["sample_pull_without_browser"] is True


def test_replay_mode_builds_contract_valid_report():
    config = module.ProbeConfig(
        mode=module.MODE_REPLAY,
        timeout_seconds=2.0,
        replay_fixture=module.DEFAULT_REPLAY_FIXTURE,
        out_json=Path("/tmp/structured-source-lane-poc-test.json"),
        out_md=Path("/tmp/structured-source-lane-poc-test.md"),
        save_live_replay=None,
        self_check=False,
    )
    report = module._run(config)
    assert report["mode"] == module.MODE_REPLAY
    assert report["summary"]["total_sources"] == 3
    assert report["summary"]["acceptance_legistar_and_one_other"] is True
    assert report["sources"][0]["source_family"] == "ca_pubinfo_leginfo"
    assert module._validate_report_contract(report) == []


def test_self_check_exits_nonzero_on_contract_error():
    bad_report = {
        "feature_key": "x",
        "poc_version": "x",
        "mode": "replay",
        "generated_at": "x",
        "probes": {"leginfo": {}, "legistar": {}, "arcgis": {}},
        "summary": {},
    }
    errors = module._validate_report_contract(bad_report)
    assert any(err.startswith("missing_probe_key:leginfo") for err in errors)
