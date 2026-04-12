# Windmill Orchestration — Affordabot

## Overview

Windmill is the scheduler of record for affordabot's scheduled jobs.
Backend remains the execution plane; Windmill handles schedule, trigger, and observability.

## Shared Dev Instance vs Workspace

Windmill dev is a shared Railway-hosted instance:
- `https://server-dev-8d5b.up.railway.app`

This repo targets a specific workspace on that shared instance:
- affordabot assets `f/affordabot/*` -> workspace `affordabot`

Do not assume all repos share one workspace.

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
- `ops/windmill/f/affordabot/*__flow/flow.yaml`
- `ops/windmill/f/affordabot/*.schedule.yaml`

Required workspace variables:

- `f/affordabot/BACKEND_PUBLIC_URL`
- `f/affordabot/CRON_SECRET`
- `f/affordabot/SLACK_WEBHOOK_URL`

Auth source for CLI and automation:
- `op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN`
- `op://dev/Agent-Secrets-Production/WINDMILL_DEV_LOGIN_URL`

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

# Sync the affordabot workspace assets into the shared Windmill instance
cd ops/windmill
wmill sync push --workspace affordabot

# Test the authenticated trigger endpoint directly
curl -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  https://backend-dev-3d99.up.railway.app/cron/discovery
```

If `wmill` is not installed locally:

```bash
npx windmill-cli --version
```

Safe auth pattern with cached 1Password helper (token never printed):

```bash
source ~/agent-skills/scripts/lib/dx-auth.sh
export WINDMILL_API_TOKEN="$(dx_auth_read_secret_cached "op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN")"
export WINDMILL_BASE_URL="$(dx_auth_read_secret_cached "op://dev/Agent-Secrets-Production/WINDMILL_DEV_LOGIN_URL")"
```

Safe live checks:

```bash
npx windmill-cli version -r "$WINDMILL_BASE_URL"
npx windmill-cli workspace list-remote -r "$WINDMILL_BASE_URL"
```

Sync safety:
- Always confirm target workspace is `affordabot` before `sync push`.
- Do not run broad sync operations if schedule mutation intent is not explicit.

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
