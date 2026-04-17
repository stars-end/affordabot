# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-17T06:19:55.270793+00:00`
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
- idempotency_key: `bd-3wefe.13-live-cycle-42-20260417061813`
- windmill_job_id: `019d9a17-4b5b-efb3-4def-200735fafb1a`
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
| searxng | failed | 0 | 889 | http_error |  |
| exa | succeeded | 5 | 244 |  | https://sanjosespotlight.com/san-jose-tackles-lack-of-parking-after-cutting-requirements/ |
| tavily | succeeded | 5 | 509 |  | https://www.planetizen.com/news/2022/12/120204-san-jose-eliminates-parking-minimums |

## DB/Storage Evidence
- probe_status: `probe_failed`
- search_snapshot_rows: `0`
- content_artifact_rows: `0`
- raw_scrape_rows: `0`
- document_chunks_count: `0`
- document_chunks_with_embedding_count: `0`
- minio_object_checks: `[]`

## Policy Evidence Capture
- scenario: `parking_policy`
- source_family: `parking_policy`
- search_query: San Jose parking minimums ordinance policy action city council
- selected_artifact_url: -
- package_id: `pkg-5cc79df1e9a1067dd990eb9d`
- reader_output_ref: ``
- storage_admin_content_artifact_ids: `[]`
- storage_admin_pipeline_command_ids: `[]`
- semantics_classification: `useful_local_policy_evidence_not_economic_ready`
- observed_useful_local_policy_evidence: `True`
- observed_economic_handoff_ready: `False`
- expected_economic_readiness: `not_required`

## Manual Audit Notes
- reader_output_excerpt: -
- reader_quality_note: Reader output was persisted and provided to analysis.
- llm_analysis_excerpt: A letter dated June 13, 2022, from various advocacy groups to the San Jose City Council urging the adoption of City Council Item 10.3, a Comprehensive Parking Policy and TDM Ordinance, aimed at eliminating parking minimums to reduce housing costs and greenhouse gas emissions.
- llm_quality_note: LLM analysis produced a substantive answer from persisted evidence.
- manual_verdict: PASS_MANUAL_AUDIT

## Blockers
- `storage/runtime`: DB/storage probe unavailable
- `storage/runtime`: storage/runtime evidence gates are pending
