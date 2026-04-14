#!/usr/bin/env python3
"""Overlay verifier for decision-grade economic readiness on live San Jose artifacts.

This verifier is deterministic and offline. It reads previously generated
artifacts and applies the economic gate taxonomy to determine whether the
current live pipeline evidence is sufficient for quantitative analysis.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FEATURE_KEY = "bd-2agbe.5"
VERIFIER_VERSION = "2026-04-14.overlay-v1"

GATE_ORDER = (
    "search_provider_source_quality",
    "reader_substrate_quality",
    "economic_evidence_card_sufficiency",
    "parameterization_sufficiency",
    "assumption_sufficiency",
    "deterministic_quantification_readiness",
    "llm_explanation_support",
)

FINAL_VERDICT_QUANTIFIED_PASS = "quantified_pass"
FINAL_VERDICT_QUAL_ONLY_FAIL_CLOSED = "fail_closed_qualitative_only"

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LIVE_REPORT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "windmill-domain-boundary-integration"
    / "artifacts"
    / "sanjose_live_gate_report.json"
)
DEFAULT_BAKEOFF_REPORT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "search-source-quality-bakeoff"
    / "artifacts"
    / "search_source_quality_bakeoff_report.json"
)
DEFAULT_MATRIX_FIXTURE = (
    REPO_ROOT
    / "backend"
    / "scripts"
    / "verification"
    / "fixtures"
    / "economic_evidence_gate_cases.json"
)
DEFAULT_OUT_JSON = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "economic-evidence-quality"
    / "artifacts"
    / "economic_readiness_overlay_report.json"
)
DEFAULT_OUT_MD = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "economic-evidence-quality"
    / "artifacts"
    / "economic_readiness_overlay_report.md"
)


@dataclass(frozen=True)
class VerifierConfig:
    live_report_path: Path
    bakeoff_report_path: Path
    gate_fixture_path: Path
    out_json: Path
    out_md: Path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_get(mapping: dict[str, Any], *path: str, default: Any = None) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _extract_primary_scope(live_report: dict[str, Any]) -> dict[str, Any]:
    idempotent_scopes = _safe_get(
        live_report,
        "idempotent_rerun",
        "result_payload",
        "scope_results",
        default=[],
    )
    if isinstance(idempotent_scopes, list) and idempotent_scopes:
        return idempotent_scopes[0]
    result_scopes = _safe_get(live_report, "result_payload", "scope_results", default=[])
    if isinstance(result_scopes, list) and result_scopes:
        return result_scopes[0]
    return {}


def _gate_result(passed: bool, reason: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "pass" if passed else "fail",
        "passed": passed,
        "reason": reason,
        "details": details,
    }


def _evaluate_search_provider_source_quality(
    live_report: dict[str, Any], bakeoff_report: dict[str, Any]
) -> dict[str, Any]:
    provider_summary = bakeoff_report.get("provider_summary", [])
    providers_with_official_hits = [
        item
        for item in provider_summary
        if float(item.get("official_domain_hit_rate_percent", 0.0)) > 0.0
    ]
    best_official_hit_rate = max(
        (float(item.get("official_domain_hit_rate_percent", 0.0)) for item in provider_summary),
        default=0.0,
    )
    best_reader_ready_rate = max(
        (float(item.get("reader_ready_rate_percent", 0.0)) for item in provider_summary),
        default=0.0,
    )

    scope = _extract_primary_scope(live_report)
    steps = scope.get("steps", {}) if isinstance(scope, dict) else {}
    search_status = _safe_get(steps, "search_materialize", "status", default="")
    search_result_count = 0
    search_rows = _safe_get(live_report, "db_storage_probe", "search_snapshot_rows", default=[])
    if isinstance(search_rows, list) and search_rows:
        search_result_count = int(search_rows[0].get("result_count", 0))

    passed = (
        search_status == "succeeded"
        and search_result_count > 0
        and best_official_hit_rate >= 70.0
        and best_reader_ready_rate > 0.0
    )
    reason = "search_sources_sufficient_for_artifact_discovery" if passed else "insufficient_search_source_quality"
    return _gate_result(
        passed,
        reason,
        {
            "provider_count": len(provider_summary),
            "providers_with_official_hits": len(providers_with_official_hits),
            "best_official_domain_hit_rate_percent": best_official_hit_rate,
            "best_reader_ready_rate_percent": best_reader_ready_rate,
            "live_search_materialize_status": search_status,
            "live_search_result_count": search_result_count,
        },
    )


def _evaluate_reader_substrate_quality(live_report: dict[str, Any]) -> dict[str, Any]:
    scope = _extract_primary_scope(live_report)
    steps = scope.get("steps", {}) if isinstance(scope, dict) else {}
    read_fetch_status = _safe_get(steps, "read_fetch", "status", default="")
    index_status = _safe_get(steps, "index", "status", default="")
    analyze_status = _safe_get(steps, "analyze", "status", default="")
    raw_scrape_rows = _safe_get(live_report, "db_storage_probe", "raw_scrape_rows", default=[])
    reader_excerpt = _safe_get(live_report, "manual_audit_notes", "reader_output_excerpt", default="")
    selected_chunk_count = int(
        _safe_get(
            steps,
            "analyze",
            "details",
            "evidence_selection",
            "selected_chunk_count",
            default=0,
        )
    )

    passed = (
        read_fetch_status == "succeeded"
        and index_status == "succeeded"
        and analyze_status == "succeeded"
        and isinstance(raw_scrape_rows, list)
        and len(raw_scrape_rows) > 0
        and isinstance(reader_excerpt, str)
        and len(reader_excerpt.strip()) >= 120
        and selected_chunk_count > 0
    )
    reason = "reader_and_substrate_outputs_are_substantive" if passed else "reader_or_substrate_quality_insufficient"
    return _gate_result(
        passed,
        reason,
        {
            "read_fetch_status": read_fetch_status,
            "index_status": index_status,
            "analyze_status": analyze_status,
            "raw_scrape_row_count": len(raw_scrape_rows) if isinstance(raw_scrape_rows, list) else 0,
            "reader_excerpt_chars": len(reader_excerpt.strip()) if isinstance(reader_excerpt, str) else 0,
            "selected_chunk_count": selected_chunk_count,
        },
    )


def _extract_structured_evidence_cards(live_report: dict[str, Any]) -> list[dict[str, Any]]:
    scope = _extract_primary_scope(live_report)
    steps = scope.get("steps", {}) if isinstance(scope, dict) else {}
    cards: list[dict[str, Any]] = []
    candidate_paths = [
        ("analyze", "details", "evidence_cards", "cards"),
        ("analyze", "details", "analysis", "evidence_cards"),
    ]
    for path in candidate_paths:
        value = _safe_get(steps, *path, default=[])
        if isinstance(value, list):
            cards.extend(value)
    return cards


def _evaluate_economic_evidence_card_sufficiency(live_report: dict[str, Any]) -> dict[str, Any]:
    cards = _extract_structured_evidence_cards(live_report)
    valid_count = 0
    for card in cards:
        if not isinstance(card, dict):
            continue
        if card.get("source_url") and card.get("content_hash") and card.get("excerpt"):
            valid_count += 1

    passed = valid_count > 0
    reason = "structured_evidence_cards_with_provenance_present" if passed else "missing_structured_evidence_cards_with_provenance"
    return _gate_result(
        passed,
        reason,
        {
            "structured_evidence_card_count": len(cards),
            "valid_evidence_card_count": valid_count,
            "note": "Reader snippets without explicit source_url/content_hash/excerpt cards are not sufficient for quantified economics.",
        },
    )


def _extract_parameterization_payload(live_report: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    scope = _extract_primary_scope(live_report)
    steps = scope.get("steps", {}) if isinstance(scope, dict) else {}
    cards = _safe_get(steps, "analyze", "details", "parameterization", "cards", default=[])
    formula_ids = _safe_get(steps, "analyze", "details", "parameterization", "formula_ids", default=[])
    if not isinstance(cards, list):
        cards = []
    if not isinstance(formula_ids, list):
        formula_ids = []
    return cards, [str(x) for x in formula_ids]


def _evaluate_parameterization_sufficiency(live_report: dict[str, Any]) -> dict[str, Any]:
    cards, formula_ids = _extract_parameterization_payload(live_report)
    resolved_numeric_cards = [
        card
        for card in cards
        if isinstance(card, dict)
        and card.get("value") is not None
        and card.get("unit")
        and (card.get("source_url") or card.get("source_evidence_id"))
    ]
    passed = bool(formula_ids) and bool(resolved_numeric_cards)
    reason = "parameterization_contract_present" if passed else "missing_parameter_cards_or_formula_ids"
    return _gate_result(
        passed,
        reason,
        {
            "parameter_card_count": len(cards),
            "resolved_numeric_parameter_count": len(resolved_numeric_cards),
            "formula_id_count": len(formula_ids),
            "formula_ids": formula_ids,
        },
    )


def _evaluate_assumption_sufficiency(live_report: dict[str, Any]) -> dict[str, Any]:
    scope = _extract_primary_scope(live_report)
    steps = scope.get("steps", {}) if isinstance(scope, dict) else {}
    cards = _safe_get(steps, "analyze", "details", "assumption_selection", "cards", default=[])
    if not isinstance(cards, list):
        cards = []
    valid_cards = 0
    for card in cards:
        if not isinstance(card, dict):
            continue
        low = card.get("low")
        central = card.get("central")
        high = card.get("high")
        if low is None or central is None or high is None:
            continue
        if float(low) <= float(central) <= float(high) and card.get("source_url"):
            valid_cards += 1
    passed = valid_cards > 0
    reason = "assumption_cards_declared_with_bounds" if passed else "missing_or_invalid_assumption_cards"
    return _gate_result(
        passed,
        reason,
        {
            "assumption_card_count": len(cards),
            "valid_assumption_card_count": valid_cards,
        },
    )


def _evaluate_deterministic_quantification_readiness(live_report: dict[str, Any]) -> dict[str, Any]:
    scope = _extract_primary_scope(live_report)
    steps = scope.get("steps", {}) if isinstance(scope, dict) else {}
    outputs = _safe_get(steps, "analyze", "details", "quantification", "outputs", default=[])
    deterministic = bool(
        _safe_get(steps, "analyze", "details", "quantification", "deterministic", default=False)
    )
    if not isinstance(outputs, list):
        outputs = []
    valid_outputs = 0
    for output in outputs:
        if not isinstance(output, dict):
            continue
        bounds = output.get("scenario_bounds", {})
        if not isinstance(bounds, dict):
            continue
        conservative = bounds.get("conservative")
        central = bounds.get("central")
        aggressive = bounds.get("aggressive")
        if any(value is None for value in (conservative, central, aggressive)):
            continue
        if float(conservative) <= float(central) <= float(aggressive) and output.get("formula_id"):
            valid_outputs += 1
    passed = deterministic and valid_outputs > 0
    reason = "deterministic_quantification_ready" if passed else "deterministic_quantification_not_supported"
    return _gate_result(
        passed,
        reason,
        {
            "deterministic_flag": deterministic,
            "quant_output_count": len(outputs),
            "valid_quant_output_count": valid_outputs,
        },
    )


def _evaluate_llm_explanation_support(live_report: dict[str, Any]) -> dict[str, Any]:
    llm_excerpt = _safe_get(live_report, "manual_audit_notes", "llm_analysis_excerpt", default="")
    llm_quality_note = _safe_get(live_report, "manual_audit_notes", "llm_quality_note", default="")
    passed = isinstance(llm_excerpt, str) and len(llm_excerpt.strip()) >= 80
    reason = "llm_explanation_present_but_requires_quant_guardrails" if passed else "missing_llm_explanation_excerpt"
    return _gate_result(
        passed,
        reason,
        {
            "llm_excerpt_chars": len(llm_excerpt.strip()) if isinstance(llm_excerpt, str) else 0,
            "llm_quality_note": llm_quality_note,
        },
    )


def _evaluate_gates(live_report: dict[str, Any], bakeoff_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    gate_results: dict[str, dict[str, Any]] = {}
    gate_results["search_provider_source_quality"] = _evaluate_search_provider_source_quality(
        live_report, bakeoff_report
    )
    gate_results["reader_substrate_quality"] = _evaluate_reader_substrate_quality(live_report)
    gate_results["economic_evidence_card_sufficiency"] = _evaluate_economic_evidence_card_sufficiency(
        live_report
    )
    gate_results["parameterization_sufficiency"] = _evaluate_parameterization_sufficiency(live_report)
    gate_results["assumption_sufficiency"] = _evaluate_assumption_sufficiency(live_report)
    gate_results["deterministic_quantification_readiness"] = _evaluate_deterministic_quantification_readiness(
        live_report
    )
    gate_results["llm_explanation_support"] = _evaluate_llm_explanation_support(live_report)
    return gate_results


def _compute_blocking_gate(gate_results: dict[str, dict[str, Any]]) -> str:
    for gate in GATE_ORDER:
        if not gate_results[gate]["passed"]:
            return gate
    return ""


def _manual_audit_notes(live_report: dict[str, Any], gate_results: dict[str, dict[str, Any]]) -> list[str]:
    notes = [
        "Search/provider quality is treated independently from quantitative economics readiness.",
        "Reader/substrate success confirms retrieval and persistence, not quantitative sufficiency.",
        "Quantified economics requires structured evidence cards + parameterization + assumptions + deterministic formulas.",
    ]
    if not gate_results["economic_evidence_card_sufficiency"]["passed"]:
        notes.append(
            "Current San Jose live artifact contains selected chunks and qualitative analysis, but does not expose structured evidence cards with source_url/content_hash/excerpt linkage."
        )
    if not gate_results["parameterization_sufficiency"]["passed"]:
        notes.append(
            "No explicit numeric parameter card payload and formula_id set were found in the live analyze step output."
        )
    if not gate_results["deterministic_quantification_readiness"]["passed"]:
        notes.append(
            "No deterministic quantification outputs with scenario bounds were found; numeric economic judgment should fail closed."
        )
    live_manual_note = _safe_get(live_report, "manual_audit_notes", "llm_quality_note", default="")
    if live_manual_note:
        notes.append(f"Live manual audit note: {live_manual_note}")
    return notes


def _build_recommendation(gate_results: dict[str, dict[str, Any]], blocking_gate: str) -> str:
    if not blocking_gate:
        return (
            "Current artifacts are decision-grade for quantitative economics: structured evidence cards, "
            "parameterization, assumptions, and deterministic quantification are all present."
        )
    if blocking_gate == "economic_evidence_card_sufficiency":
        return (
            "Not decision-grade for numeric economics. Retrieval/reader quality is usable, but structured "
            "evidence cards are missing; fail closed before parameterization."
        )
    return (
        "Not decision-grade for numeric economics. Upstream retrieval may be adequate, but quantified analysis "
        f"is blocked at `{blocking_gate}` and should fail closed."
    )


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Economic Readiness Overlay Report ({FEATURE_KEY})",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- verifier_version: `{report['verifier_version']}`",
        f"- live_report_path: `{report['inputs']['live_report_path']}`",
        f"- bakeoff_report_path: `{report['inputs']['bakeoff_report_path']}`",
        f"- gate_fixture_path: `{report['inputs']['gate_fixture_path']}`",
        "",
        "## Verdict",
        "",
        f"- decision_grade_for_numeric_economic_analysis: `{report['decision_grade_for_numeric_economic_analysis']}`",
        f"- final_verdict: `{report['final_verdict']}`",
        f"- blocking_gate: `{report['blocking_gate']}`",
        "",
        f"Recommendation: {report['recommendation']}",
        "",
        "## Gate Results",
        "",
        "| gate | status | reason |",
        "|---|---|---|",
    ]
    for gate in GATE_ORDER:
        gate_result = report["gate_results"][gate]
        lines.append(f"| {gate} | {gate_result['status']} | {gate_result['reason']} |")
    lines.extend(
        [
            "",
            "## Gate Details",
            "",
        ]
    )
    for gate in GATE_ORDER:
        gate_result = report["gate_results"][gate]
        lines.append(f"### {gate}")
        lines.append("")
        lines.append(f"- status: `{gate_result['status']}`")
        lines.append(f"- reason: `{gate_result['reason']}`")
        details = gate_result.get("details", {})
        if isinstance(details, dict):
            for key, value in details.items():
                lines.append(f"- {key}: `{value}`")
        lines.append("")
    lines.extend(["## Manual Audit Notes", ""])
    for note in report["manual_audit_notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def _run(config: VerifierConfig) -> dict[str, Any]:
    live_report = _load_json(config.live_report_path)
    bakeoff_report = _load_json(config.bakeoff_report_path)
    _ = _load_json(config.gate_fixture_path)  # Ensures fixture is present for taxonomy parity.

    gate_results = _evaluate_gates(live_report, bakeoff_report)
    blocking_gate = _compute_blocking_gate(gate_results)
    decision_grade = not bool(blocking_gate)
    final_verdict = (
        FINAL_VERDICT_QUANTIFIED_PASS if decision_grade else FINAL_VERDICT_QUAL_ONLY_FAIL_CLOSED
    )
    report = {
        "feature_key": FEATURE_KEY,
        "verifier_version": VERIFIER_VERSION,
        "generated_at": _now_iso(),
        "inputs": {
            "live_report_path": str(config.live_report_path),
            "bakeoff_report_path": str(config.bakeoff_report_path),
            "gate_fixture_path": str(config.gate_fixture_path),
        },
        "decision_grade_for_numeric_economic_analysis": decision_grade,
        "final_verdict": final_verdict,
        "blocking_gate": blocking_gate,
        "gate_results": gate_results,
        "recommendation": _build_recommendation(gate_results, blocking_gate),
        "manual_audit_notes": _manual_audit_notes(live_report, gate_results),
    }
    return report


def _write_outputs(report: dict[str, Any], out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    out_md.write_text(_render_markdown(report), encoding="utf-8")


def _parse_args() -> VerifierConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-report", type=Path, default=DEFAULT_LIVE_REPORT)
    parser.add_argument("--bakeoff-report", type=Path, default=DEFAULT_BAKEOFF_REPORT)
    parser.add_argument("--gate-fixture", type=Path, default=DEFAULT_MATRIX_FIXTURE)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()
    return VerifierConfig(
        live_report_path=args.live_report,
        bakeoff_report_path=args.bakeoff_report,
        gate_fixture_path=args.gate_fixture,
        out_json=args.out_json,
        out_md=args.out_md,
    )


def main() -> int:
    config = _parse_args()
    report = _run(config)
    _write_outputs(report, config.out_json, config.out_md)
    print(f"[{FEATURE_KEY}] wrote JSON report: {config.out_json}")
    print(f"[{FEATURE_KEY}] wrote Markdown report: {config.out_md}")
    print(
        f"[{FEATURE_KEY}] decision_grade_for_numeric_economic_analysis: "
        f"{report['decision_grade_for_numeric_economic_analysis']}"
    )
    print(f"[{FEATURE_KEY}] blocking_gate: {report['blocking_gate'] or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

