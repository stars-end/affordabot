# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-16T06:29:51.678182+00:00`
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
- idempotency_key: `bd-3wefe.13-live-cycle-06-20260416`
- windmill_job_id: `019d94f9-c6fa-9aab-f6e7-eca32b5b951f`
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
| searxng | failed | 0 | 732 | http_error |  |
| exa | succeeded | 5 | 1035 |  | https://www.researchgate.net/publication/237682174_The_Effects_of_Impact_Fees_on_the_Price_of_Housing_and_Land_a_Literature_Review |
| tavily | succeeded | 5 | 1230 |  | http://www.impactfees.com/publications%20pdf/Ihlanfeldt_Shaughnessy.pdf |

## DB/Storage Evidence
- probe_status: `not_configured`
- search_snapshot_rows: `0`
- content_artifact_rows: `0`
- raw_scrape_rows: `0`
- document_chunks_count: `0`
- document_chunks_with_embedding_count: `0`
- minio_object_checks: `[]`

## Manual Audit Notes
- reader_output_excerpt: -
- reader_quality_note: Z.ai reader executed and persisted output, but the selected San Jose source resolved to navigation/menu content rather than actual meeting minutes.
- llm_analysis_excerpt: The provided text reviews theoretical frameworks and empirical literature regarding the impact and incidence of impact fees and linkage fees. Theoretically, in scenarios with fungible jurisdictions and widespread exaction, consumers are predicted to bear 'all or most' of the fee burden. The text summarizes empirical studies (e.g., Somerville and Mayer, Singell and Lillydahl) but describes their findings qualitatively (e.g., 'small effect,' 'large differential,' 'difficult to understand') rather than providing specific quantitative incidence estimates, pass-through rates, or numerical coefficients. Consequently, the text does not contain the quantitative empirical evidence required for a prec
- llm_quality_note: Z.ai analysis correctly refused to infer housing signals from insufficient evidence; product mechanics passed, discovery/source targeting did not.
- manual_verdict: PASS_MECHANICS_FAIL_DISCOVERY_QUALITY

## Blockers
- `storage/runtime`: DB/storage probe unavailable
- `storage/runtime`: storage/runtime evidence gates are pending
