# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-17T04:13:24.488292+00:00`
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
- idempotency_key: `bd-3wefe.13-live-cycle-34-20260417041200`
- windmill_job_id: `019d99a2-f688-57e4-bbca-5241a52ecb41`
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
- idempotent_rerun: `passed` (rerun_status=succeeded rerun_quality_blocked=False idempotent_reuse=True)
- stale_drill_stale_but_usable: `passed` ({'idempotency_key': 'bd-3wefe.13-live-cycle-34-20260417041200:stale_but_usable', 'requested_stale_status': 'stale_but_usable', 'status': 'succeeded', 'scope_succeeded': 1, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run'], 'freshness_gate_status': 'succeeded_with_alerts', 'freshness_gate_reason': 'stale_but_usable', 'read_fetch_status': 'succeeded', 'read_fetch_reason': 'raw_scrapes_materialized', 'quality_blocked': False})
- stale_drill_stale_blocked: `passed` ({'idempotency_key': 'bd-3wefe.13-live-cycle-34-20260417041200:stale_blocked', 'requested_stale_status': 'stale_blocked', 'status': 'failed', 'scope_succeeded': 0, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'summarize_run'], 'freshness_gate_status': 'blocked', 'freshness_gate_reason': 'stale_blocked', 'read_fetch_status': None, 'read_fetch_reason': None, 'quality_blocked': False})
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
| searxng | failed | 0 | 841 | http_error |  |
| exa | succeeded | 5 | 1455 |  | https://www.sanjoseca.gov/Home/Components/News/News/1683/4765 |
| tavily | succeeded | 5 | 445 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |

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
- reader_quality_note: Reader output was persisted and contained substantive policy text; the analysis remained insufficient for final economic decision-grade output.
- llm_analysis_excerpt: The provided evidence summarizes the process and timeline for San Jose's Commercial Linkage Fee, citing the completion of a Nexus Analysis and a Feasibility Analysis. While these studies utilized updated economic assumptions to calculate fee levels and market viability, the text is a procedural overview. It confirms the studies exist but fails to disclose the specific source-bound economic parameters or data tables necessary for conducting a decision-grade cost-of-living analysis.
- llm_quality_note: LLM analysis extracted policy facts but fail-closed because the package did not satisfy all economic handoff gates.
- manual_verdict: PASS_DATA_EXTRACTION_FAIL_ECONOMIC_HANDOFF

## Blockers
- `storage/runtime`: DB/storage probe unavailable
- `storage/runtime`: storage/runtime evidence gates are pending
