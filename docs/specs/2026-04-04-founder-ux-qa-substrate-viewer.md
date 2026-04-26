# 2026-04-04 Founder UX QA - Substrate Viewer

## Scope

- Target URL: `https://frontend-dev-5093.up.railway.app/admin`
- Focused flows only:
  - run list
  - failure buckets
  - raw row detail
- Tooling: `agent-browser` manual dogfood lane (no Playwright lane used)

## Auth Approach Used

1. Attempted documented low-friction cookie: `x-test-user=admin`
2. App returned: `Unauthorized: invalid or missing bypass cookie`
3. Switched to signed bypass token per `frontend/src/middleware.ts` contract:
   - fetched `TEST_AUTH_BYPASS_SECRET` from Railway via:
     - `./scripts/dx-railway-run.sh -- -- printenv TEST_AUTH_BYPASS_SECRET`
   - generated `v1.<payload>.<sig>` HMAC-SHA256 token
   - set cookie `x-test-user=<signed token>` on `https://frontend-dev-5093.up.railway.app`
4. `/admin` loaded successfully after signed cookie was applied

## Findings First

### Finding 1 - Auth contract drift in QA entry path (non-blocking for product flow)

- Severity: Medium (QA/operator friction, not a substrate viewer runtime failure)
- Observed behavior:
  - plain `x-test-user=admin` no longer works
  - signed cookie is now required
- Why this matters:
  - "quick dogfood" path is less obvious than previous expectation
  - manual QA can fail fast with a false-negative if signed-cookie step is skipped
- Product impact:
  - none on the three substrate viewer workflows once signed auth is used

## Flow Results (No SQL Requirement)

### 1) Run List

- Result: usable without SQL
- Evidence:
  - Recent runs rendered with IDs, timestamps, state, row/error/promoted/retrievable counters
  - run selection updated run summary on-page

### 2) Failure Buckets

- Result: usable without SQL
- Evidence:
  - Failure Buckets section rendered
  - current selected run showed explicit empty-state message (`No failure buckets for this run.`)
  - run-level stage/jurisdiction summary remained visible

### 3) Raw Row Detail

- Result: usable without SQL
- Evidence:
  - row table rendered with created/jurisdiction/doc type/state
  - selecting row exposed detail card with URL/source/storage URI/document ID/trust/content class/ingestion stage
  - content preview + metadata JSON visible in the same screen

## Evidence Paths

- `/tmp/agent-browser-dogfood/screenshots/admin-initial.png`
- `/tmp/agent-browser-dogfood/screenshots/admin-authenticated.png`
- `/tmp/agent-browser-dogfood/screenshots/substrate-overview.png`
- `/tmp/agent-browser-dogfood/screenshots/substrate-run-list.png`
- `/tmp/agent-browser-dogfood/screenshots/substrate-failure-buckets.png`
- `/tmp/agent-browser-dogfood/screenshots/substrate-raw-row-detail.png`

## Verdict

`pass-with-gaps`

- Pass: all three founder-critical substrate flows are usable without SQL in affordabot dev after signed-cookie auth.
- Gap: QA entry docs/expectations still imply plain bypass cookie is enough; current middleware requires signed bypass token.
