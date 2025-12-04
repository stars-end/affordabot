# Scraping Architecture & Tech Spec

## Overview
This document details the technical implementation for the "Full City Infrastructure" scraping system.

## 1. Orchestration (Prefect)
- **Deployment**: Prefect Cloud (Free Tier) or Self-Hosted Server.
- **Flows**:
    - `scrape_jurisdiction_flow`: Main entry point. Accepts `jurisdiction_id`.
    - `discover_sources_flow`: Runs `z.ai` search to find new URLs.
- **Tasks**:
    - `run_spider_task`: Triggers a Scrapy spider (via subprocess or API).
    - `process_raw_content_task`: Cleaning and validation.
    - `ingest_to_rag_task`: Calls `llm-common` embedding logic.

## 2. Scraping Engine (Scrapy)
- **Project Structure**: Standard Scrapy project `affordabot_scraper`.
- **Spiders**:
    - `CityScrapersSpider`: Wrapper around `city-scrapers` classes.
    - `MunicodeSpider`: Generic spider for Municode-hosted regulations.
    - `GeneralCitySpider`: Recursive crawler for `.gov` domains with keyword filtering (e.g., "permit", "tax").
- **Middleware**:
    - `ScrapyPlaywrightDownloadHandler`: For JS rendering.
    - `RetryMiddleware`: Aggressive retries for government servers.

## 3. Database Schema (Postgres/Supabase)

### `sources`
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | PK |
| `jurisdiction_id` | UUID | FK to Jurisdictions |
| `url` | Text | Entry point URL |
| `type` | Enum | `meeting`, `code`, `general` |
| `status` | Enum | `active`, `broken`, `review` |
| `last_scraped_at` | Timestamp | |

### `raw_scrapes`
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | PK |
| `source_id` | UUID | FK to Sources |
| `content_hash` | Text | SHA256 of content (dedup) |
| `content_type` | Text | `text/html`, `application/pdf` |
| `data` | JSONB | `{ "html": "...", "text": "..." }` |
| `created_at` | Timestamp | |

## 4. Integration with `llm-common` (RAG Backend)
**Constraint**: `llm-common` is a shared dependency managed by another agent. We consume it "as-is".

- **Ingestion Workflow** (in `affordabot-rdx`):
    1.  **Read**: Fetch content from `raw_scrapes`.
    2.  **Process**: Clean and chunk text (Affordabot logic).
    3.  **Embed**: Use `llm-common.LLMClient` to generate embeddings (e.g., `text-embedding-3-small`).
    4.  **Store**: Use `llm-common.SupabasePgVectorBackend` to save documents.
        -   **Mapping**: Map Affordabot-specific metadata (jurisdiction, source type) into the backend's generic `metadata` JSON field.
        -   **No Changes**: We do not modify `llm-common`. If we need new backend features, we request them from the `llm-common` agent.

## 5. Admin UI Separation
- **Scraping Admin** (`affordabot`):
    -   Manage Jurisdictions & Sources.
    -   View Scrape Health.
    -   Trigger Manual Scrapes.
- **LLM Admin** (`llm-common` / Shared):
    -   Manage Prompts & Models.
    -   View Token Usage & Costs.
    -   *Affordabot UI will link to or consume endpoints from the shared LLM Admin for these features.*

## Feature-Key
affordabot-0yo
