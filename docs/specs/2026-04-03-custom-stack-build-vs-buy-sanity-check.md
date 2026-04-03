# Custom Stack Build vs. Buy Sanity Check

Date: 2026-04-03
Beads: `bd-us1f`
Grounding: PR #374 (current product state), PR #368 (substrate/viewer context), PR #361 (operator-proof context)

## TL;DR Verdict

**No, we are not going crazy building custom in-house.**

The current affordabot direction is mostly correct. The moat-critical custom work (scraper registry, legislation analysis pipeline, revision-aware substrate, truthfulness auditing) is genuinely non-commodity and worth owning. The main risk areas are not "we are rebuilding something that exists" but rather "we are building operator tooling slightly ahead of need." Two specific areas warrant reuse consideration in the next 1-2 waves. Everything else should stay custom.

---

## 1. Current Custom Stack Inventory

| Layer | What We Built | Files | Lines (approx) |
|-------|---------------|-------|-----------------|
| **Admin API** | FastAPI CRUD + dashboard + bill-truth diagnostic + alerts | `backend/routers/admin.py` | ~700 |
| **GlassBox Observability** | Pipeline step tracing, mechanism trace normalization, run head resolution | `backend/services/glass_box.py` | ~540 |
| **Legislation Research** | RAG-backed analysis with evidence provenance, sufficiency gates, web search | `backend/services/legislation_research.py` | ~1400 |
| **Ingestion Pipeline** | Raw scrapes -> chunks -> embeddings -> pgvector | `backend/services/ingestion_service.py` | ~305 |
| **Alerting** | Rule-based alerts derived from pipeline_runs result data | `backend/services/alerting.py` | ~187 |
| **Auto-Discovery** | GLM-4.7-powered government source URL classification | `backend/services/auto_discovery_service.py` | ~184 |
| **Scraper Registry** | Per-jurisdiction scrapers (California, San Jose, Legistar, AgendaCenter, Municode) | `backend/services/scraper/*.py` | ~35K total |
| **S3/MinIO Storage** | S3-compatible object storage for PDFs/HTML | `backend/services/storage/s3_storage.py` | ~200 |
| **Vector Backend** | pgvector wrapper with metadata filtering | `backend/services/retrieval/local_pgvector.py` | ~240 |
| **Frontend Admin** | React admin panels: AnalysisLab, ScrapeManager, PromptEditor, ModelRegistry, JurisdictionMapper | `frontend/src/components/admin/*.tsx` | ~95K total |
| **Frontend Service Layer** | TypeScript API clients for admin operations | `frontend/src/services/adminService.ts` | ~125 |
| **Substrate Framework** | Three-tier promotion model (captured_candidate -> durable_raw -> promoted_substrate) | Manual capture + expansion scripts | ~2K |
| **Windmill Flows** | Scheduled cron trigger flows for daily scrape, discovery, harvester | `ops/windmill/` | ~500 |

---

## 2. Moat-Critical Custom Areas (DO NOT REPLACE)

These are genuinely non-commodity and directly tied to affordabot's product moat:

### 2a. Scraper Registry + Per-Jurisdiction Extractors
**Why custom is correct**: Government websites are wildly heterogeneous. Legistar APIs, AgendaCenter HTML, Municode code repositories, and California state legislature all require different extraction logic. No generic scraping framework eliminates per-jurisdiction customization. Scrapy/Crawl4AI can be workers under Windmill, but the *registry* and *jurisdiction-specific parsing* is the moat.

### 2b. Legislation Research + Sufficiency Gates
**Why custom is correct**: The 1400-line `legislation_research.py` with evidence provenance tracking, sufficiency breakdown, impact discovery, and quantification eligibility is the core product logic. No OSS tool does "is this bill's analysis grounded in actual source text?" This is the engine that produces truthful outputs.

### 2c. Three-Tier Substrate Promotion Model
**Why custom is correct**: The `captured_candidate -> durable_raw -> promoted_substrate` hierarchy with ingestion truth stages (`raw_captured`, `blob_stored`, `parsed`, `chunked`, `embedded`, `retrievable`) is a novel data model. No off-the-shelf system handles revision-aware government document promotion with these semantics. This is the data moat architecture.

### 2d. Bill-Truth Diagnostic Endpoint
**Why custom is correct**: `GET /admin/bill-truth/{jurisdiction}/{bill_id}` traces a bill through Scrape -> Raw Text -> Vector Chunks -> Pipeline Runs with mechanism traces. This is a domain-specific debugging tool that no BI platform or admin builder can replicate without effectively rebuilding the same SQL.

### 2e. Trust Model + Provenance Tracking
**Why custom is correct**: The trust tier derivation (`official_partner`, `primary_government`, conservative fallback) and ingestion truth metadata stamping is domain-specific policy logic. This is what makes affordabot's data trustworthy vs. a generic scraper dump.

---

## 3. Commodity Areas: Reuse/Buy Candidates

### 3a. Pipeline Observability (GlassBox) -- REUSE CANDIDATE

**Current state**: ~540 lines of custom tracing in `glass_box.py` that normalizes pipeline steps, extracts prefix boundaries, and builds mechanism traces.

**What exists**: Langfuse (self-hosted, MIT license, acquired by ClickHouse Jan 2026) is purpose-built for LLM pipeline tracing. Tracks token usage, latency, cost, prompt versions. Framework-agnostic. Free self-hosted, cloud free tier at 50k observations/month.

**Verdict**: PARTIAL REUSE.
- Generic LLM observability (token costs, latency, model routing) should move to Langfuse. This eliminates custom code for tracking which model was used, how long each step took, and basic run status.
- Domain-specific mechanism traces (sufficiency gates, impact discovery, prefix boundaries) must stay custom. Langfuse can host the traces, but the *interpretation logic* is affordabot-specific.
- Net effect: ~200-300 lines of GlassBox could be eliminated. The mechanism trace normalization stays.

**Solo founder load**: Low. Langfuse self-hosted is a single Docker container. Cloud free tier eliminates even that.

### 3b. Data Exploration (Ad-Hoc Queries) -- REUSE CANDIDATE

**Current state**: Multiple custom admin endpoints that are essentially SQL queries rendered as JSON: `GET /admin/stats`, `GET /admin/scrapes`, `GET /admin/document-health`. The frontend renders these in custom React tables.

**What exists**: Metabase (self-hosted, $0 OSS) provides a no-code query builder over Postgres. Single Docker container. Can be deployed on Railway alongside the existing app.

**Verdict**: DEFER (evaluate in wave 2-3, not wave 1-2).
- The PR #368 raw-data-viewer memo already correctly concluded that extending the existing in-house UI wins on cognitive load for the *specific* substrate viewer use case (JSONB depth, single auth plane, single pane of glass).
- However, for *ad-hoc* data exploration by the founder (not the product surface), Metabase is genuinely useful. The founder should not be writing custom React tables every time they want to answer "how many scrapes failed in the last 24 hours by jurisdiction?"
- The right sequencing is: build the substrate viewer in-house now (per PR #368 recommendation), then add Metabase later for ad-hoc exploration when the data volume justifies it.

**Solo founder load**: Medium. Metabase is easy to deploy but is a separate auth boundary and a separate service to monitor.

---

## 4. Areas That Are NOT Commodity (Despite Appearances)

### 4a. Admin Dashboard (the whole thing) -- KEEP CUSTOM

**Tempting alternative**: Appsmith, Retool, Directus.

**Why keep custom**: The PR #368 analysis is correct. These tools:
- Introduce permanent infrastructure tax (new Railway service, separate auth, security updates)
- Have poor JSONB filtering robustness (NocoDB formula hacks, Appsmith proprietary JS bindings)
- Cannot provide the bill-truth diagnostic, mechanism trace viewer, or substrate promotion inspection without effectively rebuilding the same SQL
- Cost $10-175K/year for mature options (Retool) or add ops burden for "free" ones

The admin UI is not a generic CRUD dashboard. It is a domain-specific operator surface for government data pipeline debugging. The React components are the UI over the moat-critical backend logic.

### 4b. Object Storage (S3/MinIO) -- KEEP AS-IS

**Tempting alternative**: Railway Buckets, Cloudflare R2.

**Why keep current**: The S3-compatible MinIO backend is ~200 lines and works. The storage audit (PR #368) already verified the path. At current volumes (hundreds of PDFs, not millions), any S3-compatible backend is equivalent. Switching to Railway Buckets or R2 would be a lateral move with zero product value, and the migration cost (updating all `storage_uri` references) is not worth it.

Revisit only if MinIO becomes an operational burden or Railway Buckets offer materially better integration.

### 4c. Vector/Embedding Stack (pgvector) -- KEEP AS-IS

**Tempting alternative**: Pinecone, Weaviate, Qdrant, dedicated vector DB.

**Why keep pgvector**: At affordabot's scale (thousands to low millions of document chunks), pgvector in the existing Postgres is the correct choice. The critical advantage is transactional consistency -- embeddings, source metadata, and ingestion truth fields live in the same database, enabling atomic truthfulness audits. Moving vectors to a separate system would break the single-query bill-truth diagnostic and add operational complexity for zero benefit at this scale.

Revisit only past ~10M vectors or if query latency becomes a problem.

### 4d. Windmill (Orchestration) -- KEEP AS-IS

**Already bought**, already integrated, already working. The cron trigger pattern (Windmill -> HTTP POST -> backend `/cron/*` endpoint) is clean and observable. No reason to consider Airflow, Dagster, or Temporal at this scale.

---

## 5. "Do Not Build This" List (Next 1-2 Waves)

| Do Not Build | Why | What to Use Instead |
|--------------|-----|---------------------|
| Custom LLM cost/token tracking | Commodity observability problem | Langfuse (self-hosted or cloud free tier) |
| Custom charting/analytics dashboard | Unless it's substrate-specific operator tooling | Metabase for ad-hoc (wave 2-3), custom React only for domain views |
| Custom document parsing library | Government PDFs are hard, but the problem is well-studied | Keep markitdown + GLM-OCR fallback; evaluate Unstructured.io if parsing quality becomes a bottleneck |
| Custom embedding model serving | Not the product | Keep using the embedding API from the LLM provider |
| Custom CI/CD pipeline | Not the product | Railway auto-deploy + GitHub Actions |
| Custom auth system | Not the product | Keep Clerk |
| Generic BI/reporting | Not the product | Metabase if needed, Evidence.dev for versioned reports |
| Multi-tenant admin | Premature | Stay single-tenant until there is a second customer |

---

## 6. Comparison Table: Current Direction vs. Alternatives

| Area | Current Affordabot | Best Alternative | Switch? | Reason |
|------|-------------------|------------------|---------|--------|
| Scraper Registry | Custom per-jurisdiction | Scrapy/Crawl4AI as workers | NO | Workers are commodity; registry is moat |
| Legislation Analysis | Custom 1400-line service | Nothing equivalent | NO | Core product logic |
| Substrate Promotion | Custom 3-tier model | Nothing equivalent | NO | Novel data architecture |
| Bill-Truth Diagnostic | Custom endpoint | Nothing equivalent | NO | Domain-specific debugging |
| GlassBox (LLM tracing) | Custom ~540 lines | Langfuse | PARTIAL | Generic tracing to Langfuse; keep domain traces |
| Admin UI (operator) | Custom React + FastAPI | Appsmith/Retool/Directus | NO | Infra tax > build cost for solo founder |
| Ad-hoc Data Exploration | Custom endpoints | Metabase | LATER | Wave 2-3 when data volume justifies it |
| Object Storage | MinIO via S3 API | Railway Buckets / R2 | NO | Lateral move, no product value |
| Vector DB | pgvector in Postgres | Pinecone/Weaviate | NO | Transactional consistency > performance at this scale |
| Orchestration | Windmill | Dagster/Temporal | NO | Already working, right scale |
| PDF Extraction | markitdown + GLM-OCR | Unstructured.io | EVALUATE | Only if parsing quality degrades |
| Auth | Clerk | - | NO | Already bought, working |

---

## 7. Explicit Recommendation for Next 1-2 Waves

### Wave 1 (Current): Stay the Course
- Finish the substrate operator surface (viewer, bill-truth, storage integrity checks) as custom in-house work per PR #368 recommendation
- The admin UI extension is the correct path -- it is moat-adjacent operator tooling, not vanity engineering
- Do not introduce new infrastructure services

### Wave 2 (Next): Two Targeted Reuse Adoptions
1. **Langfuse for generic LLM observability**: Replace the generic tracing portions of GlassBox with Langfuse. Keep domain-specific mechanism traces custom. Estimated effort: 1-2 days to integrate, saves ongoing custom observability maintenance.
2. **Metabase for ad-hoc exploration**: Deploy alongside the app for founder-facing data exploration (not operator-facing product surface). Estimated effort: 1 hour to deploy, ongoing low maintenance.

### Wave 3+ (Later): Evaluate Only If Needed
- Unstructured.io if PDF parsing quality becomes a bottleneck for new jurisdictions
- Railway Buckets if MinIO ops become a burden
- Dedicated vector DB only if pgvector performance degrades at scale

---

## 8. Highest-Risk "Rebuilding Something That Exists" Areas

Ranked by risk of wasted effort:

1. **LLM tracing (GlassBox generic portions)**: Langfuse does this better and is actively maintained by ClickHouse. Risk: moderate. The custom code works today but will accumulate maintenance debt as the pipeline grows.

2. **Ad-hoc data exploration endpoints**: Every new `GET /admin/stats`-style endpoint is a mini dashboard that Metabase gives you for free. Risk: low-moderate. The endpoints are small, but they multiply.

3. **Frontend admin tables**: Each new React data table for a new data type is ~500-2000 lines. Risk: low. These are small individually but add up. The raw-data-viewer memo correctly identified this and chose build anyway -- the JSONB depth and single-auth-plane arguments are sound.

Everything else is either moat-critical (scraper registry, legislation analysis, substrate model) or already-bought (Windmill, Clerk, pgvector, MinIO).

---

## 9. The Lowest-Regret Build-vs-Buy Boundary

**Build custom**: anything that touches the data moat directly -- scraper logic, analysis pipeline, substrate promotion, truth auditing, and the operator surface that debugs these systems.

**Buy/reuse**: anything that is generic infrastructure observability or ad-hoc data access that does not require domain-specific interpretation.

**The line**: if the feature requires knowledge of affordabot's trust model, promotion semantics, or jurisdiction-specific extraction logic, build it. If it is "show me a chart of how many things ran today," reuse.

---

## 10. Answer to the Core Question

> "Are we going crazy building custom in-house?"

No. The custom work is concentrated in moat-critical areas where no off-the-shelf tool provides equivalent functionality. The two areas where commodity alternatives exist (LLM tracing, ad-hoc data exploration) are small and can be migrated incrementally without disrupting the product direction.

The current risk is not infrastructure ego -- it is the opposite. The founder is correctly building the operator surface *over* the data moat, which is exactly what a solo-founder startup should do. The minor optimization is to stop building generic observability and data browsing tools when Langfuse and Metabase exist, but this is a wave-2 refinement, not a course correction.
