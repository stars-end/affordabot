from services.discovery.classifier_validation import (
    ClassifierAcceptanceGate,
    ClassifierResponse,
    LabeledDiscoveryCandidate,
    build_outcomes,
    evaluate_predictions,
    passes_acceptance_gate,
    recommend_threshold,
    summarize_failure_modes,
    sweep_thresholds,
)


def _candidates():
    return [
        LabeledDiscoveryCandidate(url="https://good-1.gov", expected_scrapable=True),
        LabeledDiscoveryCandidate(url="https://good-2.gov", expected_scrapable=True),
        LabeledDiscoveryCandidate(url="https://bad-1.com", expected_scrapable=False),
        LabeledDiscoveryCandidate(url="https://bad-2.com", expected_scrapable=False),
    ]


def _responses():
    return [
        ClassifierResponse(
            is_scrapable=True,
            confidence=0.90,
            reasoning="official page",
        ),
        ClassifierResponse(
            is_scrapable=True,
            confidence=0.62,
            reasoning="probable page",
        ),
        ClassifierResponse(
            is_scrapable=True,
            confidence=0.58,
            reasoning="ambiguous",
        ),
        ClassifierResponse(
            is_scrapable=False,
            confidence=0.20,
            reasoning="not a source",
        ),
    ]


def test_evaluate_predictions_counts():
    metrics = evaluate_predictions(_candidates(), _responses(), threshold=0.60)
    assert metrics.true_positives == 2
    assert metrics.false_positives == 0
    assert metrics.true_negatives == 2
    assert metrics.false_negatives == 0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0


def test_recommend_threshold_prefers_passing_high_recall():
    sweep = sweep_thresholds(
        candidates=_candidates(),
        responses=_responses(),
        thresholds=[0.55, 0.60, 0.70],
    )
    gate = ClassifierAcceptanceGate(
        min_precision=0.70,
        min_recall=0.70,
        min_negative_rejection_rate=0.70,
        max_false_positive_rate=0.30,
    )
    selected = recommend_threshold(sweep, gate)
    assert selected.threshold == 0.60
    assert passes_acceptance_gate(selected, gate) is True


def test_summarize_failure_modes_includes_fp_and_fn():
    outcomes = build_outcomes(_candidates(), _responses(), threshold=0.70)
    messages = summarize_failure_modes(outcomes)
    assert any("False negatives" in message for message in messages)
