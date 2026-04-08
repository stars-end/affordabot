# Custom Stack Build-vs-Buy Sanity Check

**Date:** 2026-04-03
**Beads ID:** bd-us1f
**Mode:** qa_pass / product research
**Primary PR:** https://github.com/stars-end/affordabot/pull/374
**Supporting PRs:** #368 (build-vs-buy context), #361 (operator-proof context)

## Executive Summary

Affordabot is mostly on the right track. The substrate/document/history model and GlassBox operator surface are moat-critical and worth custom ownership. However, the admin dashboard layer is drifting into unnecessary reimplementation of commodity internal-tool patterns, and the storage/vector stack has one layer (MinIO self-hosted on Railway) that is likely to become maintenance drag without moat value.

**Verdict:** Not overbuilding yet, but close. The next 1-2 waves should stop building admin UI chrome and instead harden the substrate capture pipeline and operator debuggability.

---

## 1. Current Custom Stack Inventory

### Layer 1: Substrate / Document Capture (MOAT-CRITICAL)
| Component | Location | What it does |
|-----------|----------|-------------|
| `manual_capture.py` | `backend/scripts/substrate/` | Binary-safe document capture with content-class detection, trust tiers, promotion metadata |
| `substrate_promotion.py` | `backend/services/` | Rules-based promotion from captured_candidate → promoted_substrate |
| `ingestion_service.py` | `backend/services/` | Raw scrape → chunk → embed → vector upsert pipeline with truth tracking |
| `pdf_markdown.py` | `backend/services/` | PDF-to-markdown extraction |
| `metadata_contract.py` | `backend/scripts/substrate/` | Metadata schema for substrate documents |

### Layer 2: Operator Observability (MOAT-CRITICAL)
| Component | Location | What it does |
|-----------|----------|-------------|
| `glass_box.py` | `backend/services/` | Pipeline run traces, step-level execution history, mechanism trace normalization |
| `admin.py` (GlassBox endpoints) | `backend/routers/` | `/admin/traces`, `/admin/pipeline-runs`, `/admin/alerts`, `/admin/bill-truth/{jurisdiction}/{bill_id}` |
| `alerting.py` | `backend/services/` | Deterministic alert evaluation from pipeline_runs result data |

### Layer 3: Admin Dashboard (COMMODITY RISK)
| Component | Location | What it does |
|-----------|----------|-------------|
| `admin.py` (jurisdiction/scrape/prompt endpoints) | `backend/routers/` | CRUD for jurisdictions, scrape history, prompt management, dashboard stats |
| `adminService.ts` | `frontend/src/services/` | TypeScript client for admin API |
| Frontend admin pages | `frontend/src/pages/` | React UI for admin operations |

### Layer 4: Storage / Vector (MIXED)
| Component | Location | What it does |
|-----------|----------|-------------|
| `s3_storage.py` | `backend/services/storage/` | MinIO S3-compatible blob storage wrapper |
| `local_pgvector.py` | `backend/services/retrieval/` | PostgreSQL pgvector retrieval backend |
| `vector_backend_factory.py` | `backend/services/` | Factory for vector backend selection |

### Layer 5: Scraper Registry (MOAT-CRITICAL)
| Component | Location | What it does |
|-----------|----------|-------------|
| Scraper adapters (san_jose, santa_clara, saratoga, california_state, nyc) | `backend/services/scraper/` | Jurisdiction-specific scrapers |
| `city_scrapers_discovery.py` | `backend/services/discovery/` | Integration with City-Bureau/city-scrapers OSS |
| `municode_discovery.py` | `backend/services/discovery/` | Municode municipal code discovery |

---

## 2. Moat-Critical Custom Areas (KEEP BUILDING)

### 2.1 Substrate Document Model
**Verdict: Custom is correct.**

The substrate model (content_class detection, trust tiers, promotion rules, ingestion_truth state machine) is tightly coupled to affordabot's product thesis: truthful source handling of local government documents. No OSS tool does this because no OSS tool cares about the specific semantics of municipal document provenance.

Key moat signals:
- `content_class` distinction (html_text vs pdf_binary vs plain_text) drives different ingestion paths
- `trust_tier` (official_partner vs primary_government) affects promotion decisions
- `ingestion_truth` state machine (raw_captured → parsed → chunked → embedded → retrievable) gives operator-debuggable provenance
- Promotion rules evaluate rules and decide whether a document advances

This is the core differentiator. Building this custom is not only justified — it's mandatory.

### 2.2 GlassBox Operator Surface
**Verdict: Custom is correct.**

GlassBox is not a generic observability tool. It's a domain-specific debug surface that traces:
- Pipeline runs with bill_id/jurisdiction context
- Step-level execution (impact_discovery, mode_selection, sufficiency_gate, parameter_resolution)
- Prefix boundary detection for bounded runs
- Mechanism trace normalization for operator consumption
- Bill truth diagnostic: Scrape → Raw Text → Vector Chunks → Research pipeline trace

The `/admin/bill-truth/{jurisdiction}/{bill_id}` endpoint is the single most important operator surface in the codebase. It lets a founder answer "why is this bill wrong?" by tracing through the entire pipeline. This is moat-critical because it enables founder-debuggable raw/operator visibility.

### 2.3 Scraper Registry + Discovery
**Verdict: Custom + OSS integration is correct.**

The scraper registry pattern (base scraper → jurisdiction-specific adapters) is well-structured. The integration with City-Bureau/city-scrapers (OSS, 370 stars) for meeting discovery is the right build-vs-buy boundary: use OSS for the discovery layer, build custom adapters for jurisdiction-specific extraction.

---

## 3. Commodity Areas (Should Reuse, Not Rebuild)

### 3.1 Admin Dashboard Chrome
**Verdict: Nuanced — keep in-house, but stop building vanity pages.**

The current admin endpoints (`/admin/jurisdictions`, `/admin/scrapes`, `/admin/prompts`, `/admin/stats`) are building a generic CRUD admin panel. This is not moat-critical. It's a commodity internal tool.

**Counter-argument from PR #368 (raw data viewer build-vs-buy memo):** The PR #368 memo evaluated NocoDB, Appsmith, and Metabase for the substrate data viewer and found that for a solo founder, all three create permanent infrastructure tax: separate auth planes, new Railway deployments, JSONB query fragility (NocoDB's formula hacks), and the cognitive overhead of maintaining a separate tool. The memo correctly concluded that extending the existing in-house UI is lower total cognitive load than introducing a new platform.

**Reconciled verdict:** Do NOT deploy Retool/Appsmith/NocoDB. The infrastructure tax of a separate deployment + auth plane is worse than writing a React table. However, there is a middle ground:

- **Keep in-house** for the admin UI (single pane of glass, reuses Clerk auth, zero new infrastructure)
- **But stop building vanity pages** — only build admin pages that serve a concrete operator need (substrate browser, bill truth viewer, GlassBox trace viewer)
- **Do NOT build** jurisdiction CRUD forms, prompt editors, or dashboard stat counters as custom React pages. These should be accessed via `db_inspect.py` or simple SQL queries until there's a proven operator need.

The admin UI should be:
- GlassBox traces: keep custom (moat-critical)
- Bill truth diagnostic: keep custom (moat-critical)
- Substrate data browser: keep custom (PR #368 verdict — native JSONB queries are the robust path)
- Jurisdiction CRUD: defer (use `db_inspect.py` or direct SQL)
- Scrape history: defer (use `db_inspect.py` or direct SQL)
- Prompt management: defer (use `db_inspect.py` or direct SQL)

### 3.2 MinIO Self-Hosted Object Storage
**Verdict: Likely maintenance drag. Consider Railway Postgres large objects or S3 directly.**

The `S3Storage` class wraps MinIO for blob storage of raw scrape artifacts. On Railway, this means running a MinIO service alongside the app.

**Current state:** MinIO on Railway with public/internal URL resolution, presigned URLs, bucket management.

**Problem:** MinIO is a great OSS project, but for a solo founder at this scale:
- It's another service to monitor, backup, and upgrade
- Railway already provides Postgres with large object support
- The volume of documents is small enough that Postgres `BYTEA` or `pg_largeobject` would work fine
- If scale requires object storage, AWS S3 or Cloudflare R2 is cheaper than running MinIO on Railway

**Recommendation:** For the next 1-2 waves, replace MinIO with one of:
1. **Postgres BYTEA** (simplest, zero additional services) — viable up to ~10K documents
2. **Cloudflare R2** (S3-compatible, zero egress fees) — if external object storage is needed
3. **Keep MinIO** only if there's a specific reason (e.g., large PDF archives that exceed Postgres practical limits)

The `BlobStorage` contract interface is good — it makes the swap easy.

### 3.3 Vector Database
**Verdict: pgvector is the right choice. Don't switch.**

The current stack uses pgvector via `LocalPgVectorBackend`. This is the correct build-vs-buy decision for a solo founder:
- One less service to manage (vectors live in Postgres)
- Railway Postgres already supports pgvector
- No additional cost
- Sufficient for the current scale (thousands, not millions, of chunks)

External vector databases (Pinecone, Weaviate, Qdrant) add operational complexity without moat value at this scale. The pgvector choice should be locked in.

---

## 4. Revision-First Document History

**Verdict: Worth custom work.**

The revision-aware document history is moat-critical. Local government documents change — bills get amended, agendas get updated, meeting minutes get corrected. Being able to trace document revisions and show "what changed" is a core product differentiator.

The current substrate model supports this through:
- `content_hash` on raw_scrapes (detects changes)
- `document_id` linking (groups revisions)
- `ingestion_truth` state machine (tracks processing per revision)

This should continue to be built custom. No OSS tool provides revision-aware municipal document history because it requires the domain-specific substrate model.

---

## 5. Comparison Table

| Area | Current Approach | OSS/Buy Alternative | Recommendation | Moat Value |
|------|-----------------|-------------------|----------------|------------|
| Substrate model | Custom | None exists | **Keep custom** | HIGH |
| GlassBox traces | Custom | Datadog/Honeycomb (generic) | **Keep custom** | HIGH |
| Bill truth diagnostic | Custom | None exists | **Keep custom** | HIGH |
| Scraper adapters | Custom + City-Scrapers OSS | City-Scrapers, LegiScan | **Keep hybrid** | HIGH |
| Admin CRUD UI | Custom React | Retool, Appsmith, ToolJet | **Keep in-house, defer vanity pages** | LOW |
| Object storage | MinIO on Railway | Postgres BYTEA, R2, S3 | **Simplify to Postgres or R2** | NONE |
| Vector DB | pgvector | Pinecone, Weaviate, Qdrant | **Keep pgvector** | LOW |
| Prompt management | Custom CRUD | LangSmith, PromptLayer | **Keep simple, consider LangSmith later** | MEDIUM |
| Alerting | Custom from pipeline_runs | PagerDuty, custom | **Keep custom (deterministic from truth data)** | MEDIUM |

---

## 6. Explicit "Do Not Build This" Section

Over the next 1-2 waves, affordabot should explicitly NOT build:

1. **Vanity admin pages** — No custom React pages for jurisdiction management, scrape history tables, or prompt editors. These are CRUD operations accessible via `db_inspect.py` or direct SQL. The substrate data browser is the exception (PR #368 verdict — native JSONB queries are the robust path).
2. **MinIO cluster management** — No scaling MinIO, no bucket lifecycle policies, no MinIO monitoring. Replace with Postgres BYTEA or R2.
3. **Generic notification system** — The current Slack webhook integration is sufficient. Do not build email, SMS, or webhook routing systems.
4. **Custom vector search optimization** — Do not build HNSW index tuning, vector quantization, or hybrid search. pgvector defaults are fine.
5. **Multi-tenant admin features** — Do not build role-based access control, team management, or audit logs for the admin panel. Clerk auth + admin flag is enough.
6. **Scrape scheduling UI** — Do not build a cron job management UI. Use Railway cron or system-level cron.
7. **Custom PDF rendering** — Do not build PDF preview/rendering in the admin UI. The raw blob is sufficient for debugging.

---

## 7. Solo Founder Cognitive Load Analysis

### Current Load (Estimated)
| Area | Weekly Cognitive Load | Trend |
|------|---------------------|-------|
| Substrate pipeline | 3-4 hours | Stable (well-structured) |
| GlassBox debugging | 1-2 hours | Decreasing (maturing) |
| Admin UI maintenance | 2-3 hours | **Increasing** (new pages, new endpoints) |
| MinIO operations | 1-2 hours | **Increasing** (DNS issues, bucket management) |
| Scraper adapters | 2-3 hours | Stable (per-jurisdiction work) |
| Vector/Embedding tuning | 0-1 hours | Stable (pgvector is quiet) |

### After Recommendations
| Area | Weekly Cognitive Load | Change |
|------|---------------------|--------|
| Substrate pipeline | 3-4 hours | No change |
| GlassBox debugging | 1-2 hours | No change |
| Admin CRUD operations | 1-2 hours | **-0.5 to -1.5 hours** (defer vanity pages, keep substrate browser) |
| Storage operations | 0 hours | **-1 to -2 hours** (Postgres BYTEA or R2) |
| Scraper adapters | 2-3 hours | No change |
| Vector/Embedding tuning | 0-1 hours | No change |

**Net savings: 1.5-3.5 hours/week** — roughly 10-20% of total engineering time.

---

## 8. Verdict

**Affordabot is NOT overbuilding yet, but is approaching the boundary.**

The substrate model, GlassBox surface, and scraper registry are genuinely moat-critical and should remain custom. The admin dashboard chrome and MinIO self-hosting are the two areas where the team is drifting into unnecessary custom engineering.

The current direction is defensible for one more wave, but the next wave after that should be a consolidation wave: replace MinIO, defer vanity admin pages, and double down on substrate coverage breadth.

### Reconciliation with PR #368

PR #368's raw data viewer build-vs-buy memo correctly identified that deploying OSS internal tool platforms (NocoDB, Appsmith, Metabase) creates more cognitive load than it saves for a solo founder. This memo agrees with that verdict and refines it: the admin UI should stay in-house, but the scope should be constrained to operator-critical surfaces only (substrate browser, bill truth, GlassBox). Everything else should be deferred or accessed via CLI/SQL tools.

---

## 9. Recommended Build-vs-Buy Boundary for Next 1-2 Waves

### BUILD (custom, moat-critical)
- Substrate capture pipeline (manual_capture.py, promotion rules)
- GlassBox operator surface (traces, bill truth diagnostic, alerts)
- Scraper adapters (per-jurisdiction extraction logic)
- Ingestion service (chunk → embed → vector pipeline with truth tracking)
- Revision-aware document history

### BUY/REUSE (commodity, not moat)
- **Admin CRUD UI:** Keep in-house, but defer vanity pages (jurisdiction CRUD, prompt editors, stat dashboards). Use `db_inspect.py` or direct SQL for now.
- **Object storage:** Postgres BYTEA (immediate) or Cloudflare R2 (if scale requires)
- **Vector DB:** pgvector (already using, keep it)
- **Auth:** Clerk (already using, keep it)
- **LLM routing:** OpenRouter + direct provider (already using, keep it)

### DEFER (not needed yet)
- Multi-tenant admin features
- Custom notification routing
- Advanced vector search optimization
- PDF rendering in admin UI
- Scrape scheduling UI

---

## Sources

- City-Bureau/city-scrapers: https://github.com/City-Bureau/city-scrapers (370 stars, MIT)
- civic-scraper: https://civic-scraper.readthedocs.io/en/latest (agendas/minutes download tools)
- Retool vs Appsmith comparison: https://designrevision.com/blog/retool-vs-appsmith (2026-02)
- pgvector vs Pinecone/Weaviate: https://encore.dev/articles/best-vector-databases (2026-03)
- MinIO vs alternatives: https://www.reddit.com/r/selfhosted/comments/1s4z2ux/ (2026-03 benchmark)
