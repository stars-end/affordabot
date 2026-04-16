# Cycle 20: Canonical Binding Read Model Fix

Feature-Key: bd-3wefe.13

## Purpose

Cycle 19 taught the domain bridge to project a successful `analyze` step into the policy evidence package:

- `canonical_pipeline_run_id`
- `canonical_pipeline_step_id`
- `canonical_breakdown_ref`

Cycle 20 deployed that bridge and reran the San Jose Commercial Linkage Fee vertical through Windmill, Railway backend, Postgres, MinIO, pgvector, and the admin analysis read model.

## Live Run

- windmill_job_id: `019d9595-fd9c-b4b8-7030-6262102a228a`
- idempotency_key: `bd-3wefe.13-live-gate-20260416-091847`
- backend_run_id: `a599344a-ca06-4d4b-85cf-4e1f47cf15d8`
- package_id: `pkg-189ea06455b12e96370c5ebd`
- selected_url: `https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee`
- step_sequence: `search_materialize -> freshness_gate -> read_fetch -> index -> analyze -> summarize_run`
- final_status: `succeeded`

## Storage Proof

The live storage probe passed:

- Postgres package row linked to backend run: pass
- MinIO reader artifact readback: pass
- MinIO package artifact readback: pass
- pgvector chunks and embeddings: pass
- atomic terminal run state: pass

Artifact:

- `docs/poc/policy-evidence-quality-spine/artifacts/live_cycle_20_storage_probe.json`

## Read Model Finding

The package payload contained the projected canonical analysis identifiers:

- `canonical_pipeline_run_id=a599344a-ca06-4d4b-85cf-4e1f47cf15d8`
- `canonical_pipeline_step_id=4570a0b3-47bf-5a57-b834-71f9aaf4b53f`

The admin read model also observed the same run and step ids from `policy_evidence_packages.package_payload + pipeline_runs.result.analysis`, but still returned:

- `canonical_analysis_binding.status=not_proven`
- blocker: `canonical_llm_run_id_unverified_from_package_payload`

That was a read-model bug, not a storage or bridge bug. The fallback proof path was treating projected ids as unverified even when:

1. the projected run id matched the requested backend run id,
2. the projected step id existed,
3. the pipeline run contained an analysis payload.

## Tweak

`backend/routers/admin.py` now treats the fallback canonical analysis proof as pass when all three conditions above hold.

Expected read-model delta after deployment:

- `gates["LLM narrative"].status`: `not_proven` -> `pass`
- `canonical_analysis_binding.status`: `not_proven` -> `bound`

This only proves that the canonical domain analysis run is bound to the package. It must not make the final economic output decision-grade by itself.

## Validation

Focused local validation:

- `poetry run pytest tests/routers/test_admin_pipeline_read_model.py tests/services/pipeline/test_domain_commands.py tests/services/pipeline/test_structured_source_enrichment.py tests/services/pipeline/test_policy_evidence_quality_spine_economics.py tests/services/pipeline/test_bridge_runtime.py -q` -> 98 passed
- `poetry run ruff check routers/admin.py services/pipeline/domain/commands.py services/pipeline/domain/bridge.py services/pipeline/structured_source_enrichment.py services/pipeline/policy_evidence_quality_spine_economics.py tests/routers/test_admin_pipeline_read_model.py tests/services/pipeline/test_domain_commands.py tests/services/pipeline/test_structured_source_enrichment.py tests/services/pipeline/test_policy_evidence_quality_spine_economics.py tests/services/pipeline/test_bridge_runtime.py` -> passed

## Next Cycle

Cycle 21 should deploy this admin read-model patch and refetch the same package analysis status. It should prove the LLM narrative binding without rerunning the whole Windmill flow.
