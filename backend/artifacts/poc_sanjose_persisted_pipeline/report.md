# San Jose Persisted Pipeline POC Evidence

VERDICT: PASS
BEADS_SUBTASK: bd-jxclm.12
CONTRACT_VERSION: persisted-pipeline-poc.v1

## Scope

Capture-only vertical slice for San Jose City Council meeting minutes status:
fixed official search materialization, freshness gating, read/fetch/extract,
persisted artifacts, idempotent replay, and stale-backed search failure drill.

## Commands

```bash
python3 backend/scripts/verification/poc_sanjose_persisted_pipeline.py \
  --reset \
  --out-dir backend/artifacts/poc_sanjose_persisted_pipeline
```

## Persistence Evidence

- SQLite proof DB: `/private/tmp/agents/bd-jxclm.12/affordabot/backend/artifacts/poc_sanjose_persisted_pipeline/poc.sqlite3`
- Evidence report: `/private/tmp/agents/bd-jxclm.12/affordabot/backend/artifacts/poc_sanjose_persisted_pipeline/report.md`
- pipeline_runs: 3
- pipeline_steps: 6
- search_result_snapshots: 2
- content_artifacts: 2

## Run Results

| Run | Status | Snapshot | Stale backed | Search reuse | Read reuse |
| --- | --- | --- | --- | --- | --- |
| baseline-materialize | completed | snap_5d48a0592fa14e878914e8cef1464a3b | False | no | False |
| idempotent-replay | completed | snap_5d48a0592fa14e878914e8cef1464a3b | False | snap_5d48a0592fa14e878914e8cef1464a3b | True |
| stale-backed-search-failure-drill | completed | snap_2beb4057a08c4dc9ae618abcd1756414 | True | no | True |

## Content Artifacts

| Kind | Artifact ID | Bytes | Storage URI |
| --- | --- | --- | --- |
| raw_event_json | artifact_4266950495774ea8ab41fe9794c71660 | 899 | `/private/tmp/agents/bd-jxclm.12/affordabot/backend/artifacts/poc_sanjose_persisted_pipeline/object_store/content/san-jose-city-council-minutes:event-7616:v1/raw_event.json` |
| minutes_markdown | artifact_138c1252e62c43218dfe7265e57c43bd | 841 | `/private/tmp/agents/bd-jxclm.12/affordabot/backend/artifacts/poc_sanjose_persisted_pipeline/object_store/content/san-jose-city-council-minutes:event-7616:v1/minutes.md` |

## Checks

- [x] all_runs_completed: True
- [x] four_contract_tables_populated: True
- [x] second_run_reused_search_snapshot: True
- [x] second_run_reused_content_artifacts: True
- [x] failure_drill_stale_backed: True
- [x] failure_drill_completed: True
- [x] content_artifact_pair_written_once: True

## Boundary Notes

- Backend code owns freshness policy, stale fallback, idempotency keys, and
  alert content.
- Windmill/manual trigger is represented by the `triggered_by` field; it
  does not own business decisions.
- A zero-result search is treated as failure, not as a valid empty state.
- The stale-backed drill records provider failure on both the snapshot and
  the step while still completing from the latest fresh snapshot.
