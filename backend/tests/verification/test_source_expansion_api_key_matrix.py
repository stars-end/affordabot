from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "backend" / "scripts" / "verification" / "verify_source_expansion_api_key_matrix.py"
spec = spec_from_file_location("verify_source_expansion_api_key_matrix", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_build_report_has_required_matrix_shape():
    report = module._build_report()
    assert report["feature_key"] == module.FEATURE_KEY
    assert isinstance(report["matrix"], list)
    assert len(report["matrix"]) >= 10

    required = set(module.REQUIRED_FIELDS)
    for row in report["matrix"]:
        assert required.issubset(row.keys())

    assert module._validate(report) == []


def test_actions_include_wave1_searxng_variable():
    report = module._build_report()
    required_now = report["actions"]["required_now"]
    assert any(item["railway_variable"] == "SEARXNG_BASE_URL" for item in required_now)


def test_validate_detects_missing_required_field():
    report = module._build_report()
    bad_row = dict(report["matrix"][0])
    del bad_row["lane"]
    bad = dict(report)
    bad["matrix"] = [bad_row]
    errors = module._validate(bad)
    assert any(err.startswith("row_missing_field:0:lane") for err in errors)
