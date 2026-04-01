"""Contract tests for the golden-suite harness (bd-bkco.6)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.verification import run_golden_suite as suite


def _result(check_family: str, passed: bool, blocking: bool) -> suite.CommandResult:
    return suite.CommandResult(
        check_family=check_family,
        command=["python", f"{check_family}.py"],
        exit_code=0 if passed else 1,
        status="pass" if passed else "fail",
        passed=passed,
        blocking=blocking,
        stdout="",
        stderr="",
    )


def test_build_bill_summary_marks_manifest_only_as_live_capture_required() -> None:
    manifest_bills = [
        {
            "bill_id": "manifest-only-bill",
            "jurisdiction": "us",
            "mode_bucket": "direct_fiscal",
            "expected_quantifiable": True,
            "control_type": None,
        },
        {
            "bill_id": "fixture-backed-bill",
            "jurisdiction": "ca",
            "mode_bucket": "fail_closed_control",
            "expected_quantifiable": False,
            "control_type": "ceremonial_resolution",
        },
    ]
    checks_by_family = {
        "manifest_contract": _result("manifest_contract", True, True),
        "research_fixtures": _result("research_fixtures", True, True),
        "step_expectations": _result("step_expectations", True, True),
        "retrieval_quality": _result("retrieval_quality", True, True),
        "web_mode_comparison": _result("web_mode_comparison", False, False),
    }
    expectations_by_bill = {
        "manifest-only-bill": {"expectation_strength": "provisional_bootstrap"},
        "fixture-backed-bill": {"expectation_strength": "strong"},
    }

    rows = suite._build_bill_summary(
        manifest_bills=manifest_bills,
        expected_fixture_bill_ids={"fixture-backed-bill"},
        expectations_by_bill=expectations_by_bill,
        checks_by_family=checks_by_family,
        retrieval_by_bill={"fixture-backed-bill": {"status": "pass", "checks": {}}},
        comparison_by_bill={},
    )
    manifest_only = next(row for row in rows if row["bill_id"] == "manifest-only-bill")
    fixture_backed = next(row for row in rows if row["bill_id"] == "fixture-backed-bill")

    assert manifest_only["live_capture_required"] is True
    assert manifest_only["strong_replay_supported"] is False
    assert (
        manifest_only["check_families"]["research_fixtures"]
        == "not_applicable_manifest_only"
    )
    assert (
        manifest_only["check_families"]["retrieval_quality"]
        == "not_applicable_manifest_only"
    )
    assert fixture_backed["live_capture_required"] is False
    assert fixture_backed["strong_replay_supported"] is True


def test_overall_verdict_keeps_web_comparison_non_blocking_by_default() -> None:
    checks_by_family = {
        "manifest_contract": _result("manifest_contract", True, True),
        "research_fixtures": _result("research_fixtures", True, True),
        "step_expectations": _result("step_expectations", True, True),
        "retrieval_quality": _result("retrieval_quality", True, True),
        "web_mode_comparison": _result("web_mode_comparison", False, False),
    }

    verdict, blocking_failures, non_blocking_failures = suite._overall_verdict(
        checks_by_family, strict_web_comparison=False
    )
    assert verdict == "pass"
    assert blocking_failures == []
    assert non_blocking_failures == ["web_mode_comparison"]


def test_generate_report_writes_machine_readable_summary(monkeypatch, tmp_path: Path) -> None:
    checks = {
        "manifest_contract": _result("manifest_contract", True, True),
        "research_fixtures": _result("research_fixtures", True, True),
        "step_expectations": _result("step_expectations", True, True),
        "retrieval_quality": _result("retrieval_quality", True, True),
        "web_mode_comparison": _result("web_mode_comparison", False, False),
    }
    scripted_order = [
        "manifest_contract",
        "research_fixtures",
        "step_expectations",
        "retrieval_quality",
        "web_mode_comparison",
    ]
    index = {"i": 0}

    def fake_run_command(*, check_family, command, blocking, output_path=None):
        expected = scripted_order[index["i"]]
        index["i"] += 1
        assert check_family == expected
        result = checks[check_family]
        result.output_path = str(output_path) if output_path else None
        if output_path and check_family == "retrieval_quality":
            output_path.write_text(
                json.dumps(
                    {
                        "checks": {
                            "decisive_evidence": [
                                {"bill_id": "ca-acr-117-2024", "passed": True}
                            ],
                            "conclusion_sensitivity": [
                                {"bill_id": "ca-acr-117-2024", "passed": True}
                            ],
                        },
                        "summary": {"passed": True},
                    }
                ),
                encoding="utf-8",
            )
        return result

    monkeypatch.setattr(suite, "_run_command", fake_run_command)
    output_path = tmp_path / "suite.json"
    report = suite.generate_golden_suite_report(
        output_path=output_path,
        top_k=1,
        strict_web_comparison=False,
    )

    assert output_path.exists()
    assert report["schema_version"] == "1.0"
    assert report["feature_key"] == "bd-bkco.6"
    assert isinstance(report["checks"], list)
    assert report["fixture_coverage"]["live_capture_required_bill_count"] >= 1
    assert report["summary"]["overall_verdict"] == "pass"
