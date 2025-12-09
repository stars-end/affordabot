# Infrastructure Roadmap

Analysis of Railway templates and their role in Affordabot's future architecture.

## Phase 4: Optimizations & UX

### 1. Browserless (Headless Chrome)
*   **Template:** `b5k2mn` (Browserless / Chrome)
*   **Role:** Dedicated Scraping Infrastructure.
*   **Problem:** Currently, `Crawl4AI` and `Scrapy` launch local Chromium processes inside the backend container. This consumes high RAM and can crash the API under load.
*   **Solution:** Deploy Browserless as a microservice. Update backend to connect via WebSocket (`ws://browserless...`).
*   **Trigger:** When backend memory usage exceeds 80% or scraping volume > 100 pages/day.

### 2. Typebot (Chat UX)
*   **Template:** `typebot`
*   **Role:** Conversational UI / Front Desk.
*   **Problem:** Building a rich chat interface (streaming, bubbles, inputs) in React is time-consuming.
*   **Solution:** Use Typebot for the visual flow. Connect it to `backend` API for RAG answers.
*   **Trigger:** When focusing on "User Experience" epic.

## Rejected / Redundant

*   **FastAPI Template:** Redundant (We already have a mature FastAPI backend).
*   **pgvector Template:** Redundant (Supabase provides managed pgvector).
*   **ChromaDB:** Redundant (See `docs/TOOL_EVALUATION.md`).
*   **MinIO:** Redundant (Supabase Storage covers this).
*   **AnythingLLM:** Redundant (We built a custom, specialized RAG pipeline).
