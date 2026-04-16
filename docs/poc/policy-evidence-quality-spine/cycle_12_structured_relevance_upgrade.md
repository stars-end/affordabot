# Cycle 12: Structured Relevance Upgrade (Gate A)

Date: 2026-04-15
Owner lane: Worker B (`structured-source enrichment/catalog`)

## Problem observed from Cycle 11

- Structured enrichment was integrated, but facts were weak for economic handoff:
  - Legistar candidate emitted ID-only fields (`event_id`, `event_body_id`) as `structured_policy_facts`.
  - CKAN candidate could return broad catalog metadata with low direct economic relevance (`dataset_match_count=0` cases).
- Result: Gate A structured lane was present but insufficiently meaningful for downstream economic parameterization.

## Conservative changes made

1. Legistar matter-context fetch before event fallback
   - Parse `MatterId` from selected Legistar URL context (`gateway.aspx?...ID=...`, `LegislationDetail`, or `/Matters/{id}`).
   - Fetch `Matters/{id}` and `Matters/{id}/Attachments` from San Jose Legistar Web API.
   - Emit a structured candidate with:
     - `artifact_type="matter_metadata"`
     - `linked_artifact_refs` for attachment URLs
     - `structured_policy_facts` focused on non-ID operational counts
     - `diagnostic_facts` for IDs (`matter_id`) so diagnostics do not pollute economic parameter cards.

2. CKAN relevance filter and useful URL requirement
   - Keep only datasets whose metadata/query context matches economic-policy tokens.
   - Require at least one usable HTTP(S) resource URL.
   - Emit structured facts for relevant-dataset coverage instead of raw unfiltered totals.
   - Keep raw catalog total in `diagnostic_facts` (`dataset_match_count_raw`) only.

3. Diagnostic/economic separation hardened
   - Event IDs remain available for traceability under `diagnostic_facts`.
   - ID fields are no longer emitted as `structured_policy_facts`.

## Files touched

- `backend/services/pipeline/structured_source_enrichment.py`
- `backend/tests/services/pipeline/test_structured_source_enrichment.py`

## Validation added

- Matter ID parsing from gateway URL.
- Event IDs are diagnostic-only, not economic parameters.
- Matter metadata returns provenance-bearing structured candidate with attachment refs.
- CKAN path only uses economically relevant datasets with concrete resource URLs.

## Intended Gate A impact

- Improves D3 (structured evidence quality) without introducing scraping heuristics.
- Preserves fail-closed behavior: if relevance/URL conditions are not met, structured candidate is omitted.
