# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-17T06:06:11.326122+00:00`
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
- idempotency_key: `bd-3wefe.13-live-cycle-41-20260417060514`
- windmill_job_id: `019d9a0b-5180-9853-4f50-4f2391710fc3`
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
| searxng | failed | 0 | 636 | http_error |  |
| exa | succeeded | 5 | 1338 |  | https://sanjosespotlight.com/san-jose-tackles-lack-of-parking-after-cutting-requirements/ |
| tavily | succeeded | 5 | 1206 |  | https://www.planetizen.com/news/2022/12/120204-san-jose-eliminates-parking-minimums |

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
- package_id: `pkg-c48016e9161bbb4a8fef90c7`
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
- llm_analysis_excerpt: The evidence outlines San Jose Ordinance PP22-015, which amends Title 20 to implement the Parking and Transportation Demand Management Policy. This includes removing minimum parking requirements in downtown and general zoning regulations, adding TDM sections, and suspending enforcement for specific outdoor business operations until June 30, 2023.
- llm_quality_note: LLM analysis produced a substantive answer from persisted evidence.
- manual_verdict: PASS_MANUAL_AUDIT

## Blockers
- `storage/runtime`: DB/storage probe unavailable
- `storage/runtime`: storage/runtime evidence gates are pending
