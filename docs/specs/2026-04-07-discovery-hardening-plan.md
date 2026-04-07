# 2026-04-07 Discovery Hardening Plan (bd-gl47f)

## Summary

Affordabot should harden jurisdiction discovery before resuming broad coverage expansion.

The current system is strong enough for founder-led, bounded waves, but too weak to act as the primary source-selection engine for scaling jurisdictions. The main problem is that discovery is still shallow, query-first, and overly dependent on upstream search ranking instead of proving first-party publishing roots and truthful agenda/minute surfaces.

## Problem

Current discovery has three loosely connected modes:

1. Manual source inventory for substrate waves
2. Admin auto-discovery via LLM-generated search queries + web search results
3. Legacy search-discovery helper using Z.ai structured search with Playwright fallback

There is also a naming/documentation trap inside the code:

- `AutoDiscoveryService` in [auto_discovery_service.py](../../backend/services/auto_discovery_service.py) is the search-query and result aggregation path
- `AutoDiscoveryService` in [service.py](../../backend/services/discovery/service.py) is a separate URL/page-text classifier

Those are different systems with different jobs, but the current plan did not name that split clearly enough.

That mix creates several risks:

- query-first instead of jurisdiction-site-map-first behavior
- weak first-party bias beyond simple query wording
- little local reranking or truth scoring
- no clear staged promotion from search result -> official root -> family classification -> document validation -> inventory acceptance
- too much founder judgment needed to tell "plausible URL" from "truthful publishing path"

## Concise Critique

### 1. Discovery is too shallow

`AutoDiscoveryService` in [auto_discovery_service.py](../../backend/services/auto_discovery_service.py) generates 8-10 search queries, runs them through `WebSearchClient`, deduplicates exact URLs, and returns results. It does not deeply traverse the site or prove document surfaces.

### 2. Relevance is mostly outsourced

The current path mostly trusts the upstream search provider ordering. Affordabot does not meaningfully rerank by officiality, family fit, agenda/minute evidence, or likely publishing-root quality before returning URLs.

### 3. Search results and truthful roots are conflated

A plausible search hit is not the same thing as the correct first-party document root. The current design does not cleanly separate:

- search candidate
- official root
- family classification
- document-level validation
- inventory promotion

### 4. Manual inventory is more truthful than auto-discovery

The recent substrate work proved that manually curated source inventory is more reliable than the current auto-discovery path. That is a warning sign: the automated discovery layer is not yet trustworthy enough to drive broad expansion.

### 5. Legacy search helper remains uneven

`SearchDiscoveryService` in [search_discovery.py](../../backend/services/discovery/search_discovery.py) uses direct Z.ai structured search and falls back to DuckDuckGo + Playwright. That adds redundancy, but not a coherent truth model. It still remains search-first and result-oriented rather than first-party-path-oriented.

### 6. Discovery concepts are still ahead of implementation

Terms like `family` and `substrate` are the right target abstractions, but they are not yet mature discovery-system boundaries in the current codebase. The first implementation wave should treat them as the destination architecture, not as proof that the discovery layer already works that way.

### 7. Bounded traversal already has existence proofs

Affordabot already has specialized discovery surfaces such as [municode_discovery.py](../../backend/services/discovery/municode_discovery.py). Those do not solve general discovery, but they are evidence that bounded traversal is a valid pattern in this repo and should influence the MVP design.

## What Z.ai Gives Us Today

Official Z.ai documentation confirms the current external primitives are useful but insufficient on their own:

- The Z.AI Web Search MCP Server provides comprehensive web search, real-time information retrieval, and a `webSearchPrime` tool that returns titles, URLs, summaries, site names, and icons. It is a search primitive, not a first-party truth engine. Source: [Z.AI Web Search MCP Server](https://docs.z.ai/devpack/mcp/search-mcp-server)
- The Z.AI Web Reader MCP Server provides `webReader`, which fetches full webpage content, metadata, and links for a specified URL. It is a page-reading primitive, not a root-selection or family-classification system. Source: [Z.AI Web Reader MCP Server](https://docs.z.ai/devpack/mcp/reader-mcp-server)
- The current Z.ai web-search docs reinforce search as a tool capability, but they do not solve jurisdiction-specific official-root discovery, bounded traversal, or truthful source promotion by themselves. Source: [Z.AI Web Search Guide](https://docs.z.ai/guides/tools/web-search)

Practical takeaway:

- Z.ai search is useful for candidate generation
- Z.ai reader is useful for page inspection and link extraction
- affordabot still needs its own first-party traversal, family classification, and truth scoring

## Top 3 Upgrade Options

### Option 1. Keep current search-first model and add better reranking

What changes:

- keep LLM query generation
- keep search as primary entrypoint
- add local scoring for official domains, family patterns, agenda/minute evidence, and jurisdiction consistency

Pros:

- smallest change
- cheapest to implement
- can improve current admin discovery quickly

Cons:

- still anchored on search result quality
- still weak on deep first-party traversal
- likely to keep producing plausible-but-shallow candidates

Verdict:

- useful as an incremental patch
- not enough if the real goal is truthful jurisdiction expansion

### Option 2. Build a staged first-party discovery pipeline

What changes:

- use search only to find likely official roots
- then run bounded first-party traversal from those roots
- classify discovered surfaces into known family / candidate new family / unsupported
- validate whether agenda/minute document targets actually exist
- only then promote to source inventory

Pros:

- strongest truth model
- cleanest fit with affordabot’s moat
- reduces founder arbitration over time
- best long-term support for reusable-family expansion

Cons:

- more upfront work
- needs a clearer architecture and acceptance model

Verdict:

- recommended option

### Option 3. Use Z.ai search + reader as stronger front-end primitives, but keep truth scoring in affordabot

What changes:

- switch more discovery work onto Z.ai MCP search/reader surfaces
- use reader for follow-up page extraction and link harvesting
- still build affordabot-side scoring, family classification, and promotion rules

Pros:

- better external primitives than current shallow search-only usage
- less brittle than pure query-first returns
- lower lift than a full crawler from scratch

Cons:

- still needs affordabot-side truth model
- still not sufficient without staged validation

Verdict:

- best supporting tactic inside Option 2, not a substitute for it

## Recommended Plan

Choose Option 2, supported by Option 3 primitives.

Recommended active contract:

- search is only candidate generation
- first-party traversal is required before inventory promotion
- family classification is explicit
- agenda/minute validation is explicit
- truth scoring is local and explainable
- weak candidates remain hypotheses, not accepted sources

But the first implementation step should be smaller than the full target architecture.

## Updated MVP

The initial MVP should not try to build the full five-phase pipeline.

Instead, it should:

1. validate whether the existing classifier in [service.py](../../backend/services/discovery/service.py) can separate good from bad URLs using current source inventory plus explicit negatives
2. wire that classifier into [run_discovery.py](../../backend/scripts/cron/run_discovery.py)
3. add a simple acceptance gate before new sources are created
4. remove the current duplicate-write pattern in `run_discovery.py`

This keeps the first implementation bounded to the existing cron ingestion path and avoids premature expansion into a larger crawler/traversal project before the scoring signal is proven useful.

## Target Architecture

The following remains the correct long-term destination, but not the first implementation batch.

### Phase A. Official-root discovery

Input:

- jurisdiction name/type

Method:

- generate a small set of official-first search queries
- constrain toward first-party government or official-partner domains
- score likely root pages such as:
  - agenda center
  - archive center
  - board/calendar pages
  - legistar/granicus surfaces
  - document center

Output:

- a shortlist of candidate official roots

### Phase B. First-party traversal

Method:

- use reader/extractor tooling to fetch content and links
- follow a bounded set of likely first-party links
- stop after a small depth/budget

Output:

- a structured graph of likely civic publishing surfaces

### Phase C. Family classification

Method:

- classify each root/surface into:
  - existing known family
  - candidate new family
  - unsupported/ambiguous

Output:

- explicit family verdict and confidence

### Phase D. Document-surface validation

Method:

- prove whether the surface yields real:
  - agendas
  - minutes
  - optionally packets/attachments

Output:

- validation evidence, not just URL plausibility

### Phase E. Truth scoring and inventory promotion

Promote only when the candidate scores high enough on:

- officiality
- family fit
- agenda/minute evidence
- jurisdiction consistency
- URL/path stability
- repeatability

## Beads Structure

- `BEADS_EPIC`: `bd-gl47f`
- `BEADS_CHILDREN`:
  - `bd-gl47f.5` — Audit current discovery pipeline and external search surfaces
  - `bd-gl47f.1` — Consultant pressure-test of discovery upgrade plan
  - `bd-gl47f.3` — Design first-party truth-scored discovery architecture
  - `bd-gl47f.6` — Validate discovery classifier scoring against source inventory
  - `bd-gl47f.4` — Implement discovery-hardening MVP
- `BLOCKING_EDGES`:
  - `bd-gl47f.3` blocks on `bd-gl47f.5`
  - `bd-gl47f.3` blocks on `bd-gl47f.1`
  - `bd-gl47f.6` blocks on `bd-gl47f.5`
  - `bd-gl47f.4` blocks on `bd-gl47f.3`
  - `bd-gl47f.4` blocks on `bd-gl47f.6`
- `FIRST_TASK`: `bd-gl47f.5`

## Execution Phases

### Phase 1. Audit and pressure-test

- complete the current-state audit
- incorporate consultant review
- lock the narrowed MVP

### Phase 2. Classifier validation

- build a scored evaluation set from current inventory plus explicit negatives
- measure whether the classifier can separate likely-good from likely-bad candidates
- define the minimum acceptance threshold for cron gating

### Phase 3. Cron-gated MVP

- wire the classifier into [run_discovery.py](../../backend/scripts/cron/run_discovery.py)
- only create sources when the acceptance gate passes
- remove duplicate-write behavior
- keep the implementation to the existing discovery cron path, no new dependencies

### Phase 4. Long-term architecture follow-through

- only after the MVP proves useful, expand toward first-party traversal, explicit family classification, and richer truth-scored promotion

## Validation Gates

### Architecture Gate

- current discovery pipeline is fully mapped
- search/reader/tooling assumptions are documented
- truth scoring and promotion gates are explicit

### MVP Gate

- classifier evaluation set includes positive and negative examples
- acceptance gate is explicitly defined before cron wiring lands
- bounded discovery run on a small jurisdiction set
- false-positive promotion rate is meaningfully lower than the current search-first path
- duplicate source creation path in `run_discovery.py` is eliminated or proven impossible

### Product Gate

- founder can inspect why a source was accepted or rejected
- new-family or existing-family expansion starts from better roots than current manual-first workaround

## Risks

- overbuilding a crawler before validating the scoring model
- accidentally recreating a generic search engine instead of a government-root discovery system
- mixing exploratory candidates with accepted inventory

## Non-Goals

- broad jurisdiction expansion in the same wave
- generic consumer web search improvements
- replacing all manual curation immediately

## Recommended First Task

Start with `bd-gl47f.5`.

Why:

- it creates the baseline critique and tool inventory
- it turns current ambiguity into a concrete architecture target
- it gives the consultant lane a stable artifact to pressure-test before implementation starts
