# Policy Evidence Quality Spine (`bd-3wefe.13`)

This lane evaluates whether a vertical package is ready to feed canonical
economic analysis and admin/frontend read models.

## Artifacts

- `artifacts/horizontal_matrix.json`
- `artifacts/data_runtime_evidence.json`
- `artifacts/quality_spine_scorecard.json`
- `artifacts/quality_spine_report.md`
- `artifacts/retry_ledger.json`
- `artifacts/quality_spine_eval_cycles_report.json`
- `artifacts/quality_spine_eval_cycles_report.md`
- `artifacts/quality_spine_gap_audit.md`
- `artifacts/quality_spine_live_storage_probe.json`

## Current verdict

- overall_verdict: `partial`
- decision_grade_verdict: `not_decision_grade`
- failed_categories: `0`
- not_proven_categories: `storage/read-back, Windmill/orchestration, LLM narrative`
- storage_readback_status: `not_proven`
- storage_readback_note: `Automated deterministic scorecard remains not_proven; manual Railway SSH evidence now proves MinIO artifact readback and pgvector chunks, but exact PolicyEvidencePackage row/current-package linkage is still missing.`
- windmill_orchestration_status: `not_proven`
- windmill_orchestration_note: `Historical Windmill stub proof exists but is not valid for current vertical package.`
- llm_narrative_status: `not_proven`
- llm_narrative_note: `LLM narrative not proven (canonical_llm_run_id_missing; source=quality_spine_deterministic_lane).`
- economic_quality_failing_dimensions: `none`

The current deterministic quality-spine pass has no failed data/economic
quality categories. Retry-3 adds strict category semantics: selected-artifact
search quality can pass only with explicit artifact metrics, while storage
remains `not_proven` until real Postgres/MinIO proof is available for the
current vertical package. Windmill/LLM also remain `not_proven` when evidence
is historical or lacks canonical run ids.

Retry-4 initially found a live MinIO `AccessDenied` blocker. After Railway
Bucket/Console/backend restarts, a manual Railway SSH probe proved the current
fallback artifact can be read from MinIO (`124319` bytes), the raw scrape row
exists, and `3382` pgvector chunks have embeddings for the document id referenced
by the live run. Storage remains `not_proven` because the exact
`PolicyEvidencePackage` row/current-package linkage is still missing, the
`documents` row for that document id was not present, and the live analysis id is
not persisted in `analysis_history`.

The eval-cycle harness supports up to 10 deterministic cycles and keeps
local deterministic proof separate from live-product proof categories.

## Matrix source

- mode: `agent_a_horizontal_matrix`
- path: `docs/poc/policy-evidence-quality-spine/artifacts/horizontal_matrix.json`
- used_package_id: `pkg-sj-parking-minimum-amendment`

## Validation

```bash
cd backend
poetry run pytest tests/services/pipeline/test_policy_evidence_quality_spine_economics.py tests/services/pipeline/test_policy_evidence_quality_spine_eval_cycles.py
poetry run python scripts/verification/verify_policy_evidence_quality_spine_economics.py --max-cycles 10
poetry run python scripts/verification/verify_policy_evidence_quality_spine_eval_cycles.py --max-cycles 10
```
