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
- **Browse by Run:** Filter and browse runs by `run_id`.
- **Inspect Raw Rows:** View raw rows tied to a substrate run.
- **Rich Filtering:** Filter by jurisdiction, asset class, promotion state, trust tier, and content class.
- **Failure Inspection:** Inspect failure buckets (e.g., `ingestion_stage`, `promotion_reason`).
- **Summary Views:** View substrate inspection report summaries.
- **Deep Dives:** Drill into a single raw scrape row.
- **Artifact Access:** Open or preview stored artifact references (e.g., MinIO/S3 PDFs) when possible.
- **Context Connection:** Connect raw substrate state to GlassBox/pipeline context where useful.
- **Operator-Friendly:** Remain internal/operator-friendly without overloading Slack.

## 3. Build Option Analysis (Extend In-House)
**Approach:** Extend the existing frontend (`frontend/src/services/adminService.ts`) and FastAPI backend (`backend/routers/admin.py`) to include a "Raw Data Browser" tab.
- **Implementation Effort:** Medium-High. Requires building complex data tables, pagination, dynamic filtering over JSONB, and artifact preview modals.
- **Fit to Data Model:** Perfect. Can directly query `raw_scrapes`, `pipeline_runs`, and link GlassBox traces perfectly.
- **Artifact Preview:** Custom implementations required for PDFs/HTML.
- **Auth/Ergonomics:** Seamless integration with existing Clerk/internal auth.
- **Debugging Usefulness:** Very high, but requires developer maintenance as schemas evolve.
- **Operational Overhead:** High dev maintenance, zero additional infrastructure.

## 4. OSS / Buy Option Analysis
**Approach:** Deploy an OSS internal tool builder or data browser connected to the PostgreSQL database.

*   **NocoDB:**
    *   *Pros:* "Airtable for Postgres". Zero-code setup. Instantly provides rich filtering, sorting, and relational browsing across `raw_scrapes`. Extremely low effort to deploy.
    *   *Cons:* Can be clunky for highly customized "drill-down" views that join 4-5 tables or require deep JSONB parsing (crucial for our `metadata` and `data` blobs).
*   **Directus:**
    *   *Pros:* Instant admin panel over existing SQL database. Excellent data browsing, filtering, and relation traversal out-of-the-box. Built-in file preview capabilities.
    *   *Cons:* Modifies the database schema to add its own tracking tables (adds friction).
*   **Appsmith / Retool / ToolJet:**
    *   *Pros:* Highly customizable UI. Good for building specific workflows and querying JSONB fields via custom SQL.
    *   *Cons:* Still requires significant "building" (writing SQL queries, binding data to tables). Introduces a new platform to maintain.
*   **SQLAdmin (FastAPI Native):**
    *   *Pros:* Since the backend is FastAPI/Python, integrating `SQLAdmin` (based on SQLAlchemy) could provide a fast, code-driven admin panel.
    *   *Cons:* Less flexible for complex JSONB filtering without writing custom views.

## 5. Comparison Table

| Tool / Approach | Effort to Deploy | Fit to Affordabot JSONB Data | Custom Artifact Preview | Operational Overhead |
| :--- | :--- | :--- | :--- | :--- |
| **Extend In-House UI** | High (Weeks) | Perfect | Full Control | High (Maintenance) |
| **NocoDB (OSS)** | Very Low (Hours) | Poor (JSONB is hard) | Limited (URLs) | Low (Self-hosted app) |
| **Directus (OSS)** | Low (Days) | Medium | Excellent | Medium |
| **Appsmith (OSS)** | Medium (Days) | Good (Requires SQL) | High (Custom widgets) | Medium |
| **SQLAdmin (Python)**| Low (Days) | Medium | Medium | Low |

## 6. Recommended Path
**Recommendation: Build (Extend In-House UI + API)**

*Why not Buy/OSS?*
While tools like NocoDB or Appsmith are excellent for generic relational table browsing, Affordabot's raw substrate data heavily relies on highly specific JSON blobs (e.g., `metadata.promotion_state`, GlassBox `mechanism_trace`). OSS generic tools struggle to elegantly parse, filter, and cross-link deep JSON structures without writing extensive custom SQL views anyway. Furthermore, jumping between an OSS tool (for raw data) and the existing in-house Admin UI (for GlassBox traces and Bill Truth) creates a disjointed operator experience.

**Next-Iteration Recommendation:**
1. **Backend:** Add a new endpoint `GET /admin/substrate-runs` and `GET /admin/substrate-runs/{run_id}/rows` in `admin.py` that parses the `raw_scrapes` metadata JSON and returns structured, paginated data.
2. **Frontend:** Add a new "Substrate Browser" route in the existing admin app with a standard data table that supports filtering by `jurisdiction`, `promotion_state`, and `content_class`.
3. **Artifacts:** Include a simple "Preview" button that opens `storage_uri` URLs in a new tab.

## 7. What Not To Do
- **Do not** build a fully-featured, customer-facing BI dashboard. Keep it raw and ugly but highly functional.
- **Do not** adopt a heavy low-code platform (like Retool or Appsmith) just for this; the overhead of managing a separate internal tool deployment outweighs the frontend effort required to build a simple table in the existing admin app.
- **Do not** dump more raw JSON logs into Slack. Slack is for alerts, not browsing.
