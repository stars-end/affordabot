# System Health Monitoring API

Implement health check endpoints for the affordabot backend that report on database connectivity, LLM service availability, and per-jurisdiction scraper reachability.

## Capabilities

### Service health reporting

- `GET /health` returns a JSON object with keys `status`, `database`, and `zai_research`; `database` is `"connected"` when the database is live and `"disconnected"` otherwise [@test](./tests/test_health_root.py)
- `GET /health/jurisdictions` returns `{ "status": "success", "jurisdictions": { "<name>": "healthy" | "unhealthy" } }` for each registered jurisdiction by calling each scraper's `check_health()` method [@test](./tests/test_health_jurisdictions.py)
- `GET /health/analysis` returns `{ "status": "healthy" | "degraded" | "unhealthy", "details": { "llm": "connected" | "error", "search": "connected" | "unknown" } }` [@test](./tests/test_health_analysis.py)
- When the LLM API key validation fails, `GET /health/analysis` returns `status: "degraded"` (not `"healthy"`) [@test](./tests/test_health_degraded.py)

## Implementation

[@generates](./src/health_routes.py)

## API

```python { #api }
from fastapi import FastAPI

def register_health_routes(app: FastAPI) -> None:
    """Register /health, /health/jurisdictions, /health/analysis routes on app."""
    ...
```

## Dependencies { .dependencies }

### affordabot { .dependency }

Provides the `SCRAPERS` registry, `PostgresDB` client, `ZaiResearchService`, and `ZaiClient` with `validate_api_key()` used by the health check implementations.

[@satisfied-by](affordabot)
