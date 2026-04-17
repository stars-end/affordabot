from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = ROOT / "backend" / "scripts" / "verification" / "verify_windmill_sanjose_live_gate.py"

spec = spec_from_file_location("verify_windmill_sanjose_live_gate", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _result_payload_with_policy_package(*, economic_handoff_ready: bool | None) -> dict:
    package_payload = {}
    if economic_handoff_ready is not None:
        package_payload["economic_handoff_ready"] = economic_handoff_ready
    return {
        "scope_results": [
            {
                "steps": {
                    "read_fetch": {
                        "details": {
                            "selected_artifact": {
                                "url": "https://sanjoseca.gov/policy/parking-minimums-amendment",
                                "title": "Parking Minimums Amendment",
                            }
                        },
                        "refs": {
                            "reader_output_ref": "minio://policy-evidence/parking/doc-001",
                            "raw_scrape_ids": ["raw-001"],
                        },
                    },
                    "summarize_run": {
                        "details": {
                            "policy_evidence_package": {
                                "package_id": "pkg-cycle41-parking",
                                "package_payload": package_payload,
                            }
                        }
                    },
                }
            }
        ]
    }


def test_resolve_policy_inputs_uses_non_clf_parking_defaults():
    scenario, resolved = module._resolve_policy_inputs(
        scenario_name="parking_policy",
        jurisdiction=None,
        source_family=None,
        search_query=None,
        analysis_question=None,
    )
    assert scenario.name == "parking_policy"
    assert resolved["jurisdiction"] == "San Jose CA"
    assert resolved["source_family"] == "parking_policy"
    assert "parking minimums ordinance" in resolved["search_query"]


def test_resolve_policy_inputs_allows_explicit_source_override():
    scenario, resolved = module._resolve_policy_inputs(
        scenario_name="parking_policy",
        jurisdiction=None,
        source_family="meeting_actions",
        search_query=None,
        analysis_question=None,
    )
    assert scenario.name == "parking_policy"
    assert resolved["source_family"] == "meeting_actions"


def test_policy_capture_semantics_marks_useful_policy_when_not_economic_ready():
    capture = module._derive_policy_evidence_capture(
        policy_scenario=module.POLICY_SCENARIOS["parking_policy"],
        jurisdiction="San Jose CA",
        source_family="parking_policy",
        search_query="San Jose parking minimums ordinance policy action city council",
        analysis_question="Capture local parking policy evidence.",
        result_payload=_result_payload_with_policy_package(economic_handoff_ready=False),
        db_storage_probe={
            "content_artifact_rows": [{"id": "artifact-001"}],
            "pipeline_command_rows": [{"id": "cmd-001"}],
            "raw_scrape_rows": [{"id": "raw-001"}],
        },
    )

    semantics = capture["semantics"]
    assert semantics["observed_useful_local_policy_evidence"] is True
    assert semantics["observed_economic_handoff_ready"] is False
    assert semantics["classification"] == "useful_local_policy_evidence_not_economic_ready"
    assert semantics["expected_economic_readiness"] == "not_required"
    assert capture["package_identity"]["package_id"] == "pkg-cycle41-parking"


def test_main_builds_harness_inputs_from_policy_scenario(monkeypatch, tmp_path):
    captured: dict[str, str] = {}

    def _fake_run_harness(**kwargs):
        captured["source_family"] = kwargs["source_family"]
        captured["search_query"] = kwargs["search_query"]
        captured["policy_scenario"] = kwargs["policy_scenario"]
        return {
            "classification": "read_only_surface_pass",
            "full_run_readiness": "partial",
        }

    monkeypatch.setattr(module, "run_harness", _fake_run_harness)
    monkeypatch.setattr(module, "_render_markdown", lambda report: "ok\n")
    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_windmill_sanjose_live_gate.py",
            "--run-mode",
            "read-only",
            "--policy-scenario",
            "parking_policy",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
    )

    code = module.main()
    assert code == 0
    assert captured["policy_scenario"] == "parking_policy"
    assert captured["source_family"] == "parking_policy"
    assert "parking minimums ordinance" in captured["search_query"]
