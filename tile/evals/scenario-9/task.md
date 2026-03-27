# Pipeline Run Observability

Implement the database operations and admin API routes that record and expose structured pipeline run lifecycle events, enabling step-level debugging of the affordabot analysis pipeline.

## Capabilities

### Pipeline run tracking

- `create_pipeline_run(run_id, bill_id, jurisdiction)` inserts a new pipeline run record with status `"running"` and returns the run_id [@test](./tests/test_create_run.py)
- `complete_pipeline_run(run_id, result)` updates the run record to status `"completed"` and stores the result payload, returning `True` on success [@test](./tests/test_complete_run.py)
- `fail_pipeline_run(run_id, error)` updates the run record to status `"failed"` and records the error string, returning `True` on success [@test](./tests/test_fail_run.py)
- `GET /api/pipeline-runs/{run_id}` returns the full run record including status, result/error, and all associated pipeline steps [@test](./tests/test_get_run.py)

## Implementation

[@generates](./src/pipeline_observability.py)

## API

```python { #api }
from fastapi import APIRouter
from db.postgres_client import PostgresDB
from typing import Any, Dict, Optional

# Database methods (on PostgresDB)
async def create_pipeline_run(run_id: str, bill_id: str, jurisdiction: str) -> str: ...
async def complete_pipeline_run(run_id: str, result: Dict[str, Any]) -> bool: ...
async def fail_pipeline_run(run_id: str, error: str) -> bool: ...

# Admin API routes
def create_observability_router(db: PostgresDB) -> APIRouter:
    """Return APIRouter with /pipeline-runs and /runs/{run_id}/steps routes."""
    ...
```

## Dependencies { .dependencies }

### affordabot { .dependency }

Provides `PostgresDB` with `create_pipeline_run()`, `complete_pipeline_run()`, and `fail_pipeline_run()` methods, `GlassBoxService` for step-level data, and the `/api/pipeline-runs` admin route pattern.

[@satisfied-by](affordabot)
