# OSS Pipeline Hardening + Saratoga Evaluation Plan

Generated: 2026-04-10 UTC

## Hardening priorities (P0 -> P2)

### P0 (immediate)
1. **Backoff + retries on throttling**
   - Retry on `429/503` with exponential backoff + jitter.
   - Keep retry budget small (e.g., 2-3 attempts) to avoid stampedes.
2. **Strict timeouts + bounded concurrency**
   - Keep per-request timeout low and enforce semaphore cap around concurrent web queries.
3. **Structured observability**
   - Emit: request count, retry count, status-code distribution, p50/p95 latency, empty-result ratio.
4. **Fail-safe behavior**
   - If web search degrades, preserve pipeline output with explicit insufficiency reasons instead of silent partial failures.

### P1 (next)
1. **Domain allow/boost list for municipal workflows**
   - Prioritize: `ci.saratoga.ca.us`, `sccgov.org`, `.gov` sources.
2. **Result quality gates**
   - Require minimum unique domains + minimum official-domain hits before marking evidence sufficient.
3. **Caching / dedupe**
   - Cache by normalized query + recency window to reduce repeated scraping pressure.

### P2 (production hardening)
1. **Circuit breaker** for persistent endpoint failures.
2. **Adaptive query pruning** when retry/error budget is exhausted.
3. **A/B compare** against current z.ai route on a fixed jurisdiction corpus.

## Saratoga integration evaluation protocol (live OSS endpoint)

Use your EPYC6-hosted SearXNG endpoint and run the same RAG flow with live web search:

```bash
python3 backend/scripts/verification/poc_rag_pipeline_oss_swap.py \
  --live-endpoint "http://<epyc6-searxng-host>:8080/search" \
  --bill-id "SR-2026-001" \
  --jurisdiction "Saratoga CA" \
  --out backend/artifacts/poc_rag_pipeline_oss_swap_saratoga_live.md
```

Expected evaluation outputs:
- `top_web_sources` list for manual review.
- `official_domain_hits` and `saratoga_mention_hits` counters.
- Contract checks (`web_sources`, `evidence_envelopes`, `is_sufficient`).

## Pass criteria (initial)
- `web_sources >= 3`
- `official_domain_hits >= 1`
- `saratoga_mention_hits >= 2`
- No hard failure from OSS endpoint path.

## Notes
- In this environment, outbound live internet calls were blocked by tunnel `403`; local mock-mode validation was used for contract verification.
