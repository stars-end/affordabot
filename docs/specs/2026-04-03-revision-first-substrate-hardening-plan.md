# Revision-First Substrate Hardening Plan

Date: 2026-04-03
Beads epic: `bd-paaf`

## Summary

Affordabot should move from append-only anonymous raw scrape rows toward a revision-first substrate model.

The product moat is not merely "having scraped something once." The moat is:

- durable local-government document history
- truthful revision lineage
- explicit separation between "we checked again" and "the document changed"
- efficient reuse of ingest work when content is unchanged

That requires a model where canonical document revisions are first-class.

## Problem

Today, source rows are deduplicated, but raw scrape rows are not.

Current behavior:

- source identity is reused by URL or `(jurisdiction, name)`
- each capture computes a `content_hash`
- each capture still inserts a fresh `raw_scrapes` row
- unchanged recaptures therefore create duplicate raw rows
- changed captures create a new row, but without explicit revision lineage

This conflates:

- capture event: "we checked this document again"
- content revision: "the document content changed"

That weakens the moat because the system cannot yet cleanly answer:

- how many distinct revisions of this document exist?
- when did we last see the same revision again?
- what changed between revision N and N+1?
- did we unnecessarily re-embed identical content?

## Goals

- distinguish capture events from content revisions
- suppress duplicate identical revisions at write time
- create explicit revision lineage when content changes
- skip re-ingestion and re-embedding when content is unchanged
- surface revision history in operator tooling

## Non-Goals

- perfect semantic diffing for every document type
- OCR-first PDF diffing in this phase
- rewriting the whole substrate framework

## Active Contract

- `ALL_IN_NOW`
- revision-first model
- retain capture history
- no duplicate raw revision rows for identical content
- changed content becomes a linked new revision

## First Principles

For a local city/county government data moat, the durable asset is not a flat bag of scraped rows.

The durable asset is:

- canonical document identity
- revision timeline
- amended-content provenance
- exact replayability of what was known when

That means Affordabot should optimize for document history quality, not merely ingestion throughput.

## Design

### Conceptual Model

Separate two concepts:

1. capture event
- a fetch/check against a canonical document target
- includes timestamp, source, success/failure, and whether content changed

2. content revision
- a distinct content state for that canonical document
- identified by `content_hash`
- linked to the previous revision when changed

### Minimum Viable Identity

Add or derive:

- `canonical_document_key`
  - stable identity for the same logical doc across re-fetches
  - likely built from normalized canonical URL + document type + source identity
- `previous_raw_scrape_id`
  - pointer to prior revision row
- `revision_number`
  - monotonic within a canonical document chain
- recency metadata for repeated unchanged observation, such as:
  - `last_seen_at`
  - `seen_count`

Optional later:

- a dedicated `capture_events` table

### Minimum Viable Behavior

On capture:

1. resolve canonical document identity
2. find latest revision for that identity
3. compare new `content_hash` to latest revision hash

If hash unchanged:

- do not create a new revision row
- update recency metadata or append a capture-event record
- do not rechunk/reembed

If hash changed:

- create a new revision row
- set `previous_raw_scrape_id`
- increment `revision_number`
- run ingest/chunk/embed for the new revision only

### Diff Handling

For text-like docs:

- store a lightweight textual diff summary when a revision changes
- even a simple line-based or paragraph-based summary is valuable

For PDFs:

- phase 1 can remain hash-based only
- treat changed binary/PDF content as a new revision
- semantic diff can be deferred

## Data Model Direction

Two viable implementations:

### Option A: Extend `raw_scrapes`

Add revision fields directly to `raw_scrapes` and use metadata for recency.

Pros:

- least migration overhead
- easiest fit with current code

Cons:

- still mixes capture and revision concepts somewhat

### Option B: Add separate capture-event table

Keep `raw_scrapes` as revision records and add a separate `capture_events` ledger.

Pros:

- cleanest long-term model
- strongest moat semantics

Cons:

- more schema and UI work

Recommended phase shape:

- Phase 1: Option A
- Phase 2: graduate to Option B if repeated recapture volume justifies it

## Execution Phases

### Phase 1: Schema and identity model

- define canonical document identity rules
- add revision lineage fields
- define unchanged recapture semantics
- decide what lives in columns vs metadata

### Phase 2: Capture-path hardening

- update manual substrate capture
- update manual expansion capture flow
- update cron/source-based raw capture paths where relevant
- prevent duplicate identical revision inserts

### Phase 3: Ingestion and retrieval hardening

- skip re-ingest for unchanged content
- only re-chunk/re-embed changed revisions
- ensure “latest revision” and revision-chain reads are explicit

### Phase 4: Operator visibility

- surface revision number, prior revision, and seen-again history
- expose revision lineage in the raw-data viewer/admin/report surfaces

### Phase 5: Validation

- run stale-vs-amended document scenarios
- prove:
  - identical recapture does not create a new revision row
  - amended content creates exactly one new linked revision
  - unchanged content is not re-embedded

## Beads Structure

- `BEADS_EPIC`: `bd-paaf`
- `BEADS_CHILDREN`:
- `bd-qxih` — Design schema and identity model for canonical document revisions and capture recency
- `bd-rqup` — Implement duplicate suppression and revision chaining in substrate capture paths
- `bd-g49i` — Make ingestion and retrieval revision-aware and skip unchanged re-embedding
- `bd-gaae` — Expose revision lineage and seen-again history in admin/viewer/report surfaces
- `bd-e12k` — Validate revision-first behavior on stale vs amended municipal documents and publish readiness verdict

- `BLOCKING_EDGES`:
- `bd-rqup` blocks on `bd-qxih`
- `bd-g49i` blocks on `bd-rqup`
- `bd-gaae` blocks on `bd-rqup`
- `bd-e12k` blocks on `bd-g49i`
- `bd-e12k` blocks on `bd-gaae`
- `bd-wc1u` blocks on `bd-e12k`

## Validation

- migration/schema tests for revision fields
- capture-path tests for duplicate suppression
- ingest-path tests proving unchanged content skips re-embedding
- stale-vs-amended fixture scenarios
- bounded campaign validation against real municipal docs

## Risks

- deriving `canonical_document_key` incorrectly could merge unrelated docs
- forcing a single identity scheme too early could hurt edge-case jurisdictions
- revision logic must not hide real changed content behind over-aggressive normalization

## Rollback

- disable duplicate suppression
- continue append-only raw row inserts
- preserve already-added revision fields as inert metadata if needed

## Recommended First Task

- `FIRST_TASK`: `bd-qxih`

Why first:

- all downstream behavior depends on getting document identity right
- bad identity logic would corrupt the moat more than duplicate rows do
