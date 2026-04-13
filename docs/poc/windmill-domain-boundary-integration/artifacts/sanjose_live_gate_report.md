# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-13T16:55:32.604224+00:00`
- feature_key: `bd-9qjof.6`
- harness_version: `2026-04-13.worker-b.v1`
- run_mode: `stub-run`
- classification: `stub_orchestration_pass`
- full_run_readiness: `partial`

## Deployment Surface
- flow_deployed: `True`
- script_deployed: `True`
- flow_unscheduled: `True`

## Manual Run
- attempted: `true`
- idempotency_key: `bd-9qjof.6-live-gate-20260413-165526`
- windmill_job_id: `019d87c4-fca3-6779-c83e-960402d16ccc`
- final_status: `succeeded`
- scope_totals: `{'scope_total': 1, 'scope_succeeded': 1, 'scope_failed': 0, 'scope_blocked': 0}`
- step_sequence: `['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run']`
- step_sequence_matches_expected: `True`
- contract_metadata_present: `True`

## Storage Evidence Gates
- postgres_rows_written: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- pgvector_index_probe: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- minio_object_refs: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- reader_output_ref: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- analysis_provenance_chain: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- idempotent_rerun: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- stale_drill_stale_but_usable: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- stale_drill_stale_blocked: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- failure_handler_drill: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- bridge_mode: `stub` (Path B orchestration skeleton. Product writes belong to affordabot commands.)

## Blockers
- `product_bridge`: flow run is still stub-backed; full product validation not yet possible
- `storage/runtime`: storage/runtime evidence gates are pending
