# Substrate Promotion Policy (bd-sc6o.3)

## Summary

This spec defines how Affordabot promotes captured municipal documents from
durable raw storage into a more selective, analysis-ready substrate layer.

The core rule is:

- preserve moat data broadly and cheaply
- promote narrowly and explainably
- use model reasoning only for ambiguous cases
- fall back cleanly to deterministic rules when the model is unavailable

This policy is grounded in the manual San Jose POC:

- official HTML documents can be durably captured
- official PDFs can be durably captured after `bd-sc6o.1`
- ingestion truth can now fail honestly after `bd-sc6o.2`
- official source alone is not enough to justify promotion
- retrievability alone is too strict for moat preservation because some binary
  official artifacts may be valuable before parser support exists

It is also grounded in live dev-database inspection on April 1, 2026:

- `raw_scrapes_total = 2459`
- `processed_true = 1936`
- `raw_document_ids = 1938`
- `chunked_document_ids = 206`
- `chunk_rows = 217`
- `legislation_api` rows dominate volume (`1198`) but only map to `1`
  chunked document id across the current historical corpus
- `meetings` rows are largely unusable today (`369` raw rows, `1` processed,
  `0` chunked), with the main `San Jose Meetings` source failing on missing
  row URLs
- `general` sources mix official city pages and third-party blogs, so source
  type alone is not a safe trust signal

These live distributions mean:

- legacy `processed=true` can never be treated as equivalent to
  `analysis-ready`
- trust must use hostname/domain rules plus explicit source metadata, not just
  `sources.type`
- legacy rows with no `ingestion_truth` must be treated as not yet evaluated
  for promotion

## Problem

Affordabot needs a substrate policy that supports three product goals at once:

1. preserve unique municipal raw data as moat
2. avoid over-promoting shell pages, calendars, and other low-value wrappers
3. keep operator/founder load low even when promotion requires document-level
   reasoning

If promotion is too strict, official but not-yet-parseable data never becomes a
durable asset. If promotion is too loose, the substrate fills with low-value
noise that weakens retrieval and raises maintenance cost.

## Goals

- preserve all durable official captures that meet a minimum trust bar
- distinguish durable raw storage from analysis-ready substrate
- support lightweight nightly reasoning on ambiguous candidates
- make all promotion outcomes machine-checkable and inspectable
- keep a rules-only fallback that can run without model availability
- log model failures for later alerting without blocking deterministic fallback

## Non-Goals

- final operator QA/reporting surface (`bd-sc6o.4`)
- second grounded validation sweep (`bd-sc6o.5`)
- broad schema redesign unless the current schema cannot encode the policy
- human review queue as a mandatory step for normal promotion

## Promotion State Model

The policy introduces three semantically distinct layers:

### 1. `captured_candidate`

Meaning:
- document was seen and captured, but has not yet cleared durable-raw policy

Expected use:
- transient or initial state during capture/review

### 2. `durable_raw`

Meaning:
- the raw artifact is durably stored with provenance
- we consider it part of the moat-preservation layer
- we are **not** claiming it is analysis-ready

This is the main preservation target for official municipal data.

### 3. `promoted_substrate`

Meaning:
- the document is valuable enough to be treated as part of the analysis-ready
  substrate
- retrieval/default indexing/reporting can prioritize it over generic raw data

This is intentionally selective.

## Live-Evidence Findings That Change The Policy

### 1. `sources.type` is not enough for trust

Live `general` sources include both:

- official hosts like `www.sanjoseca.gov`
- third-party hosts like `blockchangere.com`, `sfbayadu.com`,
  `actonadu.com`, `www.samara.com`, and `www.dwellito.com`

Therefore:

- `trust_tier` may not be inferred from `sources.type` alone
- the active policy must check canonical host/domain allowlists and explicit
  trust metadata

### 2. Legacy rows require a conservative default

Only the fresh POC rows currently carry machine-checkable
`metadata.ingestion_truth`.

Live stage distribution:

- `(none) = 2456`
- `vector_upsert_failed = 2`
- `ingest_skipped_non_text = 1`

Therefore:

- missing `ingestion_truth` means `legacy_unknown`, not `healthy`
- legacy rows must not be auto-promoted by default
- they remain eligible for re-evaluation when `.4/.5` surfaces exist

### 3. Durable raw preservation must be broader than analysis readiness

The live POC proved three different cases:

- meeting-detail HTML can be substantive yet still fail vectorization
- official PDFs can be durably preserved even before parser support exists
- official code pages can still be thin wrapper/shell pages

Therefore:

- `durable_raw` must preserve official captures broadly
- `promoted_substrate` must require substance and trust, not just official URL
- binary official docs should stay preserved even when promotion is deferred

## Active Policy

### Immediate Capture Policy

A document becomes `durable_raw` when all of the following are true:

- `trust_tier` is at least `primary_government` or another allowlisted official
  tier
- raw capture succeeded
- durable blob storage succeeded when applicable
- the source URL is stable enough to preserve provenance

For this policy, `trust_tier` must be derived from:

1. explicit source metadata when present
2. otherwise, a hostname/domain allowlist for official/public-government hosts
3. otherwise, a conservative non-official default

`sources.type` alone is not sufficient.

This means official captures should generally not remain stuck in
`captured_candidate` once the raw artifact is durably preserved.

### Immediate Non-Promotion Policy

A document must **not** become `promoted_substrate` immediately if any of the
following are true:

- it is clearly a shell/wrapper page
- it is a calendar/index page with little substantive content
- it is missing minimum evidence of substance
- it failed trust checks

### Promotion Policy

Promotion from `durable_raw` to `promoted_substrate` uses:

1. deterministic rules first
2. lightweight model reasoning only for ambiguous cases
3. rules-only fallback if model execution fails

## Deterministic Promotion Rules

Documents may be auto-promoted without LLM reasoning when they are obvious wins.

### Auto-Promote

Promote to `promoted_substrate` when all are true:

- `promotion_state = durable_raw`
- trust tier is official/allowlisted
- `document_type` is in an allowlist such as:
  - `agenda`
  - `minutes`
  - `meeting_detail`
  - `staff_report`
  - `fiscal_note`
  - `attachment`
  - `municipal_code`
  - `legislation`
- the document clears minimum substance checks
- ingestion truth is compatible with usefulness

### Minimum Substance Checks

At least one must be true:

- `content_class` is a binary official artifact like `pdf_binary`
- extracted preview/text exceeds a minimum substance threshold
- title or document-type heuristics strongly indicate a substantive official
  document

And one of the following usefulness checks must be true:

- `ingestion_truth.retrievable = true`
- `content_class = pdf_binary` and trust tier is official, even if parsing is
  deferred
- deterministic heuristics strongly identify the document as a substantive
  official record such as an agenda, meeting detail, staff report, or ordinance

This allows official PDFs into the moat-preservation layer without forcing them
into analysis-prioritized retrieval before parser support exists.

### Auto-Deny Promotion

Keep as `durable_raw` and do not promote when:

- `document_type` is `meeting_calendar`, `calendar`, or similar index surface
- preview/title pattern indicates shell/wrapper content
- trust tier is below official threshold
- ingestion truth is absent on a legacy row and no rules-based substance signal
  is available
- source host is not allowlisted official and the LLM pass does not explicitly
  promote it

## LLM Promotion Pass

### Model Role

The nightly LLM job is a **selective promotion classifier**, not the gatekeeper
for raw preservation.

It only operates on documents already in `durable_raw` that were not resolved by
deterministic rules.

### Primary Model

Use a lightweight multimodal Z.ai model:

- primary: `glm-4.6v`

Rationale:
- low enough cost/latency for nightly batches
- multimodal support is useful for PDFs and image-heavy official documents
- already aligned with existing `ZAI_API_KEY` availability in Railway env

### Model Inputs

For each candidate:

- canonical URL
- normalized hostname
- title
- document type
- content class
- trust tier
- preview text
- ingestion truth
- for binary documents:
  - blob URI or a lightweight extracted representation if available

### Model Output Contract

The model must return structured output:

- `promotion_decision`: `promote` | `keep_durable_raw`
- `reason_category`:
  - `substantive_official_document`
  - `index_or_shell_page`
  - `insufficient_substance`
  - `unclear`
- `confidence`: `high` | `medium` | `low`
- `explanation`: short text

### Model Authority Boundary

The model may:
- promote ambiguous `durable_raw` documents
- decline promotion and keep them in `durable_raw`

The model may **not**:
- delete raw artifacts
- downgrade trust tier
- block durable raw preservation
- override a deterministic deny for clearly non-official or shell/index content

## Fallback Policy

If LLM classification fails for any reason:

- timeout
- auth failure
- provider outage
- malformed output
- runtime exception

Then:

1. preserve the document as `durable_raw`
2. apply deterministic rules-only fallback
3. if still unresolved, keep it in `durable_raw`
4. log the LLM failure for later alerting/reporting

This ensures model instability never causes data loss or capture blockage.

## Logging and Alerting

Every promotion attempt should persist:

- `promotion_state`
- `promotion_method`: `rules` | `llm` | `llm_fallback_rules`
- `promotion_reason_category`
- `promotion_confidence`
- `promotion_last_evaluated_at`
- `promotion_error` when present

LLM failures must be logged in a way that later supports:

- aggregated operator QA
- later Slack notifications in `#affordabot-alerts`

Slack alerting is **not** the blocking dependency for `.3`, but the data model
must preserve enough information to surface it cleanly in a later wave.

## Recommended Data Contract

This policy can likely live in current metadata first, with later schema
promotion if it proves stable.

Minimum fields to persist somewhere machine-checkable:

- `promotion_state`
- `promotion_method`
- `promotion_reason_category`
- `promotion_confidence`
- `promotion_last_evaluated_at`
- `promotion_error`
- `promotion_policy_version`
- `trust_host_classification`

## Legacy Row Handling

Historical rows without `.2`-style `ingestion_truth` should be treated as:

- `promotion_state = null`
- semantic posture = `legacy_unknown`
- not eligible for analysis-priority defaults until evaluated

This is intentionally conservative.

The first implementation does **not** need to backfill every historical row.
It only needs to ensure:

- new rows get truthful promotion fields
- nightly evaluation can gradually classify historical rows
- absence of classification does not masquerade as readiness

## Nightly Cron Contract

The nightly promotion job should:

1. select `durable_raw` candidates not already promoted or recently evaluated
2. run deterministic promotion rules
3. send ambiguous cases to `glm-4.6v`
4. persist final promotion result
5. persist any LLM failure details
6. emit summary metrics for later operator/Slack surfacing

## Validation Gates

`.3` should not be considered complete until it proves:

- obvious shell/calendar pages remain out of `promoted_substrate`
- obvious substantive official documents can be promoted without manual review
- official binary artifacts remain preserved even when not promoted
- legacy rows without evaluation remain conservative and non-prioritized
- LLM failure cleanly falls back to rules-only behavior
- promotion results are machine-checkable from persisted state

## Implementation Notes

Recommended implementation order:

1. deterministic promotion rules + state persistence
2. nightly candidate selection
3. `glm-4.6v` structured classifier for ambiguous cases
4. LLM failure logging
5. later alert/reporting integration

## Decision Summary

The policy choice for Affordabot is:

- **broad preservation at `durable_raw`**
- **selective promotion to `promoted_substrate`**
- **rules first**
- **`glm-4.6v` second**
- **rules-only fallback on model failure**

This is the most robust way to preserve moat data without polluting the
analysis-ready substrate.
