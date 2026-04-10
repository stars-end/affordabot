# SearXNG Low-Cost Web Search POC Architecture

## Overview
This POC evaluates whether we can reliably serve roughly 200 web searches per hour, spread across two VPS nodes, with near-zero marginal cost using OSS components (SearXNG) and no paid search API.

## Architecture Components

1. **SearXNG Instances (Nodes)**
   - **Why SearXNG?** It is the leading open-source metasearch engine, highly configurable, and supports JSON API output which is ideal for LLM/agentic usage.
   - **Configuration:** We simulate two VPS nodes by running two SearXNG instances via Docker Compose.
   - **Engines:**
     - **Enabled/Prioritized:** DuckDuckGo, Bing, Brave, Yahoo, Qwant. These engines tend to be more tolerant of light automated usage.
     - **Disabled:** Google, to minimize the risk of aggressive blocking or CAPTCHAs out of the gate, since Google is notoriously strict against automated scraping without proxies.
   - **Format:** `json` output format is enforced for API usage.

2. **Coordinator & Load Balancer (Python Script)**
   - **Why Python?** Simple, requires minimal dependencies (just `requests` and standard library `asyncio` / `aiohttp`), and easy to implement concurrency limits, jitter, and retries.
   - **Routing Strategy:** Round-robin or random distribution across the two nodes to evenly spread the load and avoid IP-based rate limiting from the upstream search engines as much as possible.
   - **Resilience:**
     - **Randomized Jitter:** Adds a random delay (e.g., 1-3 seconds) between requests to simulate human-like intervals and avoid triggering burst rate limits.
     - **Concurrency Limits:** Keeps per-node concurrency very low (e.g., 1-2 concurrent requests per node). 200 searches/hour is roughly 3.33 searches/minute, which is very low concurrency.
     - **Retries & Fallbacks:** If Node A fails (e.g., empty results, timeout, HTTP 429), the coordinator retries the request on Node B before marking it as a total failure.

3. **Metrics & Observability**
   - **Logging:** Simple local logging and a final summary output.
   - **Metrics tracked:**
     - Success rate
     - Median and p95 latency
     - Engine-specific failure rates (if exposed in SearXNG response)
     - Node-specific issues
     - Total run time

## Operational Simplicity
The entire stack is deployed using a single `docker-compose.yml` (simulating the two nodes locally) and a standalone Python script, keeping operations trivial.
