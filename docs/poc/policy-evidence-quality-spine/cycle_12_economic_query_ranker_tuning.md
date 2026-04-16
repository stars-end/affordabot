# Cycle 12 - Economic-query ranker tuning for Gate A scraped evidence quality

Date: 2026-04-15
Scope owner: backend search/ranker only (no storage/economic endpoint logic changes)

## Problem observed in Cycle 11

For San Jose economic-analysis search queries, the read-fetch candidate selector could prefer procedural Legistar pages (for example `MeetingDetail.aspx`) over official fee/rate pages. That allowed a persisted package with weak numeric fee/rate signal, which then failed economic sufficiency.

## Tweak implemented

File changes:
- `backend/services/pipeline/domain/commands.py`
- `backend/services/pipeline/domain/bridge.py`
- `backend/tests/services/pipeline/test_domain_commands.py`

Behavioral changes:
1. `rank_reader_candidates` now accepts optional `query_context`.
2. When `query_context` clearly indicates an economic/fee/rate question, ranking adds:
   - positive boosts for fee/rate/impact-fee/nexus signals in URL/text,
   - additional boost for numeric parameter patterns (`$`, `%`, `per sq ft`, `per square foot`),
   - extra penalties for low-value portal/procedural pages without economic value signals.
3. For non-economic queries (including meeting-minutes queries), existing scoring behavior remains the baseline.
4. Bridge runtime now passes `request.search_query` into ranking.
5. In-memory domain command runtime now passes persisted search snapshot query into ranking.

## Test coverage added

New focused tests in `backend/tests/services/pipeline/test_domain_commands.py`:
- `test_rank_reader_candidates_economic_query_prefers_fee_rate_sources_over_procedural_pages`
- `test_rank_reader_candidates_meeting_minutes_query_keeps_legistar_artifact_preference`

These cover both:
- targeted rerank improvement for San Jose fee/rate economic queries, and
- regression guard for meeting-minutes artifact preference.

## Expected Gate A impact

- Improves scraped evidence selection quality for economic-analysis queries by reducing procedural-page top picks.
- Preserves existing Legistar artifact priority for meeting-minutes oriented queries.
- Should increase probability that selected reader candidate contains fee/rate/numeric evidence needed for downstream economic sufficiency.
