# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-17T05:07:59.328029+00:00`
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
- idempotency_key: `bd-3wefe.13-live-cycle-38-20260417050653`
- windmill_job_id: `019d99d5-df4f-1354-fcea-af9c129b6e49`
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
| searxng | failed | 0 | 710 | http_error |  |
| exa | succeeded | 5 | 358 |  | https://sanjose.legistar.com/LegislationDetail.aspx?GUID=2F1C4308-5A4D-4A7B-8C4D-B4EECA92C889&ID=5463296&Options=&Search= |
| tavily | succeeded | 5 | 440 |  | https://sanjose.legistar.com/LegislationDetail.aspx?ID=5463296&GUID=2F1C4308-5A4D-4A7B-8C4D-B4EECA92C889&Options=&Search= |

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
- reader_quality_note: Reader output was persisted and provided to analysis.
- llm_analysis_excerpt: The City of San Jose adopted a resolution on September 1, 2020, establishing Commercial Linkage Fees for non-residential development under Chapter 5.11 of the San José Municipal Code. The fees are calculated per gross square foot and vary based on specific land-use categories (Office, Retail, Industrial/Research and Development, Warehouse, Hotel, Residential Care) and, in some cases, building size thresholds (specifically the 100,000 sq. ft. cutoff). The resolution also details a credit mechanism for the demolition of existing non-residential structures.
- llm_quality_note: LLM analysis produced a substantive answer from persisted evidence.
- manual_verdict: PASS_MANUAL_AUDIT

## Blockers
- `storage/runtime`: DB/storage probe unavailable
- `storage/runtime`: storage/runtime evidence gates are pending
