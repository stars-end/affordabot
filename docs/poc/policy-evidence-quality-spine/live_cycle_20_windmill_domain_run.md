# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-16T09:20:09.544340+00:00`
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
- idempotency_key: `bd-3wefe.13-live-gate-20260416-091847`
- windmill_job_id: `019d9595-fd9c-b4b8-7030-6262102a228a`
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
| searxng | succeeded | 32 | 1329 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |
| exa | succeeded | 5 | 296 |  | https://records.sanjoseca.gov/Resolutions/RES80069.pdf |
| tavily | succeeded | 5 | 510 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |

## DB/Storage Evidence
- probe_status: `queried`
- search_snapshot_rows: `1`
- content_artifact_rows: `3`
- raw_scrape_rows: `21`
- document_chunks_count: `9167`
- document_chunks_with_embedding_count: `9167`
- minio_object_checks: `[{'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/policy_documents/reader_output/71524d4b161bbf71c6145f0549351b0c4a9603630c5e8e7794fb77c552468dd3.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/policy_documents/reader_output/fa41fad8e08bfc60fa8a3dba43212d67ec16a38829d9e7869d261fc830ab4161.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/policy_documents/reader_output/107a066718d26348a7a15e23038bd44a9f2daf227b2e068b92f75dee9d2a06ce.md', 'status': 'not_probeable_without_storage_client'}]`

## Manual Audit Notes
- reader_output_excerpt: https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee: ![Image 1: Skip to page body](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 2: Home](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 3: Residents](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 4: Businesses](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 5: Jobs](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 6: Your Government](https://www.sanjoseca.gov/Default
- reader_quality_note: Z.ai reader executed and persisted output, but the selected San Jose source resolved to navigation/menu content rather than actual meeting minutes.
- llm_analysis_excerpt: The provided evidence describes the San Jose Commercial Linkage Fee (CLF) as a one-time impact fee on non-residential projects—specifically new or existing developments that add gross floor area or change use—to fund affordable housing. Fees vary by four geographic subareas and are adjusted annually using the ENR Construction Cost Index (effective July 1). While the text defines the affected categories and adjustment mechanism, it lacks the specific dollar rates per square foot (table headers are present but values are missing) and does not contain information on household pass-through assumptions.
- llm_quality_note: Z.ai analysis correctly refused to infer housing signals from insufficient evidence; product mechanics passed, discovery/source targeting did not.
- manual_verdict: PASS_MECHANICS_FAIL_DISCOVERY_QUALITY

## Blockers
- `storage/runtime`: storage/runtime evidence gates are pending
