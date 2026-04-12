# Windmill POC Orchestration Contract (bd-jxclm.14.2)

## Scope

This artifact defines the orchestration-only implementation contract for the
San Jose architecture-locking POC.

It intentionally does not change backend provider/business logic code.

## Ownership Boundary

- Windmill owns:
  - schedule/manual trigger
  - retries, timeout, and branching
  - flow-level observability
- Backend owns:
  - search/read/analyze/finalize decision logic
  - freshness/stale policy
  - all product table/object writes

## Product Flow

Flow: `f/affordabot/pipeline_sanjose_searxng_zai_poc`

Step order:

1. `start_run`
2. `search_materialize` with native retry
3. decision branch on backend `decision`
4. `read_extract` (Z.ai direct reader canonical path)
5. `analyze` (Z.ai LLM canonical path)
6. `finalize_report`

Required branch decisions:

- `fresh_snapshot`
- `stale_backed`
- `zero_results` (fail path)
- `provider_failed_no_fallback` (fail path)

## Deprecation Boundary

Z.ai direct Web Search is outside the product flow.

Canary-only artifact:

- Flow: `f/affordabot/zai_web_search_weekly_canary`
- Schedule: `ops/windmill/f/affordabot/zai_web_search_weekly_canary.schedule.yaml`
- Default: `enabled: false`

## Webhook/On-Demand Trigger Shape

Recommended route contract:

- method: `POST`
- route: `/wm/affordabot/pipeline/sanjose-poc`
- body:
  - `jurisdiction` (optional, default `San Jose, CA`)
  - `windmill_flow_run_id` (optional)
  - `windmill_job_id` (optional)

Auth model:

- Windmill route auth at route layer
- Backend step auth with `CRON_SECRET` headers from `trigger_pipeline_step`

## Syntax Assumption Note

The committed flow uses `branchone` with OpenFlow-style branch list:

- `branches: [{ expr, modules }]`
- `default: [modules]`

Reference:

- https://www.windmill.dev/docs/flows/flow_branches

This PR validates the YAML structure in repo tests by parsing YAML and asserting
the branch/failure wiring. Live `wmill sync` was not executed in this PR, so
final parser compatibility is still a runtime check.
