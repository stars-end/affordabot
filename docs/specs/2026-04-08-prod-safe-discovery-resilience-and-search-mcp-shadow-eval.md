# Prod-Safe Discovery Resilience And Search MCP Shadow Eval

Date: 2026-04-08
Beads epic: `bd-vho5t`
Prerequisite implementation context: [PR #406](https://github.com/stars-end/affordabot/pull/406) (`d14f22148091e74648ced696cc00cb1628ad82d1`)

## Summary

Affordabot's current discovery lane is now classifier-gated and no longer crashes on the main product bugs, but bounded live validation showed two real external instability classes:

- primary `z.ai` search DNS failures
- intermittent `z.ai` `429` rate limits during query generation and classification

The next wave makes discovery operationally safe for production by keeping discovery async and best-effort, reducing provider dependence, and deferring provider-limited work instead of burning cron budget on repeated failures.

After that is stable, a limited shadow evaluation will test whether `Z.ai Search MCP + OpenCode` is reliable enough to become a production fallback path.

## Problem

Today, discovery is still too provider-eager for production use:

- query generation uses `glm-4.7` every run unless it falls back to static templates
- classification attempts can repeatedly burn provider calls on low-value candidates
- provider failures are fail-closed for promotion, but not yet operationally optimized for retry/defer behavior
- there is no durable deferred-work queue for rate-limited or DNS-blocked discovery stages
- current reporting is useful for acceptance gating, but not yet explicit about provider-deferred work

This is acceptable for dev validation, but not for a resilient production discovery lane.

## Goals

1. Keep harvesting independent from discovery.
2. Make discovery best-effort async in production.
3. Reduce `z.ai` dependency per run through caching and heuristic prefiltering.
4. Persist and retry deferred provider-limited work with capped backoff.
5. Produce explicit reporting buckets for accepted, rejected, duplicate, and deferred candidates.
6. Run a limited `Search MCP + OpenCode` shadow benchmark and allow promotion to production fallback only if the benchmark clearly earns it.

## Non-Goals

- Do not make discovery a blocking prerequisite for existing trusted source harvesting.
- Do not broaden scope into a general multi-provider migration in this wave.
- Do not replace the current classifier-gated promotion contract.
- Do not centralize product discovery logic outside affordabot.
- Do not force `Search MCP + OpenCode` into the primary production path before bounded evidence exists.

## Active Contract

### Phases 1-3

- Discovery remains fail-closed for source promotion.
- Discovery becomes best-effort and quota-aware operationally.
- Provider-limited work is deferred and retried later rather than hammered in the same run.
- Query generation and classifier results are cached.
- Heuristic prefiltering is applied before expensive classification calls.
- Reporting clearly separates:
  - `accepted`
  - `duplicate`
  - `rejected_not_scrapable`
  - `rejected_low_confidence`
  - `deferred_due_to_rate_limit`
  - `deferred_due_to_dns`
  - `deferred_due_to_provider_unavailable`

### Phase 4

- `Search MCP + OpenCode` runs as a bounded shadow lane first.
- If benchmark results are clearly better, it may be promoted to a production fallback path.
- If benchmark results are mixed or noisy, it remains shadow-only and current discovery stays primary.

## Design

### 1. Production discovery remains async and non-blocking

The current discovery cron already writes candidate outcomes separately from harvesting. That separation becomes explicit policy:

- harvesting of known trusted sources remains the critical path
- discovery is an enrichment lane
- provider failures defer work; they do not count as harvest failures

### 2. Provider-light discovery path

Before calling `z.ai`, the cron should prefer:

- cached query plans for a jurisdiction
- cached classifier decisions for exact URLs
- heuristic prefiltering for obvious junk or obvious official/document-host candidates

The discovery lane should use `z.ai` only when the candidate is still uncertain after those cheaper checks.

### 3. Durable deferred retry queue

We need durable retry state across runs, not just log noise inside one cron invocation.

Implementation contract:

- add a lightweight persistence surface for deferred discovery work
- each deferred item records:
  - jurisdiction id/name
  - candidate URL or query
  - stage (`query_generation`, `search`, `classification`)
  - reason code (`rate_limit`, `dns_failure`, `provider_unavailable`)
  - retry count
  - next attempt time
  - last error summary
- cron processes due deferred items within a bounded budget before or alongside fresh work

Preferred implementation shape:

- repo-local DB-backed persistence in affordabot, not external queue infrastructure
- keep schema minimal and focused on discovery retry semantics

### 4. Caching contract

Two caches are worth building now:

1. query cache
- key: jurisdiction + jurisdiction type + prompt version
- value: generated queries
- TTL: long enough to avoid repeated daily generation churn

2. classifier cache
- key: normalized URL + classifier version
- value: `DiscoveryResponse` summary
- TTL/versioning: invalidate by classifier version change, not by short time windows

### 5. Heuristic prefilter contract

Heuristic prefiltering should make only bounded decisions:

- obvious reject:
  - social/video/general noise domains
  - unrelated commercial pages
- obvious likely-official:
  - `.gov`
  - known civic vendors like Granicus / Legistar / PrimeGov / CivicPlus-style official meeting pages

Heuristics may:

- reject obvious junk directly
- promote obvious duplicates directly
- send likely-good candidates to cached/classifier path

Heuristics should not directly create sources without preserving the classifier gate unless an exact cached positive decision already exists.

### 6. Search MCP plus OpenCode shadow lane

Phase 4 tests the following configuration:

- OpenCode remote MCP server config pointing at:
  - `https://api.z.ai/api/mcp/web_search_prime/mcp`
- Authorization header:
  - `Authorization: Bearer <ZAI_API_KEY>`
- per-agent enablement only, not global enablement by default

Grounded doc constraints:

- Z.ai Search MCP exposes `webSearchPrime` and is supported for OpenCode clients. [Z.ai Search MCP](https://docs.z.ai/devpack/mcp/search-mcp-server)
- OpenCode supports remote MCP servers with URL, headers, timeout, and per-agent tool enablement, and warns that MCP tools add context overhead. [OpenCode MCP docs](https://opencode.ai/docs/mcp-servers)

Shadow-eval contract:

- compare current resilient lane vs `Search MCP + OpenCode` on the same bounded jurisdiction set
- measure:
  - candidate yield
  - accepted-source yield
  - latency
  - quota burn
  - failure-mode distribution

Fallback promotion bar:

- clearly better or materially more reliable candidate yield
- no major new auth/config/operator burden
- no unacceptable context or quota cost

## Execution Phases

### Phase 1: Provider-light async discovery resilience

Beads: `bd-ss6db`

Implement:

- build on top of `bd-esety` / PR #406
- add query cache
- add classifier cache
- add heuristic prefilter before expensive classification
- add provider budget controls for query generation and classification
- convert discovery task logging/reporting to reflect async best-effort semantics

Acceptance:

- bounded tests cover cache hits, cache misses, heuristic skip/reject behavior, and provider budget exhaustion
- cron can complete a bounded run without repeatedly reattempting the same provider failure in one invocation

### Phase 2: Deferred retry queue and prod-safe reporting

Beads: `bd-ro2cx`

Implement:

- durable deferred-work persistence for provider-limited discovery stages
- capped backoff scheduling
- cron support for retrying due deferred items
- explicit reporting buckets for deferred outcomes

Acceptance:

- deferred items survive across runs
- retry scheduling is deterministic and bounded
- reporting cleanly distinguishes deferred vs rejected vs accepted work

### Phase 3: Bounded prod-safe validation

Beads: `bd-h6qfe`

Run bounded validation in dev with the resilient lane:

- positive control: `San Jose`
- stress sample: `Milpitas`
- stress sample: `Alameda County`

Success bar:

- discovery run finishes without product crashes
- accepted/rejected/deferred/duplicate buckets are meaningful
- at least one jurisdiction shows operationally useful accepted results
- remaining failures are classifiable as provider/runtime rather than unclear product bugs

### Phase 4: Search MCP plus OpenCode shadow eval

Beads: `bd-aa8w0`

Implement and validate:

- repo-local docs/config for limited OpenCode MCP usage
- bounded benchmark harness or runbook
- same jurisdiction sample as phase 3 unless evidence suggests a smaller subset

Decision rule:

- if initial benchmark is clearly good, allow promotion to a production fallback path
- otherwise keep shadow-only and preserve the phase 1-3 lane as primary

## Beads Structure

- `BEADS_EPIC`: `bd-vho5t`
- `bd-ss6db`: implement provider-light async discovery resilience
- `bd-ro2cx`: add deferred retry queue and prod-safe reporting
- `bd-h6qfe`: run bounded prod-safe validation for resilient discovery lane
- `bd-aa8w0`: shadow-evaluate Search MCP plus OpenCode as fallback path

Blocking edges:

- `bd-ro2cx` blocks on `bd-ss6db`
- `bd-h6qfe` blocks on `bd-ro2cx`
- `bd-aa8w0` blocks on `bd-h6qfe`

## Validation

Code-level validation:

- focused backend pytest for discovery services, cron behavior, and DB persistence
- `ruff check` on modified backend files

Runtime validation:

- explicit Railway dev backend runs using:
  - project `1ed20f8a-aeb7-4de6-a02c-8851fff50d4e`
  - env `dev`
  - service `backend`

Artifacts:

- closeout memo for phase 3
- shadow benchmark memo for phase 4

## Risks

1. Cache staleness
- mitigated by explicit versioned cache keys and bounded TTLs

2. Queue growth under extended provider outages
- mitigated by capped retry counts, cooldowns, and explicit reporting

3. Heuristic false negatives
- mitigated by keeping heuristics bounded and preserving fail-closed promotion

4. Search MCP context/quota overhead
- mitigated by per-agent enablement and bounded benchmark scope

## Recommended First Task

Start with `bd-ss6db`.

Why first:

- it makes the existing discovery cron operationally safe before we add deferred retry complexity
- it builds directly on the already-proven product fixes in PR #406
- it is the base required for both later validation and the phase 4 comparison
