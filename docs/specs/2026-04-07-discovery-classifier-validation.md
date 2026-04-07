# 2026-04-07 Discovery Classifier Validation Contract (bd-gl47f.6)

## Purpose

Define a rerunnable, repo-local validation surface for the existing URL/page classifier in `backend/services/discovery/service.py` and produce the acceptance gate contract that `bd-gl47f.4` should use before creating new discovery sources.

## Evaluation Surface

- Labeled candidate set: `backend/scripts/verification/fixtures/discovery_classifier_eval_set.json`
  - Includes explicit positives (official agenda/minutes/code surfaces)
  - Includes explicit negatives (news/social/event/petition/video surfaces)
- Validation runner: `backend/scripts/verification/validate_discovery_classifier.py`
- Output artifact: `backend/scripts/verification/artifacts/discovery_classifier_validation_report.json`

## Acceptance Gate Recommendation for bd-gl47f.4

Use the classifier only when all of the following hold on the evaluation sweep:

- `precision >= 0.70`
- `recall >= 0.70`
- `negative_rejection_rate >= 0.70`
- `false_positive_rate <= 0.30`

Recommended `min_confidence` from the stubbed baseline sweep: `0.70`.

Per-candidate cron gating contract for the next subtask (`bd-gl47f.4`):

- accept candidate only if `is_scrapable == true` and `confidence >= 0.70`
- if batch-level gate fails, fail closed (no source creation) and report metrics

## Known Failure Modes (Current Baseline)

- Plausible third-party pages can still score above threshold (false positive risk)
  - example class: video/news pages discussing a meeting without hosting canonical agenda/minute documents
- Thin snippets on real official pages can score below threshold (false negative risk)
  - example class: sparse meeting calendar pages with little inline text

## Rerun Commands

From `backend/`:

```bash
python scripts/verification/validate_discovery_classifier.py \
  --fixture scripts/verification/fixtures/discovery_classifier_eval_set.json \
  --responses scripts/verification/fixtures/discovery_classifier_stubbed_responses.json
```

Live classifier run (requires `ZAI_API_KEY` or `OPENROUTER_API_KEY`):

```bash
python scripts/verification/validate_discovery_classifier.py
```
