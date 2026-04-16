#!/usr/bin/env python3
"""Verifier for bd-3wefe.13 Agent A data moat/runtime artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.pipeline.policy_evidence_quality_spine import (  # noqa: E402
    build_data_runtime_evidence,
    build_horizontal_matrix,
)


DEFAULT_HORIZONTAL_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "horizontal_matrix.json"
)
DEFAULT_RUNTIME_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "data_runtime_evidence.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-id", default="bd-3wefe.13-baseline", help="Attempt id for retry ledger compatibility.")
    parser.add_argument("--retry-round", type=int, default=0, help="Retry round number (baseline=0).")
    parser.add_argument("--targeted-tweak", default="baseline_no_tweak", help="Targeted tweak label for this run.")
    parser.add_argument("--before-score", type=float, default=None, help="Prior score before this attempt.")
    parser.add_argument(
        "--vertical-case-id",
        default="sj-parking-minimum-amendment",
        help="Case id to run as deep vertical candidate.",
    )
    parser.add_argument(
        "--live-mode",
        choices=("off", "auto"),
        default="off",
        help="off: skip live probe, auto: attempt env-based live blocker detection.",
    )
    parser.add_argument("--horizontal-out", type=Path, default=DEFAULT_HORIZONTAL_OUTPUT)
    parser.add_argument("--runtime-out", type=Path, default=DEFAULT_RUNTIME_OUTPUT)
    return parser.parse_args()


def _gate(status: bool, note: str) -> dict[str, str]:
    return {"status": "passed" if status else "failed", "note": note}


def _quality_fields_present(row: dict[str, object]) -> bool:
    quality = row.get("selected_artifact_quality")
    if not isinstance(quality, dict):
        return False
    required = {
        "selected_artifact_url",
        "selected_artifact_provider",
        "selected_artifact_rank",
        "selected_artifact_official_domain",
        "selected_artifact_artifact_grade",
        "selected_artifact_is_portal",
        "reader_substance_status",
        "provider_quality_score",
        "provider_quality_threshold",
        "provider_quality_status",
        "metric_source",
    }
    return required.issubset(set(quality.keys()))


def main() -> int:
    args = parse_args()
    matrix = build_horizontal_matrix(
        attempt_id=args.attempt_id,
        retry_round=args.retry_round,
        targeted_tweak=args.targeted_tweak,
        before_score=args.before_score,
    )
    runtime = build_data_runtime_evidence(
        matrix=matrix,
        vertical_case_id=args.vertical_case_id,
        live_mode=args.live_mode,
    )

    args.horizontal_out.parent.mkdir(parents=True, exist_ok=True)
    args.runtime_out.parent.mkdir(parents=True, exist_ok=True)
    args.horizontal_out.write_text(json.dumps(matrix, indent=2, sort_keys=True), encoding="utf-8")
    args.runtime_out.write_text(json.dumps(runtime, indent=2, sort_keys=True), encoding="utf-8")

    readiness_counts = matrix["summary"]["readiness_counts"]
    fail_closed_count = int(readiness_counts.get("fail_closed", 0))
    quantified_count = int(readiness_counts.get("quantified_ready", 0))
    score = float(matrix["summary"]["average_score"])
    rows = matrix["rows"]
    quality_fields_count = sum(1 for row in rows if _quality_fields_present(row))
    storage = runtime["storage_readback"]
    orchestration = runtime["orchestration_proof"]
    vertical_quality = runtime.get("vertical_selected_artifact_quality") or {}

    gates = {
        "matrix_has_min_six_cases": _gate(
            int(matrix["summary"]["total_cases"]) >= 6,
            f"total_cases={matrix['summary']['total_cases']}",
        ),
        "matrix_has_min_two_jurisdictions": _gate(
            int(matrix["summary"]["jurisdiction_count"]) >= 2,
            f"jurisdiction_count={matrix['summary']['jurisdiction_count']}",
        ),
        "matrix_has_three_mechanism_families": _gate(
            len(matrix["summary"]["mechanism_family_counts"]) >= 3,
            f"mechanism_families={len(matrix['summary']['mechanism_family_counts'])}",
        ),
        "provider_policy_encoded": _gate(
            bool(matrix["summary"]["provider_policy"]["searxng_required_on_all_rows"]),
            "searxng primary policy present",
        ),
        "vertical_package_persisted": _gate(
            bool(runtime["storage_readback"]["stored"]),
            f"stored={runtime['storage_readback']['stored']}",
        ),
        "vertical_readback_proven": _gate(
            storage["artifact_readback_status"] == "proven",
            f"artifact_readback_status={storage['artifact_readback_status']}",
        ),
        "storage_proof_mode_honest": _gate(
            storage["storage_mode"] in {"in_memory", "real_postgres_minio", "blocked"}
            and storage["proof_status"] in {"in_memory_only", "real_storage_proven", "blocked"}
            and isinstance(storage["real_postgres_minio_proven"], bool)
            and (
                (storage["storage_mode"] == "in_memory" and not storage["real_postgres_minio_proven"])
                or (storage["storage_mode"] != "in_memory")
            ),
            (
                "storage_mode="
                f"{storage['storage_mode']},proof_status={storage['proof_status']},"
                f"real_postgres_minio_proven={storage['real_postgres_minio_proven']}"
            ),
        ),
        "selected_artifact_quality_fields_present": _gate(
            quality_fields_count == len(rows)
            and bool(vertical_quality)
            and str(vertical_quality.get("metric_source", "")).strip() != "",
            f"rows_with_quality={quality_fields_count}/{len(rows)},vertical_quality={bool(vertical_quality)}",
        ),
        "orchestration_proof_honest": _gate(
            orchestration["proof_status"] in {"pass", "blocked", "not_proven"}
            and orchestration["proof_mode"] in {"none", "historical_stub_flow_proof"}
            and not (
                orchestration["proof_mode"] == "historical_stub_flow_proof"
                and orchestration["proof_status"] == "pass"
            ),
            f"proof_status={orchestration['proof_status']},proof_mode={orchestration['proof_mode']}",
        ),
        "score_above_minimum_signal": _gate(score >= 70.0, f"average_score={score}"),
        "contains_both_quantified_and_fail_closed_examples": _gate(
            quantified_count >= 1 and fail_closed_count >= 1,
            f"quantified={quantified_count}, fail_closed={fail_closed_count}",
        ),
    }
    all_passed = all(item["status"] == "passed" for item in gates.values())
    report = {
        "feature_key": "bd-3wefe.13",
        "attempt_id": args.attempt_id,
        "retry_round": args.retry_round,
        "gates": gates,
        "summary": {
            "overall_status": "passed" if all_passed else "failed",
            "average_score": score,
            "horizontal_output": str(args.horizontal_out.relative_to(REPO_ROOT)),
            "runtime_output": str(args.runtime_out.relative_to(REPO_ROOT)),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
