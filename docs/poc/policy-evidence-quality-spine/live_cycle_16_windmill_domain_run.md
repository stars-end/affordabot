# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-16T08:58:58.374785+00:00`
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
- idempotency_key: `bd-3wefe.13-live-gate-20260416-085728`
- windmill_job_id: `019d9582-79a1-3eae-3a58-6421b3d023cd`
- final_status: `succeeded`
- scope_totals: `{'scope_total': 1, 'scope_succeeded': 1, 'scope_failed': 0, 'scope_blocked': 0}`
- step_sequence: `['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run']`
- step_sequence_matches_expected: `True`
- contract_metadata_present: `True`

## Storage Evidence Gates
- postgres_rows_written: `passed` (Postgres product rows found)
- pgvector_index_probe: `passed` (document_chunks rows found with embeddings (9148))
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
| searxng | succeeded | 32 | 1042 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |
| exa | succeeded | 5 | 1100 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |
| tavily | succeeded | 5 | 1253 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |

## DB/Storage Evidence
- probe_status: `queried`
- search_snapshot_rows: `1`
- content_artifact_rows: `2`
- raw_scrape_rows: `20`
- document_chunks_count: `9148`
- document_chunks_with_embedding_count: `9148`
- minio_object_checks: `[{'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/policy_documents/reader_output/fa41fad8e08bfc60fa8a3dba43212d67ec16a38829d9e7869d261fc830ab4161.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/policy_documents/reader_output/107a066718d26348a7a15e23038bd44a9f2daf227b2e068b92f75dee9d2a06ce.md', 'status': 'not_probeable_without_storage_client'}]`

## Manual Audit Notes
- reader_output_excerpt: https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee: ![Image 1: Skip to page body](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 2: Home](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 3: Residents](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 4: Businesses](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 5: Jobs](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 6: Your Government](https://www.sanjoseca.gov/Default
- reader_quality_note: Reader output was persisted and provided to analysis.
- llm_analysis_excerpt: The provided text outlines the San José Commercial Linkage Fee (CLF), a one-time impact fee on non-residential development to fund affordable housing. It specifies affected project categories, the geographic basis for fees, and the adjustment mechanism using the ENR Construction Cost Index, with adjustments effective July 1 annually. However, the specific dollar rates per square foot and household pass-through assumptions are missing.
- llm_quality_note: LLM analysis produced a substantive answer from persisted evidence.
- manual_verdict: PASS_MANUAL_AUDIT

## Blockers
- `storage/runtime`: storage/runtime evidence gates are pending
