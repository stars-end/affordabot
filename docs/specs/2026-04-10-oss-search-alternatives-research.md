# OSS/Self-Host Search Alternatives for Discovery Reliability

Date: 2026-04-10  
Mode: `qa_pass`  
Feature-Key: `bd-aa8w0`

## Findings-First Ranking

1. **SearXNG** (`metasearch`) -> **Benchmark now (first)**
2. **YaCy Search Server** (`self-indexing crawler/search engine`) -> **Benchmark now (second wave)**
3. **Scrapy + Meilisearch** (`first-party-root-discovery helper + local index`) -> **Benchmark now (bounded side-lane)**
4. **Apache Nutch (+ Solr/Elasticsearch)** (`self-indexing crawler/search framework`) -> **Fallback (high ops)**
5. **Whoogle Search** (`unofficial Google scraping proxy`) -> **Fallback only; not primary**

## Why This Ranking

Current discovery path in code is brittle under empty-search conditions:
- `backend/services/llm/web_search_factory.py` uses Z.ai structured search first, then falls back to DuckDuckGo HTML scraping.
- `backend/services/discovery/search_discovery.py` similarly attempts Z.ai structured output and then Playwright DDG fallback.
- `backend/scripts/cron/run_discovery.py` wraps a primary `llm_common.WebSearchClient` with fallback search service.
- `../llm-common/llm_common/web_search/client.py` is pinned to Z.ai `/search`.

Given repeated `HTTP 200` with empty search payloads, the first replacement should maximize:
- easy Linux deployment on VM,
- low cost,
- immediate robustness signal against empty-result failure mode,
- minimal refactor pressure.

## Candidate Analysis (Use-Case Specific)

### 1) SearXNG
- **Model**: metasearch aggregator over many upstream engines.
- **Linux/ops**: high viability; self-host deployment path is first-class.
- **Local-government suitability**: good for recall when queries need broad coverage across gov domains and long-tail portals.
- **Risks**:
  - anti-bot fragility: medium (depends on upstream engines),
  - maintenance burden: low-medium (engine tuning, block handling),
  - relevance quality: medium-high (query-dependent),
  - freshness: medium-high (inherited from upstream),
  - legal/TOS ambiguity: medium (depends on chosen upstream engines).
- **Verdict**: **benchmark now (first)**.

### 2) YaCy Search Server
- **Model**: own crawler/index (can run independent private index, optional decentralized mode).
- **Linux/ops**: high viability on Linux VM; moderate setup/tuning.
- **Local-government suitability**: good if seeded with official jurisdiction roots; strongest when we control crawl scope.
- **Risks**:
  - anti-bot fragility: low-medium (direct crawling can still face bot defenses),
  - maintenance burden: medium,
  - relevance quality: medium initially (improves with curated seeds),
  - freshness: configurable; depends on crawl schedule,
  - legal/TOS ambiguity: lower than scraping proxies when crawling allowed targets responsibly.
- **Verdict**: **benchmark now (second wave)**.

### 3) Scrapy + Meilisearch (official-root helper lane)
- **Model**: first-party-root-discovery helper + local search index (`something else`).
- **Linux/ops**: high viability (Python crawler + self-hosted index).
- **Local-government suitability**: very high for jurisdiction discovery because it can prioritize official roots, sitemaps, and bounded traversal.
- **Risks**:
  - anti-bot fragility: low-medium on public sector targets,
  - maintenance burden: medium (crawler rules + schema upkeep),
  - relevance quality: high for official-source precision; lower for broad web recall,
  - freshness: high if crawl cadence is managed,
  - legal/TOS ambiguity: low when restricted to official/public content and robots-aware behavior.
- **Verdict**: **benchmark now (bounded side-lane)**.

### 4) Apache Nutch (+ Solr/Elasticsearch)
- **Model**: self-indexing crawler/search framework for larger crawl/index workloads.
- **Linux/ops**: viable but heavier (cluster-style architecture patterns).
- **Local-government suitability**: strong long-term if we need controlled large-scale crawling.
- **Risks**:
  - anti-bot fragility: low-medium,
  - maintenance burden: high,
  - relevance quality: medium-high after tuning,
  - freshness: configurable but operationally heavier,
  - legal/TOS ambiguity: generally manageable under compliant crawling.
- **Verdict**: **fallback (high ops)**.

### 5) Whoogle Search
- **Model**: unofficial Google results proxy/scraping layer.
- **Linux/ops**: easy deployment, but upstream stability risk is intrinsic.
- **Local-government suitability**: often good raw recall when unblocked.
- **Risks**:
  - anti-bot fragility: high (blocks/CAPTCHA pressure),
  - maintenance burden: medium (constant workaround tuning),
  - relevance quality: high when working,
  - freshness: high when working,
  - legal/TOS ambiguity: high.
- **Verdict**: **fallback only; not worth primary dependency**.

## Recommended Benchmark Order

1. **SearXNG first** (fastest drop-in reliability test; strongest immediate signal against empty-result failures).
2. **YaCy second** (tests independence from third-party search APIs/scraping).
3. **Scrapy+Meilisearch side-lane** (validates official-root-first strategy to reduce dependence on general web search).

## Should We Invest in Official-Root-First + Bounded Traversal?

**Yes.**  
General web search should be an augmentation layer, not the only discovery substrate for jurisdiction intelligence. For this domain, official-root-first traversal materially lowers platform fragility and improves source trust quality.

## Smallest Benchmark Matrix That Can Decide Next Step

### Matrix

| Lane | Provider/System | Query/Crawl Set | Pass Criteria |
|---|---|---|---|
| A | SearXNG | 12 discovery prompts (4 jurisdictions x 3 intents: agenda/minutes/ordinance) | Empty-result rate < 10%, official-source hit in top 5 for >= 9/12 |
| B | YaCy | Same 12 prompts after seeding official roots for same 4 jurisdictions | Official-source hit in top 5 for >= 8/12, stable runs over 2 consecutive executions |
| C | Scrapy+Meilisearch | 4 official roots, depth-bounded crawl (e.g., depth<=2, page cap) then local search over harvested docs | >= 85% harvested URLs from official domains, >= 9/12 prompt coverage from local index |

### Shared Metrics

- empty_result_rate
- official_source_top5_rate
- relevant_source_top10_count
- median_latency_ms
- duplicate_url_rate
- run-to-run variance (2 repeated runs)

## Clear Verdict

- **SearXNG**: benchmark now
- **YaCy**: benchmark now (after SearXNG baseline)
- **Scrapy+Meilisearch**: benchmark now (bounded side-lane)
- **Nutch stack**: only use as fallback (if scale requirements outgrow YaCy/Scrapy lane)
- **Whoogle**: only use as fallback; not worth primary dependency

## Sources

- Z.ai Web Search docs: <https://docs.z.ai/api-reference/tools/web-search>
- Z.ai Search MCP docs: <https://docs.z.ai/devpack/mcp/search-mcp-server>
- OpenCode MCP server docs: <https://opencode.ai/docs/mcp-servers>
- SearXNG docs: <https://docs.searxng.org/>
- Whoogle repository/README: <https://github.com/benbusby/whoogle-search>
- YaCy docs/site: <https://yacy.net/>
- Apache Nutch site/docs: <https://nutch.apache.org/>
- Scrapy docs: <https://docs.scrapy.org/en/latest/>
- Meilisearch self-host docs: <https://www.meilisearch.com/docs/learn/self_hosted/getting_started_with_self_hosted_meilisearch>
