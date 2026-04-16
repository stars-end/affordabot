# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-16T19:22:53.665215+00:00`
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
- idempotency_key: `bd-3wefe.13-live-cycle-30b-20260416192004`
- windmill_job_id: `019d97bc-969d-5c9e-df35-3d463da2b0c9`
- final_status: `succeeded`
- scope_totals: `{'scope_total': 1, 'scope_succeeded': 1, 'scope_failed': 0, 'scope_blocked': 0}`
- step_sequence: `['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run']`
- step_sequence_matches_expected: `True`
- contract_metadata_present: `True`

## Storage Evidence Gates
- postgres_rows_written: `passed` (Postgres product rows found)
- pgvector_index_probe: `passed` (document_chunks rows found with embeddings (9167))
- minio_object_refs: `passed` (storage_uri refs present in content_artifacts)
- reader_output_ref: `passed` (content_artifacts rows found)
- analysis_provenance_chain: `passed` (successful analyze command row found)
- quality_gate_blocked_before_index_analyze: `not_applicable` (current run completed past read_fetch; reader quality block was not expected in this success path)
- idempotent_rerun: `passed` (rerun_status=succeeded rerun_quality_blocked=False idempotent_reuse=True)
- stale_drill_stale_but_usable: `passed` ({'idempotency_key': 'bd-3wefe.13-live-cycle-30b-20260416192004:stale_but_usable', 'requested_stale_status': 'stale_but_usable', 'status': 'succeeded', 'scope_succeeded': 1, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run'], 'freshness_gate_status': 'succeeded_with_alerts', 'freshness_gate_reason': 'stale_but_usable', 'read_fetch_status': 'succeeded', 'read_fetch_reason': 'raw_scrapes_materialized', 'quality_blocked': False})
- stale_drill_stale_blocked: `passed` ({'idempotency_key': 'bd-3wefe.13-live-cycle-30b-20260416192004:stale_blocked', 'requested_stale_status': 'stale_blocked', 'status': 'failed', 'scope_succeeded': 0, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'summarize_run'], 'freshness_gate_status': 'blocked', 'freshness_gate_reason': 'stale_blocked', 'read_fetch_status': None, 'read_fetch_reason': None, 'quality_blocked': False})
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
| searxng | failed | 0 | 11 | network_error |  |
| exa | succeeded | 5 | 230 |  | https://records.sanjoseca.gov/Resolutions/RES80069.pdf |
| tavily | succeeded | 5 | 483 |  | https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6 |

## DB/Storage Evidence
- probe_status: `queried`
- search_snapshot_rows: `1`
- content_artifact_rows: `17`
- raw_scrape_rows: `21`
- document_chunks_count: `9167`
- document_chunks_with_embedding_count: `9167`
- minio_object_checks: `[{'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/fa41fad8e08bfc60fa8a3dba43212d67ec16a38829d9e7869d261fc830ab4161.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/0646bb70802cd2631c5aba093b2a5bb46ab49ad51078a679e6df759e8aeb2964.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/2bb766eacf62bf205c992a8414b71603b4b6514f328d7b5ff9e2279aef4fb36f.md', 'status': 'not_probeable_without_storage_client'}]`

## Manual Audit Notes
- reader_output_excerpt: https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6: > NF:VMT:JMD 9/1/2020 1T-36631 / 1735108_43 Council Agenda: 09-01-2020 Item No.: 8.2(c)(2) > DRAFT – Contact the Office of the City Clerk at (408) 535-1260 or CityClerk@sanjoseca.gov for final document. REVISED – City Manager changes made since original posting on 8/21/2020. RESOLUTION NO. _______ A RESOLUTION OF THE COUNCIL OF THE CITY OF SAN JOSE ESTABLISHING THE AMOUNTS OF COMMERCIAL LINKAGE FEES IN ACCORDANCE WITH CHAPTER 5.11 OF TITLE 5 OF THE SAN JOSE MUNICIPAL CODE WHEREAS, the City Counc
- reader_quality_note: Z.ai reader executed and persisted output, but the selected San Jose source resolved to navigation/menu content rather than actual meeting minutes.
- llm_analysis_excerpt: The resolution establishes specific Commercial Linkage Fee rates for various non-residential land use categories in San Jose, calculated per gross square foot. It includes fee schedules differentiated by project size thresholds and establishes a credit mechanism for the demolition of existing non-residential square footage.
- llm_quality_note: Z.ai analysis correctly refused to infer housing signals from insufficient evidence; product mechanics passed, discovery/source targeting did not.
- manual_verdict: PASS_MECHANICS_FAIL_DISCOVERY_QUALITY

## Blockers
- none
