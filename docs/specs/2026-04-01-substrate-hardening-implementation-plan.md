# Municipal Data Substrate Hardening Plan

## Summary

This plan locks the next Affordabot substrate wave after live San Jose POC work.

The active direction is:

- preserve official municipal artifacts broadly in `durable_raw`
- promote selectively into `promoted_substrate`
- treat legacy corpus truth as incomplete until re-evaluated
- harden the data substrate before widening scraping breadth further

This is the correct next step because the live corpus already shows meaningful
raw municipal capture, but the current system still overstates ingest quality
and mixes official and third-party content too loosely.

## Problem

The current dev corpus proves raw acquisition is happening, but the substrate is
not yet honest enough to become the long-term moat layer.

Grounding evidence from live dev DB inspection on April 1, 2026:

- `raw_scrapes_total = 2459`
- `processed_true = 1936`
- `raw_document_ids = 1938`
- `chunked_document_ids = 206`
- `chunk_rows = 217`

The mismatch is the core problem: the system currently allows large parts of the
corpus to look healthy while only a small portion is actually chunked and
retrievable.

Important live findings:

- `legislation_api` has `1198` raw rows and `1076` `processed=true`, but only
  `1` chunked document id in the current corpus
- `meetings` has `369` raw rows, `1` processed row, and `0` chunked documents
- `San Jose Meetings` is failing on missing `url` during ingestion
- `general` sources mix official city pages and third-party blogs under the
  same type
- manual POC rows showed:
  - official PDF preservation works after `.1`
  - HTML meeting detail can be substantive but still fail vector upsert
  - official code page can still be a thin shell page

## Goals

- preserve unique official municipal artifacts even when parsing is incomplete
- replace misleading ingest health with staged substrate truth
- promote only substantive, trustworthy documents into the analysis-priority
  layer
- keep the operator model simple enough for solo-founder use
- ground promotion policy in real corpus behavior, not intuition

## Non-Goals

- broad jurisdiction expansion before the substrate is hardened
- schema redesign beyond what is required to encode truthful policy
- mandatory human review queues for everyday promotion
- deeper analytics/pipeline sophistication unrelated to substrate truth

## Active Contract

Affordabot substrate semantics are:

1. `captured_candidate`
   - seen and captured, but not yet durably preserved or evaluated
2. `durable_raw`
   - preserved moat data with provenance; not necessarily analysis-ready
3. `promoted_substrate`
   - trusted, substantive, analysis-prioritized subset

Supporting contract:

- `processed` is not a source-of-truth health signal
- `metadata.ingestion_truth` is the source of truth for new rows
- missing `ingestion_truth` on historical rows means `legacy_unknown`
- `sources.type` is not enough to determine trust
- trust must use explicit metadata plus hostname/domain rules

## Architecture / Design

### Core Model

Use:

- `jurisdiction -> source -> raw_scrape -> document_chunks`
- promotion metadata on `sources.metadata` and/or `raw_scrapes.metadata`
- rules-first promotion, then nightly `glm-4.6v` for ambiguous cases

### Trust Model

Trust is determined in this order:

1. explicit source metadata
2. official hostname/domain allowlist
3. conservative fallback

Do not infer trust from `sources.type` alone.

### Preservation Model

Official captures that succeed at raw + durable blob storage should become
`durable_raw` even when:

- parsing is incomplete
- vectorization fails
- the document is binary and parser support is deferred

This preserves moat value without lying about analysis readiness.

### Promotion Model

Promote to `promoted_substrate` only when all are true:

- trust is official/allowlisted
- content is substantive
- document class is useful
- either retrievability is proven, or deterministic heuristics justify
  promotion for a known substantive official artifact

### Legacy Corpus Posture

Historical rows without staged truth remain conservative by default:

- no auto-promotion
- no claim of readiness
- eligible for later re-evaluation

## Execution Phases

### Phase 1: Binary-Safe Preservation

Status:
- effectively done in `bd-sc6o.1`

Outcome:
- binary official artifacts can be durably stored
- `content_class` exists

### Phase 2: Truthful Ingestion State

Status:
- effectively done in `bd-sc6o.2`

Outcome:
- new rows carry machine-checkable `ingestion_truth`
- vector failures and non-text skips are surfaced honestly

### Phase 3: Promotion Policy + Nightly Evaluator

Scope:
- implement `captured_candidate -> durable_raw -> promoted_substrate`
- add trust-host classification
- add rules-first promotion
- add nightly ambiguous-case classifier using `glm-4.6v`
- add rules-only fallback and LLM failure logging

### Phase 4: Operator QA Surface

Scope:
- single low-cognitive-load report or admin surface showing:
  - host/trust classification
  - ingestion stage
  - promotion state
  - promotion reason
  - recent failures

### Phase 5: Second Grounded Validation Sweep

Scope:
- rerun manual capture with hardened contract against:
  - substantive HTML meeting detail
  - binary agenda PDF
  - official code/ordinance page
  - one third-party general page for deny-path verification

## Beads Structure

`BEADS_EPIC`
- `bd-sc6o` — `Harden municipal data substrate after manual POC`

`BEADS_CHILDREN`
- `bd-sc6o.1` — `Implement binary-safe raw capture and content classification`
- `bd-sc6o.2` — `Implement truthful ingestion stage model and retrievability accounting`
- `bd-sc6o.3` — `Implement promotion gates for candidate versus durable substrate`
- `bd-sc6o.4` — `Add substrate health inspection surface for operator QA`
- `bd-sc6o.5` — `Run second grounded validation sweep across HTML, PDF, and code docs`

`BLOCKING_EDGES`
- `bd-sc6o.2` blocks on `bd-sc6o.1`
- `bd-sc6o.3` blocks on `bd-sc6o.1`
- `bd-sc6o.3` blocks on `bd-sc6o.2`
- `bd-sc6o.4` blocks on `bd-sc6o.2`
- `bd-sc6o.4` blocks on `bd-sc6o.3`
- `bd-sc6o.5` blocks on `bd-sc6o.1`
- `bd-sc6o.5` blocks on `bd-sc6o.2`
- `bd-sc6o.5` blocks on `bd-sc6o.3`

## Validation

### Policy/State Validation

- new official PDF capture lands in `durable_raw` with non-null `storage_uri`
- new HTML capture with vector mismatch is marked `vector_upsert_failed`
- legacy rows with no `ingestion_truth` are treated as `legacy_unknown`
- non-official third-party pages do not auto-promote solely because they are
  `processed=true`

### POC Validation Targets

- one official HTML meeting-detail page
- one official PDF agenda
- one official code/ordinance page
- one third-party general informational page

### Nightly Evaluator Validation

- deterministic rules auto-promote obvious official substantive docs
- deterministic rules deny obvious shell/index pages
- ambiguous docs can be classified by `glm-4.6v`
- LLM failure falls back to rules-only and logs `promotion_error`

## Risks / Rollback

### Risk: Over-preserving low-value pages

Mitigation:
- broad preservation only to `durable_raw`
- strict/selective `promoted_substrate`

### Risk: Model-driven inconsistency

Mitigation:
- rules-first design
- LLM only for ambiguous cases
- LLM cannot delete or block preservation

### Risk: Legacy data looks healthier than it is

Mitigation:
- treat missing staged truth as `legacy_unknown`
- require new truth model for future rows

### Risk: Solo-founder operational load grows

Mitigation:
- one nightly promotion pass
- one QA surface
- no manual triage queue in the default loop

## Recommended First Task

`FIRST_TASK`
- `bd-sc6o.3`

Why first:

- `.1` and `.2` already established the preservation and truth primitives
- `.3` is the policy layer that turns those primitives into a stable substrate
  contract
- `.4` and `.5` should validate the policy, not invent it

## Decision Summary

The implementation spec is now grounded enough to lock:

- preserve official municipal data broadly in `durable_raw`
- use hostname/trust classification, not `sources.type`, as the primary trust
  signal
- keep legacy rows conservative until re-evaluated
- use `glm-4.6v` only as an ambiguous-case promotion assistant
- widen scraping only after `.3`, `.4`, and `.5` confirm the hardened contract
