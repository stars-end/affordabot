# Legislation Retrieval API

Implement the REST API routes that expose stored, analyzed legislation to frontend consumers. Each endpoint reads from the database and formats the data for client consumption.

## Capabilities

### Legislation retrieval routes

- `GET /legislation/{jurisdiction}` returns `{ "jurisdiction": str, "count": int, "legislation": [...] }` with each bill including `bill_number`, `title`, `jurisdiction`, `status`, `impacts`, `total_impact_p50`, `sufficiency_state`, and `analysis_timestamp` [@test](./tests/test_list_legislation.py)
- `total_impact_p50` is computed as the sum of `p50` values from impacts where `p50 is not None`; it is `null` when no quantified impacts exist [@test](./tests/test_total_impact.py)
- `GET /legislation/{jurisdiction}/{bill_number}` returns the full bill record or a 404 when the bill is not found [@test](./tests/test_get_bill.py)
- Requesting a jurisdiction not in the scraper registry returns a 404 with an appropriate error message for both list and detail endpoints [@test](./tests/test_unknown_jurisdiction.py)

## Implementation

[@generates](./src/legislation_routes.py)

## API

```python { #api }
from fastapi import FastAPI
from db.postgres_client import PostgresDB

def register_legislation_routes(app: FastAPI, db: PostgresDB) -> None:
    """Register /legislation routes on app."""
    ...
```

## Dependencies { .dependencies }

### affordabot { .dependency }

Provides `SCRAPERS` registry for jurisdiction validation, `PostgresDB` with `get_legislation_by_jurisdiction()` and `get_bill()` methods, and the response format contract used across the frontend.

[@satisfied-by](affordabot)
