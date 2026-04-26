# Agent A Lineage Attachment Cycles (`bd-3wefe.13`)

Feature-Key: `bd-3wefe.13`  
Lane: Official policy lineage + attachments (Legistar Matter 7526 focus)  
PR Base: #439 (`7d745304baf395e606483ef16d3db994ef54048a`)

## Cycle A-L1

Hypothesis: Matter-level attachment counts are insufficient for D1 lineage; we need attachment refs (id/title/url) with source-family classification.

Implementation:
- Hardened Legistar matter enrichment to emit `related_attachment_refs` with:
  - `attachment_id`
  - `title`
  - `url`
  - `source_family` (`resolution`, `ordinance`, `staff_report`, `fee_study`, `nexus_study`, `agenda/minutes`, `exhibit`, `unknown`)
- Preserved refs in both candidate root metadata and `lineage_metadata`.

Validation:
- `backend/tests/services/pipeline/test_structured_source_enrichment.py`

Measured Outcome:
- Matter 7526 fallback test now proves attachment refs are surfaced with ids/titles and classification.

## Cycle A-L2

Hypothesis: `policy_lineage.related_attachments` can only pass if lineage consumes structured attachment refs, not just search-candidate URLs.

Implementation:
- Updated bridge lineage construction to merge:
  - artifact URLs from candidate audit
  - structured attachment refs from enrichment candidates (`related_attachment_refs`)
  - fallback URLs from `linked_artifact_refs` when explicit refs are absent
- Added lineage payload fields:
  - `related_attachment_refs`
  - `related_attachment_source_families`
- `lineage_presence.related_attachments` now reflects real attachment refs when present.

Validation:
- `backend/tests/services/pipeline/test_bridge_runtime.py`

Measured Outcome:
- Runtime bridge regression now verifies lineage marks related attachments present and carries attachment ref metadata for Matter 7526 style inputs.

## Cycle A-L3

Hypothesis: Cycle 31 fails because CLF landing pages can outrank concrete artifacts and attachment handling stops at refs.

Implementation:
- Added economic-query artifact-first reader attempt ordering in bridge read-fetch so concrete artifacts are attempted before official landing pages when both are present.
- Added documented artifact-quality gate metadata in `source_quality_metrics`:
  - `artifact_quality_gate_status`
  - `artifact_quality_gate_reason`
  - `artifact_quality_gate.artifact_candidate_count`
  - `artifact_quality_gate.artifact_candidate_substantive_count`
  - `artifact_quality_gate.substantive_artifact_urls`
- Added maintained-fee-schedule exception gate:
  - explicit classification path (`maintained_fee_schedule`)
  - requires fee-table substance + current-context signals
  - does not grant `authoritative_policy_text` by default.
- Added bounded Legistar attachment content probe in structured enrichment:
  - probes high-value families (ordinance, resolution, memorandum/staff report, nexus/fee study)
  - emits `attachment_content_probes` with per-attachment status and excerpt
  - emits extracted attachment economic rows when parseable.
- Expanded policy lineage to distinguish:
  - refs present
  - content ingested
  - attachment economic rows available
  via `attachment_state` and new lineage presence flags.

Validation:
- `backend/tests/services/pipeline/test_bridge_runtime.py`
- `backend/tests/services/pipeline/test_structured_source_enrichment.py`

Measured Outcome:
- CLF-like source selection now prefers substantive concrete artifacts over landing pages.
- Attachment lane now surfaces ingestion status (false vs true) and economic-row availability separately from attachment refs.
