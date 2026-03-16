# Preserved Routes Registry

This registry defines the current `affordabot` route preservation contract for `bd-s8id.1`.

It exists to keep stack-alignment work from silently changing the current GUI while engineering defaults, CI, and orchestration move underneath it.

## Dispositions

- `preserve`: user-facing route that requires a committed Playwright visual baseline and CI enforcement
- `auth-preserve`: auth-facing route that requires a committed visual baseline and basic auth-shell verification
- `admin-preserve`: admin-facing route that still requires a visual baseline, but may use narrower content fixtures
- `redirect-contract`: route must preserve redirect behavior and destination rather than its own visual baseline
- `api-contract`: no visual baseline; preserve response contract and integration behavior instead
- `deprecated`: route is a removal candidate and must not be deleted until the implementation plan explicitly authorizes it

## Initial Route Inventory

| Route | Disposition | Required gate | Test file | Test name |
| --- | --- | --- | --- | --- |
| `/` | `redirect-contract` | Redirect smoke to `/dashboard/california` | `preserved-public.spec.ts` | `homepage redirects to dashboard/california` |
| `/dashboard/california` | `preserve` | Visual baseline + PR evidence | `preserved-public.spec.ts` | `dashboard/california — preserved visual baseline` |
| `/dashboard/santa-clara-county` | `preserve` | Visual baseline + PR evidence | `preserved-public.spec.ts` | `dashboard/santa-clara-county — preserved visual baseline` |
| `/dashboard/san-jose` | `preserve` | Visual baseline + PR evidence | `preserved-public.spec.ts` | `dashboard/san-jose — preserved visual baseline` |
| `/dashboard/saratoga` | `preserve` | Visual baseline + PR evidence | `preserved-public.spec.ts` | `dashboard/saratoga — preserved visual baseline` |
| `/dashboard/[jurisdiction]` | `preserve` | Visual baseline for canonical fixtures + route smoke | `preserved-public.spec.ts` | `dashboard/[jurisdiction] — generic jurisdiction route smoke` |
| `/search` | `preserve` | Visual baseline + route smoke | `preserved-public.spec.ts` | `search — preserved visual baseline (empty state)` |
| `/bill/[jurisdiction]/[billNumber]` | `preserve` | Visual baseline for canonical fixture + route smoke | `preserved-public.spec.ts` | `bill/california/AB-1234 — preserved visual baseline` |
| `/sign-in/[[...sign-in]]` | `auth-preserve` | Render health (no fatal errors); skipped in CI mode (requires real Clerk keys) | `preserved-auth.spec.ts` | `sign-in — renders without fatal errors` |
| `/sign-up/[[...sign-up]]` | `auth-preserve` | Render health (no fatal errors); skipped in CI mode (requires real Clerk keys) | `preserved-auth.spec.ts` | `sign-up — renders without fatal errors` |
| `/admin` | `admin-preserve` | Visual baseline + route smoke | `preserved-admin.spec.ts` | `admin — preserved visual baseline` |
| `/admin/audits/trace` | `admin-preserve` | Visual baseline + route smoke | `preserved-admin.spec.ts` | `admin/audits/trace — preserved visual baseline` |
| `/admin/discovery` | `admin-preserve` | Visual baseline + route smoke | `preserved-admin.spec.ts` | `admin/discovery — preserved visual baseline` |
| `/admin/jurisdiction/[id]` | `admin-preserve` | Visual baseline or stable fixture-backed smoke | `preserved-admin.spec.ts` | `admin/jurisdiction/test-jurisdiction — preserved visual baseline` |
| `/admin/prompts` | `admin-preserve` | Visual baseline + route smoke | `preserved-admin.spec.ts` | `admin/prompts — preserved visual baseline` |
| `/admin/reviews` | `admin-preserve` | Visual baseline + route smoke | `preserved-admin.spec.ts` | `admin/reviews — preserved visual baseline` |
| `/admin/sources` | `admin-preserve` | Visual baseline + route smoke | `preserved-admin.spec.ts` | `admin/sources — preserved visual baseline` |
| `/api/search` | `api-contract` | Response contract verification | — | — |
| `/api/sources` | `api-contract` | Response contract verification | — | — |

## Auth Bypass Contract

Admin preservation tests use a signed-cookie bypass that matches the middleware contract:

1. Cookie name: `x-test-user`
2. Value format: `v1.{base64url_payload}.{base64url_signature}`
3. HMAC-SHA-256 signed with `TEST_AUTH_BYPASS_SECRET`
4. Helper: `tests/e2e/auth-setup.ts` generates the cookie

### Production path (Clerk available)

When real Clerk keys are configured, the middleware uses `clerkMiddleware` which checks:
- If `RAILWAY_ENVIRONMENT_NAME` is `dev` or `staging` AND `TEST_AUTH_BYPASS_SECRET` is set, the signed bypass cookie grants access to `/admin` routes without a Clerk session.
- Otherwise, standard Clerk auth is enforced (redirect to `/sign-in` if not authenticated).

### CI path (placeholder Clerk keys)

When `NEXT_PUBLIC_TEST_AUTH_BYPASS=true` and the Clerk publishable key contains `placeholder`:
- Clerk SDK is not loaded (no import at request time).
- The CI middleware validates the signed bypass cookie for `/admin` routes using the same `verifySignedBypassCookie` function.
- When `TEST_AUTH_BYPASS_SECRET` is set: invalid or missing bypass cookie returns 401 (no redirect since Clerk is unavailable).
- When `TEST_AUTH_BYPASS_SECRET` is unset: admin routes pass through without auth check (permissive fallback for local dev).
- Public routes pass through unconditionally.
- This means the admin preservation tests genuinely exercise the signed-cookie contract in CI (where the secret is always set).

The bypass does NOT weaken production auth — it only operates in non-production environments.

## Fixtures

| Fixture file | Used by | Contents |
| --- | --- | --- |
| `tests/e2e/fixtures/legislation-california.json` | Dashboard routes | 3 California bills with impacts |
| `tests/e2e/fixtures/bill-detail.json` | Bill detail route | AB-1234 full detail with impacts |

## Anti-Prime Contamination

CI runs `scripts/ci/check-prime-contamination.sh` which scans `frontend/src` for:
- Prime-specific color tokens (`--color-navy`, `--navy-800`, `C5A55A`, `1E3A6A`, etc.)
- Prime-specific fonts (`Playfair Display`)
- Prime-specific patterns (`prime-radiant`, `PrimeRadiant`, `T-Split`, `Account Rail`)

Violations block the PR.

## Required Outputs For `bd-s8id.1`

- [x] Map every `preserve`, `auth-preserve`, and `admin-preserve` route above to a Playwright test in `frontend/`, and every `redirect-contract` route to a redirect assertion.
- [x] Initial baselines generated on first CI run (uploaded as artifact).
- [x] CI runs the preservation suite for PRs that touch `frontend/`.
- [x] Anti-Prime contamination check gates PRs.
- [x] Keep the registry repo-local so future contributors can see what must not change aesthetically.
