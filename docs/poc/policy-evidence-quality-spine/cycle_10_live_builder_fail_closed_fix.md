# Cycle 10 - Live San Jose Builder Fail-Closed Fix

- Date: `2026-04-16`
- Feature key: `bd-3wefe.13`
- Live artifact: `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_10_windmill_domain_run.json`
- Scope: deployed Railway dev backend + Windmill backend-endpoint flow

## Goal

Run a real San Jose live cycle against deployed backend code after adding structured-source enrichment and economic trace hooks.

## Inputs

- Backend deployment SHA before fix: `a33159d`
- Windmill flow: `f/affordabot/pipeline_daily_refresh_domain_boundary__flow`
- Backend command endpoint: `/cron/pipeline/domain/run-scope`
- Private SearXNG endpoint: Railway-hosted SearXNG search endpoint
- Search query: `San Jose Resolution 79705 commercial linkage fee affordable housing impact fee per square foot staff report`
- Analysis question: evaluate development-cost and cost-of-living pass-through only from source-backed facts, requesting secondary research for unsupported assumptions.

## Observed Result

The live Windmill flow reached the deployed backend but failed at backend package materialization:

- Windmill job id: `019d9557-11b4-9cea-38fa-818cd959f02e`
- Classification: `failed_run`
- Backend HTTP status: `400`
- Backend validation error: `PolicyEvidencePackage` rejected `blocking_gate_present`

The search-provider bakeoff was useful:

- Private SearXNG returned 30 results and surfaced the San Jose Commercial Linkage Fee page as top result.
- Exa returned the same San Jose city page plus a published San Jose document URL.
- Tavily returned a Legistar matter gateway plus the San Jose city page and richer extracted fee snippets.

## Root Cause

`PolicyEvidencePackageBuilder` could create a `gate_report.blocking_gate` for reader-substance failure while still setting `economic_handoff_ready=true`. The schema correctly rejects handoff-ready packages with a blocking gate. The builder was wrong: bad evidence should become a fail-closed, persisted package, not a 400.

## Code/Config Tweak

Updated `backend/services/pipeline/policy_evidence_package_builder.py` so reader-substance gate failures are included in `has_blocking_gate` before computing:

- `gate_report.verdict`
- `gate_projection.runtime_sufficiency_state`
- `economic_handoff_ready`
- `insufficiency_reasons`

Added regression coverage in `backend/tests/services/pipeline/test_policy_evidence_package_builder.py`:

- `test_builder_fails_closed_instead_of_schema_error_when_reader_gate_blocks_quantified_candidate`

## Verification

Commands executed:

```bash
cd backend
poetry run pytest tests/services/pipeline/test_policy_evidence_package_builder.py \
  tests/services/pipeline/test_structured_source_enrichment.py \
  tests/services/pipeline/test_bridge_runtime.py \
  tests/services/pipeline/test_policy_evidence_quality_spine_economics.py \
  tests/services/pipeline/test_policy_evidence_quality_spine_eval_cycles.py -q
poetry run ruff check services/pipeline/policy_evidence_package_builder.py \
  tests/services/pipeline/test_policy_evidence_package_builder.py
```

Results:

- `55 passed`
- Ruff: `All checks passed`

## Gate Delta

- `D2 scraped evidence quality`: still not manually passed; live search provider evidence is useful but selected-reader package did not complete.
- `D4 unified package identity/provenance`: improved from runtime exception risk to fail-closed packageability after redeploy.
- `D5 storage/readback`: not proven in this cycle because package materialization failed before persistence.
- `E2 sufficiency gate`: improved; reader-gate failure now becomes a backend-authored fail-closed state rather than an unstructured runtime error.

## Next Cycle

Redeploy backend with the builder fix and rerun the same San Jose live cycle as Cycle 11. Expected improvement: the pipeline should either persist a fail-closed package with explicit blocker reasons, or proceed into storage/economic read-model gates if reader quality passes.
