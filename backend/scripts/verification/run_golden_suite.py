#!/usr/bin/env python3
"""Run the golden verification suite and emit a machine-readable summary report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
FIXTURES_DIR = SCRIPT_DIR / "fixtures"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_records(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    return [item for item in payload.get("bills", []) if isinstance(item, dict)]


def _expectation_records(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    return [item for item in payload.get("bills", []) if isinstance(item, dict)]


@dataclass
class CommandResult:
    check_family: str
    command: List[str]
    exit_code: int
    status: str
    passed: bool
    blocking: bool
    stdout: str
    stderr: str
    output_path: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


def _run_command(
    *,
    check_family: str,
    command: Sequence[str],
    blocking: bool,
    output_path: Optional[Path] = None,
) -> CommandResult:
    proc = subprocess.run(
        list(command),
        cwd=str(BACKEND_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    passed = proc.returncode == 0
    status = "pass" if passed else "fail"
    return CommandResult(
        check_family=check_family,
        command=list(command),
        exit_code=proc.returncode,
        status=status,
        passed=passed,
        blocking=blocking,
        stdout=proc.stdout,
        stderr=proc.stderr,
        output_path=str(output_path) if output_path else None,
    )


def _parse_retrieval_outcome(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    outcome: Dict[str, Dict[str, Any]] = {}
    checks = payload.get("checks", {})
    decisive = checks.get("decisive_evidence", [])
    sensitivity = checks.get("conclusion_sensitivity", [])
    by_bill: Dict[str, Dict[str, Any]] = {}
    for row in decisive:
        if isinstance(row, dict) and isinstance(row.get("bill_id"), str):
            by_bill.setdefault(row["bill_id"], {})["decisive_evidence"] = bool(
                row.get("passed")
            )
    for row in sensitivity:
        if isinstance(row, dict) and isinstance(row.get("bill_id"), str):
            by_bill.setdefault(row["bill_id"], {})["conclusion_sensitivity"] = bool(
                row.get("passed")
            )
    for bill_id, checks_by_bill in by_bill.items():
        passed = all(checks_by_bill.values()) if checks_by_bill else False
        outcome[bill_id] = {
            "status": "pass" if passed else "fail",
            "checks": checks_by_bill,
        }
    return outcome


def _parse_comparison_outcome(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    outcome: Dict[str, Dict[str, Any]] = {}
    comparisons = payload.get("comparisons", [])
    for row in comparisons:
        if not isinstance(row, dict) or not isinstance(row.get("bill_id"), str):
            continue
        bill_id = row["bill_id"]
        outcome[bill_id] = {
            "status": "compared",
            "overall_verdict": row.get("overall_verdict"),
            "dimension_verdicts": row.get("dimension_verdicts", {}),
        }
    return outcome


def _build_bill_summary(
    *,
    manifest_bills: List[Dict[str, Any]],
    expected_fixture_bill_ids: Set[str],
    expectations_by_bill: Dict[str, Dict[str, Any]],
    checks_by_family: Dict[str, CommandResult],
    retrieval_by_bill: Dict[str, Dict[str, Any]],
    comparison_by_bill: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    bill_rows: List[Dict[str, Any]] = []
    for record in manifest_bills:
        bill_id = str(record.get("bill_id"))
        has_fixture = bill_id in expected_fixture_bill_ids
        expectation = expectations_by_bill.get(bill_id, {})
        expectation_strength = str(expectation.get("expectation_strength", "unknown"))
        live_capture_required = (not has_fixture) and (
            expectation_strength == "provisional_bootstrap"
        )
        strong_replay_supported = has_fixture and expectation_strength == "strong"

        fixture_family_status = (
            "not_applicable_manifest_only"
            if not has_fixture
            else ("pass" if checks_by_family["research_fixtures"].passed else "fail")
        )
        retrieval_family_status = (
            "not_applicable_manifest_only"
            if not has_fixture
            else retrieval_by_bill.get(bill_id, {}).get("status", "unknown")
        )
        comparison_payload = comparison_by_bill.get(bill_id)
        comparison_family_status = (
            "not_run_or_not_available"
            if comparison_payload is None
            else comparison_payload.get("status", "unknown")
        )

        bill_rows.append(
            {
                "bill_id": bill_id,
                "jurisdiction": record.get("jurisdiction"),
                "mode_bucket": record.get("mode_bucket"),
                "expected_quantifiable": record.get("expected_quantifiable"),
                "control_type": record.get("control_type"),
                "fixture_status": (
                    "checked_in_fixture" if has_fixture else "manifest_only_no_checked_in_fixture"
                ),
                "expectation_strength": expectation_strength,
                "live_capture_required": live_capture_required,
                "strong_replay_supported": strong_replay_supported,
                "check_families": {
                    "manifest_contract": (
                        "pass" if checks_by_family["manifest_contract"].passed else "fail"
                    ),
                    "research_fixtures": fixture_family_status,
                    "step_expectations": (
                        "pass" if checks_by_family["step_expectations"].passed else "fail"
                    ),
                    "retrieval_quality": retrieval_family_status,
                    "web_mode_comparison": comparison_family_status,
                },
                "comparison": comparison_payload,
            }
        )
    return bill_rows


def _overall_verdict(
    checks_by_family: Dict[str, CommandResult], *, strict_web_comparison: bool
) -> Tuple[str, List[str], List[str]]:
    blocking_failures = [
        family
        for family, result in checks_by_family.items()
        if result.blocking and not result.passed
    ]
    non_blocking_failures = [
        family
        for family, result in checks_by_family.items()
        if (not result.blocking) and (not result.passed)
    ]
    if strict_web_comparison and not checks_by_family["web_mode_comparison"].passed:
        blocking_failures.append("web_mode_comparison")
        non_blocking_failures = [
            family for family in non_blocking_failures if family != "web_mode_comparison"
        ]
    verdict = "pass" if not blocking_failures else "fail"
    return verdict, blocking_failures, non_blocking_failures


def generate_golden_suite_report(
    *,
    output_path: Path,
    top_k: int,
    strict_web_comparison: bool,
) -> Dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_path = FIXTURES_DIR / "golden_bill_corpus_manifest.json"
    fixture_metadata_path = FIXTURES_DIR / "research_fixture_set_metadata.json"
    step_expectations_path = FIXTURES_DIR / "golden_bill_step_expectations.json"

    retrieval_output_path = output_path.parent / f"{output_path.stem}.retrieval_quality.json"
    web_comparison_output_path = output_path.parent / f"{output_path.stem}.web_comparison.json"

    checks: List[CommandResult] = [
        _run_command(
            check_family="manifest_contract",
            command=[sys.executable, str(SCRIPT_DIR / "validate_golden_bill_corpus_manifest.py")],
            blocking=True,
        ),
        _run_command(
            check_family="research_fixtures",
            command=[sys.executable, str(SCRIPT_DIR / "validate_research_fixtures.py")],
            blocking=True,
        ),
        _run_command(
            check_family="step_expectations",
            command=[
                sys.executable,
                str(SCRIPT_DIR / "validate_golden_bill_step_expectations.py"),
            ],
            blocking=True,
        ),
        _run_command(
            check_family="retrieval_quality",
            command=[
                sys.executable,
                "-m",
                "scripts.verification.verify_retrieval_quality",
                "--top-k",
                str(top_k),
                "--json-output",
                str(retrieval_output_path),
            ],
            blocking=True,
            output_path=retrieval_output_path,
        ),
        _run_command(
            check_family="web_mode_comparison",
            command=[
                sys.executable,
                str(SCRIPT_DIR / "compare_web_research_modes.py"),
                "--output",
                str(web_comparison_output_path),
            ],
            blocking=False,
            output_path=web_comparison_output_path,
        ),
    ]
    checks_by_family = {check.check_family: check for check in checks}

    retrieval_payload: Dict[str, Any] = {}
    if retrieval_output_path.exists():
        retrieval_payload = _load_json(retrieval_output_path)
        checks_by_family["retrieval_quality"].details = retrieval_payload.get("summary", {})

    web_comparison_payload: Dict[str, Any] = {}
    if web_comparison_output_path.exists():
        web_comparison_payload = _load_json(web_comparison_output_path)
        checks_by_family["web_mode_comparison"].details = web_comparison_payload.get(
            "summary", {}
        )

    manifest_bills = _manifest_records(manifest_path)
    fixture_metadata = _load_json(fixture_metadata_path)
    expected_fixture_bill_ids = set(fixture_metadata.get("expected_fixture_bill_ids", []))
    expectations = _expectation_records(step_expectations_path)
    expectations_by_bill = {
        row["bill_id"]: row for row in expectations if isinstance(row.get("bill_id"), str)
    }
    retrieval_by_bill = _parse_retrieval_outcome(retrieval_payload) if retrieval_payload else {}
    comparison_by_bill = (
        _parse_comparison_outcome(web_comparison_payload) if web_comparison_payload else {}
    )

    bills = _build_bill_summary(
        manifest_bills=manifest_bills,
        expected_fixture_bill_ids=expected_fixture_bill_ids,
        expectations_by_bill=expectations_by_bill,
        checks_by_family=checks_by_family,
        retrieval_by_bill=retrieval_by_bill,
        comparison_by_bill=comparison_by_bill,
    )
    verdict, blocking_failures, non_blocking_failures = _overall_verdict(
        checks_by_family, strict_web_comparison=strict_web_comparison
    )

    report = {
        "schema_version": "1.0",
        "feature_key": "bd-bkco.6",
        "suite": "golden_verification_suite",
        "generated_at": _utc_now(),
        "inputs": {
            "manifest_path": str(manifest_path.relative_to(REPO_ROOT)),
            "fixture_metadata_path": str(fixture_metadata_path.relative_to(REPO_ROOT)),
            "step_expectations_path": str(step_expectations_path.relative_to(REPO_ROOT)),
            "top_k": top_k,
            "strict_web_comparison": strict_web_comparison,
        },
        "checks": [
            {
                "check_family": check.check_family,
                "command": check.command,
                "status": check.status,
                "passed": check.passed,
                "blocking": check.blocking,
                "exit_code": check.exit_code,
                "output_path": check.output_path,
                "details": check.details or {},
                "stdout_tail": check.stdout.strip().splitlines()[-5:],
                "stderr_tail": check.stderr.strip().splitlines()[-5:],
            }
            for check in checks
        ],
        "fixture_coverage": {
            "manifest_bill_count": len(manifest_bills),
            "checked_in_fixture_bill_count": len(expected_fixture_bill_ids),
            "strong_fixture_bill_count": len(
                [b for b in bills if b.get("strong_replay_supported")]
            ),
            "live_capture_required_bill_count": len(
                [b for b in bills if b.get("live_capture_required")]
            ),
            "live_capture_required_bill_ids": [
                b["bill_id"] for b in bills if b.get("live_capture_required")
            ],
        },
        "bills": bills,
        "summary": {
            "overall_verdict": verdict,
            "blocking_failures": blocking_failures,
            "non_blocking_failures": non_blocking_failures,
            "check_family_pass_counts": {
                "pass": len([c for c in checks if c.passed]),
                "fail": len([c for c in checks if not c.passed]),
            },
        },
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return SCRIPT_DIR / "artifacts" / f"golden_suite_report_{stamp}.json"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the golden suite validators and generate a machine-readable summary report."
    )
    parser.add_argument(
        "--output",
        default="",
        help="Path for the suite report JSON. Defaults to a timestamped artifacts path.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=1,
        help="Top-K chunk count for retrieval-quality checks.",
    )
    parser.add_argument(
        "--strict-web-comparison",
        action="store_true",
        help="Treat web-mode comparison failures as blocking suite failures.",
    )
    args = parser.parse_args(argv)

    if args.top_k <= 0:
        print("FAIL: --top-k must be > 0")
        return 2

    output_path = Path(args.output) if args.output else _default_output_path()
    report = generate_golden_suite_report(
        output_path=output_path,
        top_k=args.top_k,
        strict_web_comparison=args.strict_web_comparison,
    )
    print(f"PASS: wrote golden-suite report to {output_path}")
    print(f"PASS: overall_verdict={report['summary']['overall_verdict']}")
    print(
        "PASS: live_capture_required="
        f"{report['fixture_coverage']['live_capture_required_bill_count']}"
    )
    return 0 if report["summary"]["overall_verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
