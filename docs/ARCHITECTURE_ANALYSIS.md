# Architecture & Integration Analysis

## 1. Marvin vs. `llm-common`
**Conflict**: Marvin is an "AI Engineering Framework" that abstracts LLM interactions (classification, extraction). `llm-common` is *also* an LLM interaction layer (using `instructor` for extraction/classification). Using both is redundant and confusing.

**Recommendation**: **Drop Marvin. Use Prefect Core + `llm-common`.**
- **Orchestration (Prefect)**: Use Prefect solely for *scheduling*, *retries*, *logging*, and *concurrency* of scraping jobs. This is its core strength and does not conflict with `llm-common`.
- **AI Logic (`llm-common`)**: Inside a Prefect task, use `llm-common` (which wraps `litellm` + `instructor`) for any AI needs (e.g., "Extract meeting date from this text").
- **Why**: You have already invested in `llm-common` for prompt versioning, provider management (`litellm`), and structured outputs (`instructor`). Marvin would bypass this stack.

## 2. Admin UI & Discovery (Scalability)
**Challenge**: Managing 100+ jurisdictions manually is impossible.
**Solution**: "Source Management" Module.
- **Discovery**: Use `z.ai` (via `llm-common.WebSearchClient`) to auto-discover URLs.
    - *Action*: "Add Jurisdiction: San Jose" -> Triggers background job -> Searches "San Jose city council minutes", "San Jose municipal code" -> Populates `sources` table.
- **UI UX**:
    - **Jurisdiction View**: List of all tracked cities/counties.
    - **Source Health**: For each city, list known sources (Meetings, Code, Permits). Status indicators (Green/Red) based on last scrape.
    - **Review Queue**: When `z.ai` finds a *new* potential source (e.g., "San Jose launched a new permit portal"), it goes to a "Review" queue for Admin approval before scraping.

## 3. DB Schema: Raw vs. RAG
We need a "Lake" (Raw) and a "Warehouse" (RAG).

### Raw Storage (`raw_scrapes`)
- **Purpose**: The "Source of Truth". If we change our chunking strategy, we re-process from here, NOT re-scrape.
- **Schema**:
    - `id`: UUID
    - `source_id`: FK to `sources` (Jurisdiction URL)
    - `scraped_at`: Timestamp
    - `content_type`: Enum (HTML, PDF, JSON)
    - `raw_content`: JSONB (Store full HTML or text content here. For PDFs, store path to blob storage).
    - `hash`: String (for deduplication - don't re-process if hash hasn't changed).

### RAG Storage (`documents` - via `llm-common`)
- **Purpose**: Semantic search.
- **Schema** (Managed by `SupabasePgVectorBackend`):
    - `id`: UUID
    - `content`: Text (Chunk)
    - `embedding`: Vector
    - `metadata`: JSONB. **Critical**: Must contain `raw_scrape_id`, `jurisdiction_id`, `doc_type` (meeting, regulation), `timestamp`.

## 4. Embeddings in `llm-common`
- **Workflow**: `llm-common` (PR #3) provides the *storage* backend (`SupabasePgVectorBackend`). It *delegates* the embedding generation.
- **Integration**:
    1.  **Ingestion Service** (in `affordabot-rdx`):
        -   Reads `raw_scrapes`.
        -   Cleans & Chunks text.
        -   Calls Embedding API (e.g., OpenAI `text-embedding-3-small` via `litellm`).
        -   Passes (Text, Vector, Metadata) to `SupabasePgVectorBackend.add_documents()`.

## 5. Summary of Changes
1.  **No Marvin**: Use Prefect for flow control, `llm-common` for brains.
2.  **New DB Tables**: `jurisdictions`, `sources`, `raw_scrapes`.
3.  **New Admin Pages**: "Jurisdictions", "Source Discovery".
4.  **Ingestion Pipeline**: Explicit step to move data from `raw_scrapes` -> `documents` (RAG).
