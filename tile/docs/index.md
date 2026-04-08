# AffordaBot

AffordaBot is a full-stack monorepo web application ("Dependabot for government") that automatically monitors California legislative bills and regulations, uses LLMs to analyze their cost-of-living impact on typical families, and exposes findings through an interactive dashboard and REST API.

## Package Information

- **Package Name**: affordabot
- **Repository**: github:stars-end/affordabot
- **Package Type**: Application (Python FastAPI backend + Next.js frontend)
- **Languages**: Python 3.9+, TypeScript
- **Backend**: FastAPI + Poetry
- **Frontend**: Next.js 16 + Tremor + Tailwind CSS
- **Database**: Supabase (PostgreSQL via asyncpg)
- **LLMs**: Z.ai (GLM-4.7), OpenRouter (fallback), OpenAI (embeddings)
- **Auth**: Clerk JWT
- **Infra**: Railway

## Setup

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# or: poetry install

# Required env vars (see Environment Variables section)
export DATABASE_URL=postgresql://...
export ZAI_API_KEY=...
export CLERK_JWKS_URL=...
export CLERK_JWT_ISSUER=...

uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
# or: pnpm install

export NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

## Core Imports (Backend Python)

```python
from fastapi import FastAPI
from db.postgres_client import PostgresDB
from auth.clerk import require_admin_user, ClerkAuth, UserProfile
from schemas.analysis import (
    LegislationAnalysisResponse, LegislationImpact, ImpactEvidence,
    ScenarioBounds, SufficiencyState, ImpactMode, FailureCode
)
from services.glass_box import GlassBoxService, AgentStep, PipelineStep
from services.source_service import SourceService, SourceCreate, SourceUpdate
from services.auto_discovery_service import AutoDiscoveryService
from services.scraper.base import BaseScraper, ScrapedBill
from services.llm.orchestrator import AnalysisPipeline
```

## Core Imports (Frontend TypeScript)

```typescript
import { scrapeJurisdiction, getBill, getLegislation, JURISDICTIONS } from '@/lib/api';
import type { Jurisdiction, SufficiencyState, Impact, Bill } from '@/lib/api';
```

## Basic Usage

```python
import asyncio
from db.postgres_client import PostgresDB
from services.llm.orchestrator import AnalysisPipeline
from llm_common.core import LLMConfig
from llm_common.providers import ZaiClient
from llm_common.web_search import WebSearchClient

async def analyze_bill():
    db = PostgresDB()
    await db.connect()

    llm_config = LLMConfig(api_key="...", provider="zai", default_model="glm-4.7")
    llm_client = ZaiClient(llm_config)
    search_client = WebSearchClient(api_key="...")

    pipeline = AnalysisPipeline(llm_client, search_client, db)
    result = await pipeline.run(
        bill_id="AB-1234",
        bill_text="Full text of the bill...",
        jurisdiction="California",
        models={"research": "glm-4.7", "generate": "glm-4.7", "review": "glm-4.7"}
    )
    await db.close()
    return result
```

## Architecture

AffordaBot is organized as a monorepo with:

- **Backend** (`backend/`): Python FastAPI service handling data ingestion, LLM analysis, and REST API
- **Frontend** (`frontend/`): Next.js 16 dashboard that proxies API calls to the backend
- **Scrapers** (`backend/services/scraper/`): Per-jurisdiction legislation scrapers
- **Analysis Pipeline** (`backend/services/llm/orchestrator.py`): Multi-step LLM workflow for impact analysis
- **Glass Box** (`backend/services/glass_box.py`): Pipeline observability and run tracing
- **Auth** (`backend/auth/clerk.py`): Clerk JWT-based admin authentication

## Capabilities

### Public REST API (Backend)

Core endpoints for accessing legislation data, scraping jurisdictions, and health checks. No authentication required.

```python { .api }
# GET /
# Returns: {"message": str, "jurisdictions": list[str], "version": str}

# GET /health
# Returns: {"status": str, "database": str, "zai_research": str}

# GET /health/jurisdictions
# Returns: {"status": str, "jurisdictions": dict[str, str]}

# GET /health/analysis
# Returns: {"status": str, "details": {"llm": str, "search": str}}

# POST /scrape/{jurisdiction}
# Scrape, analyze, and store legislation for a jurisdiction
# jurisdiction: "saratoga" | "san-jose" | "santa-clara-county" | "california" | "nyc"
# Returns: {"jurisdiction": str, "processed": int, "skipped": int, "errors": list}

# GET /legislation/{jurisdiction}?limit=10
# Returns: {"jurisdiction": str, "count": int, "legislation": list[dict]}

# GET /legislation/{jurisdiction}/{bill_number}
# Returns: bill detail dict

# GET /api/bills/search?q={query}&jurisdiction={name}&limit=20
# Returns: {"results": [{"bill_id": str, "title": str, "jurisdiction": str, "status": str}], "count": int}

# GET /api/prompts/{prompt_type}
# GET /api/prompts
# PUT /api/prompts/{prompt_type}
# System prompt read/update (non-admin)
```

[Public REST API](./public-api.md)

### Admin REST API

Protected admin endpoints for managing jurisdictions, prompts, sources, pipeline runs, and observability. Requires Clerk admin JWT.

```python { .api }
# All admin endpoints require: Authorization: Bearer <clerk_jwt>
# Prefix: /api/admin/

# GET /api/admin/jurisdictions
# GET /api/admin/jurisdictions/{jurisdiction_id}
# GET /api/admin/jurisdiction/{jurisdiction_id}/dashboard
# GET /api/admin/prompts
# GET /api/admin/prompts/{prompt_type}
# POST /api/admin/prompts
# GET /api/admin/scrapes?limit=50
# GET /api/admin/stats
# GET /api/admin/alerts
# GET /api/admin/document-health
# GET /api/admin/bill-truth/{jurisdiction}/{bill_id}
# GET /api/admin/pipeline-runs
# GET /api/admin/pipeline-runs/{run_id}
# GET /api/admin/runs/{run_id}/steps
# GET /api/admin/traces
# GET /api/admin/traces/{query_id}
# GET /api/admin/models
# GET /api/admin/health/models
```

[Admin REST API](./admin-api.md)

### Sources & Discovery API

Admin-protected endpoints for managing data sources and running auto-discovery of new government sources.

```python { .api }
# Prefix: /api/admin/sources/ (admin-required)
# GET /api/admin/sources/?jurisdiction_id={id}
# POST /api/admin/sources/
# GET /api/admin/sources/{source_id}
# PATCH /api/admin/sources/{source_id}
# DELETE /api/admin/sources/{source_id}

# POST /api/discovery/run  (no auth required)
# Body: {"jurisdiction_name": str, "jurisdiction_type": str}
```

[Sources & Discovery API](./sources-discovery-api.md)

### Cron Endpoints

Authenticated webhook endpoints for scheduled tasks. Used by Windmill as the scheduler of record.

```python { .api }
# Auth: Authorization: Bearer $CRON_SECRET
#       X-Cron-Secret: $CRON_SECRET
#       X-PR-CRON-SECRET: $CRON_SECRET (Prime-style)

# POST /cron/discovery     — Run discovery pipeline
# POST /cron/daily-scrape  — Run daily scrape for all jurisdictions
# POST /cron/rag-spiders   — Run RAG spider pipeline
# POST /cron/universal-harvester — Run universal harvester
```

[Cron Endpoints](./public-api.md#cron-endpoints)

### Analysis Schemas

Pydantic models that define the structure of legislation analysis output, including impacts, evidence, scenario bounds, and sufficiency states.

```python { .api }
class LegislationAnalysisResponse(BaseModel):
    bill_number: str
    title: str
    jurisdiction: str
    status: str
    sufficiency_state: SufficiencyState
    insufficiency_reason: Optional[str]
    quantification_eligible: bool
    impacts: List[LegislationImpact]
    aggregate_scenario_bounds: Optional[ScenarioBounds]
    analysis_timestamp: str
    model_used: str
```

[Analysis Schemas](./schemas.md)

### Authentication

Clerk JWT-based authentication for admin endpoints, with support for role-based access, user ID allowlists, and email domain allowlists.

```python { .api }
async def require_admin_user(request: Request, credentials: ...) -> UserProfile: ...

class ClerkAuth:
    async def __call__(self, credentials: HTTPAuthorizationCredentials) -> UserProfile: ...
```

[Authentication](./auth.md)

### Pipeline Services

Python service classes for the analysis pipeline: scrapers, orchestrator, glass box observability, source management, and auto-discovery.

```python { .api }
class AnalysisPipeline:
    async def run(self, bill_id: str, bill_text: str, jurisdiction: str, models: dict) -> dict: ...

class GlassBoxService:
    async def get_pipeline_run(self, run_id: str) -> Optional[dict]: ...
    async def list_pipeline_runs(self) -> dict: ...

class BaseScraper(ABC):
    async def scrape(self) -> List[ScrapedBill]: ...
    async def check_health(self) -> bool: ...
```

[Pipeline Services](./services.md)

### Chat API (SSE Streaming)

Server-Sent Events endpoint for streaming policy analysis from the PolicyAgent in real time.

> ⚠️ **Note**: The chat router (`routers/chat.py`) is implemented but not currently mounted in `main.py`. See [Chat API docs](./chat-api.md) for activation instructions.

```python { .api }
POST /api/chat
# Body: ChatRequest
# Returns: StreamingResponse (text/event-stream)

class ChatRequest(BaseModel):
    message: str
    jurisdiction: Optional[str] = "San Jose"
    session_id: Optional[str] = None

# SSE event types: thinking, tool_call, tool_result, text, sources, done, error

GET /api/chat/health
# Returns: {"status": "healthy", "endpoint": "/api/chat"}
```

[Chat API](./chat-api.md)

### Frontend TypeScript API Client

TypeScript types and functions for interacting with the backend API from the Next.js frontend.

```typescript { .api }
async function scrapeJurisdiction(jurisdiction: Jurisdiction): Promise<any>;
async function getBill(jurisdiction: string, billNumber: string): Promise<any>;
async function getLegislation(jurisdiction: Jurisdiction, limit?: number): Promise<any>;
```

[Frontend API Client](./frontend-api.md)

### Database Client

Async PostgreSQL client wrapping asyncpg with domain-specific query methods.

```python { .api }
class PostgresDB:
    async def connect(self) -> None: ...
    async def get_legislation_by_jurisdiction(self, jurisdiction_name: str, limit: int = 10) -> List[Dict]: ...
    async def get_bill(self, jurisdiction: str, bill_number: str) -> Optional[Dict]: ...
    async def get_or_create_jurisdiction(self, name: str, type: str) -> Optional[str]: ...
```

[Database Client](./database.md)

## Environment Variables

### Backend

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection URL |
| `DATABASE_URL_PUBLIC` | Alt | Alternative PostgreSQL URL |
| `ZAI_API_KEY` | Yes | Z.ai API key for GLM-4.7 |
| `OPENROUTER_API_KEY` | No | OpenRouter fallback LLM + embeddings |
| `CLERK_JWKS_URL` | Yes | Clerk JWKS URL for JWT validation |
| `CLERK_JWT_ISSUER` | Yes | Clerk JWT issuer |
| `CLERK_TEST_JWKS_PATH` | Test | Path to test JWKS file |
| `CLERK_TEST_ISSUER` | Test | Test issuer override |
| `ENABLE_TEST_AUTH_BYPASS` | Test | Set "true" to bypass auth (test only) |
| `ADMIN_USER_IDS` | No | Comma-separated Clerk user IDs with admin access |
| `ADMIN_EMAIL_DOMAINS` | No | Comma-separated email domains with admin access |
| `CRON_SECRET` | Yes | Secret for cron endpoint authentication |
| `SENTRY_DSN` | No | Sentry DSN for error tracking |
| `ENVIRONMENT` | No | Deployment environment (default: "development") |
| `LLM_MODEL_RESEARCH` | No | Research LLM model (default: "glm-4.7") |
| `LLM_MODEL_GENERATE` | No | Generation LLM model (default: "glm-4.7") |
| `LLM_MODEL_REVIEW` | No | Review LLM model (default: "glm-4.7") |
| `LLM_MODEL_FALLBACK_OPENROUTER` | No | Fallback OpenRouter model |

### Frontend

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API base URL |
| `VITE_API_URL` | Alt | Vite fallback for API URL |
