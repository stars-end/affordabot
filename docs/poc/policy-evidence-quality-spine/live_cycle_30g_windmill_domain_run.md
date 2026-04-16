# Windmill San Jose Live Validation Gate

- generated_at: `2026-04-16T20:04:53.637378+00:00`
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
- idempotency_key: `bd-3wefe.13-live-cycle-30g-20260416200326`
- windmill_job_id: `019d97e4-4e89-f5ba-8970-cd9c6ed0386d`
- final_status: `succeeded`
- scope_totals: `{'scope_total': 1, 'scope_succeeded': 1, 'scope_failed': 0, 'scope_blocked': 0}`
- step_sequence: `['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run']`
- step_sequence_matches_expected: `True`
- contract_metadata_present: `True`

## Storage Evidence Gates
- postgres_rows_written: `passed` (Postgres product rows found)
- pgvector_index_probe: `passed` (document_chunks rows found with embeddings (9584))
- minio_object_refs: `passed` (storage_uri refs present in content_artifacts)
- reader_output_ref: `passed` (content_artifacts rows found)
- analysis_provenance_chain: `passed` (successful analyze command row found)
- quality_gate_blocked_before_index_analyze: `not_applicable` (current run completed past read_fetch; reader quality block was not expected in this success path)
- idempotent_rerun: `passed` (rerun_status=succeeded rerun_quality_blocked=False idempotent_reuse=True)
- stale_drill_stale_but_usable: `passed` ({'idempotency_key': 'bd-3wefe.13-live-cycle-30g-20260416200326:stale_but_usable', 'requested_stale_status': 'stale_but_usable', 'status': 'succeeded', 'scope_succeeded': 1, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'read_fetch', 'index', 'analyze', 'summarize_run'], 'freshness_gate_status': 'succeeded_with_alerts', 'freshness_gate_reason': 'stale_but_usable', 'read_fetch_status': 'succeeded', 'read_fetch_reason': 'raw_scrapes_materialized', 'quality_blocked': False})
- stale_drill_stale_blocked: `passed` ({'idempotency_key': 'bd-3wefe.13-live-cycle-30g-20260416200326:stale_blocked', 'requested_stale_status': 'stale_blocked', 'status': 'failed', 'scope_succeeded': 0, 'scope_failed': 0, 'step_sequence': ['search_materialize', 'freshness_gate', 'summarize_run'], 'freshness_gate_status': 'blocked', 'freshness_gate_reason': 'stale_blocked', 'read_fetch_status': None, 'read_fetch_reason': None, 'quality_blocked': False})
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
| searxng | failed | 0 | 710 | http_error |  |
| exa | succeeded | 5 | 1709 |  | https://records.sanjoseca.gov/Resolutions/RES80069.pdf |
| tavily | succeeded | 5 | 459 |  | https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee |

## DB/Storage Evidence
- probe_status: `queried`
- search_snapshot_rows: `1`
- content_artifact_rows: `19`
- raw_scrape_rows: `23`
- document_chunks_count: `9584`
- document_chunks_with_embedding_count: `9584`
- minio_object_checks: `[{'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/9297ca10ba891b810bedf8ed6b4bf0ddd7e96aea09cc4c79f28955e95b590afb.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/3ce76f23289d3a26eab6bced4dda0aa20f45dfcf8ca652b9de3bd967a410745f.md', 'status': 'not_probeable_without_storage_client'}, {'uri': 'artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/fa41fad8e08bfc60fa8a3dba43212d67ec16a38829d9e7869d261fc830ab4161.md', 'status': 'not_probeable_without_storage_client'}]`

## Manual Audit Notes
- reader_output_excerpt: https://www.sanjoseca.gov/your-government/departments-offices/housing/developers/commercial-linkage-fee: ![Image 1: Skip to page body](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 2: Home](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 3: Residents](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 4: Businesses](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 5: Jobs](https://www.sanjoseca.gov/DefaultContent/Default/_gfx/spacer.gif) ![Image 6: Your Government](https://www.sanjoseca.gov/Default
- reader_quality_note: Reader output was persisted and contained substantive policy text; the analysis remained insufficient for final economic decision-grade output.
- llm_analysis_excerpt: The provided text outlines the Commercial Linkage Fee (CLF) in San José, describing it as an impact fee on non-residential development to fund affordable housing for various income levels. It establishes that fees vary by four geographic subareas and are adjusted annually by the ENR Construction Cost Index. However, the text references a separate Fee Resolution for specific rates and does not list explicit exemptions or precise unit measurements within the provided evidence.
- llm_quality_note: LLM analysis extracted policy facts but fail-closed because the package did not satisfy all economic handoff gates.
- manual_verdict: PASS_DATA_EXTRACTION_FAIL_ECONOMIC_HANDOFF

## Blockers
- none
