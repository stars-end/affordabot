# Build vs. Buy Analysis: Raw Substrate Data Viewer

Date: 2026-04-03
Epic: bd-exvc

## 1. Current State (Affordabot Operator Surface)
Currently, affordabot has:
- **Admin Endpoints:** `/admin/bill-truth/{jurisdiction}/{bill_id}` offers a diagnostic trace.
- **GlassBox Traces:** Provides pipeline run visibility.
- **Slack Alerts:** `slack_summary.py` emits summaries of manual pipeline runs.
- **Substrate Inspection Reports:** JSON artifacts detailing the outcome of manual expansion runs.
- **Frontend Admin Service:** `adminService.ts` manages Sources, Scrapes, and Jurisdictions.

However, the setup lacks a dedicated operator-facing way to *browse* raw substrate data freely without knowing the exact `bill_id` or `run_id`, especially for early-pipeline failures or "captured_candidate" buckets.

## 2. Explicit Requirements
To support internal debugging of the raw substrate flow, a viewer must provide:
- **Browse by Run:** Filter and browse runs by `run_id` (stamped in `raw_scrapes.metadata`).
- **Rich JSONB Filtering:** Filter by fields deep inside the `metadata` JSONB blob (e.g., `asset_class`, `promotion_state`, `content_class`).
- **Failure Inspection:** Inspect failure buckets (e.g., `truth.stage`, `error_message`).
- **Artifact Access:** Open stored artifact references (`storage_uri` to MinIO/S3) with a single click.

**CRITICAL: Solo Founder Constraints (Nakomi Protocol)**
- **Minimize Cognitive Load:** The solution must not introduce permanent operational or infrastructure tax (e.g., babysitting new deployments, managing separate auth planes).
- **Robustness over Novelty:** The solution must reliably query deeply nested Postgres JSONB without fragile hacks or workarounds.
- **One Decision Surface:** Operators should not have to context-switch between three different tools to debug one pipeline failure.

## 3. Build Option Analysis (Extend In-House)
**Approach:** Extend the existing Next.js frontend and FastAPI backend to include a "Raw Data Browser" tab.
- **Implementation Effort:** Medium (Write a React table and a FastAPI asyncpg endpoint).
- **Robustness:** **High.** Native asyncpg queries (e.g., `metadata->>'promotion_state'`) are the most reliable way to filter JSONB.
- **Cognitive Load / Auth:** **Zero new load.** Seamlessly uses the existing Clerk auth and Railway deployment. Keeps all debugging in a single pane of glass.
- **Operational Tax:** Zero new infrastructure.

## 4. OSS / Buy Option Analysis (Evaluated for Solo Founder)
**Approach:** Deploy an OSS internal tool builder (NocoDB, Appsmith, Directus) as a new Railway service connected to the Postgres DB.

*   **NocoDB ("Airtable for Postgres"):**
    *   *Robustness:* **Low for JSONB.** Filtering nested JSON fields (like `metadata.promotion_state`) requires creating custom formula columns using `JSON_EXTRACT` hacks. Very fragile as schemas evolve.
    *   *Cognitive Load:* High. Requires deploying and maintaining a new Node.js app on Railway and managing its separate user accounts.
*   **Appsmith / Retool (Low-Code Builders):**
    *   *Robustness:* **Medium.** Solves JSONB by allowing raw Postgres SQL, but binds it to the UI via proprietary JS expressions `{{...}}`.
    *   *Cognitive Load:* Extremely High. The founder still has to write the SQL and build the UI manually, *plus* manage a massive Java/Spring/React deployment on Railway, *plus* figure out SSO/auth.
*   **Metabase / Redash (BI Tools):**
    *   *Robustness:* **High for read-only.** Great for custom URL drill-downs.
    *   *Cognitive Load:* Medium-High. Great for charts, but introduces a new infrastructure piece just to view a table of rows. Dead-ends any future operational workflows (like adding a "Retry Scrape" button).

## 5. Comparison Table

| Tool / Approach | JSONB Robustness | Solo Founder Cognitive Load (Infra/Auth) | Single Pane of Glass |
| :--- | :--- | :--- | :--- |
| **Extend In-House UI** | **Excellent** (Native SQL) | **Lowest** (Reuses existing stack) | **Yes** (Admin app) |
| **NocoDB (OSS)** | **Poor** (Formula hacks) | **High** (New deployment, separate auth) | **No** |
| **Appsmith (OSS)** | **Good** (Raw SQL) | **Highest** (Heavy deployment, separate auth)| **No** |
| **Metabase (OSS)** | **Good** (Raw SQL) | **High** (New deployment, separate auth) | **No** |

## 6. Recommended Path
**Recommendation: Build (Extend the existing In-House UI + API)**

**Why this wins on Robustness and Cognitive Load:**
The *Nakomi Protocol* demands a long-term payoff bias that removes recurring cognitive burden. Adopting an OSS tool like NocoDB or Appsmith seems like a shortcut, but for a solo founder, it is a trap. It introduces a permanent infrastructure tax: you must monitor a new Railway service, apply its security updates, and manage a completely separate authentication boundary (since SSO is usually enterprise-gated). 

Furthermore, OSS tools lack native robustness for our deeply nested JSONB payloads, forcing the founder to maintain clunky formula hacks. 

Biting the bullet and writing a native React table in the *already existing* Admin app guarantees maximum robustness (native asyncpg queries) and zero new cognitive load (no new deployments, reuses Clerk auth, keeps debugging in one single browser tab).

**Next-Iteration Recommendation (ALL_IN_NOW for the Viewer):**
1. **Backend:** Add `GET /admin/substrate-runs/{run_id}/rows` in `admin.py` using native asyncpg JSONB operators (`->>`).
2. **Frontend:** Add a "Substrate Browser" route in the existing Admin app with a standard data table.
3. **Artifacts:** Include a native hyperlink button opening `storage_uri`.

## 7. What Not To Do
- **Do not introduce new infrastructure.** Do not deploy Appsmith, NocoDB, or Metabase. The ongoing maintenance tax for a solo founder vastly outweighs the initial development time of a React table.
- **Do not split the operational surface.** Keep all debugging (Bill Truth, GlassBox, Substrate) in the existing Admin UI.
- **Do not dump raw logs into Slack.** Slack is for alerts, not browsing.
