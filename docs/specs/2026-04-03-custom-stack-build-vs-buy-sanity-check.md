# Custom Stack Build-vs-Buy Sanity Check

**Date:** 2026-04-03
**Mode:** qa_pass
**Epic/Subtask:** bd-us1f
**Feature Key:** bd-us1f
**Class:** product

## 1. Current Custom Stack Inventory

Based on our analysis of the `affordabot` repository (specifically `backend/routers/admin.py`, `backend/services/glass_box.py`, and `frontend/src/services/adminService.ts`), the current stack includes:
- **Custom Admin & Operator Dashboard:** A custom React/TypeScript frontend (`adminService.ts`) speaking to a custom FastAPI backend (`admin.py`), with dedicated endpoints for Jurisdiction management, Scrapes, Prompts, Traces, Pipeline Runs, Document Health, and specific "Bill Truth" diagnostics.
- **GlassBox Service:** Custom execution trace and pipeline run observability (`glass_box.py`) supporting file-based and DB-backed retrieval.
- **Data Capture & Substrate Storage:** Custom pipeline for municipal scraping and document ingestion, landing in object storage with vector indexing. 
- **Storage Tier:** Relying on PostgreSQL (with pgvector implicitly or explicitly, given the focus on DB-backed runs) for relational data, runs, traces, and vector storage.

## 2. Moat-Critical Custom Areas (What we MUST own)

The real moat for Affordabot is **truthful local-government data coverage** and **revision-aware history**.
- **The Capture & Adapter Layer:** Custom ingestion and structured parsing for disjointed municipal lanes (Legistar, AgendaCenter, Municode) is the core product value. Off-the-shelf ETLs fail on bespoke, unstructured city council PDFs.
- **Revision-First Substrate History:** Storing structured states over time with robust vector representations is what makes the intelligence trustworthy. The specific domain-aware chunking and chunk promotion pipeline is a direct moat.
- **GlassBox Observability (The Logic, Not the UI):** The ability for a solo founder to debug exact pipeline steps and "bill truth" paths is critical for maintaining confidence in the data pipeline.

## 3. Commodity Areas (Reuse / Buy)

- **Admin/Operator UI:** Building custom React components for CRUD operations on Jurisdictions, Prompts, and Scrape Tasks is an active drain on a solo founder's time. This is textbook commodity infrastructure.
- **Generic Observability Dashboarding:** Visualizing pipeline runs and alerts in a custom frontend adds zero product moat. 
- **Isolated Vector Services (At this scale):** Moving vectors from Postgres to a dedicated vector database (like Pinecone) introduces unnecessary "Sync Tax" and breaks transactional guarantees.

## 4. "Do Not Build This" (Next 1-2 Waves)

- **DO NOT build custom React Admin dashboards.** Stop adding to `adminService.ts`. You are rebuilding a worse version of Directus or Retool.
- **DO NOT build custom document layout parsers** for generic PDFs. Use Unstructured.io (OSS or Serverless) for the initial partitioning, then apply custom logic only to the output JSON.
- **DO NOT migrate off Postgres/pgvector.** A dedicated vector database (Pinecone/Qdrant) introduces an eventual-consistency nightmare and sync tax that a solo founder cannot afford. Stick to ACID transactions in Postgres.

## 5. Build vs. Buy Comparison Table

| Category | "Build" (Current Custom Path) | "Buy/Reuse" (Alternative) | Solo Founder Cognitive Load Impact | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **Admin & Operator UI** | Custom React + FastAPI endpoints | **Directus** (or Retool) | **High Tax.** Polishing custom admin pages delays core product work. Directus gives instant CRUD over the DB. | **REUSE (Directus/Retool)** |
| **Vector Storage** | Postgres + pgvector (Unified) | **Pinecone** (Dedicated) | **Sync Hell.** Dedicated DBs require complex sync logic and network hops. pgvector keeps ACID consistency. | **BUILD (Keep pgvector)** |
| **Document Ingestion** | Custom OCR / Regex parsing | **Unstructured.io** (API/OSS) | **High Tax.** Layout parsing is messy. Unstructured handles tables/PDFs instantly. | **BUY (Unstructured)** |

## 6. Explicit Recommendation for the Next 1-2 Waves

1. **Adopt an off-the-shelf Admin layer (e.g., Directus or Retool)** for all manual GlassBox operator interventions. Stop writing custom API endpoints (`admin.py`) and frontend services (`adminService.ts`) just to update a Prompt or view a Jurisdiction's scrape history. Connect Directus directly to the Postgres DB.
2. **Keep Vector and Relational data unified in Postgres (pgvector).** Do not introduce a dedicated vector database. The operational simplicity of a single database is paramount for a solo founder.
3. **Double down on Custom Adapters, not Custom UIs.** Focus engineering solely on the un-commoditized problem: writing better adapters for obscure municipal systems and ensuring the "Bill Truth" trace is flawless. 

## 7. The Final Answer: Are we going crazy building custom in-house?

**Yes, specifically in the Operator/Admin UI layer.** 

You are correctly identifying that building a custom data pipeline and capturing bespoke municipal data is your moat. However, you are "going crazy" by wrapping that moat in a custom-built React/FastAPI admin dashboard. Every hour spent adjusting table sorting in `adminService.ts` is an hour stolen from adding new municipal adapters. 

Keep the custom intelligence and pipeline logic, but aggressively offload the internal visual surfacing to a headless CMS like Directus or a low-code builder like Retool.