# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-14T00:29:06.291737+00:00`
- feature_key: `bd-9qjof.8`
- harness_version: `2026-04-13.worker-b.v2`
- run_mode: `backend-endpoint-run`
- classification: `quality_gate_block_pass`
- full_run_readiness: `ready`

## Deployment Surface
- flow_deployed: `True`
- script_deployed: `True`
- flow_unscheduled: `True`

## Manual Run
- attempted: `true`
- idempotency_key: `bd-9qjof.8-live-gate-20260414-002844`
- windmill_job_id: `019d8963-ff82-df27-0833-dcb21dc5fd47`
- final_status: `failed`
- scope_totals: `{'scope_total': 1, 'scope_succeeded': 0, 'scope_failed': 0, 'scope_blocked': 1}`
- step_sequence: `['search_materialize', 'freshness_gate', 'read_fetch', 'summarize_run']`
- step_sequence_matches_expected: `True`
- contract_metadata_present: `True`

## Storage Evidence Gates
- postgres_rows_written: `not_applicable` (current run intentionally blocked at read_fetch before persistence/index/analyze)
- pgvector_index_probe: `not_applicable` (current run intentionally blocked at read_fetch before persistence/index/analyze)
- minio_object_refs: `not_applicable` (current run intentionally blocked at read_fetch before persistence/index/analyze)
- reader_output_ref: `not_applicable` (current run intentionally blocked at read_fetch before persistence/index/analyze)
- analysis_provenance_chain: `not_applicable` (current run intentionally blocked at read_fetch before persistence/index/analyze)
- quality_gate_blocked_before_index_analyze: `passed` (reader quality gate blocked at read_fetch; index/analyze were not executed)
- idempotent_rerun: `passed` (rerun_status=failed rerun_quality_blocked=True idempotent_reuse=True)
- stale_drill_stale_but_usable: `passed` ({'idempotency_key': 'bd-9qjof.8-live-gate-20260414-002844:stale_but_usable', 'requested_stale_status': 'stale_but_usable', 'status': 'failed', 'scope_succeeded': 0, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'read_fetch', 'summarize_run'], 'freshness_gate_status': 'succeeded_with_alerts', 'freshness_gate_reason': 'stale_but_usable', 'read_fetch_status': 'blocked', 'read_fetch_reason': 'reader_output_insufficient_substance', 'quality_blocked': True})
- stale_drill_stale_blocked: `passed` ({'idempotency_key': 'bd-9qjof.8-live-gate-20260414-002844:stale_blocked', 'requested_stale_status': 'stale_blocked', 'status': 'failed', 'scope_succeeded': 0, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'summarize_run'], 'freshness_gate_status': 'blocked', 'freshness_gate_reason': 'stale_blocked', 'read_fetch_status': None, 'read_fetch_reason': None, 'quality_blocked': False})
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
| exa | succeeded | 5 | 291 |  | https://www.sanjoseca.gov/your-government/agendas-minutes |
| tavily | succeeded | 5 | 569 |  | https://www.sanjoseca.gov/your-government/appointees/city-clerk/council-agendas-minutes/council-agendas |

## DB/Storage Evidence
- probe_status: `queried`
- search_snapshot_rows: `1`
- content_artifact_rows: `3`
- raw_scrape_rows: `3`
- document_chunks_count: `504`
- document_chunks_with_embedding_count: `504`
- minio_object_checks: `[{'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/16361e3a253309a93f50d79af1878bec40d52e306966ea8b021c914894623eb1.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/62bf5da65e99ef25d7ba5a7876c182c8d40fb84e8377857177b4f88970f0fc26.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/beb5625c2920eb405475cd29fcecd1b9eab9f6087c25183754e0267a37c60800.md', 'status': 'not_probeable_without_storage_client'}]`

## Manual Audit Notes
- reader_output_excerpt: https://www.sanjoseca.gov/your-government/appointees/city-clerk/council-agendas-minutes/council-agendas: Council Agendas | City of San José ![Image 1: Skip to page body](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 2: Home](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 3: Residents](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 4: Businesses](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 5: Jobs](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 6: Your Government
- reader_quality_note: Selected San Jose source resolved to navigation/menu content and was blocked by reader quality gate before persistence/index/analyze.
- llm_analysis_excerpt: -
- llm_quality_note: Analysis was intentionally not run because the reader quality gate blocked insufficient source substance.
- manual_verdict: PASS_READER_QUALITY_GATE_BLOCKED_NAV_OUTPUT

## Blockers
- none
