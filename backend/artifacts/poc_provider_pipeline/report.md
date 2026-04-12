# Provider Pipeline POC Evidence (bd-jxclm.14.1)

VERDICT: PASS
BEADS_SUBTASK: bd-jxclm.14.1
CONTRACT_VERSION: persisted-pipeline.v1

## Architecture Lock

- SearXNG/OSS search is the primary search provider.
- Z.ai direct Web Reader is the canonical reader provider.
- Z.ai LLM analysis/synthesis is mockable locally and live-capable.
- Z.ai direct Web Search: DEPRECATED (`ZAI_DIRECT_SEARCH_DEPRECATED: True`).

## Checks

- [x] pass1_fresh_search_succeeded: True
- [x] pass1_search_decision_correct: True
- [x] pass2_idempotent_reuse: True
- [x] pass3_zero_results_distinct: True
- [x] pass3_zero_results_decision: True
- [x] pass4_stale_fallback_used: True
- [x] pass4_stale_backed_search: True
- [x] pass5_fails_closed: True
- [x] pass5_provider_failed_no_fallback: True
- [x] all_tables_populated: True
- [x] zai_direct_search_deprecated: True
- [x] no_retry_dag_fields: True

## Row Counts

- pipeline_runs: 5
- search_result_snapshots: 2
- content_artifacts: 3

## Pipeline Runs

| Label | Status | Family |
| --- | --- | --- |
| pass1-fresh-search-read-analyze | completed | san-jose-city-council-minutes |
| pass2-idempotent-replay | completed | san-jose-city-council-minutes |
| pass3-zero-results | completed | san-jose-city-council-minutes |
| pass4-provider-failure-stale-fallback | completed | san-jose-city-council-minutes |
| pass5-provider-failure-fails-closed | failed | san-jose-city-council-minutes-alt |

## Search Snapshots

| Snapshot | Provider | Results | Stale | Status |
| --- | --- | --- | --- | --- |
| snap_d78d8edfc558416... | FixedSearchProvider | 1 | no | succeeded |
| snap_39b8d7d5a7b4469... | FailingSearchProvider | 1 | yes | succeeded |

## Content Artifacts

| Kind | ID (truncated) | Bytes | Meta |
| --- | --- | --- | --- |
| raw_provider_response | artifact_12db3ba09b2... | 334 | {"mock":true,"provider":"mock_reader"} |
| reader_markdown | artifact_7893005aedc... | 235 | {"provider":"mock_reader"} |
| analysis_result | artifact_085d21340d4... | 155 | {"provider":"mock_analysis","summary_preview":"Moc |

## Boundary Notes

- Backend step responses contain NO retry/DAG fields.
- Zero-result search is a distinct decision from provider failure.
- Stale fallback only fires when `allow_stale_fallback=True` AND a fresh snapshot exists.
- Provider failure with no fallback fails closed.
- All provider shapes are mockable; live mode requires env vars.
- Reader endpoint is configurable (paas vs coding) via env.