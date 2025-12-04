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
**Constraint**: `llm-common` is a shared dependency. We consume its interfaces but implement the pipeline locally in `affordabot`.

- **Ingestion Workflow** (in `affordabot`):
    1.  **Read**: Fetch unprocessed content from `raw_scrapes`.
    2.  **Process**: Clean and chunk text (Affordabot `IngestionService`).
    3.  **Embed**: Use `llm-common.LLMClient` (via LiteLLM) to generate embeddings (e.g., `text-embedding-3-small`).
    4.  **Store**: Use `llm-common.retrieval.SupabasePgVectorBackend` interface to save documents to local `documents` table.
        -   **Schema**: Local `documents` table with `vector(1536)` column.
        -   **Metadata**: Map Affordabot-specific metadata (jurisdiction, source type) into the generic `metadata` JSON field.

### `documents` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | PK |
| `document_id` | UUID | Grouping ID for chunks |
| `content` | Text | Chunk text |
| `embedding` | Vector(1536) | OpenAI text-embedding-3-small |
| `metadata` | JSONB | Source metadata |
| `chunk_index` | Integer | Order within document |

## 5. Source Method Differentiation

Sources are prioritized by reliability and maintenance cost (Tech Lead Guidance):

### 1. Meetings (Agendas/Minutes)
*   **Primary**: `city-scrapers` (Structured, maintained, free).
    *   Use existing spiders where available.
*   **Secondary**: APIs (OpenStates, Legistar) if supported.
*   **Last Resort**: `Web Reader` + Local Parsing.
    *   Only if no spider/API exists.

### 2. Non-Meeting Content (Codes, Permits, General)
*   **Default**: `Web Reader` (z.ai `POST /paas/v4/reader`).
    *   Cost: Negligible (~$250/yr for 5k calls/block).
    *   Output: Markdown/Text.
    *   Process: Fetch → Parse/Normalize locally → Ingest.
*   **Fallback**: Playwright/Scrapy.
    *   Only for complex pages where Web Reader fails.

### 3. Discovery
*   **Strategy**: Static source lists preferred to reduce churn.
*   **Tool**: `Web Search` (z.ai) only for finding *new* URLs or replacing broken ones.

### Handlers
- `city_scrapers`: Delegates to `affordabot_scraper` spiders.
- `web_reader`: Uses z.ai Web Reader API.
- `api_client`: Uses specific API clients (e.g., OpenStates).

### Schema Changes
```sql
ALTER TABLE sources ADD COLUMN source_method VARCHAR(20) 
  CHECK (source_method IN ('scrape', 'api', 'manual')) 
  DEFAULT 'scrape';

ALTER TABLE sources ADD COLUMN handler VARCHAR(100);
-- Examples:
-- handler = 'sanjose_meetings' (spider name)
-- handler = 'legistar_generic' (reusable spider)
-- handler = 'openstates_api' (API client)
```

**Prefect Flow Routing**:
```python
if source['source_method'] == 'api':
    run_api_fetch_task(source)
elif source['source_method'] == 'scrape':
    run_spider_task(source, spider_name=source['handler'])
elif source['source_method'] == 'manual':
    skip  # No automated fetch
```

---

## 6. Auto-Discovery System

### Query Generation Strategy

**Template-Based Approach** (Primary):
```python
QUERY_TEMPLATES = {
    "city": {
        "meetings": [
            "{name} city council meetings",
            "{name} planning commission agenda"
        ],
        "code": [
            "{name} municipal code",
            "{name} zoning ordinance"
        ],
        "permits": [
            "{name} building permits",
            "{name} planning applications"
        ]
    },
    "county": {
        "meetings": ["{name} board of supervisors"],
        "code": ["{name} county code"]
    }
}
```

**Cost Model**:
- Base queries: ~15 per jurisdiction
- z.ai searches: 15 × $0.01 = **$0.15/jurisdiction**
- **100 jurisdictions: ~$15** (one-time or quarterly)

### Search Execution
- Uses `llm-common.WebSearchClient` (z.ai with 2-tier caching)
- Caching reduces repeat costs to $0
- Simple heuristic filtering (`.gov`, `.us`, known platforms)

### Template Maintenance (LLM-Assisted)

**Weekly Review Job**:
```python
# Tests templates on sample jurisdictions
# LLM reviews results and suggests improvements
# Creates admin review queue for template changes
```

**Cost**: ~$0.01/week = **$0.50/year**

**Benefits**:
- Prevents template rot
- Catches platform migrations (Legistar → Granicus)
- Scales to 1000+ jurisdictions without manual maintenance

### Admin Workflow
1. Admin clicks "Discover Sources" for jurisdiction
2. System runs template-based discovery (~30 seconds)
3. Results appear in Review Queue with status `review`
4. Admin approves/rejects each URL
5. Approved URLs → `status='active'` → scheduled scraping

### Template Review Queue
Admin sees LLM-suggested template improvements:
```
Category: permits
Current: "{name} building permits"
Suggested: Add "{name} planning applications"
Reasoning: "Found separate planning portals in 2/3 test jurisdictions"
[Approve] [Reject] [Edit]
```

---

## 7. Health Monitoring

### Source Health Tracking
```sql
CREATE TABLE source_health (
  id uuid PRIMARY KEY,
  source_id uuid REFERENCES sources(id),
  checked_at timestamptz NOT NULL,
  status VARCHAR(20), -- 'success', 'failed', 'timeout'
  error_message TEXT,
  response_time_ms INTEGER,
  items_scraped INTEGER
);
```

**Auto-Remediation**:
- 3 consecutive failures → Mark source as `broken`
- Admin receives alert
- Source disabled from scheduled runs until fixed

### Raw Scrape Debugging Fields
```sql
ALTER TABLE raw_scrapes ADD COLUMN scrape_duration_ms INTEGER;
ALTER TABLE raw_scrapes ADD COLUMN http_status_code INTEGER;
ALTER TABLE raw_scrapes ADD COLUMN error_message TEXT;
ALTER TABLE raw_scrapes ADD COLUMN scraped_by VARCHAR(50);
```

---

## 8. Admin UI Separation
- **Scraping Admin** (`affordabot`):
    -   Manage Jurisdictions & Sources
    -   View Scrape Health
    -   Trigger Manual Scrapes
    -   Review Auto-Discovered Sources
    -   Approve Template Changes
- **LLM Admin** (`llm-common` / Shared):
    -   Manage Prompts & Models
    -   View Token Usage & Costs
    -   *Affordabot UI will link to or consume endpoints from the shared LLM Admin for these features.*

---

## 9. Admin Data Access

### Source List View
Admin UI displays:
- Jurisdiction hierarchy (City → County → State)
- Sources per jurisdiction (URL, type, status, last scraped)
- Filters: jurisdiction, type, status, source_method
- Actions: Edit, Disable, View Raw Scrapes

### Raw Scrapes Viewer
**Source Detail Page**:
```
Source: San Jose Meetings (Legistar)
├─ URL: https://sanjose.legistar.com/Calendar.aspx
├─ Method: scrape (handler: sanjose_meetings)
├─ Status: Active ✅
├─ Last Scraped: 2 hours ago
└─ Raw Scrapes (5 total)
    ├─ [2024-12-04 05:40] Hash: e87add00 [View JSON]
    ├─ [2024-12-04 03:15] Hash: a1b2c3d4 [View JSON]
```

**Features**:
- Paginated table of all `raw_scrapes`
- Filter by source, date range, hash
- Click row → Modal shows full JSON
- Download as JSON/CSV

## Feature-Key
affordabot-0yo
