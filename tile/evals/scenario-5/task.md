# PgVector Semantic Retrieval Backend

Implement a PostgreSQL-backed vector retrieval component that embeds a query string and searches for similar document chunks using pgvector, supporting metadata filtering by jurisdiction.

## Capabilities

### Embedder-backed semantic retrieval

- `retrieve(query, top_k)` calls the injected embedding function with the query string, then queries the vector table and returns a list of `RetrievedChunk` objects [@test](./tests/test_retrieve_basic.py)
- Results are limited to `top_k` items [@test](./tests/test_top_k.py)
- When a `filters` dict with a `jurisdiction` key is passed, only chunks matching that jurisdiction are returned [@test](./tests/test_jurisdiction_filter.py)
- When no `embedding_fn` is provided and `fail_closed=True`, calling `retrieve()` raises an error rather than returning empty results [@test](./tests/test_fail_closed.py)

## Implementation

[@generates](./src/pgvector_backend.py)

## API

```python { #api }
from typing import List, Dict, Any, Optional, Callable, Awaitable
from llm_common.retrieval import RetrievalBackend, RetrievedChunk

class LocalPgVectorBackend(RetrievalBackend):
    def __init__(
        self,
        table_name: str = "document_chunks",
        postgres_client=None,
        embedding_fn: Optional[Callable[[str], Awaitable[List[float]]]] = None,
        fail_closed: bool = True,
    ) -> None: ...

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]: ...
```

## Dependencies { .dependencies }

### affordabot { .dependency }

Provides the `LocalPgVectorBackend` implementation pattern, `RetrievalBackend` interface, `RetrievedChunk` model, and the fail-closed error handling convention used across the retrieval layer.

[@satisfied-by](affordabot)
