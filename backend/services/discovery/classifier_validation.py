"""Validation helpers for discovery URL classifier scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from pydantic import BaseModel, Field


class LabeledDiscoveryCandidate(BaseModel):
    """A discovery candidate with expected ground-truth label."""

    url: str
    page_text: str = ""
    expected_scrapable: bool
    label: str = Field(default="", description="Human-readable reason for label")
    provenance_source: str = Field(
        default="",
        description="Repo path or source backing this label.",
    )
    provenance_note: str = Field(
        default="",
        description="Optional context for how this candidate maps to inventory.",
    )


class EvaluationMetrics(BaseModel):
    threshold: float
    total: int
    positives: int
    negatives: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    negative_rejection_rate: float


class ClassifierAcceptanceGate(BaseModel):
    """Minimum bar required before cron ingestion can trust classifier output."""

    min_precision: float = 0.70
    min_recall: float = 0.70
    min_negative_rejection_rate: float = 0.70
    max_false_positive_rate: float = 0.30


@dataclass(frozen=True)
class CandidateOutcome:
    url: str
    expected_scrapable: bool
    predicted_scrapable: bool
    confidence: float
    reasoning: str


class ClassifierResponse(BaseModel):
    is_scrapable: bool
    confidence: float
    reasoning: str = ""


def evaluate_predictions(
    candidates: Sequence[LabeledDiscoveryCandidate],
    responses: Sequence[ClassifierResponse],
    threshold: float,
) -> EvaluationMetrics:
    if len(candidates) != len(responses):
        raise ValueError("candidates and responses length must match")

    tp = fp = tn = fn = 0
    positives = negatives = 0

    for candidate, response in zip(candidates, responses):
        expected_positive = candidate.expected_scrapable
        predicted_positive = response.is_scrapable and response.confidence >= threshold

        if expected_positive:
            positives += 1
            if predicted_positive:
                tp += 1
            else:
                fn += 1
        else:
            negatives += 1
            if predicted_positive:
                fp += 1
            else:
                tn += 1

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    false_positive_rate = _safe_div(fp, fp + tn)
    negative_rejection_rate = _safe_div(tn, tn + fp)

    return EvaluationMetrics(
        threshold=threshold,
        total=len(candidates),
        positives=positives,
        negatives=negatives,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        false_positive_rate=false_positive_rate,
        negative_rejection_rate=negative_rejection_rate,
    )


def sweep_thresholds(
    candidates: Sequence[LabeledDiscoveryCandidate],
    responses: Sequence[ClassifierResponse],
    thresholds: Iterable[float],
) -> list[EvaluationMetrics]:
    return [evaluate_predictions(candidates, responses, threshold) for threshold in thresholds]


def passes_acceptance_gate(
    metrics: EvaluationMetrics,
    gate: ClassifierAcceptanceGate,
) -> bool:
    return (
        metrics.precision >= gate.min_precision
        and metrics.recall >= gate.min_recall
        and metrics.negative_rejection_rate >= gate.min_negative_rejection_rate
        and metrics.false_positive_rate <= gate.max_false_positive_rate
    )


def recommend_threshold(
    sweep_results: Sequence[EvaluationMetrics],
    gate: ClassifierAcceptanceGate,
) -> EvaluationMetrics:
    if not sweep_results:
        raise ValueError("sweep_results must not be empty")

    passing = [result for result in sweep_results if passes_acceptance_gate(result, gate)]
    if passing:
        # For ingestion gating, prefer the strictest threshold that still passes all guardrails.
        return sorted(
            passing,
            key=lambda result: (result.threshold, result.precision, -result.false_positive_rate),
            reverse=True,
        )[0]

    # Fail-closed fallback: highest precision, then lowest FPR.
    return sorted(
        sweep_results,
        key=lambda result: (result.precision, -result.false_positive_rate, result.threshold),
        reverse=True,
    )[0]


def build_outcomes(
    candidates: Sequence[LabeledDiscoveryCandidate],
    responses: Sequence[ClassifierResponse],
    threshold: float,
) -> list[CandidateOutcome]:
    outcomes: list[CandidateOutcome] = []
    for candidate, response in zip(candidates, responses):
        outcomes.append(
            CandidateOutcome(
                url=candidate.url,
                expected_scrapable=candidate.expected_scrapable,
                predicted_scrapable=response.is_scrapable and response.confidence >= threshold,
                confidence=response.confidence,
                reasoning=response.reasoning,
            )
        )
    return outcomes


def summarize_failure_modes(outcomes: Sequence[CandidateOutcome]) -> list[str]:
    messages: list[str] = []
    false_positives = [item for item in outcomes if item.predicted_scrapable and not item.expected_scrapable]
    false_negatives = [item for item in outcomes if not item.predicted_scrapable and item.expected_scrapable]

    if false_positives:
        fp_examples = ", ".join(item.url for item in false_positives[:3])
        messages.append(
            f"False positives remain for plausible-looking but non-source pages ({fp_examples})."
        )
    if false_negatives:
        fn_examples = ", ".join(item.url for item in false_negatives[:3])
        messages.append(
            f"False negatives remain for valid sources with thin/ambiguous snippets ({fn_examples})."
        )
    if not messages:
        messages.append("No observed false positives/negatives on this evaluation set.")
    return messages


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
