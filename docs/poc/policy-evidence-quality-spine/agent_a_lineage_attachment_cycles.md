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
