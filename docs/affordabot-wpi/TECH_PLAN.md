# affordabot-wpi — Implement NYC Council API Scraper (Smart Scraper)

## Status

**Post-MVP (P3):** NYC is explicitly out of MVP scope.

## Goal
Add a “Smart Scraper” integration for NYC Council using a free public API (high-quality structured data) to expand jurisdiction coverage without expensive scraping.

## Scope (MVP)
- Fetch NYC Council legislation objects + core metadata.
- Map into Affordabot’s internal ingestion format (same downstream pipeline).
- Provide a minimal discovery configuration for NYC Council.

## Open Questions (Needs User Input)
1. Which API?
   - Provide the canonical NYC Council API base URL and docs link you want to standardize on.
2. Data coverage:
   - Only active items, or include historical?
3. Update schedule:
   - Cron cadence and desired freshness.
4. Storage:
   - Store raw payloads as “scrapes” for auditability, or only store normalized rows?

## Proposed Implementation Steps
1. Implement `NYCCouncilFetcher` (HTTP client + pagination).
2. Implement mapping → internal bill/action/document structures.
3. Add fixture-based unit tests.
4. Add discovery config + verify pipeline coverage for NYC Council.

## Acceptance Criteria
- NYC Council ingestion runs end-to-end.
- Data is visible in admin UI for NYC jurisdiction.
- `make verify-pr` and `make verify-dev` remain green.

