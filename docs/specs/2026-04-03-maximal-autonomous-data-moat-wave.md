# Maximal Autonomous Data Moat Wave

Date: 2026-04-03

## Summary

This is the umbrella execution spec for the next maximal autonomous affordabot product wave.

The product moat is:

- deep, truthful local city/county document coverage
- revision-aware document history
- founder-debuggable raw data and run inspection

This wave is intentionally not a generic platform buildout. It is a moat-building execution bundle with four coordinated lanes:

1. bucket/MinIO truth cleanup
2. founder-facing raw-data viewer MVP
3. revision-first substrate hardening
4. existing-family substrate deepening, with one exploratory new-family lane only if it does not derail the primary goal

## Locked Product Decisions

The following decisions are already locked for this wave:

- primary success condition: existing-family deepening
- MVP deep coverage threshold: `agendas + minutes`
- municipal code: out of MVP unless nearly free
- revision model: revision-first
- unchanged documents:
  - no new revision row
  - update recency metadata only
- changed documents:
  - create a new revision row
  - hash-based revisioning is sufficient for MVP
  - lightweight text diffs for text-like content only
  - no PDF semantic diff in MVP
- viewer MVP stops at:
  - run list
  - failure buckets
  - raw row detail
- artifact preview is required post-MVP, not wave-gating for MVP
- semi-official sources are allowed for capture/inspection, but should not inflate “deep coverage” unless clearly in the civic publishing path
- a new provider family is acceptable if it looks clearly reusable, even if first proven on one jurisdiction

## Success Criteria

This wave counts as successful only if all of the following are true:

1. a fixed set of jurisdictions reaches truthful `agendas + minutes` coverage under existing families
2. the founder no longer needs SQL to understand what worked or failed in a substrate run
3. revision-first duplicate suppression is proven on:
   - one unchanged real document
   - one amended real document

Working threshold for this wave:

- target `5` jurisdictions with truthful `agendas + minutes`

## Non-Goals

- broad admin-platform redesign
- generic dashboard productization
- generic LLM observability rebuild
- municipal code as a primary wave goal
- broad multi-family speculative scraping

## Wave Structure

### Lane 1: Storage/Infra Truth

Track:

- `bd-85bn` — Fix Railway Bucket service config and MinIO source-of-truth drift

Purpose:

- make bucket/runtime/docs truth consistent
- remove dead source-link ambiguity from Railway
- keep infra drift from contaminating operator trust

### Lane 2: Founder-Debuggable Viewer MVP

Track:

- `bd-990j`

Children:

- `bd-afqp` — Extend backend admin surfaces for substrate runs, raw rows, and artifact drilldown
- `bd-86yw` — Build frontend substrate explorer in existing admin surface with GlassBox links
- `bd-mf66` — Add run-centric inspection/report surfaces and operator shortcuts
- `bd-fphg` — Harden auth, artifact preview, and operator readiness for raw-data viewer

Purpose:

- give the founder a single decision surface for:
  - what worked in this run
  - what failed and why
  - what the raw row actually is

### Lane 3: Revision-First Hardening

Track:

- `bd-paaf`

Children:

- `bd-qxih` — Design schema and identity model for canonical document revisions and capture recency
- `bd-rqup` — Implement duplicate suppression and revision chaining in substrate capture paths
- `bd-g49i` — Make ingestion and retrieval revision-aware and skip unchanged re-embedding
- `bd-gaae` — Expose revision lineage and seen-again history in admin/viewer/report surfaces
- `bd-e12k` — Validate revision-first behavior on stale vs amended municipal documents and publish readiness verdict

Purpose:

- stop conflating “we checked again” with “the content changed”
- preserve the moat as durable document history, not a noisy pile of duplicate raw rows

### Lane 4: Existing-Family Deepening

Track:

- `bd-2giz`

Children:

- `bd-knlg` — Expand truthful source inventory for next municipal adapter wave
- `bd-paba` — Implement next adapter families for municipal code and custom archives
- `bd-wc1u` — Run widened bounded substrate campaign with ingest and manual review
- `bd-xfcf` — Repair next-wave findings and publish post-adapter readiness verdict

Purpose:

- deepen truthful coverage on a small number of jurisdictions first
- use new-family work as a secondary unlock lane, not the primary success condition

## Recommended Execution Order

1. finish `bd-85bn` in parallel with planning/publication cleanup
2. start `bd-afqp` and `bd-qxih`
3. once backend substrate endpoints and revision identity are grounded:
   - continue `bd-86yw`
   - continue `bd-rqup`
4. once duplicate suppression and viewer read models exist:
   - continue `bd-g49i`
   - continue `bd-mf66`
5. then:
   - `bd-fphg`
   - `bd-knlg`
6. substrate expansion campaign must not start before:
   - `bd-e12k` proves revision-first behavior
7. then:
   - `bd-paba`
   - `bd-wc1u`
   - `bd-xfcf`

## Parallelism Contract

- maximum active implementation subagents: `2`
- bucket truth lane may run in parallel if it does not block product work
- do not allow orchestration experimentation to block product-critical lanes

## Grounding and Rationale

This sequencing follows the actual risks surfaced by the ad-hoc substrate work:

- current families already provide meaningful truthful coverage
- the main current weaknesses are:
  - missing founder-debuggable visibility
  - duplicate-prone revision handling
  - deferred new-family jurisdictions that do not fit existing shapes

That means the next highest-leverage work is:

- inspection surface
- revision correctness
- then deeper truthful coverage

not:

- more generic admin tooling
- more shallow jurisdictions
- broad new family speculation before the existing moat surface is solid

## Validation Gates

- `bd-85bn`: runtime/docs/service truth aligned
- `bd-990j`: founder can inspect runs without SQL
- `bd-paaf`: unchanged docs do not create new revision rows; amended docs do create linked revisions
- `bd-2giz`: target jurisdictions achieve truthful `agendas + minutes` coverage with bounded campaign validation

## Strategic Stop Conditions

Stop and ask only if one of these becomes true:

1. revision identity cannot be made trustworthy without a materially larger schema change than expected
2. semi-official source use becomes the only way to hit the coverage target and starts diluting truth too much
3. the first exploratory new family looks one-off rather than reusable
4. the viewer MVP starts expanding into generic admin-platform work

## Immediate Next Task

- `FIRST_TASK_A`: `bd-afqp`
- `FIRST_TASK_B`: `bd-qxih`

Why:

- founder debugging and revision correctness are the two highest-leverage constraints on the next coverage wave
