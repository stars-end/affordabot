# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-16T19:41:51.127616+00:00`
- feature_key: `bd-3wefe.13`
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
- idempotency_key: `bd-3wefe.13-live-cycle-30c-20260416193949`
- windmill_job_id: `019d97ce-b318-ecb3-c432-e102b3aa8450`
- final_status: `succeeded`
- scope_totals: `{'scope_total': 1, 'scope_succeeded': 1, 'scope_failed': 0, 'scope_blocked': 0}`
- step_sequence: `['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run']`
- step_sequence_matches_expected: `True`
- contract_metadata_present: `True`

## Storage Evidence Gates
- postgres_rows_written: `passed` (Postgres product rows found)
- pgvector_index_probe: `passed` (document_chunks rows found with embeddings (9237))
- minio_object_refs: `passed` (storage_uri refs present in content_artifacts)
- reader_output_ref: `passed` (content_artifacts rows found)
- analysis_provenance_chain: `passed` (successful analyze command row found)
- quality_gate_blocked_before_index_analyze: `not_applicable` (current run completed past read_fetch; reader quality block was not expected in this success path)
- idempotent_rerun: `passed` (rerun_status=succeeded rerun_quality_blocked=False idempotent_reuse=True)
- stale_drill_stale_but_usable: `passed` ({'idempotency_key': 'bd-3wefe.13-live-cycle-30c-20260416193949:stale_but_usable', 'requested_stale_status': 'stale_but_usable', 'status': 'succeeded', 'scope_succeeded': 1, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run'], 'freshness_gate_status': 'succeeded_with_alerts', 'freshness_gate_reason': 'stale_but_usable', 'read_fetch_status': 'succeeded_with_alerts', 'read_fetch_reason': 'raw_scrapes_materialized_with_reader_alerts', 'quality_blocked': False})
- stale_drill_stale_blocked: `passed` ({'idempotency_key': 'bd-3wefe.13-live-cycle-30c-20260416193949:stale_blocked', 'requested_stale_status': 'stale_blocked', 'status': 'failed', 'scope_succeeded': 0, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'summarize_run'], 'freshness_gate_status': 'blocked', 'freshness_gate_reason': 'stale_blocked', 'read_fetch_status': None, 'read_fetch_reason': None, 'quality_blocked': False})
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
| searxng | failed | 0 | 1327 | http_error |  |
| exa | succeeded | 5 | 1293 |  | https://www.sanjoseca.gov/your-government/agendas-minutes |
| tavily | succeeded | 5 | 1555 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/resource-library/council-memos |

## DB/Storage Evidence
- probe_status: `queried`
- search_snapshot_rows: `1`
- content_artifact_rows: `18`
- raw_scrape_rows: `22`
- document_chunks_count: `9237`
- document_chunks_with_embedding_count: `9237`
- minio_object_checks: `[{'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/3ce76f23289d3a26eab6bced4dda0aa20f45dfcf8ca652b9de3bd967a410745f.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/fa41fad8e08bfc60fa8a3dba43212d67ec16a38829d9e7869d261fc830ab4161.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/0646bb70802cd2631c5aba093b2a5bb46ab49ad51078a679e6df759e8aeb2964.md', 'status': 'not_probeable_without_storage_client'}]`

## Manual Audit Notes
- reader_output_excerpt: https://sanjose.legistar.com/: | Name | Meeting Date | Image 1: ics | Meeting Time | Meeting Location | Meeting Details | Agenda | Accessible Agenda | Agenda Packet | Minutes | Accessible Minutes | Video | | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | | City Council | 2/17/2026 | Image 2: Export to iCalendar | 1:30 PM | Council Chambers _CANCELED_ | Meeting details | Not available | Not available | Not available | Not available | Not available | Not available | | Miscellaneous Agendas | 2/18/2026 |
- reader_quality_note: Z.ai reader executed and persisted output, but the selected San Jose source did not contain enough substantive policy content for the requested analysis.
- llm_analysis_excerpt: The provided evidence lists the dates, times, locations, and availability of agendas and draft minutes for several San Jose city commissions and committees, including the Housing and Community Development Commission, Neighborhood Services and Education Committee, Rules and Open Government Committee, Planning Director's Hearing, City Council, and Transportation and Environment Committee. However, the evidence consists only of a metadata table and does not contain the actual content or transcripts of the meeting minutes. Consequently, it is impossible to extract or summarize any specific housing-related signals, discussions, or decisions from the meetings.
- llm_quality_note: Z.ai analysis correctly refused to infer housing signals from insufficient evidence; product mechanics passed, discovery/source targeting did not.
- manual_verdict: PASS_MECHANICS_FAIL_DISCOVERY_QUALITY

## Blockers
- none
