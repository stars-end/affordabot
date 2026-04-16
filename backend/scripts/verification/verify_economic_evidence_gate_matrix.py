#!/usr/bin/env python3
"""Economic evidence gate matrix verifier for bd-2agbe.4.

This verifier is intentionally fixture-first and deterministic. It isolates
failure attribution across search/source quality and downstream economics
gates without requiring live provider traffic.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FEATURE_KEY = "bd-2agbe.4"
VERIFIER_VERSION = "2026-04-14.fixture-v1"

GATE_ORDER = (
    "search_recall",
    "reader_substance",
    "artifact_classification",
    "evidence_cards",
    "parameterization",
    "assumption_selection",
    "quantification",
    "llm_explanation",
)

FINAL_VERDICT_QUANTIFIED_PASS = "quantified_pass"
FINAL_VERDICT_QUAL_ONLY_FAIL_CLOSED = "fail_closed_qualitative_only"
FINAL_VERDICT_QUAL_ONLY_LLM_BLOCKED = "qualitative_only_due_to_unsupported_claims"

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE_PATH = (
    REPO_ROOT / "backend" / "scripts" / "verification" / "fixtures" / "economic_evidence_gate_cases.json"
)
DEFAULT_OUT_JSON = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "economic-evidence-gate-matrix"
    / "artifacts"
    / "economic_evidence_gate_matrix_report.json"
)
DEFAULT_OUT_MD = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "economic-evidence-gate-matrix"
    / "artifacts"
    / "economic_evidence_gate_matrix_report.md"
)


@dataclass(frozen=True)
class VerifierConfig:
    fixture_path: Path
    out_json: Path
    out_md: Path
    stop_after: str | None
    provider_filter: str | None
    strict_expected: bool


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _stop_after_index(stop_after: str | None) -> int | None:
    if not stop_after:
        return None
    if stop_after not in GATE_ORDER:
        options = ", ".join(GATE_ORDER)
        raise ValueError(f"invalid --stop-after '{stop_after}'; expected one of: {options}")
    return GATE_ORDER.index(stop_after)


def _gate_status(*, passed: bool, reason: str) -> dict[str, Any]:
    return {"status": "pass" if passed else "fail", "passed": passed, "reason": reason}


def _evaluate_search_recall(case: dict[str, Any]) -> dict[str, Any]:
    payload = case.get("gate_inputs", {}).get("search_recall", {})
    artifact_candidates_found = int(payload.get("artifact_candidates_found", 0))
    official_domain_hit_rate_percent = float(payload.get("official_domain_hit_rate_percent", 0.0))
    passed = artifact_candidates_found > 0 and official_domain_hit_rate_percent > 0
    reason = "artifact_candidates_present" if passed else "no_artifact_candidates"
    return _gate_status(passed=passed, reason=reason)


def _evaluate_reader_substance(case: dict[str, Any]) -> dict[str, Any]:
    payload = case.get("gate_inputs", {}).get("reader_substance", {})
    substantive = bool(payload.get("substantive", False))
    chars = int(payload.get("selected_artifact_text_chars", 0))
    passed = substantive and chars >= 120
    reason = "reader_text_substantive" if passed else "reader_substance_insufficient"
    return _gate_status(passed=passed, reason=reason)


def _evaluate_artifact_classification(case: dict[str, Any]) -> dict[str, Any]:
    payload = case.get("gate_inputs", {}).get("artifact_classification", {})
    artifact_class = str(payload.get("selected_artifact_class", "")).strip().lower()
    is_portal_page = bool(payload.get("is_portal_page", False))
    passed = bool(artifact_class) and not is_portal_page
    reason = "artifact_classified_non_portal" if passed else "portal_or_unknown_artifact_class"
    return _gate_status(passed=passed, reason=reason)


def _evaluate_evidence_cards(case: dict[str, Any]) -> dict[str, Any]:
    cards = case.get("gate_inputs", {}).get("evidence_cards", {}).get("cards", [])
    passed = bool(cards)
    if passed:
        for card in cards:
            if not card.get("source_url") or not card.get("content_hash") or not card.get("excerpt"):
                passed = False
                break
    reason = "evidence_cards_present_with_provenance" if passed else "missing_or_invalid_evidence_cards"
    return _gate_status(passed=passed, reason=reason)


def _evaluate_parameterization(case: dict[str, Any]) -> dict[str, Any]:
    payload = case.get("gate_inputs", {}).get("parameterization", {})
    cards = payload.get("cards", [])
    required_parameters = {str(name) for name in payload.get("required_parameters", [])}
    resolved = {str(card.get("name")) for card in cards if card.get("value") is not None and card.get("unit")}
    missing_required = sorted(required_parameters - resolved)
    passed = not missing_required and bool(payload.get("formula_ids", []))
    reason = "required_parameters_resolved" if passed else f"missing_required_parameters:{','.join(missing_required)}"
    return _gate_status(passed=passed, reason=reason)


def _evaluate_assumption_selection(case: dict[str, Any]) -> dict[str, Any]:
    payload = case.get("gate_inputs", {}).get("assumption_selection", {})
    required_assumptions = {str(name) for name in payload.get("required_assumptions", [])}
    cards = payload.get("cards", [])
    provided_assumptions = {str(card.get("name")) for card in cards}
    missing = sorted(required_assumptions - provided_assumptions)
    cards_valid = True
    for card in cards:
        low = card.get("low")
        central = card.get("central")
        high = card.get("high")
        if any(value is None for value in (low, central, high)):
            cards_valid = False
            break
        if float(low) > float(central) or float(central) > float(high):
            cards_valid = False
            break
        if not card.get("source_url") or not card.get("applicability"):
            cards_valid = False
            break
    passed = not missing and cards_valid
    reason = "assumptions_declared_and_applicable" if passed else f"assumption_gap:{','.join(missing) if missing else 'invalid_card'}"
    return _gate_status(passed=passed, reason=reason)


def _evaluate_quantification(case: dict[str, Any]) -> dict[str, Any]:
    payload = case.get("gate_inputs", {}).get("quantification", {})
    deterministic = bool(payload.get("deterministic", False))
    outputs = payload.get("outputs", [])
    passed = deterministic and bool(outputs)
    if passed:
        for output in outputs:
            bounds = output.get("scenario_bounds", {})
            conservative = bounds.get("conservative")
            central = bounds.get("central")
            aggressive = bounds.get("aggressive")
            if any(value is None for value in (conservative, central, aggressive)):
                passed = False
                break
            if not (float(conservative) <= float(central) <= float(aggressive)):
                passed = False
                break
            if not output.get("formula_id"):
                passed = False
                break
    reason = "deterministic_quantification_complete" if passed else "quantification_failed_or_nondeterministic"
    return _gate_status(passed=passed, reason=reason)


def _evaluate_llm_explanation(case: dict[str, Any]) -> dict[str, Any]:
    payload = case.get("gate_inputs", {}).get("llm_explanation", {})
    unsupported_claim_count = int(payload.get("unsupported_claim_count", 0))
    introduced_numeric_claims = int(payload.get("introduced_numeric_claims", 0))
    passed = unsupported_claim_count == 0 and introduced_numeric_claims == 0
    reason = "llm_explanation_grounded" if passed else "unsupported_claims_or_novel_numbers"
    return _gate_status(passed=passed, reason=reason)


EVALUATORS = {
    "search_recall": _evaluate_search_recall,
    "reader_substance": _evaluate_reader_substance,
    "artifact_classification": _evaluate_artifact_classification,
    "evidence_cards": _evaluate_evidence_cards,
    "parameterization": _evaluate_parameterization,
    "assumption_selection": _evaluate_assumption_selection,
    "quantification": _evaluate_quantification,
    "llm_explanation": _evaluate_llm_explanation,
}


def _compute_counts(case: dict[str, Any]) -> tuple[int, int, int, list[str], int]:
    evidence_card_count = len(case.get("gate_inputs", {}).get("evidence_cards", {}).get("cards", []))
    parameter_payload = case.get("gate_inputs", {}).get("parameterization", {})
    parameter_card_count = len(parameter_payload.get("cards", []))
    assumption_card_count = len(case.get("gate_inputs", {}).get("assumption_selection", {}).get("cards", []))
    formula_ids = [str(x) for x in parameter_payload.get("formula_ids", [])]
    unsupported_claim_count = int(case.get("gate_inputs", {}).get("llm_explanation", {}).get("unsupported_claim_count", 0))
    return evidence_card_count, parameter_card_count, assumption_card_count, formula_ids, unsupported_claim_count


def _evaluate_case(case: dict[str, Any], *, stop_after_index: int | None) -> dict[str, Any]:
    gate_results: dict[str, dict[str, Any]] = {}
    blocking_gate = ""
    for gate_idx, gate_name in enumerate(GATE_ORDER):
        if stop_after_index is not None and gate_idx > stop_after_index:
            gate_results[gate_name] = {
                "status": "skipped_due_to_stop_after",
                "passed": False,
                "reason": "evaluation_truncated_by_cli_flag",
            }
            continue
        if blocking_gate:
            gate_results[gate_name] = {
                "status": "skipped_due_to_blocking_gate",
                "passed": False,
                "reason": f"upstream_gate_failed:{blocking_gate}",
            }
            continue
        result = EVALUATORS[gate_name](case)
        gate_results[gate_name] = result
        if not result["passed"]:
            blocking_gate = gate_name

    evidence_card_count, parameter_card_count, assumption_card_count, formula_ids, unsupported_claim_count = _compute_counts(case)

    if not blocking_gate:
        final_verdict = FINAL_VERDICT_QUANTIFIED_PASS
    elif blocking_gate == "llm_explanation":
        final_verdict = FINAL_VERDICT_QUAL_ONLY_LLM_BLOCKED
    else:
        final_verdict = FINAL_VERDICT_QUAL_ONLY_FAIL_CLOSED

    return {
        "case_id": str(case.get("case_id", "")),
        "jurisdiction": str(case.get("jurisdiction", "")),
        "source_family": str(case.get("source_family", "")),
        "provider": str(case.get("provider", "fixture")),
        "final_verdict": final_verdict,
        "blocking_gate": blocking_gate or "",
        "gate_results": gate_results,
        "evidence_card_count": evidence_card_count,
        "parameter_card_count": parameter_card_count,
        "assumption_card_count": assumption_card_count,
        "formula_ids": formula_ids,
        "unsupported_claim_count": unsupported_claim_count,
        "manual_audit_notes": str(case.get("manual_audit_notes", "")),
        "integration_notes": str(
            case.get(
                "integration_notes",
                "TODO integrate with bd-2agbe.2/.3 contract classes once merged.",
            )
        ),
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Economic Evidence Gate Matrix Report ({FEATURE_KEY})",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- verifier_version: `{report['verifier_version']}`",
        f"- fixture_path: `{report['fixture_path']}`",
        "",
        "## Summary",
        "",
        f"- total_cases: `{report['summary']['total_cases']}`",
        f"- quantified_pass_count: `{report['summary']['quantified_pass_count']}`",
        f"- qualitative_fail_closed_count: `{report['summary']['qualitative_fail_closed_count']}`",
        f"- llm_blocked_count: `{report['summary']['llm_blocked_count']}`",
        "",
        "## Case Results",
        "",
        "| case_id | provider | final_verdict | blocking_gate | evidence_cards | parameter_cards | assumption_cards | unsupported_claims |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for case in report["cases"]:
        lines.append(
            "| {case_id} | {provider} | {final_verdict} | {blocking_gate} | {evidence_card_count} | "
            "{parameter_card_count} | {assumption_card_count} | {unsupported_claim_count} |".format(**case)
        )

    lines.append("")
    lines.append("## Manual Audit Notes")
    lines.append("")
    for case in report["cases"]:
        lines.append(f"### {case['case_id']}")
        lines.append("")
        lines.append(f"- jurisdiction: `{case['jurisdiction']}`")
        lines.append(f"- source_family: `{case['source_family']}`")
        lines.append(f"- notes: {case['manual_audit_notes']}")
        lines.append(f"- integration_note: {case['integration_notes']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _summarize(cases: list[dict[str, Any]]) -> dict[str, Any]:
    quantified_pass_count = sum(1 for case in cases if case["final_verdict"] == FINAL_VERDICT_QUANTIFIED_PASS)
    llm_blocked_count = sum(1 for case in cases if case["final_verdict"] == FINAL_VERDICT_QUAL_ONLY_LLM_BLOCKED)
    return {
        "total_cases": len(cases),
        "quantified_pass_count": quantified_pass_count,
        "llm_blocked_count": llm_blocked_count,
        "qualitative_fail_closed_count": len(cases) - quantified_pass_count - llm_blocked_count,
    }


def _verify_expected_results(case: dict[str, Any], result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    expected = case.get("expected", {})
    expected_blocking_gate = expected.get("blocking_gate", "")
    expected_final_verdict = expected.get("final_verdict", "")
    if expected_blocking_gate != result["blocking_gate"]:
        failures.append(
            f"{result['case_id']}: expected blocking_gate={expected_blocking_gate!r} got={result['blocking_gate']!r}"
        )
    if expected_final_verdict != result["final_verdict"]:
        failures.append(
            f"{result['case_id']}: expected final_verdict={expected_final_verdict!r} got={result['final_verdict']!r}"
        )
    return failures


def _run(config: VerifierConfig) -> dict[str, Any]:
    fixture = _load_json(config.fixture_path)
    stop_after_idx = _stop_after_index(config.stop_after)
    case_inputs = fixture.get("cases", [])
    if config.provider_filter:
        case_inputs = [case for case in case_inputs if case.get("provider") == config.provider_filter]

    case_results: list[dict[str, Any]] = []
    expectation_failures: list[str] = []
    for case in case_inputs:
        result = _evaluate_case(case, stop_after_index=stop_after_idx)
        case_results.append(result)
        if config.strict_expected:
            expectation_failures.extend(_verify_expected_results(case, result))

    report = {
        "feature_key": FEATURE_KEY,
        "verifier_version": VERIFIER_VERSION,
        "generated_at": _now_iso(),
        "fixture_path": _repo_display_path(config.fixture_path),
        "stop_after": config.stop_after or "",
        "provider_filter": config.provider_filter or "",
        "cases": case_results,
        "summary": _summarize(case_results),
        "integration_notes": [
            "Current verifier uses fixture-local contract.",
            "Integration point: swap fixture-local card fields with bd-2agbe.2 card models and bd-2agbe.3 assumption registry payloads.",
        ],
    }
    if expectation_failures:
        report["expectation_failures"] = expectation_failures
    return report


def _write_report(report: dict[str, Any], out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    out_md.write_text(_render_markdown(report), encoding="utf-8")


def _parse_args() -> VerifierConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    parser.add_argument("--stop-after", choices=GATE_ORDER)
    parser.add_argument("--provider", help="Filter by provider label (e.g. fixture, searxng_private).")
    parser.add_argument(
        "--strict-expected",
        action="store_true",
        help="Fail with exit code 1 if expected fixture verdicts do not match computed results.",
    )
    args = parser.parse_args()
    return VerifierConfig(
        fixture_path=args.fixture,
        out_json=args.out_json,
        out_md=args.out_md,
        stop_after=args.stop_after,
        provider_filter=args.provider,
        strict_expected=args.strict_expected,
    )


def main() -> int:
    config = _parse_args()
    report = _run(config)
    _write_report(report, config.out_json, config.out_md)
    print(f"[{FEATURE_KEY}] wrote JSON report: {config.out_json}")
    print(f"[{FEATURE_KEY}] wrote Markdown report: {config.out_md}")
    if report.get("expectation_failures"):
        for failure in report["expectation_failures"]:
            print(f"[{FEATURE_KEY}] expectation_failure: {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
