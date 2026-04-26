# Windmill Domain Boundary Local Integration Evidence

## Run Verdict
- status: `succeeded`

## Evidence Checks
- happy_status: `succeeded`
- rerun_status: `succeeded`
- stale_blocked_status: `blocked`
- rerun_index_idempotent_reuse: `True`
- rerun_chunk_count_stable: `True`
- stale_blocked_short_circuit: `True`
- windmill_refs_propagated: `True`

## Scenario Summaries
- happy_first steps: `search_materialize, freshness_gate, read_fetch, index, analyze, summarize_run`
- happy_rerun steps: `search_materialize, freshness_gate, read_fetch, index, analyze, summarize_run`
- stale_blocked steps: `search_materialize, freshness_gate, summarize_run`

## Notes
- Windmill path uses coarse commands only.
- No external network/database/object/vector service calls were made.
