# Policy Evidence Quality Spine (`bd-3wefe.13`)

This lane evaluates whether a vertical package is ready to feed canonical
economic analysis and admin/frontend read models.

## Current Corpus Handoff

For the current broad local-government data moat work, start with
`data_moat_takeover_handoff_2026-04-22.md`.

Current corpus state is `corpus_ready_with_gaps`, not
`decision_grade_corpus`. The current non-pass corpus gates are:

- `C2`: structured-source breadth/depth is not runtime-proven enough.
- `C13`: most corpus rows still have `orchestration_intent`, not live Windmill
  run/job proof.
- `C14`: non-fee extraction depth still contains cataloged targets that are not
  live-proven.

Do not use the older San Jose vertical artifacts as the product boundary. San
Jose is now a calibrated fixture inside the broader city/county/state corpus
benchmark.

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
- `artifacts/source_identity_rules.json`
- `artifacts/source_freshness_drift_scorecard.json`
- `artifacts/external_source_promotion_register.json`

## Current verdict

- overall_verdict: `partial`
- decision_grade_verdict: `not_decision_grade`
- failed_categories: `0`
- not_proven_categories: `storage/read-back, Windmill/orchestration, LLM narrative`
- storage_readback_status: `not_proven`
- storage_readback_note: `Deterministic in-memory readback is proven, but non-memory Postgres/MinIO storage proof is not provided.`
- windmill_orchestration_status: `not_proven`
- windmill_orchestration_note: `Historical Windmill stub proof exists but is not valid for current vertical package.`
- llm_narrative_status: `not_proven`
- llm_narrative_note: `LLM narrative not proven (canonical_llm_run_id_missing; source=quality_spine_deterministic_lane).`
- economic_quality_failing_dimensions: `none`
- official_source_dominance_status: `pass`
- stale_source_count: `0`
- source_shape_changed_count: `0`
- external_source_promotions: `0`

The current deterministic quality-spine pass has no failed data/economic
quality categories. Retry-3 adds strict category semantics: selected-artifact
search quality can pass only with explicit artifact metrics, while storage
remains `not_proven` until real Postgres/MinIO proof is available for the
current vertical package. Windmill/LLM also remain `not_proven` when evidence
is historical or lacks canonical run ids.

Retry-4 attempted a live Railway-dev backend-network storage proof for the
current vertical package. The probe reached the backend dev runtime and decoded
the package, but MinIO returned `AccessDenied` for the configured bucket before
Postgres/MinIO readback could be proven. This keeps storage `not_proven` and
turns the next step into a runtime configuration gate, not another local fixture
change.

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
