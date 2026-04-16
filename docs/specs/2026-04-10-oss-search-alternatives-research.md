# OSS / Self-Hostable Web Search Alternatives for Affordabot Discovery

- Beads: bd-aa8w0 (epic bd-vho5t, dep bd-h6qfe)
- Date: 2026-04-10
- Mode: research / qa_pass (no implementation)
- Author: Claude (Opus 4.6) tech-lead handoff

## TL;DR (Findings First)

1. **SearXNG (self-hosted metasearch) is the only candidate that simultaneously meets all of: free, OSS, Linux-VM-friendly, JSON API, and no single-vendor anti-bot dependency.** It is the recommended first benchmark.
2. **Whoogle is structurally compromised** by Google's January 2025 no-JS countermeasures (per upstream README). Treat as fallback at best, not as a primary path.
3. **Common Crawl is not a search engine** for affordabot's discovery loop. It is a crawl archive and is at least weeks stale per snapshot. Useful as an *offline* seed list for local-gov roots, not as a query-time discovery surface.
4. **Brave Search API / Mojeek API** (not OSS, but cheap-tier and self-index-backed) are the realistic *quality* benchmark to compare SearXNG against. Brave runs its own index, which removes most anti-bot fragility from the affordabot side. Worth including in the matrix as a paid-but-bounded baseline.
5. The affordabot discovery lane should also **reduce dependence on general web search entirely** by investing in a "first-party root + bounded traversal" path: a curated registry of jurisdiction roots (Granicus, Legistar, CivicClerk, CivicEngage, Municode, etc.) plus a small per-jurisdiction crawler. This is the highest-leverage long-term move and is largely orthogonal to which search backend wins.

**Verdict: benchmark SearXNG now (P1), Brave/Mojeek API as paid baselines, defer Whoogle and Common Crawl, and open a parallel epic for first-party-root discovery.**

## Context

### What's broken today

Backend currently has three layered web-search paths, all routing through Z.ai:

- `llm-common/llm_common/web_search/client.py:51` — `WebSearchClient.search` posts to `https://open.z.ai/api/v1/search`. This is the "primary" path used by `run_discovery.py`.
- `backend/services/llm/web_search_factory.py:89` — `ZaiStructuredWebSearchClient._search_zai_structured` posts to the chat-completions endpoint with a `web_search` tool. Falls back to a DDG HTML scrape (`_search_duckduckgo_html`, line 149) when Z.ai returns empty.
- `backend/services/discovery/search_discovery.py:66` — legacy `_search_zai_structured` (same coding-chat workaround) with a Playwright DDG fallback. Wired in `backend/scripts/cron/run_discovery.py:165` as the "resilient" fallback service.

Empirically established (per assignment + recent Beads notes):

- Direct `z.ai` `web_search` returns `HTTP 200` with empty `search_result`.
- Z.ai search MCP server (`webSearchPrime`, `https://api.z.ai/api/mcp/web_search_prime/mcp`) also returns empty.
- The coding-chat workaround in `web_search_factory.py` is unstable and is not safe to treat as primary infrastructure.
- DDG HTML fallback exists but is brittle (CSS class drift + DDG anti-bot).

Z.ai docs (https://docs.z.ai/api-reference/tools/web-search) confirm `search_engine` is currently limited to `search-prime`, with quotas tied to subscription tier. The empty `search_result` failure mode is consistent with quota / engine-side regression rather than a payload bug, so this is not something we can patch in our client.

### What "discovery" actually needs

`backend/scripts/cron/run_discovery.py` and `backend/services/discovery/service.py` show the real shape of the dependency:

- Discovery wants **URLs** for local-government meeting / legislation / agenda / minutes pages, scoped per jurisdiction.
- Each candidate URL is then re-classified by `AutoDiscoveryService.discover_url` (LLM call) and gated by `ClassifierAcceptanceGate` before insert into `sources`.
- Search recall matters more than precision: the classifier + gate already do the precision work. We need a backend that returns *non-empty, plausibly-relevant* URLs for queries shaped like `"<jurisdiction> city council agenda site:granicus.com"` or `"<jurisdiction> planning commission minutes"`.
- Throughput is modest: O(jurisdictions × queries-per-jurisdiction), capped by `--max-queries-per-jurisdiction`. Even at full fleet, this is hundreds-to-low-thousands of queries per cron run, not millions.

That shape — moderate QPS, recall-tolerant, .gov-biased, classifier-gated — is exactly the regime where a self-hosted metasearch can win.

## Candidate Inventory

### 1. SearXNG (recommended first benchmark)

- **Model:** metasearch aggregator. No own index; queries fan out to Google, Bing, DuckDuckGo, Brave, Startpage, Mojeek, Wikipedia, Qwant, etc., normalizes results.
- **License:** AGPL-3.0. Self-hostable.
- **Deploy on epyc6:** Docker image (`searxng/searxng`) or native uWSGI. Single config file (`settings.yml`) controls enabled engines, rate limits, and JSON output. Resource footprint is small (a few hundred MB RAM); runs comfortably on a Linux VM next to existing affordabot services.
- **API:** First-class JSON output via `?format=json` (must be enabled in `settings.yml`). Returns title/url/content/engine fields, which is a near drop-in for `WebSearchResult` in `llm_common`.
- **Local-gov suitability:** High. Inherits Google/Bing recall on `.gov` domains, which is exactly the corpus affordabot cares about. `site:` operators pass through to most upstream engines, and SearXNG's own filtering supports `engines=` and `categories=` so we can pin to general web for discovery.
- **Risks:**
  - *Anti-bot fragility:* the burden moves from affordabot to SearXNG. When Google/Bing rate-limit, individual engines start returning empty; SearXNG mitigates by aggregating across N engines, so we degrade rather than fail.
  - *Maintenance burden:* low-to-moderate. Project is actively maintained (9k+ commits, regular releases). Engines occasionally need updates when upstream changes selectors.
  - *TOS/legal:* metasearch sits in a gray area but is widely deployed. For an internal jurisdiction-discovery use case (not user-facing), risk is low.
  - *Quality:* metasearch quality is generally on par with the best individual upstream — better than DDG HTML scraping, worse than a true paid index API for niche queries.
- **Cost:** $0 software, only the host VM.
- **Verdict:** **benchmark first.**

### 2. Brave Search API (paid baseline, not OSS, but include in matrix)

- **Model:** first-party crawler + index (independent of Google/Bing).
- **License:** commercial API, free tier (~2k queries/month) and pay-as-you-go (~$3/1k queries on the lowest paid tier).
- **Deploy:** SaaS, no self-hosting. Linux client is just `httpx`.
- **API:** clean JSON, supports `country`, `freshness`, `goggles` (custom ranking), `result_filter`. Goggles can be used to bias toward `.gov` and known civic-tech vendors.
- **Local-gov suitability:** Good. Brave's index covers `.gov` reasonably well; goggles can be tuned for civic content.
- **Risks:**
  - *Cost:* not free, but bounded — at affordabot's discovery QPS, even paid tier is small dollars/month.
  - *Vendor lock-in:* mitigated because the JSON shape is simple and matches `WebSearchResult`.
  - *No TOS-grey-area concerns* (this is what the API is sold for), unlike DDG/Whoogle scraping.
- **Verdict:** include as the *quality ceiling* baseline in the benchmark. If SearXNG matches Brave on recall for our query set, we ship SearXNG. If SearXNG is materially worse, Brave is the cheapest reliable Plan B.

### 3. Mojeek API (paid, independent index)

- **Model:** first-party crawler + index (UK-based, ~8B page index, fully independent of Google/Bing).
- **License:** commercial API; cheaper than Brave at small volumes, free trial available.
- **Deploy:** SaaS, simple JSON API.
- **Local-gov suitability:** Mixed. Independent index means coverage of US municipal sites is thinner than Google/Bing/Brave. Worth measuring, but I would not bet the discovery lane on it without data.
- **Risks:** thinner index coverage; smaller community.
- **Verdict:** include in the benchmark only as a tie-breaker / second independent baseline. Do not benchmark before SearXNG and Brave.

### 4. Whoogle (defer / fallback only)

- **Model:** unofficial Google search proxy/scraper. Self-hosted Flask app.
- **License:** MIT. Linux/Docker friendly.
- **API:** JSON via content negotiation.
- **Critical risk:** upstream README explicitly warns that since 2025-01-16 Google has been actively breaking no-JS scraping, and the maintainers describe this as "possibly the end for Whoogle." This is the same class of fragility that already burned the affordabot coding-chat workaround. Adopting Whoogle as primary would be trading one unstable scraper for another.
- **Verdict:** **do not benchmark as primary.** Acceptable only as a third-tier fallback behind a stable backend.

### 5. Common Crawl (defer, but useful for a different problem)

- **Model:** large-scale public web *archive*, not a search service. Monthly WARC/WAT/WET dumps on S3, plus a CDX URL index and a columnar URL index (queryable via Athena/DuckDB).
- **Local-gov suitability for *query-time discovery*:** poor. Latency is wrong (you query a static index, not a live engine), freshness is weeks-to-months stale, and you have to build relevance ranking yourself.
- **Local-gov suitability for *seed-list construction*:** very good. A one-shot DuckDB-over-CDX query for hostnames matching `*.gov` filtered by state/city patterns can produce a high-quality jurisdiction-root seed list essentially for free, which feeds the first-party-root discovery path described below.
- **Verdict:** **defer for query-time discovery.** Re-evaluate as a *seed builder* in the first-party-root epic, not as a Z.ai replacement.

### 6. (Considered, rejected fast) DuckDuckGo HTML scrape, SerpAPI, Tavily, Exa

- DDG HTML scrape: already in tree as fallback (`web_search_factory.py:149`, `search_discovery.py:135`). Same anti-bot fragility class as Whoogle. Keep only as last-resort fallback; do not invest.
- SerpAPI / Tavily / Exa: not OSS, not self-hostable, and all materially more expensive than Brave at our QPS. Out of scope for this memo (assignment explicitly biases to OSS / self-hosted).

## Strategic Question: Should we reduce dependence on general web search at all?

**Yes, in parallel.** The discovery code in `backend/scripts/cron/run_discovery.py` and the classifier in `backend/services/discovery/service.py` already assume that the *real* signal is a small set of canonical civic-tech vendors (Granicus, Legistar, CivicClerk, CivicEngage, Municode, PrimeGov, OpenGov, NovusAGENDA, etc.) plus the jurisdiction's own `.gov` root. For most US municipalities:

- The set of vendors is small (~10–15).
- Per vendor, the URL pattern for a jurisdiction is templated (e.g., `granicus.com/<slug>`, `<slug>.legistar.com`, `<slug>.civicclerk.com`).
- Once the jurisdiction-to-vendor mapping is known, most discovery can skip web search entirely and go directly to vendor-templated URLs + a bounded same-host crawl.

This means the long-term right answer is a **two-lane discovery system**:

- Lane A — *first-party-root discovery* (new): a curated jurisdiction→vendor registry + bounded same-host traversal. Covers the 80% case deterministically with zero search dependency.
- Lane B — *general web search* (the lane this memo is about): used only for the long tail of jurisdictions that don't match a known vendor, and for surfacing new vendors over time.

Lane A reduces the blast radius of any future Z.ai-class outage in Lane B and is consistent with the founder's "long-term payoff bias" (one-time investment, removes recurring fragility). It does not block this memo's recommendation — Lane B still needs a working backend today — but it should be tracked as a sibling epic.

## Recommended Benchmark Plan (smallest matrix that lets us choose)

### Backends under test

| Code | Backend | Cost | Why |
|---|---|---|---|
| A | SearXNG (self-hosted on epyc6, default engines: Google + Bing + Brave + DuckDuckGo + Mojeek) | $0 | primary OSS candidate |
| B | Brave Search API (paid tier, no goggle) | ~$0 at this volume | first-party-index ceiling |
| C | Brave Search API + civic goggle (`.gov` + known civic-tech hosts boosted) | ~$0 | measure goggle uplift |
| D | Z.ai `webSearchPrime` MCP (today's "primary") | existing | control / regression baseline |

Mojeek is intentionally excluded from the *first* wave — add it only if SearXNG and Brave are statistically tied and we want a tie-breaker.

### Query set (small, reproducible)

Pick **20 jurisdictions** stratified across 4 buckets (5 each):

1. Large city already in `sources` with known-good vendor (e.g., San Jose / Granicus).
2. Mid-size city already in `sources` with known-good vendor (e.g., a Legistar city).
3. Small city / town **not yet** in `sources` (long tail).
4. County government (different naming conventions than cities).

Per jurisdiction, run **3 query templates** (15 queries × 20 jurisdictions = 300 queries per backend):

- `"<name> city council agenda"`
- `"<name> planning commission minutes"`
- `"<name> municipal code OR ordinances"`

### Metrics

For each (backend × query):

1. **Non-empty rate** — % of queries returning ≥1 result. (Z.ai is currently failing here.)
2. **Top-10 relevance** — % of top-10 URLs that the existing `AutoDiscoveryService.discover_url` classifier rates `is_scrapable=True` with `confidence ≥ 0.75`. Reuses the gate already in `run_discovery.py`, so no new judgment infrastructure.
3. **Per-jurisdiction recall@10** — for jurisdictions in buckets 1–2 (where we know the right answer), did the backend return the canonical vendor host in the top 10?
4. **Latency p50/p95** per query.
5. **Cost per 1k queries** (effective).

Decision rule (binary, founder-cognitive-load-friendly):

- If SearXNG (A) achieves ≥ 90% of Brave (B/C) on metrics 1–3 and latency p95 < 5s, **ship SearXNG** as the primary backend; keep Brave as paid fallback behind a feature flag.
- Otherwise, ship Brave as primary; keep SearXNG as the OSS fallback.
- In either case, retire the coding-chat Z.ai workaround from the primary path.

### Out-of-scope for this benchmark

- Implementation of the chosen backend (separate Beads issue).
- Production cutover and monitoring.
- The Lane-A first-party-root work (separate epic, tracked independently).
- Mojeek and Whoogle (deferred unless A and B/C are inconclusive).

## Risks / Open Questions

- **SearXNG IP reputation:** if epyc6's egress IP is already rate-limited by Google for unrelated reasons, SearXNG numbers will look artificially bad. Pre-flight: run a handful of manual queries from epyc6 against `searxng.example.com` (any public instance) and against Google directly before standing up the local instance.
- **Benchmark reproducibility:** Z.ai's empty-results behavior is intermittent enough that we should snapshot the `D` (control) results on the same day as `A`/`B`/`C` to keep apples-to-apples.
- **Goggle authoring:** the civic goggle for backend `C` is non-trivial to write well. Time-box to ~1 hour; if it doesn't clearly help in spot-checks, drop `C` from the matrix.

## References

- Z.ai web_search API: https://docs.z.ai/api-reference/tools/web-search
- Z.ai search MCP: https://docs.z.ai/devpack/mcp/search-mcp-server
- OpenCode MCP integration: https://opencode.ai/docs/mcp-servers
- SearXNG: https://github.com/searxng/searxng , https://docs.searxng.org/admin/installation.html
- Whoogle: https://github.com/benbusby/whoogle-search
- Common Crawl: https://commoncrawl.org/the-data/get-started/
- Code touched (read-only): `backend/services/llm/web_search_factory.py`, `backend/services/discovery/search_discovery.py`, `backend/services/discovery/service.py`, `backend/scripts/cron/run_discovery.py`, `../llm-common/llm_common/web_search/client.py`
