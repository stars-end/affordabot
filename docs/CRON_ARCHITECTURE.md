# Cron Architecture

## Overview

Affordabot uses **Windmill** as the scheduler of record for all scheduled jobs.

The backend remains the execution plane. Windmill handles scheduling, triggering, and observability.
Backend cron trigger endpoints provide authenticated HTTP access for Windmill (or any authorized caller).

This replaces the legacy Prefect orchestration (removed in `bd-s8id.4`) and Railway Cron scheduling
(migrated to Windmill in `bd-s8id.3`).

## Scheduler: Windmill

### Job Inventory

| Windmill Job | Schedule | Script Entry | Auth |
| --- | --- | --- | --- |
| `discovery_run` | `0 5 * * *` UTC | `python backend/scripts/cron/run_discovery.py` | Bearer token |
| `daily_scrape` | `0 6 * * *` UTC | `python scripts/daily_scrape.py` | Bearer token |
| `rag_spiders` | `0 7 * * *` UTC | `python backend/scripts/cron/run_rag_spiders.py` | Bearer token |
| `universal_harvester` | `0 8 * * *` UTC | `python backend/scripts/cron/run_universal_harvester.py` | Bearer token |

### Execution Model

Default: Windmill runs the existing CLI/script entrypoint directly.
This preserves exit-code and log observability (no fire-and-forget HTTP triggers).

### Auth Contract

All cron trigger endpoints require:

```
Authorization: Bearer $CRON_SECRET
```

Or:

```
X-Cron-Secret: $CRON_SECRET
```

The backend validates these against the `CRON_SECRET` environment variable.
When `CRON_SECRET` is not set, cron auth is disabled (dev mode only).

### Assets

Committed Windmill job definitions: `ops/windmill/jobs/`
Runbook: `ops/windmill/README.md`

## Backend Trigger Endpoints

| Endpoint | Method | Script |
| --- | --- | --- |
| `/cron/discovery` | POST | `backend/scripts/cron/run_discovery.py` |
| `/cron/daily-scrape` | POST | `scripts/daily_scrape.py` |
| `/cron/rag-spiders` | POST | `backend/scripts/cron/run_rag_spiders.py` |
| `/cron/universal-harvester` | POST | `backend/scripts/cron/run_universal_harvester.py` |

All endpoints require auth (see Auth Contract above).

## Key Features

1. **Retries:** Uses `tenacity` for exponential backoff on transient failures.
2. **Concurrency:** Uses `asyncio.Semaphore` (default: 3) to prevent DB overload.
3. **Logging:** Writes status to `admin_tasks` and `scrape_history` tables.
4. **Observability:** View real-time status in the Admin Dashboard (`/admin`).
5. **Auth:** All trigger endpoints require `CRON_SECRET` authentication.

## Retired

| Component | Disposition |
| --- | --- |
| Prefect orchestration | Removed (`bd-s8id.4`) — dependency `prefect>=2.0.0` deleted |
| Railway Cron scheduling | Migrated to Windmill (`bd-s8id.3`) — entries removed from `railway.toml` |
| Public `/cron/daily-scrape` (unauthenticated) | Auth-gated — now requires `CRON_SECRET` |

## Local Testing

```bash
# Run a single job locally
export PYTHONPATH=backend
source backend/.env
python scripts/daily_scrape.py

# Test authenticated trigger endpoint
curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
  https://backend-dev-3d99.up.railway.app/cron/discovery
```

## Rollback

If Windmill parity fails, Railway cron entries remain in git history and can be restored to `railway.toml`.
The backend cron trigger endpoints are additive and don't remove existing functionality.
