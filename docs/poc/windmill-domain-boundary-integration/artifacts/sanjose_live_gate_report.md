# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-14T01:31:41.234673+00:00`
- feature_key: `bd-9qjof.8`
- harness_version: `2026-04-13.worker-b.v2`
- run_mode: `backend-endpoint-run`
- classification: `full_product_pass`
- full_run_readiness: `ready`

## Deployment Surface
- flow_deployed: `True`
- script_deployed: `True`
- flow_unscheduled: `True`

## Manual Run
- attempted: `true`
- idempotency_key: `bd-9qjof.8-live-gate-20260414-012813`
- windmill_job_id: `019d899a-75c2-9a90-2307-f6d45d8185dc`
- final_status: `succeeded`
- scope_totals: `{'scope_total': 1, 'scope_succeeded': 1, 'scope_failed': 0, 'scope_blocked': 0}`
- step_sequence: `['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run']`
- step_sequence_matches_expected: `True`
- contract_metadata_present: `True`

## Storage Evidence Gates
- postgres_rows_written: `passed` (Postgres product rows found)
- pgvector_index_probe: `passed` (document_chunks rows found with embeddings (3533))
- minio_object_refs: `passed` (storage_uri refs present in content_artifacts)
- reader_output_ref: `passed` (content_artifacts rows found)
- analysis_provenance_chain: `passed` (successful analyze command row found)
- quality_gate_blocked_before_index_analyze: `not_applicable` (current run completed past read_fetch; reader quality block was not expected in this success path)
- idempotent_rerun: `passed` (rerun_status=succeeded rerun_quality_blocked=False idempotent_reuse=True)
- stale_drill_stale_but_usable: `passed` ({'idempotency_key': 'bd-9qjof.8-live-gate-20260414-012813:stale_but_usable', 'requested_stale_status': 'stale_but_usable', 'status': 'succeeded', 'scope_succeeded': 1, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run'], 'freshness_gate_status': 'succeeded_with_alerts', 'freshness_gate_reason': 'stale_but_usable', 'read_fetch_status': 'succeeded', 'read_fetch_reason': 'raw_scrapes_materialized', 'quality_blocked': False})
- stale_drill_stale_blocked: `passed` ({'idempotency_key': 'bd-9qjof.8-live-gate-20260414-012813:stale_blocked', 'requested_stale_status': 'stale_blocked', 'status': 'failed', 'scope_succeeded': 0, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'summarize_run'], 'freshness_gate_status': 'blocked', 'freshness_gate_reason': 'stale_blocked', 'read_fetch_status': None, 'read_fetch_reason': None, 'quality_blocked': False})
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
| searxng | failed | 0 | 662 | http_error |  |
| exa | succeeded | 5 | 1073 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/resource-library/council-memos |
| tavily | succeeded | 5 | 511 |  | https://www.legigram.com/places/san-jose |

## DB/Storage Evidence
- probe_status: `queried`
- search_snapshot_rows: `1`
- content_artifact_rows: `7`
- raw_scrape_rows: `7`
- document_chunks_count: `3533`
- document_chunks_with_embedding_count: `3533`
- minio_object_checks: `[{'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/b92d37510cd93d99ca0e5e65bd5e264464b71073ec1e7722f1cdf341e67a3d89.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/a00b0e24aa244f8da659216c1cc5bf55d5ead056e1c28963eb6cb233f47de70c.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/455339488e8ec3cb7d8ae97cd637cbc37de737fbba16e459fdf4b1f5b3d0224f.md', 'status': 'not_probeable_without_storage_client'}]`

## Manual Audit Notes
- reader_output_excerpt: https://sanjose.legistar.com/gateway.aspx?ID=30dfe51f-d23d-4480-a407-44e17ef4c0c3.pdf&M=F: City Council Meeting Minutes # Tuesday, February 10, 2026 1:30 PM Council Chambers Closed Session at 9:30 a.m. MATT MAHAN, MAYOR ROSEMARY KAMEI, DISTRICT 1 PAMELA CAMPOS, DISTRICT 2 ANTHONY TORDILLOS, DISTRICT 3 DAVID COHEN, DISTRICT 4 PETER ORTIZ, DISTRICT 5 MICHAEL MULCAHY, DISTRICT 6 BIEN DOAN, DISTRICT 7 DOMINGO CANDELAS, DISTRICT 8 PAM FOLEY, VICE MAYOR, DISTRICT 9 GEORGE CASEY, DISTRICT 10 San José City Council February 10, 2026 > Page 2 # • Call to Order and Roll Call 9:31 a.m.- Closed Se
- reader_quality_note: Reader output was persisted and provided to analysis.
- llm_analysis_excerpt: The San Jose City Council adopted several housing-related ordinances, including updates to the Inclusionary Housing Ordinance (Item 8.4) to adjust affordability levels and compliance, amendments to the Mobilehome Rent Ordinance (Item 8.6) regarding a one-year exception, and the passage of Ordinance No. 31305 to reduce construction taxes for multifamily housing incentive projects.
- llm_quality_note: LLM analysis produced a substantive answer from persisted evidence.
- manual_verdict: PASS_MANUAL_AUDIT

## Blockers
- none
