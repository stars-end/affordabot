# affordabot-nik — Migrate California State to Plural Policy API

## Goal
Replace OpenStates for California State legislation ingestion with Plural Policy API to reduce recurring costs while maintaining (or improving) data quality.

## Scope (MVP)
- Implement a Plural Policy “source adapter” that can:
  - fetch CA bills + metadata
  - fetch actions/versions/documents if available
  - map into Affordabot’s internal scrape/legislation ingestion format
- Make the adapter usable by the existing discovery + ingestion pipeline without rewriting the pipeline.

## Open Questions (Needs User Input)
1. Plural Policy API access:
   - Do we have an API key? If yes: what env var name should we standardize on?
2. Coverage requirements:
   - Only current session bills, or historical backfill too?
3. Canonical identifiers:
   - Should Plural bill IDs be stored verbatim, or mapped to a canonical `external_id` scheme?
4. Rate limits:
   - What are acceptable fetch rates and retry policies?

## Proposed Implementation Steps
1. Add a new fetcher module under the existing “sources/scrapers” structure.
2. Normalize Plural payloads into the internal bill model used by ingestion.
3. Add unit tests with fixture payloads (golden JSON).
4. Add a feature flag/config switch:
   - CA State uses Plural; other jurisdictions remain unchanged.

## Acceptance Criteria
- CA State pipeline runs end-to-end using Plural as the upstream.
- `make verify-pr` and `make verify-dev` remain green.
- Costs reduced by removing OpenStates calls for CA State.

