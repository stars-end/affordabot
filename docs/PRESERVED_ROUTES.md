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

| Route | Disposition | Required gate |
| --- | --- | --- |
| `/` | `redirect-contract` | Redirect smoke to `/dashboard/california` |
| `/dashboard/california` | `preserve` | Visual baseline + PR evidence |
| `/dashboard/santa-clara-county` | `preserve` | Visual baseline + PR evidence |
| `/dashboard/san-jose` | `preserve` | Visual baseline + PR evidence |
| `/dashboard/saratoga` | `preserve` | Visual baseline + PR evidence |
| `/dashboard/[jurisdiction]` | `preserve` | Visual baseline for canonical fixtures + route smoke |
| `/search` | `preserve` | Visual baseline + route smoke |
| `/bill/[jurisdiction]/[billNumber]` | `preserve` | Visual baseline for canonical fixture + route smoke |
| `/sign-in/[[...sign-in]]` | `auth-preserve` | Visual baseline + auth-shell smoke |
| `/sign-up/[[...sign-up]]` | `auth-preserve` | Visual baseline + auth-shell smoke |
| `/admin` | `admin-preserve` | Visual baseline + route smoke |
| `/admin/audits/trace` | `admin-preserve` | Visual baseline + route smoke |
| `/admin/discovery` | `admin-preserve` | Visual baseline + route smoke |
| `/admin/jurisdiction/[id]` | `admin-preserve` | Visual baseline or stable fixture-backed smoke |
| `/admin/prompts` | `admin-preserve` | Visual baseline + route smoke |
| `/admin/reviews` | `admin-preserve` | Visual baseline + route smoke |
| `/admin/sources` | `admin-preserve` | Visual baseline + route smoke |
| `/api/search` | `api-contract` | Response contract verification |
| `/api/sources` | `api-contract` | Response contract verification |

## Required Outputs For `bd-s8id.1`

- Map every `preserve`, `auth-preserve`, and `admin-preserve` route above to a Playwright visual test in `frontend/`, and every `redirect-contract` route to a redirect assertion.
- Commit initial visual baselines in-repo.
- Add CI execution for the visual suite on PRs that touch `frontend/`.
- Revisit this registry before `bd-s8id.2` starts and mark any newly discovered routes with a disposition instead of leaving them implicit.
- Keep the registry repo-local so future contributors can see what must not change aesthetically.
