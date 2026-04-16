# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-16T09:58:35.845696+00:00`
- feature_key: `bd-3wefe.13`
- harness_version: `2026-04-13.worker-b.v2`
- run_mode: `backend-endpoint-run`
- classification: `backend_bridge_surface_ready`
- full_run_readiness: `partial`

## Deployment Surface
- flow_deployed: `True`
- script_deployed: `True`
- flow_unscheduled: `True`

## Manual Run
- attempted: `true`
- idempotency_key: `bd-3wefe.13-live-cycle-25-20260416095637`
- windmill_job_id: `019d95b8-d449-8788-17de-731d14e99b4f`
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
- quality_gate_blocked_before_index_analyze: `not_applicable` (current run completed past read_fetch; reader quality block was not expected in this success path)
- idempotent_rerun: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- stale_drill_stale_but_usable: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- stale_drill_stale_blocked: `pending` (not proven in Windmill stub run; requires Worker A product bridge + live storage adapters)
- failure_handler_drill: `not_run` (failure injection is a separate pre-schedule gate; this San Jose product path run verified the native failure handler surface was configured)
- bridge_mode: `railway_runtime` ()

## Backend Endpoint Readiness
- status: `ready_for_opt_in`
- note: backend endpoint config is present and local mock probe passed
- missing_inputs: `[]`
- local_mock_probe: `{'status': 'passed', 'note': 'local mock backend endpoint probe passed'}`

## Search Provider Bakeoff
| Provider | Status | Result Count | Latency (ms) | Failure Class | Top URL |
|---|---:|---:|---:|---|---|
| searxng | failed | 0 | 680 | http_error |  |
| exa | succeeded | 5 | 1255 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |
| tavily | succeeded | 5 | 442 |  | https://www.sanjoseca.gov/Home/Components/News/News/1801/4699 |

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
- reader_quality_note: Z.ai reader executed and persisted output, but the selected San Jose source resolved to navigation/menu content rather than actual meeting minutes.
- llm_analysis_excerpt: The City of San Jose Resolution establishes Commercial Linkage Fees for various non-residential development categories based on gross square footage. The fees act as a direct cost on developers, ranging from $0.00 to $18.706.00 per square foot depending on use type and size, with credits available for demolished non-residential space. The provided text does not contain evidence or claims regarding household cost-of-living impacts or indirect cost pass-through.
- llm_quality_note: Z.ai analysis correctly refused to infer housing signals from insufficient evidence; product mechanics passed, discovery/source targeting did not.
- manual_verdict: PASS_MECHANICS_FAIL_DISCOVERY_QUALITY

## Blockers
- `storage/runtime`: DB/storage probe unavailable
- `storage/runtime`: storage/runtime evidence gates are pending
