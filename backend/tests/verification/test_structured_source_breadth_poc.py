from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "backend" / "scripts" / "verification" / "verify_structured_source_breadth_poc.py"
spec = spec_from_file_location("verify_structured_source_breadth_poc", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_replay_mode_outputs_required_candidate_fields():
    config = module.AuditConfig(
        mode=module.MODE_REPLAY,
        timeout_seconds=2.0,
        out_json=Path("/tmp/structured-source-breadth-audit-test.json"),
        out_md=Path("/tmp/structured-source-breadth-audit-test.md"),
        self_check=False,
    )
    report = module._run(config)
    assert report["mode"] == module.MODE_REPLAY
    assert len(report["candidates"]) >= 8

    required = {
        "source_family",
        "jurisdiction_scope",
        "signup_or_key_link",
        "free_status",
        "api_or_raw_confirmed",
        "sample_endpoint_or_file_url",
        "auth_required",
        "recommendation",
        "policy_mechanism_relevance",
        "live_probe_status",
        "evidence_summary",
        "downstream_economic_usefulness",
    }
    for candidate in report["candidates"]:
        assert required.issubset(candidate.keys())
    assert module._validate(report) == []


def test_replay_summary_contains_wave1_candidates():
    report = {
        "feature_key": "x",
        "artifact_version": "x",
        "mode": "replay",
        "generated_at": "x",
        "candidates": module.REPLAY_CANDIDATES,
        "summary": module._summary(module.REPLAY_CANDIDATES),
    }
    wave1 = report["summary"]["wave1_structured_feeds"]
    assert "legistar_sanjose" in wave1
    assert "ca_pubinfo_leginfo" in wave1


def test_validate_detects_missing_candidate_key():
    bad = {
        "feature_key": "x",
        "artifact_version": "x",
        "mode": "replay",
        "generated_at": "x",
        "candidates": [{"source_family": "only_one_key"}],
        "summary": {},
    }
    errors = module._validate(bad)
    assert any(err.startswith("candidate_missing_key:0:jurisdiction_scope") for err in errors)
