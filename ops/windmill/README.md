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

Path B orchestration skeleton (unscheduled by default):
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary.py`
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary.script.yaml`
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary__flow/flow.yaml`

Boundary note:
- this flow shape calls coarse domain-command stubs only (`search_materialize`, `freshness_gate`,
  `read_fetch`, `index`, `analyze`, `summarize_run`).
- direct product writes (Postgres, pgvector, object storage) stay outside Windmill assets.

Required workspace variables:

- `f/affordabot/BACKEND_PUBLIC_URL`
- `f/affordabot/CRON_SECRET`
- `f/affordabot/SLACK_WEBHOOK_URL`

Auth source for CLI and automation:
- `op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN`
- `op://dev/Agent-Secrets-Production/WINDMILL_DEV_LOGIN_URL`

Canonical shell variables for agent runs:

- `WINDMILL_API_TOKEN`: resolved from the cached 1Password helper.
- `WINDMILL_DEV_LOGIN_URL`: resolved from the cached 1Password helper. This is
  the browser login URL and currently ends with `/user/login`.
- `WINDMILL_BASE_URL`: derived by stripping `/user/login` from
  `WINDMILL_DEV_LOGIN_URL`. Windmill CLI API calls need this instance root.
- `WINDMILL_WORKSPACE`: `affordabot`.
- `TMP_WMILL_CONFIG`: a temporary `wmill` config directory created per run.

Do not depend on ambient `~/.config/windmill` state in agent workflows. Create a
throwaway profile with `--config-dir` for each CLI smoke test, dry-run, or sync
operation. Do not use raw `op read`, `op item get`, `op item list`, or GUI-backed
1Password auth from agents.

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
export WINDMILL_API_TOKEN="$(DX_AUTH_CACHE_ONLY=1 dx_auth_read_secret_cached "op://dev/Agent-Secrets-Production/WINDMILL_API_TOKEN")"
WINDMILL_DEV_LOGIN_URL="$(DX_AUTH_CACHE_ONLY=1 dx_auth_read_secret_cached "op://dev/Agent-Secrets-Production/WINDMILL_DEV_LOGIN_URL")"
WINDMILL_BASE_URL="${WINDMILL_DEV_LOGIN_URL%/user/login}"
WINDMILL_WORKSPACE="affordabot"
TMP_WMILL_CONFIG="$(mktemp -d)"
trap 'rm -rf "$TMP_WMILL_CONFIG"' EXIT

npx --yes windmill-cli workspace add "$WINDMILL_WORKSPACE" "$WINDMILL_WORKSPACE" "$WINDMILL_BASE_URL" \
  --token "$WINDMILL_API_TOKEN" \
  --config-dir "$TMP_WMILL_CONFIG"
```

Safe live checks for CLI version `1.682.0`:

```bash
npx --yes windmill-cli workspace list \
  --config-dir "$TMP_WMILL_CONFIG"

npx --yes windmill-cli job list \
  --workspace "$WINDMILL_WORKSPACE" \
  --config-dir "$TMP_WMILL_CONFIG" \
  --limit 5 \
  --json

npx --yes windmill-cli flow list \
  --workspace "$WINDMILL_WORKSPACE" \
  --config-dir "$TMP_WMILL_CONFIG"

npx --yes windmill-cli flow get f/affordabot/manual_substrate_expansion \
  --workspace "$WINDMILL_WORKSPACE" \
  --config-dir "$TMP_WMILL_CONFIG" \
  --json

npx --yes windmill-cli script list \
  --workspace "$WINDMILL_WORKSPACE" \
  --config-dir "$TMP_WMILL_CONFIG"

npx --yes windmill-cli script get f/affordabot/trigger_cron_job \
  --workspace "$WINDMILL_WORKSPACE" \
  --config-dir "$TMP_WMILL_CONFIG" \
  --json
```

CLI notes:
- `WINDMILL_DEV_LOGIN_URL` is intentionally a login URL in the current secret
  cache; normalize it before API use.
- Do not use `-r "$WINDMILL_BASE_URL"` with `windmill-cli` `1.682.0`; this
  build rejects `-r`. Use the temporary-profile pattern above.
- `wmill.yaml` currently emits a deprecation warning because it uses
  `gitBranches`; this does not block read-only checks, but should be cleaned up
  before relying on broad sync automation.

Domain-boundary POC live gate:

```bash
npx --yes windmill-cli flow get f/affordabot/pipeline_daily_refresh_domain_boundary__flow \
  --workspace "$WINDMILL_WORKSPACE" \
  --config-dir "$TMP_WMILL_CONFIG" \
  --json
```

Canonical manual validation harness (Worker B):

```bash
cd backend
poetry run python scripts/verification/verify_windmill_sanjose_live_gate.py \
  --run-mode stub-run
```

Harness artifacts:
- `docs/poc/windmill-domain-boundary-integration/artifacts/sanjose_live_gate_report.json`
- `docs/poc/windmill-domain-boundary-integration/artifacts/sanjose_live_gate_report.md`

Harness classifications:
- `stub_orchestration_pass`: Windmill orchestration succeeded, but run is still stub-backed.
- `backend_bridge_surface_ready`: backend endpoint configuration + local mock probe passed, but storage/runtime evidence is still pending.
- `full_product_pass`: orchestration plus storage/runtime evidence gates succeeded.
- `read_only_surface_pass`: deployment/auth surface checks passed in `--run-mode read-only`.

Backend endpoint mode (`command_client=backend_endpoint`) is opt-in and fail-closed.
The flow default remains `command_client=stub`. Do not switch live runs to
`backend_endpoint` until backend URL/auth and storage adapters are ready.
When enabled, the flow calls the backend-owned coarse command endpoint at
`/cron/pipeline/domain/run-scope`; it resolves `BACKEND_PUBLIC_URL` and
`CRON_SECRET` from Windmill vars using the same pattern as the existing cron
flows, rather than accepting a pasted auth token in manual run input.

Harness blocker categories:
- `infra/auth`
- `windmill_cli`
- `deployment`
- `product_bridge`
- `storage/runtime`

Deploy only the unscheduled domain-boundary POC assets:

```bash
npx --yes windmill-cli script push f/affordabot/pipeline_daily_refresh_domain_boundary.py \
  --workspace "$WINDMILL_WORKSPACE" \
  --config-dir "$TMP_WMILL_CONFIG" \
  --message "bd-9qjof.6 deploy domain-boundary POC script"

# For flow push, pass the local flow directory, not the nested flow.yaml file.
npx --yes windmill-cli flow push \
  f/affordabot/pipeline_daily_refresh_domain_boundary__flow \
  f/affordabot/pipeline_daily_refresh_domain_boundary__flow \
  --workspace "$WINDMILL_WORKSPACE" \
  --config-dir "$TMP_WMILL_CONFIG" \
  --message "bd-9qjof.6 deploy domain-boundary POC flow"
```

Manual San Jose skeleton run:

```bash
npx --yes windmill-cli flow run f/affordabot/pipeline_daily_refresh_domain_boundary__flow \
  --workspace "$WINDMILL_WORKSPACE" \
  --config-dir "$TMP_WMILL_CONFIG" \
  -d '{
    "idempotency_key": "bd-9qjof.6-cli-smoke-YYYY-MM-DD",
    "jurisdictions": ["San Jose CA"],
    "source_families": ["meeting_minutes"],
    "search_query": "San Jose CA city council meeting minutes housing",
    "analysis_question": "Summarize housing-related signals from recent San Jose meeting minutes.",
    "mode": "manual",
    "scope_parallelism": 1,
    "stale_status": "fresh"
  }'
```

Sync safety:
- Always confirm target workspace is `affordabot` before `sync push`.
- Do not run broad sync operations if schedule mutation intent is not explicit.
- A missing domain-boundary POC flow means live dry-run is blocked on deployment,
  not on CLI auth.
- The domain-boundary POC flow is unscheduled and should remain unscheduled until
  the backend domain commands replace the current skeleton stubs.

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
