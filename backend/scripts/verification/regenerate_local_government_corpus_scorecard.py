"""Regenerate local-government corpus scorecard/report from Windmill overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from services.pipeline.local_government_corpus_benchmark import (
    LocalGovernmentCorpusBenchmarkService,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MATRIX_PATH = (
    ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "local_government_corpus_matrix.json"
)
DEFAULT_WINDMILL_ORCHESTRATION_PATH = (
    ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "local_government_corpus_windmill_orchestration.json"
)
DEFAULT_SCORECARD_PATH = (
    ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "local_government_corpus_scorecard.json"
)
DEFAULT_REPORT_PATH = (
    ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "local_government_corpus_report.md"
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object JSON at {path}")
    return payload


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _repo_relative(path: Path) -> str:
    absolute = path.resolve()
    try:
        return absolute.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(absolute)


def _live_attempt_rows(artifact: dict[str, Any]) -> list[str]:
    rows: set[str] = set()
    attempts = artifact.get("attempts")
    if not isinstance(attempts, list):
        return []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        row_id = str(attempt.get("corpus_row_id") or "")
        if not row_id:
            continue
        status = str(attempt.get("status") or "").lower()
        if status not in {"proven", "live_proven"}:
            continue
        run_id = str(attempt.get("windmill_run_id") or attempt.get("run_id") or "")
        job_id = str(attempt.get("windmill_job_id") or attempt.get("job_id") or "")
        if not run_id or not job_id:
            continue
        if run_id.startswith("wm::") or job_id.startswith("wm-job::"):
            continue
        rows.add(row_id)
    return sorted(rows)


def _blocked_attempt_rows(artifact: dict[str, Any]) -> list[str]:
    rows: set[str] = set()
    attempts = artifact.get("attempts")
    if not isinstance(attempts, list):
        return []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        row_id = str(attempt.get("corpus_row_id") or "")
        if not row_id:
            continue
        status = str(attempt.get("status") or "").lower()
        blocker_class = str(attempt.get("blocker_class") or "")
        if status == "blocked" or blocker_class:
            rows.add(row_id)
    return sorted(rows)


def _row_id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        row_id = str(item or "").strip()
        if row_id:
            rows.append(row_id)
    return rows


def _overlay_burndown_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    post_metrics = artifact.get("post_metrics")
    if not isinstance(post_metrics, dict):
        post_metrics = {}

    seeded_placeholder_rows = _row_id_list(post_metrics.get("seeded_placeholder_rows"))
    missing_live_refs_rows = _row_id_list(post_metrics.get("missing_live_refs_rows"))
    blocker_rows = post_metrics.get("blocker_rows")
    blocker_row_count = len(blocker_rows) if isinstance(blocker_rows, list) else 0
    next_target_rows = seeded_placeholder_rows[:5]
    if not next_target_rows:
        next_target_rows = missing_live_refs_rows[:5]

    return {
        "seeded_placeholder_rows_remaining": len(seeded_placeholder_rows),
        "seeded_placeholder_rows_sample": seeded_placeholder_rows[:10],
        "missing_live_refs_rows_remaining": len(missing_live_refs_rows),
        "blocked_row_count": blocker_row_count,
        "live_attempt_rows_proven": len(_live_attempt_rows(artifact)),
        "next_seeded_ref_target_rows": next_target_rows,
    }


def _build_artifact_inputs(
    *,
    windmill_orchestration_path: Path,
    windmill_orchestration_artifact: dict[str, Any],
) -> dict[str, Any]:
    return {
        "windmill_orchestration_artifact": _repo_relative(windmill_orchestration_path),
        "windmill_orchestration_digest": _hash_payload(windmill_orchestration_artifact),
        "windmill_orchestration_generated_at": windmill_orchestration_artifact.get(
            "generated_at"
        ),
        "windmill_orchestration_verdict": windmill_orchestration_artifact.get(
            "c13_verdict_candidate"
        ),
        "windmill_live_attempt_rows": _live_attempt_rows(
            windmill_orchestration_artifact
        ),
        "windmill_blocked_attempt_rows": _blocked_attempt_rows(
            windmill_orchestration_artifact
        ),
        "windmill_overlay_burndown_summary": _overlay_burndown_summary(
            windmill_orchestration_artifact
        ),
        "overlay_applied": True,
    }


def run(
    *,
    matrix_path: Path,
    windmill_orchestration_path: Path,
    scorecard_output_path: Path,
    report_output_path: Path,
) -> dict[str, Any]:
    matrix = _load_json(matrix_path)
    windmill_orchestration_artifact = _load_json(windmill_orchestration_path)
    service = LocalGovernmentCorpusBenchmarkService()
    scorecard = service.evaluate(
        matrix=matrix,
        windmill_orchestration_artifact=windmill_orchestration_artifact,
    )
    scorecard["artifact_inputs"] = _build_artifact_inputs(
        windmill_orchestration_path=windmill_orchestration_path,
        windmill_orchestration_artifact=windmill_orchestration_artifact,
    )

    report_markdown = service.render_markdown_report(matrix=matrix, scorecard=scorecard)
    scorecard_output_path.parent.mkdir(parents=True, exist_ok=True)
    report_output_path.parent.mkdir(parents=True, exist_ok=True)
    scorecard_output_path.write_text(
        json.dumps(scorecard, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_output_path.write_text(report_markdown, encoding="utf-8")
    return {
        "scorecard": scorecard,
        "report_markdown": report_markdown,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-path", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument(
        "--windmill-orchestration-path",
        type=Path,
        default=DEFAULT_WINDMILL_ORCHESTRATION_PATH,
    )
    parser.add_argument("--scorecard-out", type=Path, default=DEFAULT_SCORECARD_PATH)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run(
        matrix_path=args.matrix_path,
        windmill_orchestration_path=args.windmill_orchestration_path,
        scorecard_output_path=args.scorecard_out,
        report_output_path=args.report_out,
    )
    c13 = ((result["scorecard"].get("gates") or {}).get("C13") or {})
    metrics = c13.get("metrics") or {}
    print(
        "local_government_corpus_scorecard regenerated: "
        f"c13_status={c13.get('status')} "
        f"seeded_not_live_proven_rows={metrics.get('seeded_not_live_proven_rows')} "
        f"corpus_state={result['scorecard'].get('corpus_state')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
