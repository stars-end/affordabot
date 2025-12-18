# RAG & Scraping Expansion Plan

## Executive Summary
This plan outlines the strategy to expand Affordabot's data ingestion to include comprehensive city/county data (regulations, meetings, full website text) for key California jurisdictions. The goal is to build a high-value, RAG-ready dataset that is maintainable by a single developer.

## Scope Expansion
### Target Jurisdictions
- **Cities**: Saratoga, San Jose, Palo Alto, San Francisco, Oakland.
- **Counties**: Santa Clara, San Mateo, Alameda, San Francisco.
- **State**: California.

### Data Types
1.  **Regulations/Laws**: Municipal codes, zoning ordinances.
2.  **Meetings**: Agendas, minutes, transcripts (if available).
3.  **Full Website Text**: General pages, department info, FAQs (permitting, taxes, easements).

## Architecture & Tooling

### Orchestration: Prefect + Marvin
**Recommendation: Prefect**
- **Why**:
    - **Observability**: Built-in UI to see what failed and why. Essential for "bulletproof" scraping.
    - **Retries**: Native support for retries with backoff (crucial for flaky govt sites).
    - **Concurrency**: Manages parallel scraping jobs better than cron scripts.
    - **Agentic Workflows**: Use **Marvin** (Prefect's AI engineering framework) or standard Prefect + `llm-common` for agentic steps. *Note: ControlFlow has been merged into Marvin.*

### Scraping Engine
- **Framework**: **Scrapy** (Python).
    - **Meetings**: **Use `City-Bureau/city-scrapers`**.
        - **Status**: Active (40+ contributors, recent commits).
        - **Strategy**: Import their spiders/pipelines. Do not reinvent.
    - **Full Site & Regulations**: Build custom Scrapy spiders.
        - **Gap**: `city-scrapers` focuses on meetings. We need to scrape municipal codes (Municode/Amlegal) and general city pages.
- **Browser Automation**: **Playwright** (via `scrapy-playwright`) for dynamic JS-heavy sites.

### RAG & Ingestion (`llm-common` Integration)
- **Current State**: `llm-common` provides `LLMClient` and `WebSearchClient`.
- **New Capabilities (PR #3)**: Adds `SupabasePgVectorBackend`.
    - **Strategy**: Use this backend for storage. `affordabot-rdx` will focus on the *ingestion pipeline* (Scraper -> Text Cleaning -> Chunking -> `SupabasePgVectorBackend`).
    - **Shared Schema**: Define a common schema for "Documents" (source, type, content, embedding) in `llm-common`.

## Competitive Landscape
- **GatherGov**: API for meetings (50 states). ~$300/state/month. *Meeting focused.*
- **Council Data Project**: Open source, meeting transcripts. Deployed in Oakland/San Jose. *Meeting focused.*
- **Civic APIs**: Cicero, USgeocoder (mostly reps/districts).
- **Gap Analysis**:
    - Competitors are heavily focused on **meetings** and **representatives**.
    - **Our Value Prop**: "Full City Infrastructure" RAG.
        - **Scope**: Meetings + **Permits** + **Property Taxes** + **Easements** + **Regulations**.
        - **Why**: Real estate developers, homeowners, and businesses need more than just meeting minutes; they need the *rules* and *processes*.
    - **Build vs Buy**: Build. We need the full data ownership to train/RAG over the complete city context, which no single competitor offers comprehensively.

## Implementation Roadmap
1.  **Pilot (affordabot-i0x)**:
    - Set up Prefect + Scrapy.
    - Implement spiders for **1 City (e.g., San Jose)** covering:
        - Meetings (reuse `city-scrapers` logic).
        - Municipal Code (usually hosted on distinct platforms like Municode or Amlegal - *high value*).
        - General Website (recursive crawl).
2.  **Ingestion (affordabot-rdx)**:
    - Define `Document` schema in `llm-common`.
    - Implement embedding pipeline (Supabase).
3.  **Scale**:
    - Roll out to remaining target cities/counties.
