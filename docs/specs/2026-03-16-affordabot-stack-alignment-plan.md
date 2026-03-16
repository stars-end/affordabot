# Affordabot Stack Alignment Implementation Spec

## Summary

Align `affordabot` with `prime-radiant-ai` on the underlying tech stack while preserving `affordabot`'s current visual language and deployed Next.js GUI.

The active contract is:

- preserve the current `affordabot` look and layout
- converge on one frontend stack inside `affordabot`
- migrate scheduling from Railway Cron to Windmill
- simplify and align `llm-common` consumption
- avoid any forced visual convergence with `prime-radiant-ai`

## Problem

`affordabot` currently mixes two frontend stacks:

- deployed Next.js + Tailwind/shadcn-style UI in `frontend/`
- legacy Vite + MUI UI in `frontend-v2/`

That split causes maintenance and validation drift:

- CI still builds `frontend-v2`
- default local dev paths still point at `frontend-v2`
- the visually important deployed app is not the canonical engineering target

Backend orchestration is also split:

- root `railway.toml` still owns scheduled jobs via Railway Cron
- jobs are invoked through direct scripts and a public `/cron/daily-scrape` route
- there is no Windmill source-of-truth bundle equivalent to `prime-radiant-ai`

Shared-library usage is inconsistent:

- `backend/pyproject.toml` pins `llm-common` from git
- `.gitmodules` and helper scripts still assume a `packages/llm-common` submodule
- several scripts keep local path hacks or fallback implementations that imply dependency drift

## Goals

1. Preserve the current deployed `affordabot` GUI without visual regression.
2. Make `frontend/` the sole canonical frontend stack for `affordabot`.
3. Replace Railway Cron with Windmill as scheduler of record.
4. Align `llm-common` consumption and remove local drift where safe.
5. Improve validation so functional repairs do not accidentally damage the preserved UI.

## Non-Goals

1. Do not adopt `prime-radiant-ai`'s visual language, tokens, shell, or page composition.
2. Do not force `affordabot` to match Prime's frontend runtime if that endangers the preserved UI.
3. Do not redesign the product surface during the stack-alignment work.
4. Do not rewrite backend business logic when thin orchestration adapters are sufficient.

## Active Contract

### UI Preservation

- The current deployed Next.js app in `frontend/` is the preservation target.
- The deployed dev surface at `frontend-dev-5093.up.railway.app` is confirmed to be `frontend/`, not `frontend-v2`, based on the live Next.js response signature (`x-powered-by: Next.js`, `/_next/static/...`, and HTML matching the current App Router shell).
- The current `affordabot` visual language remains repo-specific.
- Visual changes are only allowed when required to keep existing behavior stable or to repair current broken functionality.

### Tech Stack Alignment

Shared with `prime-radiant-ai` where useful:

- Tailwind + shadcn/Radix component architecture
- verification discipline and visual regression workflow
- Windmill orchestration pattern
- `llm-common` dependency and shared utility model

Explicitly not shared:

- product design language
- tokens, palette, typography direction, and layout composition

## Final Decisions

These decisions are resolved for this implementation and should not be reopened during normal execution unless a blocking runtime fact contradicts them.

1. `affordabot` stays on Next.js.
2. `frontend/` is the only canonical frontend surface.
3. The GUI preservation gate is `ALL_IN_NOW`, not advisory.
4. Public and admin Prism routes receive blocking Playwright visual coverage with stable mocked fixtures where needed.
5. Clerk auth routes receive smoke coverage first, not pixel-perfect visual baselines.
6. Non-production testability fixes for Clerk and Next build/runtime issues are in scope for `bd-s8id.1`.
7. CI ownership moves to `frontend/` once the preservation gate is real and green.
8. `frontend-v2` leaves all default workflows as part of the convergence work; deletion waits for deploy/dependency verification.
9. Windmill replaces Railway Cron using thin authenticated backend trigger contracts.
10. `llm-common` converges on the git-pinned dependency model; mixed submodule assumptions are removed.

## Implementation Principles

- Preserve the Prism GUI by changing infrastructure and runtime seams under it, not by redesigning surfaces.
- Prefer one decisive cutover per concern over long-lived dual-path maintenance.
- Where visual stability matters, use deterministic test fixtures instead of live backend state.
- Where runtime assumptions block testing, fix the runtime assumption rather than weakening the gate.
- Only keep local compatibility layers when they protect runtime behavior that the shared stack cannot yet cover.

## Architecture / Design

### 1. Frontend Canonicalization

Canonical frontend surface:

- `frontend/` only

Actions:

- add `frontend/` CI coverage before removing any existing `frontend-v2` CI job
- move CI build/test ownership to `frontend/` after the new checks are green under the preservation gate
- move default local dev flow to `frontend/`
- retire `frontend-v2` from default workflows
- keep `frontend-v2` only long enough to confirm no active dependency remains, then archive/remove it

Preservation rule:

- before any structural frontend cleanup, freeze screenshots and route expectations for the current deployed experience through committed visual baselines and CI enforcement

### 2. Visual Preservation Layer

Adopt Prime's process, not Prime's theme:

- capture screenshot baselines for preserved `affordabot` routes using Playwright visual regression against `frontend/`
- commit the initial baselines in-repo
- enforce the visual suite in CI for PRs that touch `frontend/`
- use a default visual-diff threshold of `<= 0.5%` unless a route needs a narrower tolerance
- add route-level no-regression checks
- add a small frontend evidence section for implementation PRs touching preserved routes
- add a lightweight CI guard that rejects Prime-specific theme token imports or variable names in `affordabot`

Preserved route contract:

- `bd-s8id.1` must create an exhaustive route manifest in `docs/PRESERVED_ROUTES.md`
- each route must be assigned one of:
  - `preserve`
  - `auth-preserve`
  - `admin-preserve`
  - `redirect-contract`
  - `api-contract`
  - `deprecated`
- each preserved route must map to a visual baseline or explicit non-visual verification rule
- no frontend cleanup may start until the manifest, baselines, and CI gates exist together

Implementation details:

- dashboard and bill-detail preserved routes should use Playwright network interception with canonical fixture payloads so screenshots are stable across environments
- admin preserved routes should use either fixture-backed API interception or stable built-in empty/demo states, depending on which produces the least test-only code
- auth routes should prove render/redirect health without forcing exact Clerk-hosted visuals into the blocking baseline
- redirect-only routes such as `/` should preserve redirect behavior and destination rather than force a meaningless page-level screenshot
- the preservation suite should assert both screenshot stability and core visible text markers so failures are easier to diagnose

### 3. Windmill Orchestration

Target contract:

- Windmill becomes scheduler of record
- backend remains execution plane
- existing script/business logic is preserved where practical

Recommended shape:

- add `ops/windmill/` as canonical committed assets
- create thin internal authenticated trigger endpoints or job wrappers for existing scheduled work
- remove scheduling responsibility from root `railway.toml`

Candidate initial Windmill jobs:

- discovery run
- daily scrape
- RAG spiders
- universal harvester

Design preference:

- thin orchestration adapters over large rewrites
- internal authenticated job contract over public cron entrypoints

Implementation details:

- add `ops/windmill/README.md` plus committed function/job assets modeled on Prime's structure
- each migrated job should have one clear owner:
  - Windmill for schedule/orchestration
  - backend for business logic and execution
- for long-running current cron jobs, prefer Windmill execution that preserves exit-code and log observability over fire-and-forget HTTP triggers
- if an HTTP trigger is retained, it must expose explicit completion status that Windmill can poll before marking the run successful
- all Windmill-to-backend HTTP triggers must use a simple shared-secret auth contract such as `Authorization: Bearer $CRON_SECRET` or `X-Cron-Secret: $CRON_SECRET`
- public cron endpoints should be replaced with internal-only triggers or wrappers where feasible
- removal of Railway cron config happens only after each target job has a parity checklist and successful dev/staging proof
- `scripts/daily_scrape.py` and the current public `/cron/daily-scrape` route require explicit migration handling because they are inconsistent with the rest of the backend cron surface and should be retired, auth-gated, or moved into the backend cron layout during the Windmill cutover

### 4. `llm-common` Alignment

Target contract:

- one clear dependency model
- no committed local-path assumptions
- no unnecessary fallback implementations kept alive by packaging drift

Preferred direction:

- align to the newer git-pinned `llm-common` consumption model used in `prime-radiant-ai`
- remove submodule/path expectations from scripts and bootstrap steps
- only keep repo-local fallbacks when the shared library still cannot cover the use case safely

Primary cleanup candidates:

- `.gitmodules`
- `packages/llm-common/`
- bootstrap/install scripts that require `packages/llm-common`
- `Makefile` install flow and any unconditional submodule initialization
- CI checkout settings that still require recursive submodules
- dead runtime dependencies such as `prefect>=2.0.0` if they are no longer imported anywhere
- inline `MockEmbeddingService` implementations
- local pgvector fallback paths that should be replaced by stable shared backends

Implementation details:

- remove the assumption that engineers must initialize a local `packages/llm-common` checkout to work on `affordabot`
- standardize one install/bootstrap path in CI and local docs
- treat each fallback as a live runtime dependency until proven otherwise; delete only with direct verification
- `LocalPgVectorBackend` is presumed necessary until the shared backend is proven to handle affordabot's `document_id` mapping and UUID/JSON serialization safely

## Implementation Surface

### `bd-s8id.1` — Freeze Current Next GUI Contract And Visual Preservation Gates

Primary outcomes:

- `frontend/` becomes testable and buildable in CI-friendly non-production mode
- preserved routes have committed baselines or explicit smoke-only treatment
- CI can block on Prism GUI regressions

Expected file areas:

- `frontend/playwright.config.ts`
- `frontend/tests/e2e/**`
- `frontend/src/app/layout.tsx`
- `frontend/src/middleware.ts`
- `frontend/src/app/**`
- `docs/PRESERVED_ROUTES.md`
- `.github/workflows/ci.yml`
- optional small test-fixture helpers under `frontend/tests/`

Required implementation points:

- add a safe non-production test mode so invalid/missing Clerk keys do not break build/test execution for public pages
- fix current `frontend/` build blockers that prevent CI ownership
- add preserved-route Playwright specs with canonical fixtures for dashboards and bill detail routes
- add admin-route preserved coverage where the Prism shell is visible and meaningful
- keep Clerk auth routes in smoke coverage unless exact snapshotting becomes trivial
- reconcile the current Playwright auth bypass with the middleware contract so admin preservation tests use the same signed-cookie path the app actually checks
- add a CI guard that rejects Prime-specific theme token leakage

Acceptance criteria:

1. `frontend/` builds in CI-compatible mode without requiring production Clerk configuration.
2. Preserved public/admin routes have committed visual baselines or explicit smoke-only classification in `docs/PRESERVED_ROUTES.md`.
3. The CI workflow runs the new preservation checks for changes touching `frontend/`.
4. Prime-specific theme token leakage is machine-checked.

### `bd-s8id.2` — Canonicalize Frontend Stack Around `frontend` And Retire `frontend-v2` Defaults

Primary outcomes:

- engineers land on `frontend/` by default
- legacy `frontend-v2` stops consuming CI and developer attention

Expected file areas:

- `.github/workflows/ci.yml`
- `Makefile`
- root `package.json`
- `frontend/railway.toml`
- repo docs referencing local dev/build flows
- `frontend-v2/**` only if final cleanup/removal is safe

Required implementation points:

- switch CI from dual coverage to `frontend/` as the canonical frontend job once `bd-s8id.1` gates are green
- update `make install`, `make dev`, `make build`, and related developer entry points
- verify no active Railway or repo automation path still depends on `frontend-v2`
- remove or archive `frontend-v2` only after dependency/deploy truth is confirmed

Acceptance criteria:

1. Default dev/build/install flows point at `frontend/`.
2. CI no longer treats `frontend-v2` as the canonical frontend.
3. No active deploy surface depends on `frontend-v2`.

### `bd-s8id.3` — Migrate Scheduled Orchestration From Railway Cron To Windmill

Primary outcomes:

- Windmill owns scheduling
- backend logic remains largely unchanged

Expected file areas:

- `railway.toml`
- `ops/windmill/**`
- `backend/main.py`
- `backend/scripts/cron/**`
- `scripts/daily_scrape.py`
- `docs/CRON_ARCHITECTURE.md`
- any auth/config helpers needed for internal trigger endpoints

Required implementation points:

- inventory each existing Railway Cron job and map it to a Windmill job or justified retirement
- choose the execution shape per job explicitly:
  - default: Windmill runs the existing CLI/script entrypoint in a way that preserves exit-code observability
  - exception: an authenticated backend HTTP trigger is allowed only if Windmill also observes final success/failure through polling or callback state
- add thin internal backend trigger endpoints or wrappers as needed
- commit Windmill assets and runbook/docs
- retire or auth-gate the current public `/cron/daily-scrape` endpoint as part of the migration
- remove Railway cron entries after successful parity verification

Acceptance criteria:

1. Every existing scheduled responsibility has a declared Windmill owner or explicit deprecation decision.
2. Dev/staging parity is proven before Railway cron removal.
3. Root `railway.toml` no longer acts as scheduler of record.

### `bd-s8id.4` — Align `llm-common` Dependency Model And Remove Fallback Drift

Primary outcomes:

- one supported `llm-common` consumption path
- less bootstrap/install confusion

Expected file areas:

- `backend/pyproject.toml`
- `.gitmodules`
- `Makefile`
- `scripts/bootstrap.sh`
- backend services/scripts using local fallback implementations
- docs describing local setup

Required implementation points:

- remove submodule-first assumptions from install/bootstrap flows
- update docs and CI to the single dependency model
- verify and either remove or explicitly justify repo-local fallbacks
- treat `LocalPgVectorBackend` as a known-risk compatibility layer that requires targeted parity testing before removal
- if `.3` and `.4` proceed in parallel, keep cron-script import cleanup owned by `.4` so Windmill migration work does not invalidate parity testing

Acceptance criteria:

1. `affordabot` uses one clear `llm-common` dependency model.
2. Bootstrap/install docs no longer require a local submodule checkout.
3. Remaining fallbacks are explicitly justified rather than accidental drift.

### `bd-s8id.5` — Run Integrated Validation, Docs Cleanup, And Deployment Cutover Checks

Primary outcomes:

- repo defaults, docs, CI, and runtime behavior match the new reality

Expected file areas:

- `docs/**`
- `.github/workflows/**`
- `Makefile`
- cleanup of stale scripts/config after prior tasks land

Required implementation points:

- run end-to-end validation across preserved GUI, frontend defaults, Windmill scheduling, and shared-lib setup
- remove stale docs and references to retired paths
- re-verify deployed surface and routing assumptions before closing the epic

Acceptance criteria:

1. Integrated validation passes across all completed subtasks.
2. Docs/default workflows describe the post-migration stack accurately.
3. No stale canonical-path guidance remains for retired frontend or cron flows.

## Execution Phases

### Phase 1: Preservation Gate

Outcome:

- the current deployed GUI is frozen as the no-regression contract

Includes:

- confirm the currently deployed frontend surface and record the evidence
- create `docs/PRESERVED_ROUTES.md` with an exhaustive route inventory and disposition for each route
- capture Playwright visual baselines for preserved routes and commit them
- wire the visual suite into CI for changes touching `frontend/`
- define acceptance gates for frontend-preserving work, including the anti-Prime-token check and Tailwind version pin

Execution order inside the phase:

1. make `frontend/` buildable/testable in CI-safe mode
2. finalize preserved route manifest
3. add stable Playwright fixture strategy
4. commit initial baselines
5. wire blocking CI gates

### Phase 2: Frontend Stack Convergence

Outcome:

- `frontend/` becomes the sole default frontend stack

Includes:

- add a parallel CI job for `frontend/` before removing the `frontend-v2` job
- fix any surfaced `frontend/` build or lint issues under the preservation gate before switching defaults
- update Makefile and root package workflow references, including `install`, `dev`, `dev-frontend-v2`, and `build`
- audit deploy hooks and service references to confirm `frontend-v2` is not an active deployment surface
- removal of `frontend-v2` from default workflows
- validation that preserved routes still render identically enough

Execution order inside the phase:

1. prove `frontend/` CI is green and blocking
2. switch default dev/build/install paths
3. remove legacy CI ownership
4. verify deploy/dependency truth for `frontend-v2`
5. archive/remove legacy frontend only if unused

### Phase 3: Windmill Migration

Outcome:

- scheduling is owned by Windmill, not Railway Cron

Includes:

- internal trigger contracts
- committed Windmill assets
- verification scripts
- removal of root cron scheduling after parity is proven

Execution order inside the phase:

1. map current cron inventory
2. choose and document the observability-preserving execution contract for each job
3. add Windmill assets and backend triggers
4. prove parity per job in dev/staging, including failure observability rather than success-only triggering
5. remove Railway scheduler ownership

### Phase 4: Shared Library Alignment

Outcome:

- `affordabot` consumes `llm-common` consistently and no longer carries avoidable drift

Includes:

- dependency source cleanup
- fallback removal where safe
- script/bootstrap cleanup

Execution order inside the phase:

1. standardize dependency source
2. clean install/bootstrap/docs
3. verify fallbacks one-by-one
4. remove unjustified compatibility layers

Coordination note:

- `bd-s8id.3` and `bd-s8id.4` may proceed in parallel for planning and isolated edits, but `bd-s8id.4` must land or otherwise freeze shared dependency/import changes before `bd-s8id.3` performs final Windmill parity validation on cron execution paths

### Phase 5: Integration and Cutover Validation

Outcome:

- the preserved GUI still holds, new orchestration is live, and docs/defaults match reality

Includes:

- integrated validation
- docs cleanup
- stale path removal
- final deployment/cutover checks

Execution order inside the phase:

1. run integrated verification
2. reconcile docs/defaults with implementation
3. remove stale references
4. re-verify deployed surface assumptions

## Beads Structure

### Epic

- `bd-s8id` — Affordabot stack alignment while preserving current GUI

### Children

- `bd-s8id.1` — Freeze current Next GUI contract and visual preservation gates
- `bd-s8id.2` — Canonicalize frontend stack around `frontend` and retire `frontend-v2` defaults
- `bd-s8id.3` — Migrate scheduled orchestration from Railway Cron to Windmill
- `bd-s8id.4` — Align `llm-common` dependency model and remove fallback drift
- `bd-s8id.5` — Run integrated validation, docs cleanup, and deployment cutover checks

### Blocking Edges

- `bd-s8id.1` blocks `bd-s8id.2`
- `bd-s8id.1` blocks `bd-s8id.3`
- `bd-s8id.1` blocks `bd-s8id.4`
- `bd-s8id.2` blocks `bd-s8id.5`
- `bd-s8id.3` blocks `bd-s8id.5`
- `bd-s8id.4` blocks `bd-s8id.5`

### Parallelism

Parallel after `bd-s8id.1`:

- `bd-s8id.2`
- `bd-s8id.3`
- `bd-s8id.4`

Final integration:

- `bd-s8id.5`

## Validation

### Core Commands

Frontend preservation track:

- `pnpm --dir frontend build`
- `pnpm --dir frontend exec playwright test`
- any route-scoped visual update command added by `bd-s8id.1`

Frontend convergence track:

- updated canonical frontend CI job in `.github/workflows/ci.yml`
- targeted `make` entry point verification after defaults are switched

Backend/orchestration track:

- backend tests for migrated trigger paths
- Windmill parity verification per migrated job
- explicit proof that Windmill observes both success and failure for each migrated job shape

Shared library track:

- clean install/bootstrap run using the new single dependency model
- targeted verification that the shared pgvector backend can replace `LocalPgVectorBackend` before any removal

### Frontend Preservation Gates

- Playwright visual regression baselines are committed for each preserved route
- preserved route screenshots remain within agreed thresholds (`<= 0.5%` by default)
- CI runs the visual suite on every PR that touches `frontend/`
- `docs/PRESERVED_ROUTES.md` exists and covers every App Router route with a disposition
- deployed-signature routes still render with the current `affordabot` design language
- current user-visible layout and styling are not unintentionally replaced with Prime patterns

### Frontend Canonicalization Gates

- a temporary dual-CI period validates both `frontend/` and `frontend-v2` before the legacy job is removed
- CI validates `frontend/`, not `frontend-v2`
- default `make dev` / build paths use the canonical frontend
- root install/dev/build scripts no longer point engineers at `frontend-v2`
- no active deploy path depends on `frontend-v2`
- the deployed frontend surface is re-verified immediately before retiring `frontend-v2`

### Frontend Theme Isolation Gates

- CI rejects Prime-specific theme-token imports or CSS variable names in `frontend/`
- no implementation PR imports Prime shell/layout code into `affordabot`
- `affordabot` remains pinned to Tailwind `v4.x` during this migration; any future Tailwind major upgrade requires fresh visual baselines

### Auth Coverage Gates

- Clerk-backed auth routes render without fatal runtime errors
- auth pages are covered by smoke checks even if they are not part of the initial pixel-perfect baseline set
- non-production test mode does not weaken production auth behavior

### Windmill Gates

- committed Windmill assets exist in-repo
- schedule parity is proven for each migrated job
- root Railway cron entries are removed only after verified Windmill parity

### Shared Library Gates

- `llm-common` loads through one supported path
- bootstrap and verification scripts stop depending on local submodule assumptions
- unnecessary repo-local fallback implementations are removed or explicitly justified

## Risks / Rollback

### Primary Risks

1. A frontend cleanup accidentally changes the preserved GUI.
2. Windmill migration changes job timing or execution semantics before parity is proven.
3. `llm-common` cleanup removes a fallback that is still covering a packaging/runtime gap.
4. Switching CI from `frontend-v2` to `frontend/` creates pressure for opportunistic fixes that bypass the preservation contract.
5. Prime theme tokens or shell patterns leak into `affordabot` during stack-alignment work.
6. Windmill HTTP triggers could mask long-running job failures if success is measured only at trigger time.

### Mitigations

1. Do preservation gates first, not after the cleanup.
2. Keep backend business logic stable and migrate scheduling separately from logic changes.
3. Remove shared-library fallbacks only after direct verification in `affordabot` runtime paths.
4. Run a temporary dual-CI window so `frontend/` problems surface before the legacy job is removed.
5. Add a machine-checkable anti-Prime-token guard instead of relying on reviewer memory alone.
6. Preserve execution observability by preferring CLI/script execution for long-running jobs or requiring explicit completion polling for any HTTP-triggered path.

### Rollback

Frontend:

- revert stack-cleanup changes while keeping preservation artifacts

Windmill:

- keep Railway cron config available until Windmill parity is proven in dev/staging
- remove Railway cron only after verified equivalence

Shared library:

- revert to prior pin/fallbacks if shared dependency upgrade breaks runtime behavior

## Stop Conditions

Pause and re-confirm with the founder if any of these occur:

- preserving the current Prism GUI would require abandoning the Next runtime decision
- a required testability fix weakens production auth/security behavior
- Windmill migration requires substantive business-logic rewrites rather than thin orchestration changes
- `llm-common` alignment breaks a production-critical path with no safe shared alternative

Otherwise, proceed without reopening the already-resolved decision set.

## Consultant Review Focus

### Consultant 1

Review focus:

- UI-preservation contract
- frontend convergence sequence
- whether the plan is sufficiently protective of the existing `affordabot` GUI

Revisions incorporated from consultant feedback:

- preservation gate is now defined in terms of Playwright baselines, route manifest, CI enforcement, and thresholded diffs
- CI migration is explicitly sequenced through a temporary dual-CI period
- Makefile/default-workflow audit is called out directly
- anti-Prime-token and Tailwind-version gates are now part of the plan

### Consultant 2

Review focus:

- Windmill migration contract
- `llm-common` alignment approach
- whether the backend/orchestration sequencing is minimal-risk and low-cognitive-load

## Recommended First Task

Start with `bd-s8id.1`.

Why first:

- it establishes the preserved GUI as an explicit contract
- it reduces the risk of accidental visual damage during the rest of the migration
- it unlocks the three main implementation tracks in parallel
- it resolves the highest-risk ambiguity first: what must be preserved, how that preservation is enforced, and how future frontend work is prevented from drifting aesthetically
