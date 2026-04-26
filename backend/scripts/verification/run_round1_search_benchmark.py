#!/usr/bin/env python3
"""Run Round 1 search benchmark: baseline lane vs SearXNG lane."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
DISCOVERY_ROOT = BACKEND_ROOT / "services" / "discovery"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(DISCOVERY_ROOT) not in sys.path:
    sys.path.insert(0, str(DISCOVERY_ROOT))

from round1_benchmark import (
    BaselineSearchProvider,
    FixtureSearchProvider,
    SearxngSearchProvider,
    resolve_searxng_dependency,
    run_lane_benchmark,
)

DEFAULT_MATRIX_FILE = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "round1-search-benchmark"
    / "matrix.local_government_round1.json"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "round1-search-benchmark"
    / "artifacts"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("live", "fixture"),
        default="live",
        help="Benchmark source mode.",
    )
    parser.add_argument(
        "--matrix-file",
        type=Path,
        default=DEFAULT_MATRIX_FILE,
        help="Deterministic benchmark matrix JSON path.",
    )
    parser.add_argument(
        "--fixture-file",
        type=Path,
        default=(
            BACKEND_ROOT
            / "scripts"
            / "verification"
            / "fixtures"
            / "round1_search_benchmark_fixture.json"
        ),
        help="Fixture payload for --mode fixture.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Artifact output directory.",
    )
    parser.add_argument(
        "--result-count",
        type=int,
        default=10,
        help="Maximum results consumed per query.",
    )
    parser.add_argument(
        "--searxng-base-url",
        default=os.getenv("SEARXNG_BASE_URL", ""),
        help="SearXNG base URL (live mode).",
    )
    parser.add_argument(
        "--zai-api-key",
        default=os.getenv("ZAI_API_KEY", ""),
        help="Optional Z.ai API key for baseline lane.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_matrix(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    matrix = payload.get("matrix", [])
    if not isinstance(matrix, list):
        raise ValueError(f"Invalid matrix payload at {path}")
    return matrix


def _render_markdown_report(report_payload: dict[str, Any]) -> str:
    run = report_payload["run"]
    lanes = report_payload.get("lanes", {})
    lines: list[str] = []
    lines.append("# Round 1 Search Benchmark Report")
    lines.append("")
    lines.append(f"- generated_at: `{run['generated_at']}`")
    lines.append(f"- benchmark_state: `{run['benchmark_state']}`")
    lines.append(f"- mode: `{run['mode']}`")
    lines.append(f"- matrix_queries: `{run['matrix_query_count']}`")
    if run.get("live_run_blocker"):
        lines.append(f"- live_run_blocker: `{run['live_run_blocker']}`")
    lines.append("")
    lines.append("## Lane Metrics")
    lines.append("")
    lines.append(
        "| lane | empty_result_rate | non_empty_result_rate | official_source_top5_rate | useful_url_yield | unique_useful_url_yield | artifact_vs_portal_rate | duplicate_url_rate | median_latency_ms | hard_failure_rate |"
    )
    lines.append(
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    for lane_name in ("baseline", "searxng"):
        lane = lanes.get(lane_name)
        if not lane:
            continue
        metrics = lane["metrics"]
        lines.append(
            f"| {lane_name} | {metrics['empty_result_rate']:.3f} | {metrics['non_empty_result_rate']:.3f} | {metrics['official_source_top5_rate']:.3f} | {metrics['useful_url_yield']:.3f} | {metrics['unique_useful_url_yield']:.3f} | {metrics['artifact_vs_portal_rate']:.3f} | {metrics['duplicate_url_rate']:.3f} | {metrics['median_latency_ms']} | {metrics['hard_failure_rate']:.3f} |"
        )

    lines.append("")
    for lane_name in ("baseline", "searxng"):
        lane = lanes.get(lane_name)
        if not lane:
            continue
        metrics = lane["metrics"]
        lines.append(f"## {lane_name.capitalize()} Failure Modes")
        lines.append("")
        failure_modes = metrics.get("failure_modes", {})
        if not failure_modes:
            lines.append("- none")
        else:
            for mode, count in failure_modes.items():
                lines.append(f"- `{mode}`: {count}")
        lines.append("")
        lines.append(f"## {lane_name.capitalize()} Representative Samples")
        lines.append("")
        for sample in metrics.get("representative_samples", []):
            lines.append(f"- `{sample['query_id']}`: {sample['query']}")
            for result in sample.get("top_results", [])[:3]:
                lines.append(
                    f"  - {result['title'] or '(no title)'} :: {result['url']} :: official={result['is_official']} useful={result['is_useful']}"
                )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


async def _run_live(
    *,
    matrix: list[dict[str, Any]],
    result_count: int,
    zai_api_key: str,
    searxng_base_url: str,
) -> tuple[dict[str, Any], str | None]:
    lanes: dict[str, Any] = {}
    live_run_blocker = resolve_searxng_dependency(searxng_base_url)

    baseline_provider = BaselineSearchProvider(api_key=zai_api_key or None)
    try:
        baseline_result = await run_lane_benchmark(
            lane="baseline",
            matrix=matrix,
            provider=baseline_provider,
            result_count=result_count,
        )
    finally:
        await baseline_provider.close()

    lanes["baseline"] = {
        "metrics": baseline_result.metrics,
        "query_results": baseline_result.query_results,
    }

    if live_run_blocker is None:
        searxng_provider = SearxngSearchProvider(base_url=searxng_base_url)
        try:
            searxng_result = await run_lane_benchmark(
                lane="searxng",
                matrix=matrix,
                provider=searxng_provider,
                result_count=result_count,
            )
        finally:
            await searxng_provider.close()
        lanes["searxng"] = {
            "metrics": searxng_result.metrics,
            "query_results": searxng_result.query_results,
        }

    return lanes, live_run_blocker


async def _run_fixture(
    *,
    matrix: list[dict[str, Any]],
    fixture_file: Path,
    result_count: int,
) -> tuple[dict[str, Any], str | None]:
    payload = _load_json(fixture_file)
    lane_payloads = payload.get("lanes", {})
    baseline_map = lane_payloads.get("baseline", {}).get("results_by_query_id", {})
    searxng_map = lane_payloads.get("searxng", {}).get("results_by_query_id", {})

    baseline_provider = FixtureSearchProvider(results_by_query_id=baseline_map)
    searxng_provider = FixtureSearchProvider(results_by_query_id=searxng_map)

    try:
        baseline_result = await run_lane_benchmark(
            lane="baseline",
            matrix=matrix,
            provider=baseline_provider,
            result_count=result_count,
        )
        searxng_result = await run_lane_benchmark(
            lane="searxng",
            matrix=matrix,
            provider=searxng_provider,
            result_count=result_count,
        )
    finally:
        await baseline_provider.close()
        await searxng_provider.close()

    lanes = {
        "baseline": {
            "metrics": baseline_result.metrics,
            "query_results": baseline_result.query_results,
        },
        "searxng": {
            "metrics": searxng_result.metrics,
            "query_results": searxng_result.query_results,
        },
    }
    return lanes, None


async def _async_main(args: argparse.Namespace) -> int:
    matrix = _load_matrix(args.matrix_file)
    generated_at = datetime.now(timezone.utc).isoformat()

    if args.mode == "fixture":
        lanes, live_run_blocker = await _run_fixture(
            matrix=matrix,
            fixture_file=args.fixture_file,
            result_count=args.result_count,
        )
        benchmark_state = "round1_reviewable"
    else:
        lanes, live_run_blocker = await _run_live(
            matrix=matrix,
            result_count=args.result_count,
            zai_api_key=args.zai_api_key,
            searxng_base_url=args.searxng_base_url,
        )
        benchmark_state = (
            "benchmark_harness_ready_live_run_blocked"
            if live_run_blocker
            else "round1_reviewable"
        )

    report_payload = {
        "schema_version": "1.0",
        "feature_key": "bd-vho5t.1",
        "run": {
            "generated_at": generated_at,
            "mode": args.mode,
            "benchmark_state": benchmark_state,
            "matrix_query_count": len(matrix),
            "live_run_blocker": live_run_blocker,
            "matrix_file": str(args.matrix_file),
            "result_count": args.result_count,
        },
        "lanes": lanes,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = args.output_dir / f"round1_search_benchmark_{ts}.json"
    md_path = args.output_dir / f"round1_search_benchmark_{ts}.md"
    json_path.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown_report(report_payload), encoding="utf-8")

    print(f"[round1-benchmark] state={benchmark_state}")
    print(f"[round1-benchmark] json={json_path}")
    print(f"[round1-benchmark] markdown={md_path}")
    if live_run_blocker:
        print(f"[round1-benchmark] blocker={live_run_blocker}")
        return 2
    return 0


def main() -> int:
    args = _parse_args()
    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
