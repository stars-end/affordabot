# AffordaBot Public REST API

The public REST API provides endpoints for accessing legislation data, triggering scraping, and health monitoring. These endpoints do not require authentication (except cron endpoints).

**Base URL:** Configured via `NEXT_PUBLIC_API_URL` (default: `https://backend-production-c383.up.railway.app`)

## Root & Health Endpoints

### GET /

Returns welcome message with supported jurisdictions.

```python { .api }
GET /
# Returns:
# {
#   "message": "Welcome to AffordaBot API",
#   "jurisdictions": ["saratoga", "san-jose", "santa-clara-county", "california", "nyc", ...],
#   "version": "1.0.0"
# }
```

### GET /health

Health check for database and Z.ai research connectivity.

```python { .api }
GET /health
# Returns:
# {
#   "status": "healthy",
#   "database": "connected" | "disconnected",
#   "zai_research": "connected" | "disconnected"
# }
```

### GET /health/jurisdictions

Health check for all registered jurisdiction scrapers.

```python { .api }
GET /health/jurisdictions
# Returns:
# {
#   "status": "success",
#   "jurisdictions": {
#     "saratoga": "healthy" | "unhealthy",
#     "california": "healthy" | "unhealthy",
#     ...
#   }
# }
```

### GET /health/analysis

Health check for the LLM pipeline (LLM + web search).

```python { .api }
GET /health/analysis
# Returns on success:
# {
#   "status": "healthy" | "degraded",
#   "details": {
#     "llm": "connected" | "error",
#     "search": "connected" | "unknown"
#   }
# }
# Returns on failure:
# {"status": "unhealthy", "error": str}
```

## Legislation Endpoints

### POST /scrape/{jurisdiction}

Scrape legislation from a jurisdiction, analyze with the LLM pipeline, and store results in the database.

```python { .api }
POST /scrape/{jurisdiction}
# jurisdiction: str — one of the supported jurisdiction keys
# Returns:
# {
#   "jurisdiction": str,
#   "processed": int,   # number of bills successfully analyzed
#   "skipped": int,     # number of bills skipped (e.g., missing text)
#   "errors": [{"bill": str, "error": str}]
# }
# Errors:
#   404 — jurisdiction not supported
#   500 — pipeline error
```

**Supported jurisdictions:**

| Key | Description |
|-----|-------------|
| `saratoga` | City of Saratoga |
| `san-jose` | City of San Jose (API scraper) |
| `sanjose` | Alias for `san-jose` |
| `san-jose-cityscrapers` | City of San Jose (CityScrapers adapter) |
| `santa-clara-county` | County of Santa Clara |
| `california` | State of California |
| `nyc` | New York City |

### GET /legislation/{jurisdiction}

Get stored legislation for a jurisdiction with their impact analyses.

```python { .api }
GET /legislation/{jurisdiction}?limit=10
# jurisdiction: str — one of the supported jurisdiction keys
# limit: int = 10 — number of results to return
# Returns:
# {
#   "jurisdiction": str,
#   "count": int,
#   "legislation": [
#     {
#       "bill_number": str,
#       "title": str,
#       "jurisdiction": str,
#       "status": str,
#       "impacts": [Impact],
#       "total_impact_p50": float | None,
#       "sufficiency_state": SufficiencyState | None,
#       "insufficiency_reason": str | None,
#       "quantification_eligible": bool | None,
#       "analysis_timestamp": str | None,  # ISO 8601
#       "model_used": str
#     }
#   ]
# }
# Errors:
#   404 — jurisdiction not supported
```

**Impact object in legislation list response:**

```python { .api }
{
  "impact_number": int,
  "impact_description": str,
  "relevant_clause": str,
  "confidence": float | None,  # renamed from confidence_score
  "p50": float | None,         # central scenario estimate (annual $/household)
  "evidence": [ImpactEvidence],
  # ... other impact fields
}
```

### GET /legislation/{jurisdiction}/{bill_number}

Get detailed data for a specific bill.

```python { .api }
GET /legislation/{jurisdiction}/{bill_number}
# jurisdiction: str — jurisdiction key
# bill_number: str — bill identifier (e.g., "AB-1234")
# Returns: bill detail dict (structure same as individual entry in legislation list)
# Errors:
#   404 — jurisdiction not supported or bill not found
```

## Bills Search

### GET /api/bills/search

Search for bills by bill number or title.

```python { .api }
GET /api/bills/search?q={query}&jurisdiction={name}&limit=20
# q: str — required, minimum 2 characters
# jurisdiction: Optional[str] — filter by jurisdiction name (case-insensitive)
# limit: int = 20
# Returns:
# {
#   "results": [
#     {
#       "bill_id": str,
#       "title": str | None,
#       "jurisdiction": str,
#       "status": str | None
#     }
#   ],
#   "count": int
# }
```

---

## System Prompts (Non-Admin)

Non-admin endpoints for reading and updating system prompts. These are included with the `/api` prefix.

### GET /api/prompts/{prompt_type}

Get a system prompt by type.

```python { .api }
GET /api/prompts/{prompt_type}
# prompt_type: str — e.g., "legislation_analysis", "discovery_query_generator"
# Returns: prompt record dict (id, prompt_type, system_prompt, description, version, is_active)
# Errors: 404 — prompt not found
```

### GET /api/prompts

Get all system prompts (currently returns `legislation_analysis` prompt only).

```python { .api }
GET /api/prompts
# Returns: List of prompt records (may be empty)
```

### PUT /api/prompts/{prompt_type}

Update a system prompt by type. The `prompt_type` in URL must match body.

```python { .api }
PUT /api/prompts/{prompt_type}
# Body: SystemPromptUpdate
# Returns: {"prompt_type": str, "new_version": int}
# Errors: 400 — URL/body type mismatch, 500 — update failed

class SystemPromptUpdate(BaseModel):
    prompt_type: str
    system_prompt: str
    description: Optional[str] = None
```

---

## Cron Endpoints

Authenticated endpoints for scheduled background tasks. Used by Windmill as the scheduler.

**Authentication:** Provide one of:
- `Authorization: Bearer <CRON_SECRET>`
- `X-Cron-Secret: <CRON_SECRET>`
- `X-PR-CRON-SECRET: <CRON_SECRET>` (Prime-style shared Windmill)

```python { .api }
POST /cron/discovery
# Trigger the source discovery pipeline
# Returns on success: {"job": "discovery", "status": "succeeded", "exit_code": 0, "stdout_tail": str, "stderr_tail": str}
# Returns on failure: {"job": "discovery", "status": "failed", ...}
# Errors: 401 — invalid credentials, 500 — job failure

POST /cron/daily-scrape
# Trigger daily scrape for all jurisdictions
# Returns: same structure as /cron/discovery

POST /cron/rag-spiders
# Trigger RAG spider pipeline
# Returns: same structure as /cron/discovery

POST /cron/universal-harvester
# Trigger universal harvester pipeline
# Returns: same structure as /cron/discovery
```

**Cron job response structure:**

```python { .api }
{
  "job": str,          # job name
  "script_path": str,  # absolute path to the script
  "exit_code": int,    # process exit code
  "status": "succeeded" | "failed",
  "stdout_tail": str,  # last 4000 chars of stdout
  "stderr_tail": str   # last 4000 chars of stderr
}
```
