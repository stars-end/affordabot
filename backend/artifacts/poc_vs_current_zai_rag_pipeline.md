# POC vs Current Z.ai Web Search in the RAG Pipeline

Generated: 2026-04-10 UTC

## Scope
- **Compared artifact:** `poc_two_vps_search_rate.py` + `poc_two_vps_search_rate_report.md`.
- **Compared runtime path:** current production-oriented research path in `legislation_research.py` + `web_search_factory.py`.
- This is a **code-path comparison**, not a live benchmark against z.ai service internals.

## Executive summary
- The two-VPS POC validates **scheduler mechanics** (round-robin, jitter, per-node concurrency caps, synthetic 429 behavior).
- Current Z.ai-backed RAG pipeline already has **query fanout, timeout guards, dedupe, and ranking**, but does **not** enforce the same explicit per-node/per-engine traffic shaping used in the POC.
- Practical takeaway: the POC is best treated as a **traffic-control module candidate** that can be inserted before `search_client.search(...)` calls in web research.

## Stage-by-stage comparison

| RAG stage | Current Z.ai-backed pipeline | Two-VPS POC | Gap / implication |
|---|---|---|---|
| Query planning | Builds ordered bill-specific query set (including CA official-site queries), then truncates by `LEG_RESEARCH_WEB_MAX_QUERIES` (default 8). | Fixed synthetic query load; no bill-aware query synthesis. | POC does not evaluate retrieval relevance quality. |
| Search provider | Primary: Z.ai structured `web_search` tool; fallback: DuckDuckGo HTML parsing on empty/failed structured result. | Local mock `/search` endpoint with deterministic soft-throttle window. | POC does not measure real upstream behavior/policy changes. |
| Concurrency | In-query parallelism with asyncio semaphore (`LEG_RESEARCH_WEB_MAX_CONCURRENCY`, default 3). | Per-node concurrency cap (`max_concurrency_per_node`) with thread workers. | Similar concept, different control surface (global coroutine semaphore vs per-node slot accounting). |
| Rate shaping | Timeout-bounded requests; no explicit token bucket / RPM limiter in current path. | Explicit paced dispatch: target RPM + jitter + round-robin. | POC introduces stronger anti-burst mechanics than current runtime. |
| Retry/backoff | Timeouts and fallback path exist; no explicit adaptive cooldown state machine in this path. | No retries either; just reports 429 outcomes under load. | Both paths currently lack adaptive backoff controller logic. |
| Result normalization | Normalizes raw results, dedupes by URL, then domain/keyword scoring + top-20 cutoff. | Returns only status outcomes (200/429) per node/engine. | POC says nothing about downstream ranking quality. |
| Sufficiency gates | Computes sufficiency using RAG chunks + web source counts and surfaces insufficiency reasons. | No sufficiency or evidence-quality gate. | POC is transport-layer only; not evidence-layer. |
| Provenance | Produces evidence envelopes/chunks integrated with analysis pipeline. | No provenance output. | Cannot compare factual-grounding quality from POC alone. |

## What the POC results mean for current pipeline

From `poc_two_vps_search_rate_report.md`:
- `200/hour total` scenario: 0 throttles.
- `24/min total` scenario: 0 throttles.
- `40/min total` scenario: 3 throttles out of 270 (1.1%).

Interpretation for the current pipeline:
- These results support that **paced + jittered dispatch is robust** under a soft-throttle model.
- They do **not** prove current Z.ai path has identical throttle behavior, because current path depends on external provider behavior and does not share the POC's explicit node-level scheduler.

## Recommended “ALL_IN_NOW” integration path (minimal scope)
1. Add a lightweight **pre-dispatch rate controller** abstraction in web research.
2. Implement **token-bucket + jitter + per-engine cooldown** behind that abstraction.
3. Keep existing retrieval/ranking/sufficiency logic unchanged.
4. Add verification mode that replays existing query lists through controller and records:
   - dispatch timestamps,
   - timeout/error rates,
   - source-count/sufficiency deltas.

This would make the comparison apples-to-apples: same research queries and scoring, different transport control policy.

## Evidence pointers
- POC harness and scheduler controls: `backend/scripts/verification/poc_two_vps_search_rate.py`
- POC results artifact: `backend/artifacts/poc_two_vps_search_rate_report.md`
- Current web search client (Z.ai structured + DDG fallback): `backend/services/llm/web_search_factory.py`
- Current research orchestration, fanout, ranking, sufficiency: `backend/services/legislation_research.py`
