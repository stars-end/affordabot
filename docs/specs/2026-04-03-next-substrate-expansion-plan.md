# Next Substrate Expansion Plan

Date: 2026-04-03
Beads epic: `bd-2giz`

## Summary

The next substrate phase should move from proving current provider families to expanding truthful coverage with new adapter families and a larger bounded validation campaign.

The next wave should not be “more defaults under the same families.” It should add real new coverage surface, then re-run the same campaign -> inspect -> repair loop.

## Problem

The current substrate wave proved:

- operator-ready bounded manual `capture_and_ingest`
- stable storage integrity across Postgres + pgvector + bucket storage
- truthful coverage for current provider families

The remaining misses are now mostly structural, not accidental:

- municipal code outside `san-jose`
- `meeting_details` for `agenda_center`-family jurisdictions
- custom archive/document-center jurisdictions like `palo-alto`, `milpitas`, and `alameda-county`

So the next expansion phase must add adapter truth, not pretend existing families cover more than they do.

## Goals

- expand jurisdiction coverage by adding real new adapter families or truthful new source inventory
- widen the surface area that can survive bounded `capture_and_ingest`
- preserve the same substrate truth model and inspection discipline

## Non-Goals

- framework redesign
- speculative source defaults
- breadth for its own sake without adapter truth
- unbounded campaigns

## Active Contract

- `ALL_IN_NOW`
- adapter-first expansion
- bounded validation after each coherent adapter tranche
- no fake coverage inflation

## Recommended Scope For The Next Wave

### Primary target

Add at least one of these real new capability lanes:

1. broader municipal code support beyond `san-jose`
2. custom archive / document-center family for jurisdictions that do not fit current Legistar or AgendaCenter assumptions
3. explicit model decision for `meeting_details` on non-Legistar municipal families

### Highest-value candidate jurisdictions

- `palo-alto`
- `milpitas`
- `alameda-county`

These were already deferred because they did not truthfully fit the current family assumptions.

### Secondary candidate jurisdictions

- additional county and municipal code targets only after adapter truth exists

## Adapter Strategy

### Lane A: Municipal code expansion

Investigate whether the next code targets can be truthfully covered by:

- additional `municode`-style mapping
- another hosted code-family adapter
- explicit non-support if the target does not match a stable hosted family

### Lane B: Custom archive/document-center family

Build a new adapter family for archive-style jurisdictions where the source of truth is:

- meeting archive pages
- agenda/minutes index pages
- document-center patterns

This is the most likely unlock for `palo-alto`, `milpitas`, and `alameda-county`.

### Lane C: Meeting-detail model decision

Do not automatically force `meeting_details` into families that do not have a real meeting-detail concept.

Instead:

- decide whether the product wants synthetic meeting-detail rows
- if not, preserve truthful absence and keep those lanes unsupported

## Execution Phases

### Phase 1: Source inventory expansion

- add truthful source rows for the next target jurisdictions
- classify trust and document types carefully
- no speculative roots

### Phase 2: Adapter implementation

- add the next family or families
- add fixture tests proving each supported asset class
- ensure source targeting and ingest paths are truthful

### Phase 3: Campaign validation

- run a widened bounded `capture_and_ingest` campaign
- include both old and newly added families
- require object storage, vector integrity, and run coverage to pass again

### Phase 4: Repair and verdict

- inspect failure buckets
- repair only real non-strategic defects
- publish the next readiness verdict and updated truthful coverage matrix

## Beads Structure

- `BEADS_EPIC`: `bd-2giz`
- `BEADS_CHILDREN`:
- `bd-knlg` — Expand truthful source inventory for next municipal adapter wave
- `bd-paba` — Implement next adapter families for municipal code and custom archives
- `bd-wc1u` — Run widened bounded substrate campaign with ingest and manual review
- `bd-xfcf` — Repair next-wave findings and publish post-adapter readiness verdict

- `BLOCKING_EDGES`:
- `bd-paba` blocks on `bd-knlg`
- `bd-wc1u` blocks on `bd-paba`
- `bd-xfcf` blocks on `bd-wc1u`

## Validation

- adapter-level tests for each newly supported family
- bounded `capture_and_ingest` campaign on the new matrix
- raw inspection of rows and report artifacts
- storage integrity pass:
  - object storage
  - vector integrity
  - run coverage
- updated truthful unsupported-lane list after repairs

## Risks

- custom archive families may not generalize as cleanly as Legistar or AgendaCenter
- municipal code sources can look deceptively similar while having different extraction semantics
- forcing meeting-detail parity across families may create fake product truth

## Rollback

- revert the new family defaults
- keep the old proven families intact
- continue using the existing bounded operator lane

## Recommended First Task

- `FIRST_TASK`: `bd-knlg`

Why first:

- adapter implementation is only as honest as the source inventory and target selection beneath it
- the next wave should fail fast on source truth before it commits to a new family shape
