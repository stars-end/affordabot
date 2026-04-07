#!/usr/bin/env python3
"""Evaluate discovery classifier usefulness on labeled candidates."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

sys.path.append(str(Path(__file__).resolve().parents[2]))

from services.discovery.classifier_validation import (
    ClassifierAcceptanceGate,
    ClassifierResponse,
    LabeledDiscoveryCandidate,
    build_outcomes,
    passes_acceptance_gate,
    recommend_threshold,
    summarize_failure_modes,
    sweep_thresholds,
)


DEFAULT_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "discovery_classifier_eval_set.json"
)
DEFAULT_ARTIFACT = (
    Path(__file__).resolve().parent
    / "artifacts"
    / "discovery_classifier_validation_report.json"
)
DEFAULT_THRESHOLDS = (0.50, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument(
        "--thresholds",
        default=",".join(str(v) for v in DEFAULT_THRESHOLDS),
        help="Comma-separated confidence thresholds (e.g. 0.6,0.7,0.8).",
    )
    parser.add_argument(
        "--responses",
        type=Path,
        default=None,
        help="Optional JSON file of DiscoveryResponse payloads keyed by URL.",
    )
    return parser.parse_args()


def load_candidates(path: Path) -> list[LabeledDiscoveryCandidate]:
    payload = json.loads(path.read_text())
    return [LabeledDiscoveryCandidate.model_validate(item) for item in payload]


def parse_thresholds(raw_value: str) -> list[float]:
    values = []
    for token in raw_value.split(","):
        token = token.strip()
        if not token:
            continue
        values.append(float(token))
    if not values:
        raise ValueError("At least one threshold is required")
    return values


def load_stubbed_responses(
    path: Path,
    candidates: Sequence[LabeledDiscoveryCandidate],
) -> list[ClassifierResponse]:
    payload = json.loads(path.read_text())
    by_url = {item["url"]: item["response"] for item in payload}
    responses = []
    for candidate in candidates:
        if candidate.url not in by_url:
            raise ValueError(f"Missing stub response for URL: {candidate.url}")
        responses.append(ClassifierResponse.model_validate(by_url[candidate.url]))
    return responses


async def score_with_live_classifier(
    candidates: Sequence[LabeledDiscoveryCandidate],
) -> list[ClassifierResponse]:
    from services.discovery.service import AutoDiscoveryService

    classifier = AutoDiscoveryService()
    responses: list[ClassifierResponse] = []
    for candidate in candidates:
        raw = await classifier.discover_url(url=candidate.url, page_text=candidate.page_text)
        responses.append(
            ClassifierResponse(
                is_scrapable=raw.is_scrapable,
                confidence=raw.confidence,
                reasoning=raw.reasoning,
            )
        )
    return responses


async def main() -> int:
    args = parse_args()
    thresholds = parse_thresholds(args.thresholds)
    gate = ClassifierAcceptanceGate()
    candidates = load_candidates(args.fixture)

    if args.responses:
        responses = load_stubbed_responses(args.responses, candidates)
    else:
        responses = await score_with_live_classifier(candidates)

    sweep = sweep_thresholds(candidates=candidates, responses=responses, thresholds=thresholds)
    recommendation = recommend_threshold(sweep, gate)
    outcomes = build_outcomes(candidates, responses, threshold=recommendation.threshold)
    failure_modes = summarize_failure_modes(outcomes)
    gate_passes = passes_acceptance_gate(recommendation, gate)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture_path": str(args.fixture),
        "stubbed_responses_path": str(args.responses) if args.responses else None,
        "sample_size": len(candidates),
        "gate_requirements": gate.model_dump(),
        "sweep": [item.model_dump() for item in sweep],
        "recommendation": {
            "min_confidence": recommendation.threshold,
            "passes_acceptance_gate": gate_passes,
            "metrics": recommendation.model_dump(),
        },
        "known_failure_modes": failure_modes,
    }

    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(report, indent=2) + "\n")

    print(
        f"[discovery-classifier] threshold={recommendation.threshold:.2f} "
        f"precision={recommendation.precision:.2f} recall={recommendation.recall:.2f} "
        f"fpr={recommendation.false_positive_rate:.2f} pass={gate_passes}"
    )
    print(f"[discovery-classifier] report={args.artifact}")
    return 0 if gate_passes else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
