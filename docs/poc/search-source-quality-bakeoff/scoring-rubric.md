# Search Source Quality Bakeoff Scoring Rubric

Feature key: `bd-9qjof.8`
Scope: Provider comparison for municipal source discovery (`private_searxng`, `tavily`, `exa`)

## 1) Per-query source scoring (0-100)

Each provider is evaluated against each query in `docs/poc/search-source-quality-bakeoff/query-corpus.json`. Score the best candidate from top-`k` search results (`k=5` default).

### A. Source relevance (0-40)

- `+20`: URL domain matches one of `preferred_domains`.
- `+10`: URL matches one of `preferred_url_patterns`.
- `+10`: Page content contains at least 3 `expected_signal_terms`.

### B. Reader-readiness proxy (0-35)

For the provider bakeoff harness, score these from title, snippet/highlights, and URL shape. The selected provider still requires the post-selection Windmill/Z.ai reader gate below.

- `+15`: title/snippet/URL strongly indicates a stable source document or meeting record.
- `+10`: title/snippet/URL has agenda/minutes structure indicators (date, item, meeting, motion/vote/action language).
- `+10`: title/snippet/URL includes housing-policy signal terms (housing, zoning, permit, affordable, planning, RHNA, HCD, rezoning, ADU).

### C. Quality and provenance (0-25)

- `+10`: source appears official primary source (city/county domain, official document host, or recognized meeting platform page under official context).
- `+10`: no obvious nav-shell dominance (menus/headers/footers dominate less than 40% of extracted text).
- `+5`: source includes stable document reference (`.pdf`, `MeetingDetail`, `.ashx`, explicit minutes/agenda permalink).

## 2) Disqualifiers (force per-query score to 0)

Any one condition sets the query score to `0`:

- Reader extraction is mostly navigation shell and lacks substantive meeting content.
- Source is clearly non-official or commercial aggregator without linkable primary source.
- Source is unreachable or returns anti-bot/interstitial content.
- Source does not reference the target jurisdiction.
- Query is non-negative-control and no municipal governance document is found in top-5.

## 3) Provider-level metrics

For each provider, compute:

- `query_success_rate`: fraction of corpus queries with score >= 60.
- `median_query_score`: median per-query score.
- `p90_latency_ms`: p90 search request latency.
- `error_rate`: fraction of failed search calls.
- `rate_limit_rate`: fraction of 429 or equivalent throttling.
- `reader_ready_rate`: fraction with reader-readiness subtotal >= 20.
- `official_domain_hit_rate`: fraction where top-3 includes preferred official domains.

## 4) Provider-level weighted score (0-100)

Compute:

`provider_score = 0.55 * median_query_score + 0.15 * (query_success_rate * 100) + 0.10 * (reader_ready_rate * 100) + 0.10 * (official_domain_hit_rate * 100) + 0.10 * reliability_score`

Where:

- `reliability_score = max(0, 100 - (error_rate * 100) - (rate_limit_rate * 150))`

Rationale:

- Discovery quality dominates (`55%`).
- Operational stability and reader-readiness are required for production path confidence.

## 5) MVP selection threshold

A provider is eligible for MVP only if all are true:

- `provider_score >= 75`
- `query_success_rate >= 0.70`
- `reader_ready_rate >= 0.65`
- `official_domain_hit_rate >= 0.70`
- `error_rate <= 0.05`
- `rate_limit_rate <= 0.03`
- No repeated disqualifier pattern on `San Jose CA` minutes/agendas queries (`sj-001` to `sj-006`)

Tie-breakers:

1. Higher `median_query_score`.
2. Lower `rate_limit_rate`.
3. Lower `p90_latency_ms`.

## 6) Mandatory post-selection gate

After selecting an MVP provider, run a full Windmill San Jose live gate using the selected provider and require:

- `PASS_MECHANICS` and `PASS_DISCOVERY_QUALITY` for San Jose query family.
- Z.ai LLM analysis is not marked as insufficient for at least one San Jose housing query with official-source provenance.
- Persisted evidence rows exist in Postgres and storage refs exist in MinIO for search -> reader -> analysis chain.

The architecture decision should remain provisional until this post-selection gate passes.
