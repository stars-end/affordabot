# Build vs. Buy Analysis: Raw Substrate Data Viewer

Date: 2026-04-03
Epic: bd-exvc

## 1. Current State (Affordabot Operator Surface)
Currently, affordabot has:
- **Admin Endpoints:** `/admin/bill-truth/{jurisdiction}/{bill_id}` offers a diagnostic trace (Scrape -> Raw Text -> Vector Chunks -> Research).
- **GlassBox Traces:** Provides pipeline run visibility (`PipelineStep`, `AgentStep`).
- **Slack Alerts:** `slack_summary.py` emits summaries of manual pipeline runs directly to Slack.
- **Substrate Inspection Reports:** `substrate_inspection_report.py` generates JSON artifacts detailing the outcome of manual expansion runs, identifying promotion states, failure buckets, and sample rows.
- **Frontend Admin Service:** `adminService.ts` manages Sources, Scrapes, and Jurisdictions.

However, the current setup lacks an operator-facing way to *browse* raw substrate data freely without knowing exactly what `bill_id` or `run_id` to query, especially for data that failed early in the pipeline or sits in the "captured_candidate" bucket.

## 2. Explicit Requirements
To support internal operators debugging the raw substrate flow, a viewer must provide:
- **Browse by Run:** Filter and browse runs by `run_id` (typically stamped in `raw_scrapes.metadata`).
- **Inspect Raw Rows:** View raw rows tied to a substrate run.
- **Rich Filtering on JSONB:** Filter by jurisdiction (joined via `sources`), and critically, by fields deep inside the `metadata` JSONB blob (e.g., `asset_class`, `promotion_state`, `trust_tier`, `content_class`).
- **Failure Inspection:** Inspect failure buckets (e.g., `truth.stage`, `metadata.promotion_reason_category`, and raw `error_message`).
- **Deep Dives:** Drill into a single raw scrape row's JSON payload.
- **Artifact Access:** Open or preview stored artifact references (e.g., `storage_uri` pointing to MinIO/S3) with a single click.
- **Operator-Friendly:** Remain internal/operator-friendly (read-only for now, but potentially extensible to "retry scrape" actions) without overloading Slack.

## 3. Build Option Analysis (Extend In-House)
**Approach:** Extend the existing frontend (`frontend/src/services/adminService.ts`) and FastAPI backend (`backend/routers/admin.py`) to include a "Raw Data Browser" tab.
- **Implementation Effort:** Medium. Requires building a React data table, pagination, dynamic filtering over Postgres JSONB, and a simple link/modal for `storage_uri`.
- **Fit to Data Model:** Perfect. We can directly write the optimal SQLAlchemy/asyncpg queries (e.g., `metadata->>'promotion_state'`) and link GlassBox traces.
- **Artifact Preview:** We can render `storage_uri` as a native hyperlink or an iframe modal.
- **Auth/Ergonomics:** Seamless integration with existing Clerk/internal auth. No context-switching for operators who already use the Admin UI for Bill Truth.
- **Operational Overhead:** High dev maintenance for the initial build, but zero additional infrastructure.

## 4. OSS / Buy Option Analysis (Re-evaluated with Fresh Eyes)
**Approach:** Deploy an OSS internal tool builder or data browser connected directly to the PostgreSQL database.

*   **NocoDB ("Airtable for Postgres"):**
    *   *Pros:* Extremely low effort to deploy. Instantly provides relational browsing across `raw_scrapes`.
    *   *Cons:* **JSONB filtering is a major friction point.** Filtering by nested JSON fields (like our required `metadata.promotion_state`) requires creating custom formula columns using `JSON_EXTRACT` hacks. It is clunky for complex, deep JSON inspection.
*   **Appsmith / Retool (Low-Code Builders):**
    *   *Pros:* Highly customizable UI. Solves the JSONB problem because it allows writing raw Postgres SQL (e.g., `WHERE metadata->>'run_id' = {{...}}`). We can easily bind `storage_uri` to a button widget.
    *   *Cons:* We still have to "build" the UI and write the SQL queries manually within the platform. It introduces a completely new deployment, hosting, and authentication plane just for one table view, creating a disjointed experience from our existing Admin app.
*   **Directus (Headless CMS/Admin):**
    *   *Pros:* Excellent data browsing and file preview capabilities. Supports JSON filtering via its API (`json(field, path)`).
    *   *Cons:* Standard GUI filtering on JSON is still somewhat limited compared to flat columns. It also requires modifying the database schema to add its own tracking tables, which adds unnecessary friction to our cleanly separated DB.
*   **Metabase / Redash (BI Tools):**
    *   *Pros:* Good for writing SQL-backed tables with custom URL drill-downs (Metabase "Custom Click Behavior").
    *   *Cons:* Read-only by design. If we ever want operators to click "Retry Scrape" directly from the viewer, BI tools cannot support this operational workflow.
*   **DBeaver / Beekeeper Studio (DB Clients):**
    *   *Pros:* The best pure JSONB tree inspection.
    *   *Cons:* Violates the "operator-friendly" requirement. Giving raw DB access to operators is unsafe, and there are no clickable artifact URLs.

## 5. Comparison Table

| Tool / Approach | Fit to Affordabot JSONB Data | Custom Artifact Preview (`storage_uri`) | Operational Workflow (e.g. Retries) | Infrastructure Overhead |
| :--- | :--- | :--- | :--- | :--- |
| **Extend In-House UI** | **Perfect** (Native asyncpg SQL) | **Excellent** (Native UI links) | **Supported** (Add an API route) | **None** (Reuses existing apps) |
| **Appsmith (OSS)** | **Good** (Requires writing SQL) | **Good** (Button widgets) | **Supported** | **High** (New deployment & auth) |
| **NocoDB (OSS)** | **Poor** (Formula workarounds) | **Limited** (Text URLs) | **Unsupported** | **Medium** (Self-hosted app) |
| **Metabase (OSS)** | **Good** (Requires SQL) | **Excellent** (Custom Click) | **Unsupported** (Read-only) | **Medium** (Self-hosted app) |

## 6. Recommended Path
**Recommendation: Build (Extend the existing In-House UI + API)**

*Why not Buy/OSS?*
Our requirements are heavily anchored in deeply nested Postgres JSONB payloads (`metadata`, `truth`, `data`) and operator workflows. 
- "No-code" tools like NocoDB fail on deep JSONB filtering without clunky formula hacks. 
- "Low-code" tools like Appsmith solve the JSONB problem by making you write raw SQL anyway, but force you to maintain a whole separate platform and auth boundary. 
- Since we *already* maintain a dedicated React/FastAPI Admin app with established auth and styling, the effort to write one `GET /admin/substrate-runs` endpoint and one React Table is less than the overhead of provisioning, securing, and maintaining Appsmith just for this view. Furthermore, keeping it in-house allows us to easily add operational actions like "Retry Scrape" later, which BI tools (Metabase) cannot do.

**Next-Iteration Recommendation:**
1. **Backend:** Add a new endpoint `GET /admin/substrate-runs/{run_id}/rows` in `admin.py` that executes the native asyncpg query filtering by the requested `run_id` and extracting top-level keys from the `metadata` JSONB for sorting/filtering.
2. **Frontend:** Add a new "Substrate Browser" route in the existing Admin app with a standard data table that supports filtering by `jurisdiction`, `promotion_state`, and `content_class`.
3. **Artifacts:** Include a simple "Preview" button in the table row that opens the `storage_uri` URL in a new tab.

## 7. What Not To Do
- **Do not** adopt a heavy low-code platform (like Retool or Appsmith) just for this; the overhead of managing a separate internal tool deployment outweighs the frontend effort required to build a simple table in the existing admin app.
- **Do not** use Metabase/BI tools for this specific view; while great for charts, they dead-end operational workflows where operators might want to trigger a retry.
- **Do not** dump more raw JSON logs into Slack. Slack is for alerts, not browsing.
