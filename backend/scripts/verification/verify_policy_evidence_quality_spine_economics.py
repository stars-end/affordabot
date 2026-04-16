#!/usr/bin/env python3
"""Verifier for policy evidence quality spine economics (bd-3wefe.13 Agent B)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.pipeline.policy_evidence_quality_spine_economics import (  # noqa: E402
    MatrixInput,
    PolicyEvidenceQualitySpineEconomicsService,
)


DEFAULT_MATRIX_PATH = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "horizontal_matrix.json"
)
DEFAULT_RUNTIME_PATH = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "data_runtime_evidence.json"
)
DEFAULT_OUT_DIR = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
)
DEFAULT_README_PATH = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "README.md"
)
LIVE_STORAGE_PROBE_FILENAME = "quality_spine_live_storage_probe.json"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def _load_matrix(path: Path, runtime_path: Path) -> tuple[dict[str, Any] | None, str]:
    payload = _load_json(path)
    if payload is None:
        return None, "missing"

    runtime = _load_json(runtime_path)
    if isinstance(runtime, dict) and isinstance(runtime.get("vertical_package_payload"), dict):
        payload = {
            **payload,
            "agent_a_runtime_evidence": {
                "path": _repo_relative(runtime_path),
                "vertical_package_payload": runtime["vertical_package_payload"],
                "storage_readback": runtime.get("storage_readback", {}),
                "live_probe": runtime.get("live_probe", {}),
                "orchestration_proof": runtime.get("orchestration_proof", {}),
                "llm_narrative_proof": runtime.get("llm_narrative_proof", {}),
            },
        }
    return payload, "agent_a_horizontal_matrix"


def _write_readme(path: Path, *, scorecard: dict[str, Any]) -> None:
    lines = [
        "# Policy Evidence Quality Spine (`bd-3wefe.13`)",
        "",
        "This lane evaluates whether a vertical package is ready to feed canonical",
        "economic analysis and admin/frontend read models.",
        "",
        "## Artifacts",
        "",
        "- `artifacts/horizontal_matrix.json`",
        "- `artifacts/data_runtime_evidence.json`",
        "- `artifacts/quality_spine_scorecard.json`",
        "- `artifacts/quality_spine_report.md`",
        "- `artifacts/retry_ledger.json`",
        "- `artifacts/quality_spine_eval_cycles_report.json`",
        "- `artifacts/quality_spine_eval_cycles_report.md`",
        "- `artifacts/quality_spine_gap_audit.md`",
        f"- `artifacts/{LIVE_STORAGE_PROBE_FILENAME}`",
        "",
        "## Current verdict",
        "",
        f"- overall_verdict: `{scorecard['overall_verdict']}`",
        f"- failed_categories: `{len(scorecard['failure_classification']['failed_categories'])}`",
        f"- not_proven_categories: `{', '.join(scorecard['failure_classification']['not_proven_categories']) or 'none'}`",
        f"- storage_readback_status: `{scorecard['taxonomy']['storage/read-back']['status']}`",
        f"- storage_readback_note: `{scorecard['taxonomy']['storage/read-back']['details']}`",
        f"- windmill_orchestration_status: `{scorecard['taxonomy']['Windmill/orchestration']['status']}`",
        f"- windmill_orchestration_note: `{scorecard['taxonomy']['Windmill/orchestration']['details']}`",
        f"- llm_narrative_status: `{scorecard['taxonomy']['LLM narrative']['status']}`",
        f"- llm_narrative_note: `{scorecard['taxonomy']['LLM narrative']['details']}`",
        "",
        "The current deterministic quality-spine pass has no failed data/economic",
        "quality categories. Retry-3 adds strict category semantics: selected-artifact",
        "search quality can pass only with explicit artifact metrics, while storage",
        "remains `not_proven` until real Postgres/MinIO proof is available for the",
        "current vertical package. Windmill/LLM also remain `not_proven` when evidence",
        "is historical or lacks canonical run ids.",
        "",
        "Retry-4 attempted a live Railway-dev backend-network storage proof for the",
        "current vertical package. The probe reached the backend dev runtime and decoded",
        "the package, but MinIO returned `AccessDenied` for the configured bucket before",
        "Postgres/MinIO readback could be proven. This keeps storage `not_proven` and",
        "turns the next step into a runtime configuration gate, not another local fixture",
        "change.",
        "",
        "The eval-cycle harness supports up to 10 deterministic cycles and keeps",
        "local deterministic proof separate from live-product proof categories.",
        "",
        "## Matrix source",
        "",
        f"- mode: `{scorecard['matrix_source']['mode']}`",
        f"- path: `{scorecard['matrix_source']['path']}`",
        f"- used_package_id: `{scorecard['matrix_source']['used_package_id']}`",
        "",
        "## Validation",
        "",
        "```bash",
        "cd backend",
        "poetry run pytest tests/services/pipeline/test_policy_evidence_quality_spine_economics.py "
        "tests/services/pipeline/test_policy_evidence_quality_spine_eval_cycles.py",
        "poetry run python scripts/verification/verify_policy_evidence_quality_spine_economics.py --max-cycles 10",
        "poetry run python scripts/verification/verify_policy_evidence_quality_spine_eval_cycles.py --max-cycles 10",
        "```",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _merge_live_storage_probe(
    retry_ledger: dict[str, Any], *, live_storage_probe_path: Path
) -> dict[str, Any]:
    probe = _load_json(live_storage_probe_path)
    if not isinstance(probe, dict):
        return retry_ledger
    attempt_id = str(probe.get("attempt_id") or "")
    if not attempt_id.startswith("bd-3wefe.13-retry-"):
        return retry_ledger
    retry_index = attempt_id.rsplit("-", maxsplit=1)[-1]
    retry_attempt_id = f"retry_{retry_index}"

    attempts = retry_ledger.get("attempts")
    if not isinstance(attempts, list):
        return retry_ledger

    probe_status = str(probe.get("status") or "not_proven")
    blocker = str(probe.get("blocker") or "unknown")
    is_passed = probe_status == "passed"
    retry_attempt = {
        "attempt_id": retry_attempt_id,
        "status": "completed" if is_passed else "blocked",
        "result_verdict": "partial",
        "failed_categories": [],
        "not_proven_categories": ["storage/read-back", "Windmill/orchestration", "LLM narrative"],
        "tweaks_applied": ["railway_dev_current_run_storage_probe"],
        "result_note": (
            "Railway-dev storage probe passed; scorecard still requires regenerated runtime proof linkage."
            if is_passed
            else f"Railway-dev storage probe blocked at {blocker}; see {LIVE_STORAGE_PROBE_FILENAME}."
        ),
        "score_delta": None,
    }

    merged = dict(retry_ledger)
    saw_attempt = False
    merged_attempts = []
    for item in attempts:
        if not isinstance(item, dict):
            continue
        if item.get("attempt_id") == retry_attempt_id:
            merged_attempts.append(retry_attempt)
            saw_attempt = True
        else:
            merged_attempts.append(item)
    if not saw_attempt:
        merged_attempts.append(retry_attempt)
    merged["attempts"] = merged_attempts
    return merged


def run(
    *,
    matrix_path: Path,
    runtime_path: Path,
    out_dir: Path,
    readme_path: Path,
    max_cycles: int,
) -> dict[str, Any]:
    matrix_payload, matrix_mode = _load_matrix(matrix_path, runtime_path)
    service = PolicyEvidenceQualitySpineEconomicsService()
    evaluation = service.evaluate(
        matrix_input=MatrixInput(
            payload=matrix_payload,
            source_path=_repo_relative(matrix_path),
            source_mode=matrix_mode,
        ),
        max_cycles=max_cycles,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    scorecard_path = out_dir / "quality_spine_scorecard.json"
    report_path = out_dir / "quality_spine_report.md"
    retry_path = out_dir / "retry_ledger.json"
    live_storage_probe_path = out_dir / LIVE_STORAGE_PROBE_FILENAME
    retry_ledger = _merge_live_storage_probe(
        evaluation["retry_ledger"],
        live_storage_probe_path=live_storage_probe_path,
    )

    scorecard_path.write_text(
        json.dumps(evaluation["scorecard"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(
        service.render_markdown_report(evaluation=evaluation),
        encoding="utf-8",
    )
    retry_path.write_text(
        json.dumps(retry_ledger, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_readme(readme_path, scorecard=evaluation["scorecard"])
    return evaluation


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix",
        type=Path,
        default=DEFAULT_MATRIX_PATH,
        help="Path to Agent A horizontal matrix artifact.",
    )
    parser.add_argument(
        "--runtime",
        type=Path,
        default=DEFAULT_RUNTIME_PATH,
        help="Path to Agent A data/runtime evidence artifact.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output directory for scorecard/report/retry artifacts.",
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=DEFAULT_README_PATH,
        help="README output path for the quality-spine lane.",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=10,
        help="Maximum deterministic eval cycles to encode in retry ledger (1..10).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    evaluation = run(
        matrix_path=args.matrix,
        runtime_path=args.runtime,
        out_dir=args.out_dir,
        readme_path=args.readme,
        max_cycles=args.max_cycles,
    )
    scorecard = evaluation["scorecard"]
    failures = scorecard["failure_classification"]["failed_categories"]
    print(
        "policy_evidence_quality_spine_economics verification complete: "
        f"verdict={scorecard['overall_verdict']} "
        f"failed={len(failures)} "
        f"matrix_mode={scorecard['matrix_source']['mode']}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
