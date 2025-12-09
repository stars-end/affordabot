# Future n8n Integration Strategy

**Status:** Defer to Phase 4 (Business Ops / Marketing)
**Recommended Role:** "Glue Code" for external integrations (Notifications, CRM, Ops).
**Core Rule:** Do NOT use for Core RAG/Scraping pipelines.

## What is n8n?
n8n is an open-source, self-hostable workflow automation tool ("Open-Source Zapier"). On Railway, it offers flat-fee pricing rather than per-task pricing, making it cost-effective for high-volume automation.

## Decision: Why NOT for Core RAG?
We explicitly decided **against** using n8n for the core scraping/ingestion pipeline (`daily_scrape.py`, `run_rag_spiders.py`, `IngestionService`) for the following reasons:
1.  **Specialized Logic:** Our "Universal Harvester" uses complex fallback logic (Web Reader -> Crawl4AI -> GLM-4.6) that is painful to maintain in visual node graphs ("Spaghetti Nodes").
2.  **Version Control:** Python code is easier to version, test, and deploy via CI/CD than visual workflows.
3.  **Model Specificity:** We rely on specific Z.ai GLM-4.6 capabilities that generic n8n AI nodes may not support natively.

## Proposed Use Cases (Phase 4+)
Once the core product is stable, n8n is an excellent candidate for handling "Noisy Integrations" without polluting the Python backend.

### 1. Alerts & Notifications
*   **Trigger:** Database event (e.g., New High-Impact Legislation found in `impacts` table).
*   **Action:** Post summary to Twitter/X, Send Email digest via Resend/SendGrid, Post to Discord.
*   **Benefit:** Zero maintenance of 3rd party API libraries (`tweepy`, etc.) in our codebase.

### 2. Ops & Monitoring
*   **Trigger:** `admin_tasks` record marked as `failed`.
*   **Action:** Send alert to Developer Discord/Slack.
*   **Benefit:** Instant observability without configuring PagerDuty.

### 3. User CRM Sync
*   **Trigger:** New user signup in Supabase `users`.
*   **Action:** Add to Mailchimp/HubSpot/Resend audiences.
*   **Benefit:** Decouples marketing logic from authentication logic.

## Implementation Plan
1.  Deploy n8n via Railway Template (e.g., `n8n-with-workers`).
2.  Connect n8n to Supabase (Postgres).
3.  Create workflows triggered by Postgres Database Changes (CDC) or Cron schedules.
