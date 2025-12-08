# Cron Architecture

## Overview
Affordabot uses **Railway Cron** + **Python Scripts** for scheduled automation.
This replaces the legacy Prefect orchestration to reduce cost and complexity.

## Scripts
*   `scripts/daily_scrape.py`: Runs nightly. Scrapes all jurisdictions defined in `backend/services/scraper/registry.py`.

## Key Features
1.  **Retries:** Uses `tenacity` for exponential backoff on transient failures.
2.  **Concurrency:** Uses `asyncio.Semaphore` (default: 3) to prevent DB overload.
3.  **Logging:** Writes status to `admin_tasks` and `scrape_history` tables in Supabase.
4.  **Observability:** View real-time status in the Admin Dashboard (`/admin`).

## Deployment
To deploy, add this to `railway.toml` (or configure in Railway UI):

```toml
[service]
name = "cron-worker"
dockerfile = "Dockerfile.backend"

[[cron]]
schedule = "0 6 * * *" # 6 AM UTC
command = "python scripts/daily_scrape.py"
```

## Local Testing
```bash
# Set up environment
export PYTHONPATH=backend
source backend/.env

# Run script
python scripts/daily_scrape.py
```
