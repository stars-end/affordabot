# CI and Testing Infrastructure

**Last Updated**: 2026-03-18  
**Status**: Aligned with the shared-stack cutover

## Overview

Affordabot now treats the preserved Next.js Prism UI, shared-instance Windmill wrappers, and backend cron endpoints as the canonical test surface.

The defaults are intentionally narrow:

- preserved-route Playwright tests are the default frontend gate
- legacy Playwright specs are quarantined and opt-in only
- backend pytest covers the Windmill wrapper and alert contract

## Local Commands

### Makefile

```bash
make test         # Canonical preserved-route Playwright suite
make e2e          # Alias for the canonical preserved-route suite
make test-legacy  # Quarantined legacy Playwright specs
make ci           # Build + canonical preserved-route suite
make ci-lite      # Fast local validation
```

### Frontend

```bash
cd frontend
pnpm test                 # Canonical preserved-route suite
pnpm test:headed          # Canonical preserved-route suite with browser visible
pnpm test:ui              # Canonical preserved-route suite in Playwright UI
pnpm test:legacy          # Quarantined legacy Playwright specs
pnpm test:legacy:headed   # Legacy suite with browser visible
pnpm test:report          # Open last Playwright report
```

### Backend

```bash
cd backend
poetry run pytest
poetry run pytest tests/ops/test_windmill_contract.py -q
```

## Canonical Frontend Contract

### Preserved Suite

The canonical preserved-route suite lives in:

- `frontend/tests/e2e/preserved-public.spec.ts`
- `frontend/tests/e2e/preserved-admin.spec.ts`
- `frontend/tests/e2e/preserved-auth.spec.ts`

These tests protect the current Prism GUI and match the CI preservation gate.

### Legacy Suite

Older exploratory Playwright specs live in:

- `frontend/tests/legacy-e2e/smoke.spec.ts`
- `frontend/tests/legacy-e2e/audit_trail.spec.ts`

They are not part of the blocking preservation contract. Keep them only for explicit manual investigation, migration follow-up, or future modernization.

### Playwright Configuration

- Canonical config: `frontend/playwright.config.ts`
- Legacy-only config: `frontend/playwright.legacy.config.ts`
- Reports: `frontend/playwright-report/`
- Canonical snapshots: `frontend/tests/e2e/*-snapshots/`

## Backend and Windmill Contract Coverage

### Cron Endpoint Tests

`backend/tests/test_cron_endpoints.py` verifies:

- missing auth returns `401`
- valid auth runs the backend cron handlers synchronously
- Prime-style shared-instance headers are accepted
- failed jobs surface `500`
- `daily-scrape` uses the backend-scoped entrypoint

### Windmill Wrapper Tests

`backend/tests/ops/test_windmill_contract.py` verifies:

- each committed shared-instance flow still points at `f/affordabot/trigger_cron_job`
- required Windmill vars are still referenced:
  - `BACKEND_PUBLIC_URL`
  - `CRON_SECRET`
  - `SLACK_WEBHOOK_URL`
- schedules still point at the expected four affordabot flows
- stale `BACKEND_INTERNAL_URL` does not reappear in repo assets
- Slack success and failure alert branches still execute

## GitHub Actions

Workflow: `.github/workflows/ci.yml`

### Frontend Lint & Build

- installs dependencies
- builds `frontend/`

### Frontend Preservation Gate

Runs only the canonical preserved suite:

- `tests/e2e/preserved-public.spec.ts`
- `tests/e2e/preserved-admin.spec.ts`
- `tests/e2e/preserved-auth.spec.ts`

It does not run the quarantined legacy specs.

### Backend Lint & Test

Runs backend pytest, including the Windmill contract coverage.

### Beads Validation

Checks for required Beads metadata on PR commits.

## Expected Local Verification

Before opening a PR for stack-affecting work, run:

```bash
make ci
cd backend && poetry run pytest tests/ops/test_windmill_contract.py tests/test_cron_endpoints.py -q
```

If you changed legacy specs intentionally, also run:

```bash
cd frontend && pnpm test:legacy
```

## Troubleshooting

| Issue | Solution |
| --- | --- |
| Playwright browsers missing locally | `cd frontend && pnpm exec playwright install --with-deps chromium` |
| Canonical preserved suite passes but legacy suite fails | Expected unless you touched the legacy lane; they are non-blocking by default |
| Windmill wrapper tests fail | Re-check `ops/windmill/f/affordabot/*` flow, schedule, and script contracts |
| Slack alert-path tests fail | Inspect `ops/windmill/f/affordabot/trigger_cron_job.py` before changing alert payload semantics |
| Backend pytest fails after dependency edits | Regenerate `backend/poetry.lock` and rerun `poetry install --no-interaction --no-root` |

## File Structure

```text
affordabot/
├── .github/workflows/ci.yml
├── Makefile
├── docs/CI_AND_TESTING.md
├── frontend/
│   ├── playwright.config.ts
│   ├── playwright.legacy.config.ts
│   └── tests/
│       ├── e2e/
│       │   ├── preserved-public.spec.ts
│       │   ├── preserved-admin.spec.ts
│       │   ├── preserved-auth.spec.ts
│       │   └── fixtures/
│       └── legacy-e2e/
│           ├── smoke.spec.ts
│           └── audit_trail.spec.ts
└── backend/
    └── tests/
        ├── test_cron_endpoints.py
        └── ops/test_windmill_contract.py
```
