# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-13T18:39:13.929315+00:00`
- feature_key: `bd-9qjof.6`
- harness_version: `2026-04-13.worker-b.v2`
- run_mode: `stub-run`
- classification: `stub_orchestration_pass`
- full_run_readiness: `partial`

## Deployment Surface
- flow_deployed: `True`
- script_deployed: `True`
- flow_unscheduled: `True`

## Manual Run
- attempted: `true`
- idempotency_key: `bd-9qjof.6-live-gate-20260413-183856`
- windmill_job_id: `019d8823-beaa-4d65-27b8-fc19d6c43537`
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
- idempotent_rerun: `pending` (rerun_status=succeeded idempotent_reuse=False)
- stale_drill_stale_but_usable: `passed` ({'idempotency_key': 'bd-9qjof.6-live-gate-20260413-183856:stale_but_usable', 'requested_stale_status': 'stale_but_usable', 'status': 'succeeded', 'scope_succeeded': 1, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run']})
- stale_drill_stale_blocked: `passed` ({'idempotency_key': 'bd-9qjof.6-live-gate-20260413-183856:stale_blocked', 'requested_stale_status': 'stale_blocked', 'status': 'failed', 'scope_succeeded': 0, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'summarize_run']})
- failure_handler_drill: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- bridge_mode: `stub` (Path B orchestration skeleton. Product writes belong to affordabot commands.)

## Backend Endpoint Readiness
- status: `not_configured`
- note: backend endpoint mode is opt-in and currently not configured
- missing_inputs: `['backend_endpoint_url', 'backend_endpoint_auth_token']`
- local_mock_probe: `{'status': 'skipped', 'note': 'missing required backend endpoint inputs'}`

## Search Provider Bakeoff
| Provider | Status | Result Count | Latency (ms) | Failure Class | Top URL |
|---|---:|---:|---:|---|---|
| searxng | failed | 0 | 673 | http_error |  |
| exa | not_configured | 0 | 0 | missing_secret |  |
| tavily | not_configured | 0 | 0 | missing_secret |  |

## DB/Storage Evidence
- probe_status: `not_configured`
- search_snapshot_rows: `0`
- content_artifact_rows: `0`
- raw_scrape_rows: `0`
- document_chunks_count: `0`
- minio_object_checks: `[]`

## Manual Audit Notes
- reader_output_excerpt: -
- reader_quality_note: -
- llm_analysis_excerpt: -
- llm_quality_note: -
- manual_verdict: PENDING_MANUAL_AUDIT

## Blockers
- `storage/runtime`: DB/storage probe unavailable
- `product_bridge`: flow run is still stub-backed; full product validation not yet possible
- `storage/runtime`: storage/runtime evidence gates are pending
- `product_bridge`: backend endpoint client is not configured for live Windmill validation
