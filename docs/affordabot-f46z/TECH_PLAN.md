# affordabot-f46z — make verify-pr should not require Railway login

## Problem
`make verify-pr` (and related targets) wrap commands with `railway run` when not in a Railway shell. In non-interactive contexts (CI, headless agents) this can fail with:
`Unauthorized. Please login`.

## Goal
Verification should be runnable without an interactive Railway login **when required env vars are provided**.

## Proposed Approach
1. Add a “no-railway” execution path for verification:
   - If a required set of env vars is present (e.g., `FRONTEND_URL`, `BACKEND_URL`, credentials), run verification directly without `railway run`.
2. Keep `railway run` as an optional convenience path:
   - Only use it when `RAILWAY_TOKEN` is present or when already inside `railway shell`.
3. Improve error messages:
   - If env vars are missing, print a concise list of what to set.

## User Intervention Required
If you want CI to keep using Railway-injected env, you’ll likely need:
- a non-interactive `RAILWAY_TOKEN` (or equivalent) configured in GitHub Actions secrets.

## Acceptance Criteria
- `make verify-pr PR=<N>` runs on a fresh machine without `railway login`, given explicit env vars.
- CI can still run verification using Railway env (either via token or explicit env configuration).

