# Changelog

All notable changes to llm-common will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2025-12-09

### Added

- **Generic PgVectorBackend for Railway Postgres** ([bd-nxvn](https://github.com/stars-end/prime-radiant-ai))
  - New `PgVectorBackend` class using SQLAlchemy + asyncpg for direct DATABASE_URL connection
  - Works with Railway Postgres, self-hosted Postgres, or any pgvector-enabled database
  - Native SQL with pgvector operators (`<->` for cosine similarity)
  - Factory function `create_pg_backend()` for easy instantiation
  - Full async/await support with connection pooling
  - Comprehensive mock-based test suite (500+ lines, 20+ test cases)
  - Optional dependencies via `llm-common[pgvector]` extras

- **Migration Documentation**
  - New `docs/LLM_COMMON_PG_BACKEND_MIGRATION.md` (531 lines)
    - Complete migration guide from SupabasePgVectorBackend to PgVectorBackend
    - Reference SQL schema with HNSW index setup
    - Installation instructions and code examples
    - Full RAGService implementation example
    - Docker Compose setup for local testing
    - Troubleshooting guide and performance tuning
  - Updated `docs/LLM_COMMON_WORKSTREAMS/INTEGRATION_AND_RETRIEVAL.md`
    - Now recommends PgVectorBackend as default implementation
    - Documents Railway Postgres as recommended production backend
    - Clarifies when to consider alternative backends (Qdrant, etc.)

- **Examples**
  - New `railway_pgvector_backend_example()` in `examples/retrieval_usage.py`
    - Demonstrates factory pattern usage
    - Shows ingestion with `upsert()` method
    - Illustrates search with metadata filters
    - Documents production setup steps

### Changed

- **Optional Dependencies**
  - Added `sqlalchemy ^2.0.0`, `asyncpg ^0.29.0`, `pgvector ^0.3.0` as optional deps
  - Install with `poetry add "llm-common[pgvector]"` for pgvector support
  - Graceful import fallback when pgvector extras not installed

- **Backend Exports**
  - `llm_common.retrieval.backends.__init__.py` now exports:
    - `PgVectorBackend` (recommended)
    - `create_pg_backend()` (factory)
    - `SupabasePgVectorBackend` (legacy)
  - Falls back to legacy exports only if pgvector dependencies unavailable

### Deprecated

- **SupabasePgVectorBackend** is now marked as legacy/deprecated
  - Still available for backwards compatibility
  - Recommend migrating to `PgVectorBackend` for new projects
  - See migration guide at `docs/LLM_COMMON_PG_BACKEND_MIGRATION.md`

### Technical Details

**PgVectorBackend Features:**
- Direct DATABASE_URL connection (no vendor-specific client libraries)
- Native pgvector operators for optimal performance
- UPSERT support for safe re-ingestion (`INSERT ... ON CONFLICT DO UPDATE`)
- JSONB metadata filtering
- Configurable column names for flexible schema support
- Health check for pgvector extension availability
- Context manager support for resource cleanup

**Testing Strategy:**
- Mock-based tests for CI independence (no Railway access required)
- Optional local Postgres testing via Docker Compose
- 100% test pass rate maintained (66/66 tests passing)

**Integration Status:**
- Ready for Prime Radiant and Affordabot integration
- Railway pgvector services provisioned
- Each app owns its own database tables
- Feature-Key: bd-nxvn (Prime Radiant epic)

### Migration Path

For projects using SupabasePgVectorBackend:

```python
# Before (Supabase)
from supabase import create_client
from llm_common.retrieval.backends import SupabasePgVectorBackend

supabase = create_client(url, key)
backend = SupabasePgVectorBackend(
    supabase_client=supabase,
    table="document_chunks",
    embed_fn=embed_function,
    rpc_function="match_document_chunks"
)

# After (Railway Postgres)
import os
from llm_common.retrieval.backends import create_pg_backend

backend = create_pg_backend(
    database_url=os.getenv("DATABASE_URL"),
    table="document_chunks",
    embed_fn=embed_function,
    vector_dimensions=1536
)
```

See full migration guide: `docs/LLM_COMMON_PG_BACKEND_MIGRATION.md`

---

## [0.3.0] - 2025-12-08

### Added

- Initial retrieval backend implementation with SupabasePgVectorBackend
- Core abstractions: `RetrievalBackend`, `RetrievedChunk`
- LLM client implementations for z.ai and OpenRouter
- Web search with caching
- Type-safe Pydantic models
- Comprehensive test suite (66/66 passing)

### Documentation

- `docs/LLM_COMMON_WORKSTREAMS/INTEGRATION_AND_RETRIEVAL.md`
- `DEVELOPMENT_STATUS.md` - Integration phase guidelines
- `IMPLEMENTATION_STATUS.md` - Feature tracking
- `CLAUDE.md` - Agent guidelines

---

[0.4.0]: https://github.com/stars-end/llm-common/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/stars-end/llm-common/releases/tag/v0.3.0
