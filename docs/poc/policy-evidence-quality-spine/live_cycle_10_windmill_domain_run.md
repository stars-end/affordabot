# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-16T08:11:56.338557+00:00`
- feature_key: `bd-3wefe.13`
- harness_version: `2026-04-13.worker-b.v2`
- run_mode: `backend-endpoint-run`
- classification: `failed_run`
- full_run_readiness: `partial`

## Deployment Surface
- flow_deployed: `True`
- script_deployed: `True`
- flow_unscheduled: `True`

## Manual Run
- attempted: `true`
- idempotency_key: `bd-3wefe.13-live-gate-20260416-081003`
- windmill_job_id: `019d9557-11b4-9cea-38fa-818cd959f02e`
- final_status: `failed`
- scope_totals: `{'scope_total': 1, 'scope_succeeded': 0, 'scope_failed': 1, 'scope_blocked': 0}`
- step_sequence: `['run_scope_pipeline']`
- step_sequence_matches_expected: `False`
- contract_metadata_present: `True`

## Storage Evidence Gates
- postgres_rows_written: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- pgvector_index_probe: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- minio_object_refs: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- reader_output_ref: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- analysis_provenance_chain: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- quality_gate_blocked_before_index_analyze: `not_applicable` (current run completed past read_fetch; reader quality block was not expected in this success path)
- idempotent_rerun: `pending` (rerun_status=failed rerun_quality_blocked=False idempotent_reuse=False)
- stale_drill_stale_but_usable: `failed` ({'idempotency_key': 'bd-3wefe.13-live-gate-20260416-081003:stale_but_usable', 'requested_stale_status': 'stale_but_usable', 'status': 'failed', 'scope_succeeded': 0, 'scope_failed': 1, 'step_sequence': ['run_scope_pipeline'], 'freshness_gate_status': None, 'freshness_gate_reason': None, 'read_fetch_status': None, 'read_fetch_reason': None, 'quality_blocked': False})
- stale_drill_stale_blocked: `passed` ({'idempotency_key': 'bd-3wefe.13-live-gate-20260416-081003:stale_blocked', 'requested_stale_status': 'stale_blocked', 'status': 'failed', 'scope_succeeded': 0, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'summarize_run'], 'freshness_gate_status': 'blocked', 'freshness_gate_reason': 'stale_blocked', 'read_fetch_status': None, 'read_fetch_reason': None, 'quality_blocked': False})
- failure_handler_drill: `not_run` (failure injection is a separate pre-schedule gate; this San Jose product path run verified the native failure handler surface was configured)
- bridge_mode: `unknown` ()

## Backend Endpoint Readiness
- status: `ready_for_opt_in`
- note: backend endpoint config is present and local mock probe passed
- missing_inputs: `[]`
- local_mock_probe: `{'status': 'passed', 'note': 'local mock backend endpoint probe passed'}`

## Search Provider Bakeoff
| Provider | Status | Result Count | Latency (ms) | Failure Class | Top URL |
|---|---:|---:|---:|---|---|
| searxng | succeeded | 30 | 1619 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |
| exa | succeeded | 5 | 1492 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |
| tavily | succeeded | 5 | 1865 |  | https://sanjose.legistar.com/gateway.aspx?m=l&id=/matter.aspx?key=15360 |

## DB/Storage Evidence
- probe_status: `probe_failed`
- search_snapshot_rows: `0`
- content_artifact_rows: `0`
- raw_scrape_rows: `0`
- document_chunks_count: `0`
- document_chunks_with_embedding_count: `0`
- minio_object_checks: `[]`

## Manual Audit Notes
- reader_output_excerpt: -
- reader_quality_note: Reader output evidence was not available in the DB probe.
- llm_analysis_excerpt: -
- llm_quality_note: LLM analysis excerpt was not available in the run payload.
- manual_verdict: PENDING_MANUAL_AUDIT

## Blockers
- `storage/runtime`: DB/storage probe unavailable
- `storage/runtime`: storage/runtime evidence gates are pending
