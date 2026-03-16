# Affordabot Stack Alignment Plan

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

## Architecture / Design

### 1. Frontend Canonicalization

Canonical frontend surface:

- `frontend/` only

Actions:

- move CI build/test ownership to `frontend/`
- move default local dev flow to `frontend/`
- retire `frontend-v2` from default workflows
- keep `frontend-v2` only long enough to confirm no active dependency remains, then archive/remove it

Preservation rule:

- before any structural frontend cleanup, freeze screenshots and route expectations for the current deployed experience

### 2. Visual Preservation Layer

Adopt Prime's process, not Prime's theme:

- capture screenshot baselines for key `affordabot` routes
- add route-level no-regression checks
- add a small frontend evidence section for implementation PRs touching preserved routes

Candidate preserved routes:

- `/dashboard/california`
- `/dashboard/santa-clara-county`
- `/dashboard/san-jose`
- `/dashboard/saratoga`
- any current landing/auth/admin routes still in regular use

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
- bootstrap/install scripts that require `packages/llm-common`
- inline `MockEmbeddingService` implementations
- local pgvector fallback paths that should be replaced by stable shared backends

## Execution Phases

### Phase 1: Preservation Gate

Outcome:

- the current deployed GUI is frozen as the no-regression contract

Includes:

- identify active frontend surface
- capture visual baselines
- document preserved routes/components
- define acceptance gates for frontend-preserving work

### Phase 2: Frontend Stack Convergence

Outcome:

- `frontend/` becomes the sole default frontend stack

Includes:

- CI/build/dev changes
- removal of `frontend-v2` from default workflows
- validation that preserved routes still render identically enough

### Phase 3: Windmill Migration

Outcome:

- scheduling is owned by Windmill, not Railway Cron

Includes:

- internal trigger contracts
- committed Windmill assets
- verification scripts
- removal of root cron scheduling after parity is proven

### Phase 4: Shared Library Alignment

Outcome:

- `affordabot` consumes `llm-common` consistently and no longer carries avoidable drift

Includes:

- dependency source cleanup
- fallback removal where safe
- script/bootstrap cleanup

### Phase 5: Integration and Cutover Validation

Outcome:

- the preserved GUI still holds, new orchestration is live, and docs/defaults match reality

Includes:

- integrated validation
- docs cleanup
- stale path removal
- final deployment/cutover checks

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

### Frontend Preservation Gates

- preserved route screenshots remain within agreed thresholds
- deployed-signature routes still render with the current `affordabot` design language
- current user-visible layout and styling are not unintentionally replaced with Prime patterns

### Frontend Canonicalization Gates

- CI validates `frontend/`, not `frontend-v2`
- default `make dev` / build paths use the canonical frontend
- no active deploy path depends on `frontend-v2`

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

### Mitigations

1. Do preservation gates first, not after the cleanup.
2. Keep backend business logic stable and migrate scheduling separately from logic changes.
3. Remove shared-library fallbacks only after direct verification in `affordabot` runtime paths.

### Rollback

Frontend:

- revert stack-cleanup changes while keeping preservation artifacts

Windmill:

- keep Railway cron config available until Windmill parity is proven in dev/staging
- remove Railway cron only after verified equivalence

Shared library:

- revert to prior pin/fallbacks if shared dependency upgrade breaks runtime behavior

## Consultant Review Focus

### Consultant 1

Review focus:

- UI-preservation contract
- frontend convergence sequence
- whether the plan is sufficiently protective of the existing `affordabot` GUI

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
