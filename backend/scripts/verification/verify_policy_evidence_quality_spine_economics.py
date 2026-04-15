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
        "",
        "## Current verdict",
        "",
        f"- overall_verdict: `{scorecard['overall_verdict']}`",
        f"- failed_categories: `{len(scorecard['failure_classification']['failed_categories'])}`",
        f"- not_proven_categories: `{', '.join(scorecard['failure_classification']['not_proven_categories']) or 'none'}`",
        "",
        "The current deterministic quality-spine pass has no failed data/economic",
        "quality categories. Remaining `not_proven` categories are live",
        "Windmill/orchestration ids and live LLM narrative evidence, not data-quality",
        "failures.",
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
        "poetry run pytest tests/services/pipeline/test_policy_evidence_quality_spine_economics.py",
        "poetry run python scripts/verification/verify_policy_evidence_quality_spine_economics.py",
        "```",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    *,
    matrix_path: Path,
    runtime_path: Path,
    out_dir: Path,
    readme_path: Path,
) -> dict[str, Any]:
    matrix_payload, matrix_mode = _load_matrix(matrix_path, runtime_path)
    service = PolicyEvidenceQualitySpineEconomicsService()
    evaluation = service.evaluate(
        matrix_input=MatrixInput(
            payload=matrix_payload,
            source_path=_repo_relative(matrix_path),
            source_mode=matrix_mode,
        )
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    scorecard_path = out_dir / "quality_spine_scorecard.json"
    report_path = out_dir / "quality_spine_report.md"
    retry_path = out_dir / "retry_ledger.json"

    scorecard_path.write_text(
        json.dumps(evaluation["scorecard"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(
        service.render_markdown_report(evaluation=evaluation),
        encoding="utf-8",
    )
    retry_path.write_text(
        json.dumps(evaluation["retry_ledger"], indent=2, ensure_ascii=False) + "\n",
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
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    evaluation = run(
        matrix_path=args.matrix,
        runtime_path=args.runtime,
        out_dir=args.out_dir,
        readme_path=args.readme,
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
