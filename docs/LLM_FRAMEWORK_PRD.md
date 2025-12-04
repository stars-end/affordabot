# LLM Framework & RAG Expansion - Product Requirements Document (PRD)

**Version:** 2.0
**Date:** 2025-12-03
**Status:** Approved
**Owner:** Engineering Team
**Epics:** `affordabot-0yo` (RAG Expansion)

---

## Executive Summary

This PRD defines the architecture for Affordabot's "Full City Infrastructure" RAG system. It unifies `affordabot` and `prime-radiant-ai` under a shared `llm-common` framework while expanding Affordabot's scope to include comprehensive city data (meetings, regulations, permits, taxes).

### Core Architecture
- **Orchestration**: **Prefect** (Scheduling, Retries, Concurrency).
- **AI Logic**: **`llm-common`** (LiteLLM + Instructor) used as a library.
- **Scraping**: **Scrapy** (City-Scrapers for meetings, Custom Spiders for full sites).
- **Storage**:
    - **Raw**: `raw_scrapes` (Postgres/Blob) - Managed by `affordabot`.
    - **RAG**: `documents` (Supabase pgvector) - Managed via `llm-common` backend.
- **Discovery**: **z.ai** (Auto-discovery of new sources).

### Constraints
- **`llm-common`**: Shared library. **NO CHANGES** permitted by this team. Must be consumed as-is. Feature requests go to the `llm-common` agent.

---

## Functional Requirements

### FR-1: Multi-Provider LLM Support (`llm-common`)
**Priority:** P0
- **Description**: Unified interface for OpenAI, Anthropic, OpenRouter, z.ai.
- **Implementation**: `LLMClient` in `llm-common`.

### FR-2: Comprehensive City Scraping (`affordabot-yr8`)
**Priority:** P0
- **Scope**:
    - **Meetings**: Agendas, Minutes, Transcripts (via `city-scrapers` fork/import).
    - **Regulations**: Municipal Codes, Zoning Ordinances (Custom Spiders).
    - **Infrastructure**: Permits, Property Taxes, Easements (Custom Spiders).
- **Orchestration**: Prefect flows managed in `affordabot`.

### FR-3: RAG Ingestion Pipeline (`affordabot-1z4`)
**Priority:** P0
- **Workflow**:
    1.  Read from `raw_scrapes`.
    2.  Clean & Chunk text.
    3.  Generate Embeddings (via `llm-common` / LiteLLM).
    4.  Store in `documents` (via `SupabasePgVectorBackend`).
- **Schema**: Shared `Document` schema in `llm-common`.

### FR-4: Admin Source Management (`affordabot-9ko`)
**Priority:** P1
- **Description**: UI to manage 100+ jurisdictions and discover new sources.
- **Features**:
    - **Jurisdiction View**: List of tracked cities/counties.
    - **Auto-Discovery**: Background job (z.ai) finds new URLs (e.g., "New Permit Portal").
    - **Review Queue**: Admin approves/rejects discovered sources.
    - **Health Dashboard**: Scrape status (Green/Red) per source.

---

## Data Architecture

### Raw Storage (`raw_scrapes`)
- **Purpose**: Source of Truth. Allows re-processing.
- **Content**: Full HTML, PDF blobs, JSON.
- **Deduplication**: Content hashing.

### RAG Storage (`documents`)
- **Backend**: Supabase pgvector (via `llm-common` PR #3).
- **Metadata**: `jurisdiction_id`, `source_type` (meeting, code), `timestamp`.

---

## Implementation Roadmap

### Phase 0: The "Walking Skeleton" (San Jose Only)
**Goal**: End-to-end data flow for *one* city (San Jose) without UI.
- **Scope**:
    -   1 City: San Jose.
    -   2 Sources: Meetings (`city-scrapers`) + Municipal Code (Municode).
- **Deliverables**:
    -   DB Schema (`sources`, `raw_scrapes`).
    -   Minimal Scrapy project with 2 spiders.
    -   Minimal Prefect flow (`scrape_jurisdiction_flow`).
    -   Manual SQL insertion of sources.

### Phase 1: Infrastructure Hardening & Ingestion
**Goal**: Robust storage and RAG ingestion.
- **Deliverables**:
    -   `IngestionService`: `raw_scrapes` -> Chunk -> Embed -> `documents`.
    -   Integration with `llm-common` (SupabasePgVectorBackend).
    -   Validation of RAG pipeline (Query -> Vector Search).

### Phase 2: Admin UI (Visibility)
**Goal**: Manage what we have.
- **Deliverables**:
    -   Admin UI to view Jurisdictions and Sources.
    -   Manual trigger buttons for scrapes.
    -   Health status indicators.

### Phase 3: Scale & Automation
**Goal**: Expand reach.
- **Deliverables**:
    -   `z.ai` Auto-Discovery Job.
    -   Onboard 4+ more cities (SF, Oakland, etc.).
    -   Automated scheduling and alerting.

## Feature-Key
affordabot-0yo

