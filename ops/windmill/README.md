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
| `daily_scrape` | `daily_scrape.py` at 0600 UTC | `0 6 * * *` | `python scripts/daily_scrape.py` |
| `rag_spiders` | `run_rag_spiders.py` at 0700 UTC | `0 7 * * *` | `python backend/scripts/cron/run_rag_spiders.py` |
| `universal_harvester` | `run_universal_harvester.py` at 0800 UTC | `0 8 * * *` | `python backend/scripts/cron/run_universal_harvester.py` |

### Execution Model

Default: Windmill runs the existing CLI/script entrypoint directly.
This preserves exit-code and log observability (no fire-and-forget HTTP triggers).

### Auth Contract

All Windmill-to-backend HTTP calls use:

```
Authorization: Bearer $CRON_SECRET
```

The backend validates this via `X-Cron-Secret` header or `Authorization: Bearer` token
against `CRON_SECRET` environment variable.

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
# Run a single job locally (with Railway env for secrets)
railway run -p <project-id> -e <env> -s backend -- python backend/scripts/cron/run_discovery.py

# Test the authenticated trigger endpoint
curl -H "Authorization: Bearer $CRON_SECRET" https://backend-dev-3d99.up.railway.app/cron/discovery
```

## Rollback

If Windmill parity fails, Railway cron entries remain in git history and can be restored.
The backend cron trigger endpoints are additive and don't remove existing functionality.
