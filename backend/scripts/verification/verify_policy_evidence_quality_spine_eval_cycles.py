#!/usr/bin/env python3
"""Build deterministic eval-cycle artifacts for the policy evidence quality spine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS_DIR = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
)
DEFAULT_SCORECARD_PATH = ARTIFACTS_DIR / "quality_spine_scorecard.json"
DEFAULT_RETRY_LEDGER_PATH = ARTIFACTS_DIR / "retry_ledger.json"
DEFAULT_LIVE_STORAGE_PATH = ARTIFACTS_DIR / "quality_spine_live_storage_probe.json"
DEFAULT_OUTPUT_JSON = ARTIFACTS_DIR / "quality_spine_eval_cycles_report.json"
DEFAULT_OUTPUT_MD = ARTIFACTS_DIR / "quality_spine_eval_cycles_report.md"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _status_rank(status: str) -> int:
    if status == "fail":
        return 2
    if status == "not_proven":
        return 1
    return 0


def _combine_status(statuses: list[str]) -> str:
    rank = max((_status_rank(status) for status in statuses), default=0)
    if rank == 2:
        return "fail"
    if rank == 1:
        return "not_proven"
    return "pass"


def _gate_entry(status: str, details: str) -> dict[str, str]:
    normalized = status if status in {"pass", "not_proven", "fail"} else "not_proven"
    return {"status": normalized, "details": details}


def _build_gate_statuses(scorecard: dict[str, Any], live_probe: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    taxonomy = scorecard.get("taxonomy", {})
    scraped = taxonomy.get("scraped/search", {})
    reader = taxonomy.get("reader", {})
    structured = taxonomy.get("structured-source", {})
    identity = taxonomy.get("identity/dedupe", {})
    storage = taxonomy.get("storage/read-back", {})
    sufficiency = taxonomy.get("sufficiency gate", {})
    economics = taxonomy.get("economic reasoning", {})
    frontend = taxonomy.get("frontend/read-model auditability", {})
    windmill = taxonomy.get("Windmill/orchestration", {})
    llm = taxonomy.get("LLM narrative", {})

    storage_details = str(storage.get("details", "storage status unavailable"))
    if isinstance(live_probe, dict) and live_probe.get("status") == "blocked":
        blocker = str(live_probe.get("blocker") or "unknown_blocker")
        error_summary = str(live_probe.get("error_summary") or "")
        storage_details = (
            f"{storage_details} Live probe blocker={blocker}."
            + (f" {error_summary}" if error_summary else "")
        )

    unified_status = _combine_status(
        [
            str(identity.get("status", "not_proven")),
            str(sufficiency.get("status", "not_proven")),
            str(frontend.get("status", "not_proven")),
        ]
    )
    unified_details = (
        "identity="
        f"{identity.get('status', 'not_proven')}, "
        "sufficiency="
        f"{sufficiency.get('status', 'not_proven')}, "
        "read_model="
        f"{frontend.get('status', 'not_proven')}"
    )

    economic_readiness_status = _combine_status(
        [
            str(sufficiency.get("status", "not_proven")),
            str(economics.get("status", "not_proven")),
        ]
    )
    economic_readiness_details = (
        "sufficiency="
        f"{sufficiency.get('status', 'not_proven')}, "
        "economic_reasoning="
        f"{economics.get('status', 'not_proven')}"
    )

    return {
        "scraped_quality": _gate_entry(
            _combine_status(
                [
                    str(scraped.get("status", "not_proven")),
                    str(reader.get("status", "not_proven")),
                ]
            ),
            "scraped/search="
            f"{scraped.get('status', 'not_proven')}, reader={reader.get('status', 'not_proven')}",
        ),
        "structured_quality": _gate_entry(
            str(structured.get("status", "not_proven")),
            str(structured.get("details", "structured quality unavailable")),
        ),
        "unified_package": _gate_entry(unified_status, unified_details),
        "storage/read-back": _gate_entry(
            str(storage.get("status", "not_proven")),
            storage_details,
        ),
        "Windmill/orchestration": _gate_entry(
            str(windmill.get("status", "not_proven")),
            str(windmill.get("details", "windmill orchestration status unavailable")),
        ),
        "LLM narrative": _gate_entry(
            str(llm.get("status", "not_proven")),
            str(llm.get("details", "llm narrative status unavailable")),
        ),
        "economic_analysis_readiness": _gate_entry(
            economic_readiness_status,
            economic_readiness_details,
        ),
    }


def _build_recommendations(gates: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    failed = [gate for gate, info in gates.items() if info["status"] == "fail"]
    not_proven = [gate for gate, info in gates.items() if info["status"] == "not_proven"]
    mapping = {
        "scraped_quality": "Tighten provider selection/ranker and verify selected artifact metrics per query family.",
        "structured_quality": "Add broader structured-source coverage with source-family and jurisdiction metadata.",
        "unified_package": "Repair package identity/read-model linkage and rerun deterministic package build checks.",
        "storage/read-back": "Resolve live storage credentials/policy and re-run Postgres+MinIO read-back proof.",
        "Windmill/orchestration": "Capture current Windmill run/job ids linked to the same package_id.",
        "LLM narrative": "Run canonical LLM narrative step and persist canonical run/step identifiers.",
        "economic_analysis_readiness": "Strengthen source-bound parameter/assumption evidence and gate projection.",
    }
    ordered = failed + [gate for gate in not_proven if gate not in failed]
    return {
        "failed_gates": failed,
        "not_proven_gates": not_proven,
        "next_tweaks": [mapping[gate] for gate in ordered if gate in mapping],
    }


def _upsert_cycle_attempts(
    retry_ledger: dict[str, Any] | None,
    *,
    scorecard: dict[str, Any],
    max_cycles: int,
    recommendations: dict[str, list[str]],
) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    existing = (retry_ledger or {}).get("attempts", [])
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, dict):
                attempts.append(dict(item))
    attempts_by_id = {str(item.get("attempt_id")): item for item in attempts if item.get("attempt_id")}

    matrix_attempt = scorecard.get("matrix_attempt", {})
    current_round = int(matrix_attempt.get("retry_round") or 0)
    current_round = max(0, min(current_round, max_cycles - 1))
    current_id = "baseline" if current_round == 0 else f"retry_{current_round}"

    for cycle_index in range(max_cycles):
        attempt_id = "baseline" if cycle_index == 0 else f"retry_{cycle_index}"
        if attempt_id in attempts_by_id:
            continue
        status = "not_executed"
        verdict = None
        failed: list[str] = []
        not_proven: list[str] = []
        result_note = None
        tweaks = recommendations["next_tweaks"]
        if attempt_id == current_id:
            status = "completed"
            verdict = scorecard.get("overall_verdict")
            failed = list(scorecard.get("failure_classification", {}).get("failed_categories", []))
            not_proven = list(scorecard.get("failure_classification", {}).get("not_proven_categories", []))
            tweaks = [str(matrix_attempt.get("targeted_tweak") or "baseline_no_tweak")]
            result_note = "Current deterministic evaluation cycle."
        attempts_by_id[attempt_id] = {
            "attempt_id": attempt_id,
            "status": status,
            "result_verdict": verdict,
            "failed_categories": failed,
            "not_proven_categories": not_proven,
            "tweaks_applied": tweaks,
            "result_note": result_note,
            "score_delta": None,
        }

    def _attempt_order(value: str) -> int:
        if value == "baseline":
            return 0
        if value.startswith("retry_"):
            try:
                return int(value.split("_", maxsplit=1)[1])
            except ValueError:
                return 10_000
        return 10_000

    ordered_ids = sorted(attempts_by_id.keys(), key=_attempt_order)
    return [attempts_by_id[item_id] for item_id in ordered_ids[:max_cycles]]


def build_eval_cycles_report(
    *,
    scorecard: dict[str, Any],
    retry_ledger: dict[str, Any] | None,
    live_storage_probe: dict[str, Any] | None,
    max_cycles: int,
) -> dict[str, Any]:
    bounded_max_cycles = max(1, min(int(max_cycles), 10))
    gates = _build_gate_statuses(scorecard=scorecard, live_probe=live_storage_probe)
    recommendations = _build_recommendations(gates)
    failed = recommendations["failed_gates"]
    not_proven = recommendations["not_proven_gates"]
    verdict = "fail" if failed else ("partial" if not_proven else "pass")
    matrix_source = scorecard.get("matrix_source", {})
    matrix_mode = str(matrix_source.get("mode") or "unknown")

    proof_scope = {
        "local_deterministic_proof": matrix_mode in {"agent_a_horizontal_matrix", "fallback_fixture"},
        "live_product_proof": all(
            gates[name]["status"] == "pass"
            for name in ("storage/read-back", "Windmill/orchestration", "LLM narrative")
        ),
        "distinction_note": (
            "This harness never upgrades local deterministic evidence into full live-product proof. "
            "Live-product proof requires pass on storage/read-back, Windmill/orchestration, and LLM narrative."
        ),
    }
    attempts = _upsert_cycle_attempts(
        retry_ledger=retry_ledger,
        scorecard=scorecard,
        max_cycles=bounded_max_cycles,
        recommendations=recommendations,
    )
    return {
        "feature_key": "bd-3wefe.13",
        "max_cycles": bounded_max_cycles,
        "current_cycle_input": scorecard.get("matrix_attempt", {}),
        "proof_scope": proof_scope,
        "gate_categories": gates,
        "recommendations": recommendations,
        "final_verdict": verdict,
        "cycle_ledger": attempts,
        "artifact_sources": {
            "scorecard_present": True,
            "retry_ledger_present": retry_ledger is not None,
            "live_storage_probe_present": live_storage_probe is not None,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Policy Evidence Quality Spine Eval Cycles",
        "",
        f"- feature_key: `{report['feature_key']}`",
        f"- final_verdict: `{report['final_verdict']}`",
        f"- max_cycles: `{report['max_cycles']}`",
        f"- local_deterministic_proof: `{report['proof_scope']['local_deterministic_proof']}`",
        f"- live_product_proof: `{report['proof_scope']['live_product_proof']}`",
        "",
        "## Gate status",
        "",
        "| Gate | Status | Details |",
        "| --- | --- | --- |",
    ]
    for gate in (
        "scraped_quality",
        "structured_quality",
        "unified_package",
        "storage/read-back",
        "Windmill/orchestration",
        "LLM narrative",
        "economic_analysis_readiness",
    ):
        item = report["gate_categories"][gate]
        lines.append(f"| {gate} | {item['status']} | {item['details']} |")

    lines.extend(
        [
            "",
            "## Recommended tweaks",
            "",
        ]
    )
    for tweak in report["recommendations"]["next_tweaks"]:
        lines.append(f"- {tweak}")

    lines.extend(
        [
            "",
            "## Cycle ledger",
            "",
            "| Cycle | Status | Verdict | Tweaks |",
            "| --- | --- | --- | --- |",
        ]
    )
    for cycle in report["cycle_ledger"]:
        tweaks = ", ".join(cycle.get("tweaks_applied") or []) or "none"
        lines.append(
            f"| {cycle.get('attempt_id')} | {cycle.get('status')} | "
            f"{cycle.get('result_verdict') or 'n/a'} | {tweaks} |"
        )
    lines.append("")
    lines.append("## Proof boundary")
    lines.append("")
    lines.append(report["proof_scope"]["distinction_note"])
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD_PATH)
    parser.add_argument("--retry-ledger", type=Path, default=DEFAULT_RETRY_LEDGER_PATH)
    parser.add_argument("--live-storage-probe", type=Path, default=DEFAULT_LIVE_STORAGE_PATH)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--max-cycles", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    scorecard = _load_json(args.scorecard)
    if scorecard is None:
        raise SystemExit(f"missing scorecard artifact: {args.scorecard}")
    retry_ledger = _load_json(args.retry_ledger)
    live_storage_probe = _load_json(args.live_storage_probe)
    report = build_eval_cycles_report(
        scorecard=scorecard,
        retry_ledger=retry_ledger,
        live_storage_probe=live_storage_probe,
        max_cycles=args.max_cycles,
    )
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.out_md.write_text(render_markdown(report), encoding="utf-8")
    print(
        "policy_evidence_quality_spine_eval_cycles complete: "
        f"verdict={report['final_verdict']} max_cycles={report['max_cycles']}"
    )
    return 1 if report["final_verdict"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
