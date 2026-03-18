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

### Execution Model

Canonical shared-instance model: Windmill triggers authenticated backend cron endpoints over HTTP.
The backend executes the underlying script synchronously and returns a success/failure payload,
so Windmill preserves final job observability without needing the repository mounted in the worker.

Committed Windmill assets:

- `ops/windmill/wmill.yaml`
- `ops/windmill/f/affordabot/trigger_cron_job.py`
- `ops/windmill/f/affordabot/*.flow/flow.yaml`
- `ops/windmill/f/affordabot/*.schedule.yaml`

Required workspace variables:

- `f/affordabot/BACKEND_PUBLIC_URL`
- `f/affordabot/CRON_SECRET`
- `f/affordabot/SLACK_WEBHOOK_URL`

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

## Rollback

If Windmill parity fails, Railway cron entries remain in git history and can be restored.
The backend cron trigger endpoints remain additive and can still be exercised directly.
