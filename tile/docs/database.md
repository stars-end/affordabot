# AffordaBot Database Client

**Location:** `backend/db/postgres_client.py`

Async PostgreSQL client wrapping `asyncpg` with domain-specific query methods. Handles connection pool management and Railway SSL auto-detection.

## Import

```python
from db.postgres_client import PostgresDB
```

## PostgresDB

```python { .api }
class PostgresDB:
    def __init__(self, database_url: Optional[str] = None) -> None:
        # database_url: override; if not provided, reads DATABASE_URL_PUBLIC or DATABASE_URL env
        ...

    async def connect(self) -> None:
        # Create asyncpg connection pool.
        # Auto-detects SSL: disables SSL for Railway internal URLs
        # (*.railway.internal, *.proxy.rlwy.net), uses ssl="require" otherwise.
        # Raises: ValueError if DATABASE_URL not set
        ...

    async def close(self) -> None:
        # Close the connection pool
        ...

    def is_connected(self) -> bool:
        # Returns True if pool is open
        ...
```

## Low-Level Query Methods

These are building blocks used by higher-level domain methods and internal admin code.

```python { .api }
    async def _execute(self, query: str, *args) -> str:
        # Execute a query (INSERT/UPDATE/DELETE), auto-connects if needed
        # Returns asyncpg status string
        ...

    async def _fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        # Fetch a single row, auto-connects if needed
        # Returns asyncpg.Record (dict-like) or None
        ...

    async def _fetch(self, query: str, *args) -> List[asyncpg.Record]:
        # Fetch multiple rows, auto-connects if needed
        # Returns list of asyncpg.Record objects (each is dict-like)
        ...
```

## Jurisdiction Methods

```python { .api }
    async def get_jurisdiction_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        # Get jurisdiction config by exact name
        ...

    async def get_or_create_jurisdiction(self, name: str, type: str) -> Optional[str]:
        # Get jurisdiction UUID by name, creating if not found.
        # type: "city" | "county" | "state" (normalizes "municipality" -> "city")
        # Returns: UUID string or None on error
        ...
```

## Source Methods

```python { .api }
    async def get_sources(
        self, jurisdiction_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        # List sources, optionally filtered by jurisdiction UUID
        ...

    async def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        # Get a single source by UUID
        ...

    async def create_source(self, data: dict) -> Dict[str, Any]:
        # Create a new source record
        # data: dict from SourceCreate.model_dump(exclude_none=True)
        ...

    async def update_source(self, source_id: str, data: dict) -> Dict[str, Any]:
        # Update an existing source record
        # data: dict from SourceUpdate.model_dump(exclude_none=True)
        ...

    async def delete_source(self, source_id: str) -> None:
        # Delete a source by UUID
        ...

    async def get_or_create_source(
        self, jurisdiction_id: str, name: str, type: str, url: str = None
    ) -> Optional[str]:
        # Get source UUID by URL (preferred) or name, creating if not found.
        # If url is None, a stable placeholder URL is synthesized.
        # Returns: source UUID string, or None on error
        ...
```

## Legislation Methods (Write)

```python { .api }
    async def store_legislation(
        self, jurisdiction_id: str, bill_data: Dict[str, Any]
    ) -> Optional[str]:
        # Insert or update a legislation record.
        # bill_data keys: bill_number (required), title, text, status, introduced_date,
        #   raw_html, sufficiency_state, insufficiency_reason, quantification_eligible,
        #   total_impact_p50
        # Returns: legislation UUID string, or None on error
        ...

    async def create_legislation(
        self, jurisdiction_id: str, bill_data: Dict[str, Any]
    ) -> Optional[str]:
        # Alias for store_legislation
        ...

    async def store_impacts(
        self, legislation_id: str, impacts: List[Dict[str, Any]]
    ) -> bool:
        # Replace all impacts for a legislation record (delete + re-insert in a transaction).
        # Each impact dict keys: impact_number, relevant_clause, impact_description,
        #   evidence (list), chain_of_causality, confidence_score, p10, p25, p50, p75, p90,
        #   sufficiency_state, quantification_eligible, numeric_basis, estimate_method
        # Sets analysis_status = 'completed' on the legislation record.
        # Returns: True on success, False on error
        ...
```

## Pipeline Run Methods

```python { .api }
    async def create_pipeline_run(
        self,
        bill_id: str,
        jurisdiction: str,
        models: Dict[str, str],
        trigger_source: str = "manual",
    ) -> Optional[str]:
        # Create a pipeline run record.
        # models keys: "research", "generate", "review"
        # trigger_source: "manual" | "prefix:<label>" | "fixture:<label>"
        # Returns: pipeline run UUID string, or None on error
        ...

    async def complete_pipeline_run(
        self, run_id: str, result: Dict[str, Any]
    ) -> bool:
        # Mark a pipeline run as completed with result data.
        # Returns: True on success, False on error
        ...

    async def fail_pipeline_run(self, run_id: str, error: str) -> bool:
        # Mark a pipeline run as failed with an error message.
        # Returns: True on success, False on error
        ...
```

## Admin Task Methods

```python { .api }
    async def create_admin_task(
        self,
        task_id: str,
        task_type: str,
        jurisdiction: str,
        status: str = "queued",
        config: Dict = None,
    ) -> bool:
        # Create an admin task record.
        # Returns: True on success, False on error
        ...

    async def update_admin_task(
        self,
        task_id: str,
        status: str,
        result: Dict = None,
        error: str = None,
    ) -> bool:
        # Update an admin task's status, optional result and error.
        # Returns: True on success, False on error
        ...

    async def get_admin_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        # Get an admin task by ID.
        # Returns: task dict or None if not found
        ...
```

## Scrape History Methods

```python { .api }
    async def log_scrape_history(self, entry: Dict[str, Any]) -> bool:
        # Insert a scrape history record.
        # entry keys: jurisdiction (required), status (required), bills_found,
        #   bills_new, task_id, error_message, notes
        # Returns: True on success, False on error
        ...

    async def create_scrape_history(self, **kwargs) -> bool:
        # Wrapper for log_scrape_history accepting keyword arguments.
        # Returns: True on success, False on error
        ...

    async def get_latest_scrape_for_bill(
        self, jurisdiction: str, bill_number: str
    ) -> Optional[Dict[str, Any]]:
        # Find the most recent raw_scrapes record matching the given bill.
        # Matches by jurisdiction name and metadata.bill_number JSONB field.
        # Returns: raw scrape dict or None
        ...
```

## RAG / Vector Methods

```python { .api }
    async def create_raw_scrape(
        self, scrape_record: Dict[str, Any]
    ) -> Optional[str]:
        # Insert a raw_scrapes record.
        # scrape_record keys: source_id, content_hash, content_type, data (dict),
        #   url, metadata (dict), storage_uri (optional), document_id (optional)
        # Returns: raw scrape UUID string, or None on error
        ...

    async def get_vector_stats(self, document_id: str) -> Dict[str, Any]:
        # Get vector chunk count for a document.
        # Returns: {"chunk_count": int}
        ...
```

## Model Config Methods

```python { .api }
    async def get_model_configs(self) -> List[Dict[str, Any]]:
        # Get all model configurations ordered by priority.
        # Returns: list of model config dicts (provider, model_name, use_case, priority, enabled)
        ...

    async def update_model_config(
        self,
        provider: str,
        model_name: str,
        use_case: str,
        priority: int,
        enabled: bool,
    ) -> bool:
        # Upsert a model configuration (INSERT ... ON CONFLICT DO UPDATE).
        # Returns: True on success, False on error
        ...
```

## System Prompt Methods

```python { .api }
    async def get_system_prompt(
        self, prompt_type: str
    ) -> Optional[Dict[str, Any]]:
        # Get active system prompt by type (e.g., "legislation_analysis", "discovery_query_generator")
        # Returns dict with keys: id, prompt_type, system_prompt, description, version, is_active
        ...

    async def update_system_prompt(
        self,
        prompt_type: str,
        system_prompt: str,
        description: str = None,
        user_id: str = "admin",
    ) -> Optional[int]:
        # Create or update a system prompt (deactivates existing, inserts new version).
        # user_id: Clerk user ID recorded as created_by (defaults to "admin")
        # Returns: new version number (int), or None on failure
        ...
```

## Analysis History Methods

```python { .api }
    async def get_analysis_history(
        self,
        jurisdiction: str = None,
        bill_id: str = None,
        step: str = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        # Get analysis history with optional filters.
        # Returns: list of analysis_history records ordered by created_at DESC
        ...
```

## Template Review Methods

```python { .api }
    async def get_pending_reviews(self) -> List[Dict[str, Any]]:
        # Get all template_reviews records with status = 'pending'.
        # Returns: list of review dicts
        ...

    async def update_review_status(self, review_id: str, status: str) -> bool:
        # Update review status (e.g., 'approved', 'rejected').
        # Returns: True on success, False on error
        ...

    async def create_template_review(
        self, review_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        # Insert a new template_reviews record.
        # review_data: dict matching the template_reviews table columns
        # Returns: created review dict, or None on error
        ...
```

## Legislation Methods (Read)

```python { .api }
    async def get_legislation_by_jurisdiction(
        self, jurisdiction_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        # Get legislation records with impact analysis for a jurisdiction.
        # Each record includes: bill_number, title, status, jurisdiction_id,
        #   impacts (list), sufficiency_state, insufficiency_reason,
        #   quantification_eligible, created_at
        ...

    async def get_bill(
        self, jurisdiction: str, bill_number: str
    ) -> Optional[Dict[str, Any]]:
        # Get a specific bill by jurisdiction and bill number.
        # Returns full bill dict or None if not found
        ...
```

## Database Schema Overview

Key tables (from `db/schema.sql`):

| Table | Description |
|-------|-------------|
| `jurisdictions` | Registered jurisdictions (id, name, type) |
| `sources` | Data source URLs per jurisdiction |
| `raw_scrapes` | Raw scraped content records |
| `legislation` | Processed legislation with analysis |
| `system_prompts` | LLM system prompts (versioned) |
| `document_chunks` | Vector-indexed document chunks for RAG |
| `pipeline_runs` | Pipeline execution records |

## Usage Example

```python
import asyncio
from db.postgres_client import PostgresDB

async def main():
    db = PostgresDB()
    await db.connect()

    # Get or create a jurisdiction
    jur_id = await db.get_or_create_jurisdiction("San Jose", "city")

    # Fetch legislation
    bills = await db.get_legislation_by_jurisdiction("San Jose", limit=5)
    for bill in bills:
        print(bill["bill_number"], bill["title"])

    # Fetch a specific bill
    bill = await db.get_bill("california", "AB-1234")

    # Direct SQL query
    rows = await db._fetch(
        "SELECT * FROM jurisdictions WHERE type = $1", "city"
    )

    await db.close()

asyncio.run(main())
```
