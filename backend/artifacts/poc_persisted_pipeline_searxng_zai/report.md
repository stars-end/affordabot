# Architecture-Locking POC Evidence (bd-jxclm.14.1)

VERDICT: PASS
BEADS_SUBTASK: bd-jxclm.14.1
CONTRACT_VERSION: persisted-pipeline.v1
ZAI_DIRECT_SEARCH_DEPRECATED: True

## Architecture Decisions Locked

- SearXNG/OSS search is the primary search provider
- Z.ai direct Web Reader (POST /api/paas/v4/reader or /api/coding/paas/v4/reader) is the canonical reader
- Z.ai LLM analysis/synthesis is mockable locally and live-capable when env exists
- Z.ai direct Web Search is DEPRECATED and excluded from product flow
- Backend step responses contain NO retry/DAG fields (no next_recommended_step, max_retries, retry_after_seconds)

## Commands

```bash
python3 backend/scripts/verification/poc_persisted_pipeline_searxng_zai.py \
  --reset --out-dir backend/artifacts/poc_persisted_pipeline_searxng_zai
```

## Persistence Evidence

- SQLite proof DB: `/private/tmp/agents/bd-jxclm.14.1/affordabot/backend/artifacts/poc_persisted_pipeline_searxng_zai/poc.sqlite3`
- Evidence report: `/private/tmp/agents/bd-jxclm.14.1/affordabot/backend/artifacts/poc_persisted_pipeline_searxng_zai/report.md`
- pipeline_runs: 4
- search_result_snapshots: 2
- content_artifacts: 3

## Run Results

| Label | Status | Decision | Step | Snapshot |
| --- | --- | --- | --- | --- |
| baseline | succeeded | fresh_snapshot | finalize | snap_77a7e79cfc8f4b5bbdd0781b575014a4 |
| replay | succeeded | fresh_snapshot | finalize | snap_77a7e79cfc8f4b5bbdd0781b575014a4 |
| zero_results | succeeded | zero_results | finalize | None |
| stale_fallback | succeeded | stale_backed | finalize | snap_b10b8f6c5c734effa8fe4fd20358dbe3 |
| fails_closed | failed | provider_failed_no_fallback | search_materialize | N/A |

## Content Artifacts

| Kind | ID | Bytes | Source |
| --- | --- | --- | --- |
| raw_provider_response | artifact_6a6c16b24a2... | 334 | {"mock":true,"provider":"mock_ |
| reader_markdown | artifact_63950a5b32d... | 235 | {"provider":"mock_reader"} |
| analysis_result | artifact_64ab013b100... | 155 | {"provider":"mock_analysis","s |

## Requirement Checks

- [x] 1_searxng_success_produces_snapshots: True
- [x] 2_zero_results_distinct_from_failure: True
- [x] 3_provider_failure_stale_fallback: True
- [x] 4_provider_failure_fails_closed: True
- [x] 5_zai_reader_endpoint_configurable: True
- [x] 6_reader_output_persisted: True
- [x] 7_analysis_mockable: True
- [x] 8_idempotent_replay_reuses: True
- [x] 9_zai_direct_search_deprecated: True
- [x] three_tables_populated: True

## Provider Shape Checks

- searxng_class_exists: True
- zai_reader_paas_endpoint: True
- zai_reader_coding_endpoint: True
- zai_reader_class_exists: True
- zai_llm_class_exists: True
- mock_analysis_class_exists: True
- zai_direct_search_deprecated: True

## Step Response Contract

Backend step responses conform to:
```json
{
  "contract_version": "persisted-pipeline.v1",
  "run_id": "string",
  "windmill_flow_run_id": "string|null",
  "windmill_job_id": "string|null",
  "step": "search_materialize|read_extract|analyze|finalize",
  "status": "succeeded|failed|blocked",
  "decision": "fresh_snapshot|stale_backed|zero_results|provider_failed_no_fallback|reader_succeeded|reader_failed|analysis_succeeded|analysis_failed",
  "decision_reason": "string",
  "evidence": {},
  "alerts": []
}
```

No `next_recommended_step`, `max_retries`, or `retry_after_seconds` fields.
Windmill owns retry/DAG decisions.
