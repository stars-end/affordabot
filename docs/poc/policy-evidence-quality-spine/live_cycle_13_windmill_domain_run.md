# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-16T08:41:42.544749+00:00`
- feature_key: `bd-3wefe.13`
- harness_version: `2026-04-13.worker-b.v2`
- run_mode: `backend-endpoint-run`
- classification: `failed_run`
- full_run_readiness: `partial`

## Deployment Surface
- flow_deployed: `True`
- script_deployed: `True`
- flow_unscheduled: `True`

## Manual Run
- attempted: `true`
- idempotency_key: `bd-3wefe.13-live-gate-20260416-083910`
- windmill_job_id: `019d9571-ba10-6e09-4355-3cc297c83d5a`
- final_status: `failed`
- scope_totals: `{'scope_total': 1, 'scope_succeeded': 0, 'scope_failed': 1, 'scope_blocked': 0}`
- step_sequence: `['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run']`
- step_sequence_matches_expected: `True`
- contract_metadata_present: `True`

## Storage Evidence Gates
- postgres_rows_written: `passed` (Postgres product rows found)
- pgvector_index_probe: `passed` (document_chunks rows found with embeddings (8915))
- minio_object_refs: `passed` (storage_uri refs present in content_artifacts)
- reader_output_ref: `passed` (content_artifacts rows found)
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
| searxng | succeeded | 28 | 3381 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |
| exa | succeeded | 5 | 1175 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |
| tavily | succeeded | 5 | 1320 |  | https://www.biabayarea.org/city-of-san-jose-affordable-housing-impact-fe |

## DB/Storage Evidence
- probe_status: `queried`
- search_snapshot_rows: `1`
- content_artifact_rows: `1`
- raw_scrape_rows: `19`
- document_chunks_count: `8915`
- document_chunks_with_embedding_count: `8915`
- minio_object_checks: `[{'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/policy_documents/reader_output/107a066718d26348a7a15e23038bd44a9f2daf227b2e068b92f75dee9d2a06ce.md', 'status': 'not_probeable_without_storage_client'}]`

## Manual Audit Notes
- reader_output_excerpt: https://siliconvalleyathome.org/resources/commercial-linkage-fees-2/: Commercial Linkage Fees (CLF) are a standard tool used by local communities for generating affordable housing resources. The CLF is similar to other impact fees levied on new development, and helps cover the cost associated with creating new or expanded public facilities to meet the additional demand created by the development, such as parks, schools, libraries and streets. Before levying an impact fee, jurisdictions are required by state law to complete a nexus study that shows the linkage betw
- reader_quality_note: Reader output evidence was not available in the DB probe.
- llm_analysis_excerpt: -
- llm_quality_note: LLM analysis excerpt was not available in the run payload.
- manual_verdict: PENDING_MANUAL_AUDIT

## Blockers
- `storage/runtime`: storage/runtime evidence gates are pending
