# Windmill Orchestration — Affordabot

## Overview

Windmill is the scheduler of record for affordabot's scheduled jobs.
Backend remains the execution plane; Windmill handles schedule, trigger, and observability.

## Migration from Railway Cron

As of `bd-s8id.3`, scheduling moved from root `railway.toml` Railway Cron to Windmill.

### Job Inventory

| Windmill Job | Former Railway Cron | Schedule | Script Entry |
| --- | --- | --- | --- |
| `discovery_run` | `run_discovery.py` at 0500 UTC | `0 5 * * *` | `python backend/scripts/cron/run_discovery.py` |
| `daily_scrape` | `daily_scrape.py` at 0600 UTC | `0 6 * * *` | `python backend/scripts/cron/run_daily_scrape.py` |
| `rag_spiders` | `run_rag_spiders.py` at 0700 UTC | `0 7 * * *` | `python backend/scripts/cron/run_rag_spiders.py` |
| `universal_harvester` | `run_universal_harvester.py` at 0800 UTC | `0 8 * * *` | `python backend/scripts/cron/run_universal_harvester.py` |
| `manual_substrate_expansion` | On-demand only (no schedule) | Manual trigger | `POST /cron/manual-substrate-expansion` |

### Execution Model

Canonical shared-instance model: Windmill triggers authenticated backend cron endpoints over HTTP.
The backend executes the underlying script synchronously and returns a success/failure payload,
so Windmill preserves final job observability without needing the repository mounted in the worker.

Committed Windmill assets:

- `ops/windmill/wmill.yaml`
- `ops/windmill/f/affordabot/trigger_cron_job.py`
- `ops/windmill/f/affordabot/trigger_pipeline_step.py`
- `ops/windmill/f/affordabot/*__flow/flow.yaml`
- `ops/windmill/f/affordabot/*.schedule.yaml`

Required workspace variables:

- `f/affordabot/BACKEND_PUBLIC_URL`
- `f/affordabot/CRON_SECRET`
- `f/affordabot/SLACK_WEBHOOK_URL`

Slack webhook note:
- `trigger_cron_job` now normalizes accidentally quoted webhook values (for example `"https://hooks.slack..."`) before posting.
- Keep `SLACK_WEBHOOK_URL` as a plain URL string in Windmill to avoid ambiguity.

Alerting follows the same Windmill-script webhook pattern used by Prime's EODHD flows:
- success/failure messages originate from `f/affordabot/trigger_cron_job`
- route them to `#railway-dev-alerts` with the workspace `SLACK_WEBHOOK_URL`
- remove the stale `BACKEND_INTERNAL_URL` variable from the affordabot workspace if it still exists

Automated contract coverage lives in `backend/tests/ops/test_windmill_contract.py` and verifies:
- the committed shared-instance flow/schedule wrappers still point at `f/affordabot/trigger_cron_job`
- the required Windmill variables remain in the contract
- the Slack alert success/failure branches still fire as expected

### Auth Contract

Shared-instance wrappers send:

```
Authorization: Bearer $CRON_SECRET
X-PR-CRON-SECRET: $CRON_SECRET
X-PR-CRON-SOURCE: windmill:f/affordabot/<job>
```

The backend accepts:

- `Authorization: Bearer $CRON_SECRET`
- `X-Cron-Secret: $CRON_SECRET`
- `X-PR-CRON-SECRET: $CRON_SECRET`

All are validated against the backend `CRON_SECRET` environment variable.

### Retired Routes

| Route | Disposition |
| --- | --- |
| Railway Cron scheduling of `/cron/daily-scrape` | Retired — scheduling moved to Windmill |

### Active Routes

All cron trigger endpoints remain live and auth-gated:

| Route | Method | Windmill Job |
| --- | --- | --- |
| `/cron/discovery` | POST | `discovery_run` |
| `/cron/daily-scrape` | POST | `daily_scrape` |
| `/cron/rag-spiders` | POST | `rag_spiders` |
| `/cron/universal-harvester` | POST | `universal_harvester` |
| `/cron/manual-substrate-expansion` | POST | `manual_substrate_expansion` (manual flow only) |

### Persisted Pipeline POC (Windmill-Maximal Orchestration)

The `pipeline_sanjose_searxng_zai_poc` flow is the architecture-locking POC for
`bd-jxclm.14`. It models the intended ownership boundary:

- Windmill owns schedule/manual triggering, retry, timeout, branching, and flow-level observability.
- Backend owns product/domain policy and all writes to product tables/artifacts.

Flow assets:

- `ops/windmill/f/affordabot/pipeline_sanjose_searxng_zai_poc__flow/flow.yaml`
- `ops/windmill/f/affordabot/pipeline_sanjose_searxng_zai_poc.schedule.yaml`
- `ops/windmill/f/affordabot/trigger_pipeline_step.py`
- `ops/windmill/f/affordabot/trigger_pipeline_step.script.yaml`

POC flow shape:

1. `start_run`
2. `search_materialize` (native retry + timeout)
3. `decision_branch` over backend `decision`
4. `read_extract` (Z.ai direct reader canonical path)
5. `analyze` (Z.ai LLM canonical path)
6. `finalize_report`

Expected backend decision branches:

- `fresh_snapshot`
- `stale_backed`
- `zero_results`
- `provider_failed_no_fallback`

Trigger shapes:

- Manual trigger:
  - Windmill UI run surface for `f/affordabot/pipeline_sanjose_searxng_zai_poc`
- Schedule trigger:
  - `pipeline_sanjose_searxng_zai_poc.schedule.yaml` (committed disabled until HITL signoff)
- Webhook/on-demand trigger:
  - recommended pattern is a Windmill HTTP route or webhook bound to the same flow with the same input contract (`jurisdiction`, optional run identifiers)
  - keep auth at Windmill route layer and backend `CRON_SECRET` boundary

Backend contract notes:

`trigger_pipeline_step` targets backend step endpoints only. It does not write to Postgres/MinIO directly.

Assumed response shape for branching:

```json
{
  "contract_version": "persisted-pipeline.v1",
  "run_id": "string",
  "windmill_flow_run_id": "string|null",
  "windmill_job_id": "string|null",
  "step": "search_materialize|read_extract|analyze|finalize_report",
  "status": "succeeded|failed|blocked",
  "decision": "fresh_snapshot|stale_backed|zero_results|provider_failed_no_fallback|reader_succeeded|analysis_succeeded",
  "decision_reason": "string",
  "evidence": {},
  "alerts": []
}
```

OpenFlow reference and syntax note:

- Windmill docs describe `branch one` using an ordered `branches` list with per-branch `expr` + `modules`, plus a `default` branch.
- Reference: `https://www.windmill.dev/docs/flows/flow_branches` (OpenFlow/TS branch-one examples).

This repo validates that shape via parsed YAML tests. We did not run live `wmill sync`
in this PR, so parser compatibility remains a runtime verification item. If parser
wrapping differs, keep branch semantics and only adapt syntax wrappers during rollout.

### Z.ai Direct Web Search Deprecation Boundary

Product pipeline flows must not depend on Z.ai direct Web Search.

A separate canary-only flow is committed for weekly health checks:

- `ops/windmill/f/affordabot/zai_web_search_weekly_canary__flow/flow.yaml`
- `ops/windmill/f/affordabot/zai_web_search_weekly_canary.schedule.yaml`

Policy:

- Product path search provider: OSS/SearXNG
- Product path reader: Z.ai direct Web Reader
- Product path analysis: Z.ai LLM
- Z.ai direct Web Search: deprecated, canary only, disabled by default

### Manual Substrate Expansion Contract

The `manual_substrate_expansion` flow accepts a manifest and forwards it to
`POST /cron/manual-substrate-expansion` using the shared trigger script.

Manifest fields:

- `run_label: string`
- `jurisdictions: string[]`
- `asset_classes: string[]`
- `max_documents_per_source: int (1..100)`
- `run_mode: capture_only|capture_and_ingest`
- `ocr_mode: off|hard_doc_only`
- `sample_size_per_bucket: int (1..10)`
- `notes?: string`

Current backend behavior is a truthful skeleton response plus an immediate
inspection artifact: it returns `run_id`, manifest echo, target estimates,
zero-count capture/ingestion/promotion summaries, `failures`, and an
`inspection_report` block with artifact path for manual review.

## Local Testing

```bash
# Contract tests for the shared-instance wrappers and alert path
cd backend
poetry run pytest tests/ops/test_windmill_contract.py -q
poetry run pytest tests/ops/test_windmill_persisted_pipeline_contract.py -q

# Sync the affordabot workspace assets into the shared Windmill instance
cd ops/windmill
wmill sync push --workspace affordabot

# Test the authenticated trigger endpoint directly
curl -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  https://backend-dev-3d99.up.railway.app/cron/discovery
```

## Manual Operator Run (CLI-Safe)

Use the manual flow from the Windmill UI run surface, or via CLI without `-s`.

```bash
cd ops/windmill
wmill flow run f/affordabot/manual_substrate_expansion \
  -d @/absolute/path/manual-substrate-manifest.json
```

Operator note:
- Do not pass `-s` for this flow path. On older `wmill` CLI builds (for example `1.654.0`), `flow run ... -s` can return a completed-job-not-found style response even when the flow run exists.
- If you hit that symptom, rerun without `-s` and check the run in Windmill UI.
- Prefer `wmill upgrade` before manual flow execution.
- Validate operator output from `trigger_cron_job`: flow-level completion is `status: succeeded`, and backend run identity is in `response.run_id`.
- If `response.status` is `failed`, the flow wiring still executed correctly; fix the manifest inputs (for example jurisdiction/asset coverage) and rerun.

## Rollback

If Windmill parity fails, Railway cron entries remain in git history and can be restored.
The backend cron trigger endpoints remain additive and can still be exercised directly.
