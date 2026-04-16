---
repo_memory: true
status: active
owner: affordabot-architecture
last_verified_commit: f0a29e3b24e4d7f752614216b44d1d5d084852a2
last_verified_at: 2026-04-16T16:24:11Z
stale_if_paths:
  - backend/**
  - frontend/**
  - ops/**
  - contracts/**
  - docs/specs/**
---

# Brownfield Map

Affordabot is not just a web app with a scraper. The product moat is the
evidence system: source discovery, raw/substrate capture, structured official
data, provenance, retrieval, reader output, economic analysis, and final
explanation. Treat pipeline changes as product changes.

## Current Pipeline Shape

- Discovery and scrape entry points are still split across existing backend
  cron endpoints and newer domain-command experiments. Do not assume the new
  Windmill domain-boundary POC has replaced every legacy path.
- `backend/services/pipeline/domain/commands.py` is the important new boundary
  surface for search execution, candidate ranking, freshness gates, reader
  calls, indexing, and analysis orchestration.
- `backend/services/pipeline/domain/in_memory.py` is a POC storage adapter. It
  proves contracts but is not durable product storage.
- `ops/windmill/f/affordabot/pipeline_daily_refresh_domain_boundary.py` is the
  Windmill-native flow harness. Windmill should own scheduling, retries,
  branching, fanout, and observability; backend/domain code should own product
  invariants and storage writes.
- `backend/services/ingestion_service.py` maps raw scrape material into chunks
  and vector storage. It is part of the data moat and must preserve provenance.
- `backend/services/glass_box.py` exposes traces and pipeline/admin read-model
  data. Prefer extending this surface before inventing another admin status
  API.
- `frontend/src/services/adminService.ts` is the existing frontend client for
  admin pipeline/substrate views. Check it before adding any admin panel data
  surface.

## Source Families

- Scraped search lane: private SearXNG is the intended low-cost primary probe
  path once quality gates pass; Tavily is a hot fallback candidate; Exa is
  useful for bakeoffs/evals but cost and quota make it less attractive as the
  default.
- Reader lane: Z.ai direct reader remains valuable and should stay canonical
  unless evidence shows quality failure. Z.ai web search is deprecated as a
  primary path because repeated tests found it unreliable.
- Structured lane: OpenStates, Legistar-derived official records, CKAN,
  ArcGIS, OpenDataSoft, Socrata, static CSV/JSON feeds, and other free
  API/raw-file sources should run in parallel with scraped search. Do not turn
  hard-to-ingest portals into a second scraper layer without a separate ROI
  decision.

## Critical Product Invariants

- Canonical document identity must be stable across scraped and structured
  lanes. Prefer jurisdiction-scoped identity over URL-only identity.
- Every claim in the analysis path must point back to raw or structured
  evidence with provenance.
- Promotion tiers matter: captured candidate, durable raw artifact, indexed
  chunk, promoted substrate, and analysis-ready package are different states.
- Zero-result search is not the same as provider failure. Fallback policies
  must distinguish weak recall, portal misranking, reader failure, and stale
  but usable evidence.
- Windmill reruns whole flows rather than resuming a single failed step. Backend
  commands and storage writes must be idempotent.

## Known Fragile Areas

- Ranking and reader gates are the likely failure point for scraped sources.
  Prior San Jose bakeoffs showed SearXNG often found artifact URLs, but backend
  ranking selected portals instead.
- Storage proof must include Postgres rows, pgvector derivation, MinIO object
  readability, replay/idempotency, and admin read-model visibility.
- Economic analysis quality cannot be inferred from source count. The package
  must include mechanism, parameters, assumptions, uncertainty, and rejection of
  unsupported claims.
- Frontend status/admin work should reuse existing glass-box/admin surfaces
  unless there is a documented gap.

## Before Changing This Area

Read these first:
- `docs/specs/2026-04-13-windmill-domain-brownfield-spec-lock.md`
- `docs/specs/2026-04-14-evidence-package-dependency-lockdown.md`
- `docs/specs/2026-03-19-affordabot-california-pipeline-truth-remediation.md`
- `docs/research/2026-04-14-private-searxng-quality-review.md`
- `docs/architecture/2026-04-12-windmill-affordabot-boundary-adr.md`
- `docs/architecture/2026-04-13-admin-pipeline-read-model-map.md`
