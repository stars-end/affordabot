# Consultant Review: Discovery Hardening Plan (bd-gl47f.1)

**Date:** 2026-04-07
**Reviewer:** Architecture consultant (Claude Opus 4.6)
**Artifact under review:** `docs/specs/2026-04-07-discovery-hardening-plan.md` (PR #400)
**Beads:** bd-gl47f.1 (depends on bd-gl47f.5)

---

## Verdict

**Approve with changes.**

The plan's diagnosis is accurate and the recommended direction (staged first-party discovery pipeline, Option 2 + Option 3 primitives) is correct. However, the plan overbuilds the target architecture before validating the core scoring model, and underspecifies the MVP boundary. The Beads structure needs one adjustment. Specific changes below.

---

## 1. Is the Critique of Current Discovery Architecture Accurate and Complete?

**Accurate: yes. Complete: mostly.**

The plan correctly identifies the five weaknesses:

1. **Shallow discovery** — `AutoDiscoveryService` (the one in `auto_discovery_service.py`) generates queries, runs search, deduplicates URLs, and stops. No traversal, no validation of what the URL actually contains.

2. **Outsourced relevance** — The only ranking is upstream search-engine ordering. No affordabot-side reranking.

3. **Conflation of search hits and truthful roots** — Correct. The `run_discovery.py` cron writes every deduplicated URL directly to the `sources` table with `type='web'` and `status='active'`. There is no promotion gate.

4. **Manual > automated** — Correct directionally, though the plan references "substrate waves" and "family classification" as existing concepts. They are not implemented in the codebase. The plan's language implies these are shipped features being outperformed — they are aspirational concepts. This should be stated plainly.

5. **Legacy search helper is uneven** — Correct. `SearchDiscoveryService` uses Z.ai structured search with DuckDuckGo/Playwright fallback, but produces the same flat list with no truth model.

### What the critique misses

**A. Two separate `AutoDiscoveryService` classes exist and do different things.**

- `backend/services/auto_discovery_service.py` — LLM-generated search queries → web search → flat URL list. This is the one the cron job uses.
- `backend/services/discovery/service.py` — LLM-powered URL classifier (given a URL + page text, returns `DiscoveryResponse` with `is_scrapable`, `source_type`, `recommended_spider`, `confidence`). This is a classification service, not a search service.

The plan treats discovery as a single pipeline. In reality, there are two disconnected halves: one generates candidates (search-first), the other classifies a single URL (classification-first). Neither calls the other. The cron job (`run_discovery.py`) uses only the search half and never classifies what it finds. This is a bigger architectural gap than the plan acknowledges.

**B. The cron job has a double-write bug.**

`run_discovery.py` calls both `get_or_create_source()` and `create_source()` for every new URL (lines 72-93). This likely creates duplicate source rows unless `get_or_create_source` does an upsert that silently absorbs the second call. This is not a discovery-architecture issue per se, but it means the current source inventory may already contain duplicates from automated discovery.

**C. No "family" concept exists in the codebase.**

The plan discusses family classification as a pipeline stage (Phase C). This is correct as a design target, but the plan should acknowledge that "family" is a new concept to implement, not an existing concept to improve. The current source type system (`'web'`, `'agenda'`, `'minutes'`, `'legislation'`, `'generic'`) is flat and carries no hierarchical or pattern-based grouping.

**D. MunicodeDiscoveryService and CityScrapersDiscoveryService exist but are not part of the plan.**

These are domain-specific discovery services (Playwright-based Municode crawling, City Scrapers spider wrapping) that already do bounded first-party traversal for specific platforms. They are exactly the kind of thing Phase B envisions — but they exist today and are not referenced. The plan should position these as existence proofs for the general pattern, not reinvent the concept.

---

## 2. Is the Recommended Direction the Right Next Move?

**Yes.** Option 2 (staged first-party discovery pipeline) with Option 3 primitives (Z.ai search + reader) is the correct architecture.

The core insight is right: search is candidate generation, not truth. Affordabot's moat is knowing which government publishing surfaces are real and complete, not running better web searches.

However, the plan jumps too quickly to a five-phase target architecture (A through E) without validating the single most important primitive: **can affordabot reliably distinguish an official government publishing root from a plausible-but-wrong URL, given only the URL and its page content?**

If that primitive works (even via LLM classification), the rest of the pipeline follows. If it doesn't, the pipeline is wasted infrastructure around a broken scoring model.

**Recommendation:** Invert the validation order. Before building the pipeline, validate the scoring model on known-good and known-bad URLs from the existing source inventory.

---

## 3. Missing Failure Modes and Blind Spots

### 3.1 Government site diversity defeats pattern-based traversal

Government websites vary enormously. A bounded traversal strategy (Phase B) will work well for sites that follow common CMS patterns (Granicus, Legistar, CivicPlus/Municode, Boarddocs) but will fail on bespoke municipal sites. The plan should explicitly scope Phase B to known CMS families first and treat bespoke sites as a later tier.

### 3.2 URL instability

Government sites frequently reorganize. A URL that is a valid agenda center today may 404 in six months. The plan mentions "URL/path stability" as a truth-scoring signal but does not describe a liveness/health-check mechanism. Without periodic re-validation, the promoted inventory degrades silently.

### 3.3 Rate limiting and cost

Z.ai web search and reader have usage quotas (100-4000 combined operations per billing period depending on plan tier). A discovery pipeline that runs bounded traversal across hundreds of jurisdictions will burn through quotas quickly. The plan should specify per-jurisdiction budget limits and fallback behavior when quotas are exhausted.

### 3.4 LLM classification confidence is uncalibrated

The existing `DiscoveryResponse.confidence` field (0.0-1.0) is produced by an LLM. LLM confidence scores are notoriously uncalibrated — a 0.8 does not mean 80% accuracy. The plan should not treat LLM confidence as a probability. Instead, use it as a ranking signal and validate acceptance thresholds empirically.

### 3.5 No negative examples in the scoring model

The plan describes what a good source looks like but does not describe what a rejected source looks like. Without explicit rejection criteria and negative test cases, the pipeline will tend toward false acceptance (every government-looking URL gets promoted).

### 3.6 Cron job runs discovery for ALL jurisdictions every time

`run_discovery.py` iterates every row in the `jurisdictions` table. As jurisdiction count grows, this becomes expensive and slow. The plan does not address scheduling strategy (e.g., discovery budget per jurisdiction, priority ordering, cooldown periods).

---

## 4. How Z.ai Web Search, Search MCP, and Reader MCP Should Fit

### What Z.ai provides

| Surface | Tool | Affordabot use |
|---------|------|----------------|
| Web Search API | `search()` via `WebSearchClient` | Candidate generation (Phase A) |
| Search MCP Server | `webSearchPrime` | Alternative search entry for MCP-capable agents |
| Reader MCP Server | `webReader` | Page content + link extraction (Phase B traversal) |
| Chat with web_search tool | Structured search via chat completions | Current `SearchDiscoveryService` path |

### How they should be used

1. **Candidate generation (Phase A):** Use `WebSearchClient.search()` with domain filters (e.g., `["*.gov", "*.us"]`) to constrain results toward government domains. This is the existing capability, already working. The `search_domain_filter` parameter in the Z.ai API is underused today.

2. **Page inspection and link harvesting (Phase B):** Use Z.ai Reader (`webReader`) to fetch page content and extract links from candidate root pages. This replaces ad-hoc Playwright fallback for content extraction. Reader returns structured content, metadata, and link lists — exactly what bounded traversal needs.

3. **Do NOT use for truth scoring or family classification.** Z.ai search and reader are retrieval primitives. They return what is on the page, not whether the page is the correct official publishing root for a jurisdiction. Truth scoring must remain in affordabot.

### What affordabot must own locally

- **Official-root scoring model:** Is this URL the canonical publishing root for this jurisdiction's agendas/minutes?
- **Family classification:** Does this site match a known CMS family (Granicus, Legistar, CivicPlus, etc.)?
- **Document-surface validation:** Does this root actually yield real agenda/minute documents?
- **Promotion/demotion logic:** When does a candidate become an accepted source? When does an accepted source get flagged for re-validation?
- **Source inventory and lifecycle:** Status transitions, health checks, deduplication, and audit trail.

---

## 5. Minimum MVP That Materially Improves Discovery

The plan's five-phase architecture is the right long-term target but is too large for an MVP. The minimum viable improvement is:

### MVP: Scored candidate review with acceptance gate

**What it does:**
1. Run existing search-based candidate generation (already works)
2. For each candidate URL, fetch page content (via Z.ai Reader or existing Playwright extractor)
3. Run the existing `DiscoveryResponse` classifier (in `discovery/service.py`) on the fetched content
4. Apply a simple acceptance gate: only promote to `sources` table if `confidence >= threshold` AND `source_type in ['agenda', 'minutes']` AND domain matches known government TLD patterns (`.gov`, `.us`, `.org` for known civic orgs)
5. Log rejected candidates with reasons (for founder review and threshold tuning)

**What it changes in the codebase:**
- Wire `run_discovery.py` to call the URL classifier after search, before source creation
- Add a `discovery_status` field to sources (`candidate`, `accepted`, `rejected`) instead of writing directly as `active`
- Add domain-pattern allowlist for government TLDs
- Add rejection logging to `admin_tasks`

**What it proves:**
- Whether the classifier can distinguish good from bad at useful accuracy
- Whether domain filtering reduces false positives meaningfully
- Whether the acceptance rate is reasonable (too high = gate is useless; too low = gate is too strict)

**What it does NOT do:**
- No bounded traversal (Phase B) — that's post-MVP
- No family classification — that's post-MVP
- No new CMS-specific crawlers — existing Municode/CityScrapers services remain as-is
- No new external API integrations beyond Reader for page fetch

**Estimated scope:** 2-3 files changed, no new dependencies, testable against existing jurisdiction set.

---

## 6. What Should Stay Out of Scope for MVP

1. **Family classification system** — Valuable but premature. Build it after the scoring model is validated.
2. **Bounded first-party traversal** — Correct concept but needs the scoring model to work first. Otherwise you traverse and still can't tell good from bad.
3. **New CMS-specific crawlers** — Municode and CityScrapers already exist. Don't add more until the general pipeline proves itself.
4. **Multi-hop link following** — Phase B depth > 1 should wait until depth-1 (root page inspection) is proven useful.
5. **Automated re-validation / liveness checks** — Important but separate from discovery hardening.
6. **Search MCP Server integration** — `webSearchPrime` duplicates what `WebSearchClient` already does. No value in switching surfaces for MVP.

---

## 7. Recommended Changes to Beads Structure

The current structure is:

```
bd-gl47f (epic)
├── bd-gl47f.5 — Audit current discovery pipeline and external search surfaces
├── bd-gl47f.1 — Consultant pressure-test (this document)
├── bd-gl47f.3 — Design first-party truth-scored discovery architecture
└── bd-gl47f.4 — Implement discovery-hardening MVP
```

### Recommended change: Add a scoring-model validation task between .3 and .4

The plan jumps from architecture design (.3) to MVP implementation (.4). The riskiest assumption is whether the scoring model works. Add:

```
bd-gl47f (epic)
├── bd-gl47f.5 — Audit current discovery pipeline ✓ (done)
├── bd-gl47f.1 — Consultant pressure-test ✓ (this document)
├── bd-gl47f.3 — Design first-party truth-scored discovery architecture
│   blocks on: bd-gl47f.5, bd-gl47f.1
├── bd-gl47f.6 — Validate scoring model on existing source inventory (NEW)
│   blocks on: bd-gl47f.3
│   description: Run the DiscoveryResponse classifier against known-good and
│   known-bad URLs from the existing sources table. Measure precision/recall.
│   Determine acceptance threshold. This is the go/no-go gate for .4.
└── bd-gl47f.4 — Implement discovery-hardening MVP
    blocks on: bd-gl47f.6
```

**Why:** If the classifier doesn't work, .4 needs to be re-scoped to fix the classifier first. Finding this out during implementation is expensive. Finding it out in a focused validation task is cheap.

---

## 8. Summary of Recommendations

| # | Recommendation | Priority |
|---|---------------|----------|
| 1 | Acknowledge that "family" and "substrate" are new concepts, not existing features being improved | Documentation fix |
| 2 | Fix the double-write bug in `run_discovery.py` | Bug fix, do before MVP |
| 3 | Wire the existing URL classifier into the discovery cron (the core of MVP) | MVP critical path |
| 4 | Add `discovery_status` field to sources table (`candidate`/`accepted`/`rejected`) | MVP critical path |
| 5 | Use Z.ai Reader for page content fetch in the classifier step | MVP, replaces ad-hoc Playwright |
| 6 | Use `search_domain_filter` in WebSearchClient to constrain to government TLDs | MVP, easy win |
| 7 | Add bd-gl47f.6 (scoring model validation) before bd-gl47f.4 (implementation) | Beads structure |
| 8 | Scope Phase B (traversal) and Phase C (family classification) as post-MVP | Scope control |
| 9 | Add per-jurisdiction discovery budget and cooldown to cron scheduling | Post-MVP but design for it |
| 10 | Reference existing MunicodeDiscoveryService and CityScrapersDiscoveryService as existence proofs | Documentation fix |

---

## Appendix: Code References

| File | Role in current architecture |
|------|------------------------------|
| `backend/routers/discovery.py` | FastAPI endpoint, thin wrapper |
| `backend/services/auto_discovery_service.py` | LLM query generation + web search (cron path) |
| `backend/services/discovery/service.py` | URL classifier (unused by cron) |
| `backend/services/discovery/search_discovery.py` | Z.ai structured search + DuckDuckGo fallback |
| `backend/services/discovery/municode_discovery.py` | Playwright-based Municode crawler |
| `backend/services/discovery/city_scrapers_discovery.py` | City Scrapers spider wrapper |
| `backend/scripts/cron/run_discovery.py` | Discovery cron job (direct-to-sources write) |
| `llm_common/web_search/client.py` | Z.ai WebSearchClient with caching |

Tool routing exception: Used Explore agent + direct Grep/Read instead of llm-tldr for initial codebase discovery. Reason: llm-tldr requires `tldr warm` first and the breadth of the initial search (discovery architecture across multiple directories) was better served by parallel Glob/Grep via the Explore agent. Direct file reads were used for the small number of critical files identified.
