# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-16T09:10:36.762193+00:00`
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
- idempotency_key: `bd-3wefe.13-live-gate-20260416-090909`
- windmill_job_id: `019d958d-2c51-5e21-f010-3fb74a514e3b`
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
| searxng | succeeded | 33 | 1272 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |
| exa | succeeded | 5 | 1034 |  | https://records.sanjoseca.gov/Resolutions/RES80069.pdf |
| tavily | succeeded | 5 | 502 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |

## DB/Storage Evidence
- probe_status: `queried`
- search_snapshot_rows: `1`
- content_artifact_rows: `3`
- raw_scrape_rows: `21`
- document_chunks_count: `9167`
- document_chunks_with_embedding_count: `9167`
- minio_object_checks: `[{'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/policy_documents/reader_output/71524d4b161bbf71c6145f0549351b0c4a9603630c5e8e7794fb77c552468dd3.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/policy_documents/reader_output/fa41fad8e08bfc60fa8a3dba43212d67ec16a38829d9e7869d261fc830ab4161.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/policy_documents/reader_output/107a066718d26348a7a15e23038bd44a9f2daf227b2e068b92f75dee9d2a06ce.md', 'status': 'not_probeable_without_storage_client'}]`

## Manual Audit Notes
- reader_output_excerpt: https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6: > NF:VMT:JMD 9/1/2020 1T-36631 / 1735108_43 Council Agenda: 09-01-2020 Item No.: 8.2(c)(2) > DRAFT – Contact the Office of the City Clerk at (408) 535-1260 or CityClerk@sanjoseca.gov for final document. REVISED – City Manager changes made since original posting on 8/21/2020. RESOLUTION NO. _______ A RESOLUTION OF THE COUNCIL OF THE CITY OF SAN JOSE ESTABLISHING THE AMOUNTS OF COMMERCIAL LINKAGE FEES IN ACCORDANCE WITH CHAPTER 5.11 OF TITLE 5 OF THE SAN JOSE MUNICIPAL CODE WHEREAS, the City Counc
- reader_quality_note: Reader output was persisted and provided to analysis.
- llm_analysis_excerpt: San Jose City Council Resolution establishes Commercial Linkage Fees for non-residential development calculated on gross square footage, effective upon adoption of Chapter 5.11 ordinance.
- llm_quality_note: LLM analysis produced a substantive answer from persisted evidence.
- manual_verdict: PASS_MANUAL_AUDIT

## Blockers
- `storage/runtime`: storage/runtime evidence gates are pending
