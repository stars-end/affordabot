# Policy Evidence Quality Spine (`bd-3wefe.13`)

This lane evaluates whether a vertical package is ready to feed canonical
economic analysis and admin/frontend read models.

## Artifacts

- `artifacts/horizontal_matrix.json`
- `artifacts/data_runtime_evidence.json`
- `artifacts/quality_spine_scorecard.json`
- `artifacts/quality_spine_report.md`
- `artifacts/retry_ledger.json`

## Current verdict

- overall_verdict: `partial`
- failed_categories: `0`
- not_proven_categories: `Windmill/orchestration, LLM narrative`

The current deterministic quality-spine pass has no failed data/economic
quality categories. Remaining `not_proven` categories are live
Windmill/orchestration ids and live LLM narrative evidence, not data-quality
failures.

## Matrix source

- mode: `agent_a_horizontal_matrix`
- path: `docs/poc/policy-evidence-quality-spine/artifacts/horizontal_matrix.json`
- used_package_id: `pkg-sj-parking-minimum-amendment`

## Validation

```bash
cd backend
poetry run pytest tests/services/pipeline/test_policy_evidence_quality_spine_economics.py
poetry run python scripts/verification/verify_policy_evidence_quality_spine_economics.py
```
