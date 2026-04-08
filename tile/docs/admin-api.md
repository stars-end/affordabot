# AffordaBot Admin REST API

All admin endpoints are protected by Clerk JWT authentication. The authenticated user must have the admin role, be listed in `ADMIN_USER_IDS`, or have an email matching a domain in `ADMIN_EMAIL_DOMAINS`.

**Prefix:** `/api/admin`
**Auth:** `Authorization: Bearer <clerk_jwt>`

For test environments with `ENABLE_TEST_AUTH_BYPASS=true`, use token `TEST_TOKEN_ADMIN` to bypass auth.

## Jurisdiction Endpoints

### GET /api/admin/jurisdictions

List all jurisdictions.

```python { .api }
GET /api/admin/jurisdictions
# Returns: List[Jurisdiction]
# Errors: 500 — database error

class Jurisdiction(BaseModel):
    id: str
    name: str
    type: str  # "city" | "county" | "state"
```

### GET /api/admin/jurisdictions/{jurisdiction_id}

Get detailed information about a jurisdiction by ID or slug.

```python { .api }
GET /api/admin/jurisdictions/{jurisdiction_id}
# jurisdiction_id: str — UUID, name, or slug (e.g., "california", "san-jose")
# Returns: JurisdictionDetail
# Errors: 404 — not found, 500 — database error

class JurisdictionDetail(BaseModel):
    id: str
    name: str
    type: str        # "city" | "county" | "state"
    bill_count: int
    source_count: int
    last_scrape: Optional[str]  # ISO timestamp or None
```

### GET /api/admin/jurisdiction/{jurisdiction_id}/dashboard

Get dashboard statistics for a specific jurisdiction.

```python { .api }
GET /api/admin/jurisdiction/{jurisdiction_id}/dashboard
# jurisdiction_id: str — UUID, name, or slug
# Returns:
# {
#   "jurisdiction": str,
#   "last_scrape": str | None,
#   "total_raw_scrapes": int,
#   "processed_scrapes": int,
#   "total_bills": int,
#   "pipeline_status": "healthy" | "degraded" | "unknown",
#   "active_alerts": []
# }
# Errors: 404 — not found, 500 — database error
```

## Prompt Endpoints

System prompts are stored in the `system_prompts` database table and used by LLM pipeline steps.

### GET /api/admin/prompts

List all active system prompts.

```python { .api }
GET /api/admin/prompts
# Returns: List[Prompt]
# Errors: 500 — database error

class Prompt(BaseModel):
    id: Optional[str]
    prompt_type: str        # e.g., "legislation_analysis", "discovery_query_generator"
    system_prompt: str
    description: Optional[str]
    version: int            # auto-incremented on update
    is_active: bool
```

### GET /api/admin/prompts/{prompt_type}

Get a specific active system prompt by type.

```python { .api }
GET /api/admin/prompts/{prompt_type}
# prompt_type: str — e.g., "legislation_analysis"
# Returns: Prompt
# Errors: 404 — prompt type not found, 500 — database error
```

### POST /api/admin/prompts

Create or update a system prompt (creates a new version).

```python { .api }
POST /api/admin/prompts
# Body: PromptUpdate
# Returns: {"success": True, "message": "Prompt updated", "version": int}
# Errors: 500 — database error

class PromptUpdate(BaseModel):
    type: str           # prompt_type
    system_prompt: str
```

## Scrapes & Stats

### GET /api/admin/scrapes

List recent scrapes (raw ingestion records).

```python { .api }
GET /api/admin/scrapes?limit=50
# limit: int = 50
# Returns: list of scrape records
# [
#   {
#     "id": str,
#     "url": str,
#     "scraped_at": str | None,
#     "jurisdiction_id": str | None,
#     "jurisdiction_name": str | None,
#     "metadata": dict | None
#   }
# ]
# Errors: 500 — database error
```

### GET /api/admin/stats

Get overall dashboard statistics.

```python { .api }
GET /api/admin/stats
# Returns:
# {
#   "jurisdictions": int,
#   "scrapes": int,
#   "sources": int,
#   "chunks": int   # vector document chunks
# }
# Errors: 500 — database error
```

## Glass Box (Pipeline Observability)

### GET /api/admin/pipeline-runs

List recent pipeline runs.

```python { .api }
GET /api/admin/pipeline-runs
# Returns: list of pipeline run summary objects
# Each entry:
# {
#   "id": str,
#   "bill_id": str,
#   "jurisdiction": str,
#   "status": "completed" | "failed" | "running" | "prefix_halted" | "fixture_invalid",
#   "started_at": str | None,
#   "completed_at": str | None,
#   "error": str | None,
#   "trigger_source": str,   # "manual", "prefix:<label>", "fixture:<label>"
#   "is_prefix_run": bool,
#   "is_fixture_run": bool,
#   "run_label": str | None
# }
```

### GET /api/admin/pipeline-runs/{run_id}

Get details for a specific pipeline run, including all steps.

```python { .api }
GET /api/admin/pipeline-runs/{run_id}
# run_id: str — pipeline run UUID
# Returns: pipeline run detail + "steps": List[PipelineStep]
# Errors: 404 — run not found
```

### GET /api/admin/runs/{run_id}/steps

Get granular execution steps for a pipeline run.

```python { .api }
GET /api/admin/runs/{run_id}/steps
# run_id: str — pipeline run UUID
# Returns: List[PipelineStep]

class PipelineStep(BaseModel):
    id: str
    run_id: str
    step_number: int
    step_name: str    # one of CANONICAL_PIPELINE_STEPS
    status: str
    input_context: Optional[Dict[str, Any]]
    output_result: Optional[Dict[str, Any]]
    model_info: Optional[Dict[str, Any]]
    duration_ms: Optional[int]
    created_at: Any   # timestamp
```

**Canonical pipeline step names** (in order):

```python { .api }
CANONICAL_PIPELINE_STEPS = [
    "ingestion_source",
    "chunk_index",
    "research_discovery",
    "impact_discovery",
    "mode_selection",
    "parameter_resolution",
    "sufficiency_gate",
    "generate",
    "parameter_validation",
    "review",
    "refine",
    "persistence",
    "notify_debug"
]
```

### GET /api/admin/traces

List all recorded agent session IDs (file-based trace legacy).

```python { .api }
GET /api/admin/traces
# Returns: List[str]  # list of query_id strings
```

### GET /api/admin/traces/{query_id}

Get full execution trace for a specific agent session.

```python { .api }
GET /api/admin/traces/{query_id}
# query_id: str
# Returns: List[AgentStep]

class AgentStep(BaseModel):
    tool: str
    args: Dict[str, Any]
    result: Any
    task_id: str
    query_id: str
    timestamp: int   # Unix timestamp
```

## Alerts

### GET /api/admin/alerts

List system alerts derived from pipeline run result data (deterministic, no separate alert store).

```python { .api }
GET /api/admin/alerts
# Returns:
# {
#   "alerts": [
#     {
#       "id": str,           # "{rule}-{run_id}"
#       "type": "error" | "warning",
#       "severity": str,     # "high" | "medium" | "low"
#       "rule": str,
#       "message": str,
#       "jurisdiction": str | None,
#       "bill_id": str | None,
#       "run_id": str,
#       "created_at": str,
#       "acknowledged": False
#     }
#   ]
# }
# Errors: 500 — alert evaluation failed
```

## Document Health

### GET /api/admin/document-health

View ingestion and vector indexing status for scraped documents.

```python { .api }
GET /api/admin/document-health
# Returns:
# {
#   "documents": [
#     {
#       "id": str,
#       "url": str,
#       "jurisdiction": str | None,
#       "jurisdiction_id": str | None,
#       "scraped_at": str | None,
#       "content_hash": str | None,
#       "chunk_count": int,       # number of vector chunks
#       "document_id": str | None,
#       "extraction_status": str | None,
#       "source_type": str | None,
#       "bill_number": str | None,
#       "has_vector_chunks": bool
#     }
#   ],
#   "total": int
# }
# Errors: 500 — database error
```

### GET /api/admin/bill-truth/{jurisdiction}/{bill_id}

Bill-level truth diagnostic: trace a bill through Scrape → Raw Text → Vector Chunks → Research → Pipeline.

```python { .api }
GET /api/admin/bill-truth/{jurisdiction}/{bill_id}
# jurisdiction: str — e.g., "california"
# bill_id: str — bill number (partial match supported, e.g., "AB-1234")
# Returns:
# {
#   "jurisdiction": str,
#   "bill_id": str,
#   "scrape": {
#     "raw_scrape_id": str,
#     "url": str,
#     "scraped_at": str | None,
#     "content_length": int,
#     "extraction_status": str | None,
#     "source_type": str | None,
#     "source_url": str | None
#   } | None,
#   "legislation": {
#     "legislation_id": str,
#     "bill_number": str,
#     "title": str,
#     "analysis_status": str | None,
#     "sufficiency_state": str | None,
#     "insufficiency_reason": str | None,
#     "quantification_eligible": bool | None
#   } | None,
#   "pipeline_run": PipelineRunInfo | None,
#   "pipeline_runs": {
#     "latest_run": PipelineRunInfo | None,
#     "latest_completed_run": PipelineRunInfo | None,
#     "latest_failed_run": PipelineRunInfo | None
#   }
# }

# PipelineRunInfo:
# {
#   "run_id": str,
#   "status": str,
#   "started_at": str | None,
#   "completed_at": str | None,
#   "error": str | None,
#   "trigger_source": str,
#   "is_prefix_run": bool,
#   "is_fixture_run": bool,
#   "run_label": str | None,
#   "sufficiency_breakdown": dict | None,
#   "source_text_present": bool | None,
#   "rag_chunks_retrieved": int,
#   "quantification_eligible": bool | None,
#   "aggregate_scenario_bounds": dict | None,
#   "prefix_boundary": Any,     # from pipeline run details
#   "mechanism_trace": Any      # from pipeline run details
# }
# Errors: 500 — diagnostic failed
```

## Model & Analysis Stubs

These endpoints are partially implemented and may be expanded in future versions.

```python { .api }
GET /api/admin/models
# List available LLM models
# Returns:
# {
#   "models": [
#     {"id": str, "name": str, "provider": str, "status": "active" | "unconfigured"}
#   ]
# }

GET /api/admin/health/models
# Returns: {"zai": "healthy" | "missing_key", "openrouter": "healthy" | "missing_key"}

GET /api/admin/reviews
# Returns: {"reviews": [], "message": str}

POST /api/admin/reviews/{review_id}
# Returns: {"status": "success", "message": str}

POST /api/admin/analyze
# Returns: {"status": "pending", "message": str}
```
