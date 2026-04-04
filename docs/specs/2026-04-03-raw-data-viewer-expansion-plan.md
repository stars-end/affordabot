# Raw Data Viewer Expansion Plan

Date: 2026-04-03
Beads epic: `bd-990j`

## Summary

Expand the existing admin and GlassBox surfaces into a substrate-focused operator viewer for raw runs, raw rows, artifact drilldown, and failure debugging.

This should be built in-house on top of the current affordabot backend and frontend, not by introducing a separate OSS dashboard product.

## Problem

Affordabot can now run bounded substrate campaigns and produce grounded inspection artifacts, but browsing the underlying raw data is still awkward. Operators need a run-centric way to:

- find a manual substrate run quickly
- inspect captured rows tied to that run
- filter by jurisdiction, asset class, trust tier, content class, and promotion state
- drill into one raw scrape row
- inspect artifact references and storage-backed objects
- connect substrate rows to GlassBox and pipeline context when useful

Slack is appropriate for summaries, not browsing. The current `/admin` and GlassBox surfaces already provide the right trust boundary and auth model, but they do not yet expose the substrate-specific read model.

## Why This Is Safe Now

The data framework lock makes this safe.

The viewer is no longer being built against shifting substrate semantics. The locked framework now gives stable operator concepts:

- `manual_run_id`
- `promotion_state`
- `trust_tier`
- `content_class`
- `document_type`
- `ingestion_truth`
- `storage_uri`
- `document_id`
- substrate inspection report artifacts

That means the viewer can be built as a read-oriented operator surface over stable substrate contracts instead of chasing moving ingestion behavior.

## Goals

- make raw substrate runs and rows browsable from the existing affordabot admin surface
- preserve one operator decision surface by linking to GlassBox instead of creating a parallel debugging tool
- support grounded manual inspection of raw artifacts, failures, and storage integrity
- keep the viewer internal-only and Clerk-protected through the existing admin auth boundary

## Non-Goals

- customer-facing analytics
- generic BI dashboarding
- Slack-first browsing
- replacing GlassBox
- changing substrate promotion or ingestion policy

## Active Contract

- `ALL_IN_NOW`
- build on current admin + GlassBox surfaces
- no new standalone dashboard service
- no new infrastructure dependency for the first two iterations

## Existing Grounding

Current repo surfaces already in place:

- backend admin router: `backend/routers/admin.py`
- backend trace/debug service: `backend/services/glass_box.py`
- frontend admin service: `frontend/src/services/adminService.ts`
- admin UI routes under `frontend/src/app/admin/*`
- substrate run artifact generation: `backend/scripts/substrate/substrate_inspection_report.py`

The viewer should extend these, not bypass them.

## Design

### Read Model

Add a substrate-focused read layer in the backend admin surface with three levels:

1. run list
- query manual substrate runs by `manual_run_id`
- return top-level counts and timestamps
- include status, resolved-target count, capture count, promotion buckets, and storage-integrity summary

2. run detail
- show the inspection report summary for a selected run
- list failures grouped by reason, jurisdiction, and asset class
- list sample raw rows or paginated rows for that run

3. raw row detail
- one raw scrape row with:
  - source/jurisdiction metadata
  - content class
  - trust tier
  - promotion state
  - ingestion truth
  - storage URI
  - document ID
  - direct artifact preview/open affordance when possible

### Operator UX

Add a new substrate explorer area under admin rather than a separate app.

Recommended UI structure:

- `Run Explorer`
  - run search/filter table
- `Run Detail`
  - summary cards
  - failure buckets
  - storage integrity results
  - raw row table
- `Raw Row Detail`
  - metadata JSON
  - extracted text preview where safe
  - artifact link / preview
  - GlassBox jump link if a downstream run exists

### GlassBox Relationship

GlassBox remains the step-trace tool.

The substrate viewer should:

- link from raw rows to GlassBox when `document_id` or downstream pipeline identity exists
- not attempt to absorb all pipeline-step UX into the substrate table itself

That preserves one decision surface without duplicating trace logic.

## Execution Phases

### Phase 1: Backend substrate read surface

- add backend admin endpoints for substrate runs, run detail, row detail, and report retrieval
- keep queries Postgres-native and JSONB-aware
- use the existing admin auth boundary

### Phase 2: Frontend substrate explorer

- add admin route(s) and shared types/services
- build a run table, run detail pane, and raw row drilldown
- link to existing GlassBox views where appropriate

### Phase 3: Report and operator shortcuts

- expose inspection report summaries directly in the viewer
- add copyable run ids, artifact links, and failure-bucket navigation
- support operator filters for jurisdiction, asset class, promotion state, content class, and trust tier

### Phase 4: Hardening

- tighten artifact preview rules
- add pagination and safe truncation for large rows
- verify auth, internal-only access, and operational usability

## Beads Structure

- `BEADS_EPIC`: `bd-990j`
- `BEADS_CHILDREN`:
- `bd-afqp` — Extend backend admin surfaces for substrate runs, raw rows, and artifact drilldown
- `bd-86yw` — Build frontend substrate explorer in existing admin surface with GlassBox links
- `bd-mf66` — Add run-centric inspection/report surfaces and operator shortcuts
- `bd-fphg` — Harden auth, artifact preview, and operator readiness for raw-data viewer

- `BLOCKING_EDGES`:
- `bd-86yw` blocks on `bd-afqp`
- `bd-mf66` blocks on `bd-afqp`
- `bd-fphg` blocks on `bd-86yw`
- `bd-fphg` blocks on `bd-mf66`

## Validation

- backend route tests for new substrate endpoints
- UI route load and auth verification for new admin surface
- run-level smoke check against a real `manual_run_id`
- artifact preview/open works for at least one text row and one storage-backed row
- GlassBox jump link works where downstream run identity exists

## Risks

- raw row payloads may be too large for naive UI rendering
- artifact preview can create accidental sensitive-data overexposure if not bounded
- GlassBox linkage may be partial for rows that never entered downstream analysis

## Rollback

- hide substrate explorer routes
- keep backend read endpoints behind admin auth only
- no migration or write-path dependency is required for the first release

## Recommended First Task

- `FIRST_TASK`: `bd-afqp`

Why first:

- the frontend viewer should not invent its own substrate read model
- the stable backend query surface is the dependency that makes the rest of the viewer honest
