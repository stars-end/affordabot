# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-17T04:58:50.028031+00:00`
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
- idempotency_key: `bd-3wefe.13-live-cycle-37-20260417045750`
- windmill_job_id: `019d99cd-9d57-0018-67b9-0ef407fa3d3b`
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
- idempotent_rerun: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- stale_drill_stale_but_usable: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- stale_drill_stale_blocked: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
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
| searxng | failed | 0 | 664 | http_error |  |
| exa | succeeded | 5 | 1138 |  | https://sanjose.legistar.com/LegislationDetail.aspx?GUID=2F1C4308-5A4D-4A7B-8C4D-B4EECA92C889&ID=5463296&Options=&Search= |
| tavily | succeeded | 5 | 1580 |  | https://sanjose.legistar.com/LegislationDetail.aspx?ID=5463296&GUID=2F1C4308-5A4D-4A7B-8C4D-B4EECA92C889&Options=&Search= |

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
