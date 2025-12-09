# llm-common pgvector Backend Migration Guide

## Overview

This guide helps Prime Radiant and Affordabot migrate from Supabase-specific retrieval to the generic PgVectorBackend that works with Railway Postgres.

**Feature-Key**: bd-nxvn (Prime Radiant epic)
**Version**: llm-common 0.4.0+
**Status**: Ready for app integration

## What Changed

### Before: SupabasePgVectorBackend
- Required Supabase client library
- Used Supabase RPC functions for similarity search
- Coupled to Supabase infrastructure

### After: PgVectorBackend
- Uses standard PostgreSQL with pgvector extension
- Direct DATABASE_URL connection via SQLAlchemy + asyncpg
- Works with Railway Postgres, self-hosted Postgres, or any pgvector-enabled DB
- Native SQL with pgvector operators

## Installation

### 1. Install llm-common with pgvector extras

```bash
# In your backend directory
cd backend/

# Poetry
poetry add "llm-common[pgvector]"

# Or update pyproject.toml manually:
[tool.poetry.dependencies]
llm-common = {version = "^0.4.0", extras = ["pgvector"]}

# Then install
poetry install
```

This installs:
- `llm-common` core
- `sqlalchemy` ^2.0.0
- `asyncpg` ^0.29.0
- `pgvector` ^0.3.0

## Schema Setup

### 2. Get Railway DATABASE_URL

```bash
# From your app repo (prime-radiant-ai or affordabot)
railway variables -s pgvector

# Copy DATABASE_URL or DATABASE_URL_PRIVATE
# Format: postgresql://user:password@host:port/database
```

Add to your backend `.env`:
```bash
DATABASE_URL="postgresql+asyncpg://user:password@host:port/database"
```

**Note**: For asyncpg, replace `postgresql://` with `postgresql+asyncpg://`

### 3. Create Your Table Schema

**Important**: Each app creates its own table(s) in its own Railway pgvector database. The schema below is a reference - customize as needed for your app.

#### Reference Schema

```sql
-- Enable pgvector extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create document chunks table
CREATE TABLE IF NOT EXISTS document_chunks (
    -- Primary key (UUID, auto-generated string, or custom ID)
    id TEXT PRIMARY KEY,

    -- Required fields
    content TEXT NOT NULL,              -- The actual text content
    source TEXT NOT NULL,               -- Source identifier (file path, URL, doc ID)

    -- Metadata (stored as JSONB for flexible querying)
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Vector embedding
    -- Adjust dimensions based on your embedding model:
    -- - OpenAI text-embedding-3-small: 1536
    -- - OpenAI text-embedding-3-large: 3072
    -- - Sentence transformers: 384, 768, 1024, etc.
    embedding vector(1536) NOT NULL,

    -- Timestamps (optional but recommended)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create HNSW index for fast similarity search
-- HNSW is faster than IVFFlat for most use cases
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- Optional: Index on metadata for filtering
CREATE INDEX IF NOT EXISTS document_chunks_metadata_idx
ON document_chunks USING gin (metadata);

-- Optional: Index on source for lookups
CREATE INDEX IF NOT EXISTS document_chunks_source_idx
ON document_chunks (source);
```

#### Running the Schema

**Option A: Direct psql**
```bash
# Get DATABASE_URL from Railway
railway variables -s pgvector

# Connect and run schema
railway run -s pgvector -- psql "$DATABASE_URL" -f schema.sql
```

**Option B: From your backend service**
```python
# backend/scripts/init_db.py
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def init_schema():
    engine = create_async_engine(os.getenv("DATABASE_URL"))

    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE EXTENSION IF NOT EXISTS vector;

            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                metadata JSONB DEFAULT '{}'::jsonb,
                embedding vector(1536) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
            ON document_chunks USING hnsw (embedding vector_cosine_ops);
        """))

    await engine.dispose()
    print("✅ Schema created successfully")

if __name__ == "__main__":
    asyncio.run(init_schema())
```

### 4. Customize for Your App

**Prime Radiant**:
- May want separate tables per document type (e.g., `etf_descriptions`, `financial_docs`)
- Metadata might include: `{symbol, sector, doc_type, date}`
- Consider partitioning by date for large datasets

**Affordabot**:
- May want `affordabot_chunks` or split by content type
- Metadata might include: `{user_id, category, tags, scrape_date}`
- Consider tenant isolation via metadata filters

**Table naming**: Choose names that make sense for your app. PgVectorBackend is flexible - just pass the table name to the constructor.

## Code Migration

### 5. Update Your Backend Code

#### Old Code (SupabasePgVectorBackend)

```python
from supabase import create_client
from llm_common.retrieval.backends import SupabasePgVectorBackend

supabase = create_client(url, key)

backend = SupabasePgVectorBackend(
    supabase_client=supabase,
    table="document_chunks",
    embed_fn=embed_function,
    rpc_function="match_document_chunks"  # Supabase RPC
)

results = await backend.retrieve("query", top_k=5)
```

#### New Code (PgVectorBackend)

```python
import os
from llm_common.retrieval.backends import create_pg_backend

backend = create_pg_backend(
    database_url=os.getenv("DATABASE_URL"),
    table="document_chunks",
    embed_fn=embed_function,
    vector_dimensions=1536  # Match your model
)

results = await backend.retrieve("query", top_k=5)
```

### 6. Update Ingestion Code

The new backend includes `upsert()` for batch ingestion:

```python
# Ingest documents
chunks = [
    {
        "content": "Prime Radiant is a financial advisor platform...",
        "source": "docs/intro.md",
        "metadata": {"section": "overview", "date": "2025-01-01"},
        "chunk_id": "doc_001"  # Optional, will be generated if omitted
    },
    {
        "content": "Affordabot helps with budgeting...",
        "source": "docs/features.md",
        "metadata": {"section": "features"},
    }
]

await backend.upsert(chunks)
```

**Notes**:
- Embeddings are generated automatically via `embed_fn`
- `chunk_id` is optional (provide your own or let DB generate)
- `upsert` does INSERT ... ON CONFLICT DO UPDATE (safe for re-ingestion)

### 7. Update Search Code

Search API is mostly unchanged:

```python
# Basic search
results = await backend.retrieve(
    query="What is Prime Radiant?",
    top_k=5
)

# With filters and minimum score
results = await backend.retrieve(
    query="financial planning",
    top_k=10,
    min_score=0.7,  # Only results with similarity > 0.7
    filters={"section": "overview"}  # JSONB metadata filter
)

# Process results
for chunk in results:
    print(f"Score: {chunk.score:.3f}")
    print(f"Source: {chunk.source}")
    print(f"Content: {chunk.content[:100]}...")
    print(f"Metadata: {chunk.metadata}")
```

### 8. Full Example Service

```python
# backend/services/rag_service.py
import os
from typing import List
from llm_common.retrieval.backends import create_pg_backend
from openai import AsyncOpenAI

class RAGService:
    def __init__(self):
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.backend = None

    async def initialize(self):
        """Initialize the pgvector backend."""
        self.backend = create_pg_backend(
            database_url=os.getenv("DATABASE_URL"),
            table="document_chunks",
            embed_fn=self._embed_text,
            vector_dimensions=1536
        )

        # Verify connection
        if not await self.backend.health_check():
            raise RuntimeError("Failed to connect to pgvector database")

    async def _embed_text(self, text: str) -> List[float]:
        """Generate embeddings using OpenAI."""
        response = await self.openai.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    async def ingest_documents(self, documents: List[dict]):
        """Ingest documents into vector store."""
        await self.backend.upsert(documents)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: dict = None
    ) -> List[dict]:
        """Search for relevant documents."""
        results = await self.backend.retrieve(
            query=query,
            top_k=top_k,
            filters=filters
        )

        return [
            {
                "content": chunk.content,
                "score": chunk.score,
                "source": chunk.source,
                "metadata": chunk.metadata
            }
            for chunk in results
        ]

    async def cleanup(self):
        """Clean up resources."""
        if self.backend:
            await self.backend.close()

# Usage in FastAPI
from fastapi import FastAPI

app = FastAPI()
rag_service = RAGService()

@app.on_event("startup")
async def startup():
    await rag_service.initialize()

@app.on_event("shutdown")
async def shutdown():
    await rag_service.cleanup()

@app.post("/search")
async def search(query: str, top_k: int = 5):
    return await rag_service.search(query, top_k)
```

## Testing

### Local Testing (Optional)

For integration testing against a real pgvector database:

#### Docker Compose Setup

```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: testdb
      POSTGRES_USER: testuser
      POSTGRES_PASSWORD: testpass
    ports:
      - "5432:5432"
    volumes:
      - pgvector_data:/var/lib/postgresql/data

volumes:
  pgvector_data:
```

```bash
# Start local pgvector
docker-compose up -d

# Test connection
export DATABASE_URL="postgresql+asyncpg://testuser:testpass@localhost:5432/testdb"
python -c "from llm_common.retrieval.backends import create_pg_backend; print('OK')"
```

### CI Testing

llm-common's CI uses mocks - no live database required. See `tests/retrieval/backends/test_pg_backend.py`.

## Troubleshooting

### Error: "pgvector dependencies not installed"

```bash
# Install with extras
poetry add "llm-common[pgvector]"

# Or manually:
poetry add sqlalchemy asyncpg pgvector
```

### Error: "extension 'vector' does not exist"

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
```

Run via Railway:
```bash
railway run -s pgvector -- psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Error: "operator does not exist: vector <-> vector"

Ensure you're using the pgvector-enabled Postgres image. Railway's pgvector service template should have this pre-configured.

### Slow Queries

```sql
-- Check if index exists
SELECT indexname FROM pg_indexes WHERE tablename = 'document_chunks';

-- If missing, create HNSW index
CREATE INDEX document_chunks_embedding_idx
ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

### Connection Pool Exhaustion

Adjust pool settings:
```python
backend = PgVectorBackend(
    database_url=os.getenv("DATABASE_URL"),
    table="document_chunks",
    embed_fn=embed_function,
    vector_dimensions=1536,
    pool_size=10,      # Default: 5
    max_overflow=20    # Default: 10
)
```

## Migration Checklist

**For Prime Radiant**:
- [ ] Install llm-common[pgvector] in backend
- [ ] Get DATABASE_URL from Railway pgvector service
- [ ] Create document_chunks table (or custom schema)
- [ ] Create HNSW index on embedding column
- [ ] Update ingestion code to use PgVectorBackend
- [ ] Update search endpoints to use PgVectorBackend
- [ ] Test against Railway dev environment
- [ ] Deploy to production

**For Affordabot**:
- [ ] Install llm-common[pgvector] in backend
- [ ] Get DATABASE_URL from Railway pgvector service
- [ ] Create affordabot_chunks table (or custom schema)
- [ ] Create HNSW index on embedding column
- [ ] Update RAG ingestion to use PgVectorBackend
- [ ] Update search logic to use PgVectorBackend
- [ ] Test scraping + RAG flow
- [ ] Deploy to production

## Performance Tuning

### Index Selection

**HNSW** (Hierarchical Navigable Small World):
- Faster queries, slower inserts
- Better for read-heavy workloads
- Recommended for production

```sql
CREATE INDEX USING hnsw (embedding vector_cosine_ops);
```

**IVFFlat** (Inverted File with Flat compression):
- Faster inserts, slower queries
- Better for write-heavy workloads

```sql
CREATE INDEX USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);  -- Tune based on dataset size
```

### Distance Operators

- `<->` Cosine distance (recommended)
- `<#>` Inner product
- `<+>` L1 distance
- `<=>` L2 distance

### Query Optimization

```python
# Pre-filter with metadata before vector search
results = await backend.retrieve(
    query="financial planning",
    top_k=10,
    filters={"doc_type": "report", "year": "2024"}  # Reduces search space
)
```

## References

- **llm-common docs**: `docs/LLM_COMMON_WORKSTREAMS/INTEGRATION_AND_RETRIEVAL.md`
- **Example code**: `examples/retrieval_usage.py`
- **Tests**: `tests/retrieval/backends/test_pg_backend.py`
- **pgvector docs**: https://github.com/pgvector/pgvector
- **Railway guide**: https://docs.railway.app/databases/postgresql

## Support

**Questions about llm-common pgvector backend**:
- Feature-Key: bd-nxvn (Prime Radiant epic)
- Implementation: `llm_common/retrieval/backends/pg_backend.py`
- Tests: `tests/retrieval/backends/test_pg_backend.py`

**Questions about Railway Postgres setup**:
- Contact coordinator agent
- Railway docs: https://docs.railway.app/

**Questions about app-specific integration**:
- Prime Radiant agent
- Affordabot agent
