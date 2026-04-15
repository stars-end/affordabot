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
- not_proven_categories: `storage/read-back, Windmill/orchestration, LLM narrative`
- storage_readback_status: `not_proven`
- storage_readback_note: `Deterministic in-memory readback is proven, but non-memory Postgres/MinIO storage proof is not provided.`
- windmill_orchestration_status: `not_proven`
- windmill_orchestration_note: `Historical Windmill stub proof exists but is not valid for current vertical package.`
- llm_narrative_status: `not_proven`
- llm_narrative_note: `LLM narrative not proven (canonical_llm_run_id_missing; source=quality_spine_deterministic_lane).`

The current deterministic quality-spine pass has no failed data/economic
quality categories. Retry-3 adds strict category semantics: selected-artifact
search quality can pass only with explicit artifact metrics, while storage
remains `not_proven` until real Postgres/MinIO proof is available for the
current vertical package. Windmill/LLM also remain `not_proven` when evidence
is historical or lacks canonical run ids.

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
