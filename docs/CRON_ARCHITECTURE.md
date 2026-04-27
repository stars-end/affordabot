# Cron Architecture

## Overview

Affordabot uses **Windmill** as the scheduler of record for all scheduled jobs.

The backend remains the execution plane. Windmill handles scheduling, triggering, and observability.
Backend cron trigger endpoints provide authenticated HTTP access for Windmill (or any authorized caller).

This replaces the legacy Prefect orchestration (removed in `bd-s8id.4`) and Railway Cron scheduling
(migrated to Windmill in `bd-s8id.3`).

For implementation-ready cycle-review architecture and HITL 10-20 cycle workflows, see:
`docs/specs/2026-04-27-data-moat-cycle-review-architecture.md`.

Boundary lock:
- Windmill cron/run data is runtime evidence and orchestration metadata.
- Windmill-native labels, `wm_labels`, job result envelopes, asset references,
  and run deep links are required transparency primitives for data-moat cycles.
- Affordabot backend/admin read models remain product truth for cycle gates and review decisions.
- OSS data-quality tooling, if used, is bounded pilot support only and not the truth surface.

## Scheduler: Windmill

Shared dev instance:
- `https://server-dev-8d5b.up.railway.app`

Workspace mapping:
- affordabot repo assets `f/affordabot/*` -> workspace `affordabot`
- prime-radiant-ai EODHD assets `f/eodhd/*` -> workspace `eodhd`

The instance is shared, but workspaces are separated by repo/domain.

### Job Inventory

| Windmill Job | Schedule | Script Entry | Auth |
| --- | --- | --- | --- |
| `discovery_run` | `0 5 * * *` UTC | `python backend/scripts/cron/run_discovery.py` | Bearer token |
| `daily_scrape` | `0 6 * * *` UTC | `python backend/scripts/cron/run_daily_scrape.py` | Bearer token |
| `rag_spiders` | `0 7 * * *` UTC | `python backend/scripts/cron/run_rag_spiders.py` | Bearer token |
| `universal_harvester` | `0 8 * * *` UTC | `python backend/scripts/cron/run_universal_harvester.py` | Bearer token |

### Execution Model

Canonical shared-instance model: Windmill runs a thin wrapper that POSTs to the backend cron endpoint.
The backend then executes the real script synchronously and returns a final success/failure payload.
This keeps one execution plane in Railway while preserving Windmill observability.

### Auth Contract

Windmill wrappers send:

```
Authorization: Bearer $CRON_SECRET
X-PR-CRON-SECRET: $CRON_SECRET
X-PR-CRON-SOURCE: windmill:f/affordabot/<job>
```

The backend also accepts:

```
X-Cron-Secret: $CRON_SECRET
```

The backend validates these against the `CRON_SECRET` environment variable.
When `CRON_SECRET` is not set, all cron trigger endpoints return 401.

### Assets

Committed Windmill workspace definitions: `ops/windmill/f/affordabot/`
Windmill sync config: `ops/windmill/wmill.yaml`
Runbook: `ops/windmill/README.md`

Required Windmill workspace variables:

- `f/affordabot/BACKEND_PUBLIC_URL`
- `f/affordabot/CRON_SECRET`
- `f/affordabot/SLACK_WEBHOOK_URL`

## Backend Trigger Endpoints

| Endpoint | Method | Script |
| --- | --- | --- |
| `/cron/discovery` | POST | `backend/scripts/cron/run_discovery.py` |
| `/cron/daily-scrape` | POST | `backend/scripts/cron/run_daily_scrape.py` |
| `/cron/rag-spiders` | POST | `backend/scripts/cron/run_rag_spiders.py` |
| `/cron/universal-harvester` | POST | `backend/scripts/cron/run_universal_harvester.py` |

All endpoints require auth (see Auth Contract above).

## Key Features

1. **Retries:** Uses `tenacity` for exponential backoff on transient failures.
2. **Concurrency:** Uses `asyncio.Semaphore` (default: 3) to prevent DB overload.
3. **Logging:** Writes status to `admin_tasks` and `scrape_history` tables.
4. **Observability:** View real-time status in the Admin Dashboard (`/admin`).
5. **Auth:** All trigger endpoints require `CRON_SECRET` authentication.
6. **Alerts:** Windmill wrappers can post success/failure messages to `#railway-dev-alerts` via `SLACK_WEBHOOK_URL`, matching Prime's pattern.

## Retired

| Component | Disposition |
| --- | --- |
| Prefect orchestration | Removed (`bd-s8id.4`) — dependency `prefect>=2.0.0` deleted |
| Railway Cron scheduling | Migrated to Windmill (`bd-s8id.3`) — entries removed from `railway.toml` |
| Unauthenticated `/cron/daily-scrape` | No longer exists — all cron endpoints require `CRON_SECRET` |

## Local Testing

```bash
# Push affordabot workspace assets to the shared Windmill instance
cd ops/windmill
wmill sync push --workspace affordabot

# Test authenticated trigger endpoint
curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
  https://backend-dev-3d99.up.railway.app/cron/discovery
```

CLI fallback when `wmill` is unavailable:

```bash
npx windmill-cli --version
```

Safe live checks (no secret output):

```bash
source ~/agent-skills/scripts/lib/dx-auth.sh
export WINDMILL_API_TOKEN="$(dx_auth_read_secret_cached "op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN")"
export WINDMILL_BASE_URL="$(dx_auth_read_secret_cached "op://dev/Agent-Secrets-Production/WINDMILL_DEV_LOGIN_URL")"
npx windmill-cli version -r "$WINDMILL_BASE_URL"
npx windmill-cli workspace list-remote -r "$WINDMILL_BASE_URL"
```

Safety warning:
- Do not run broad `sync push` without confirming workspace target and schedule mutation intent.

## Rollback

If Windmill parity fails, Railway cron entries remain in git history and can be restored to `railway.toml`.
The backend cron trigger endpoints are additive and don't remove existing functionality.
