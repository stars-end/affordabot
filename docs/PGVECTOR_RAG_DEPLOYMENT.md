# PgVector RAG Deployment Guide

## Overview
This guide covers deploying the updated Affordabot backend with PgVector RAG support to Railway dev environment.

## Prerequisites
- ✅ PR #43 merged (llm-common git dependency)
- ✅ Poetry lockfile generation fixed (system-git-client enabled)
- ✅ Backend dependencies include llm-common 0.4.1 with pgvector extras

## Railway Backend Service Configuration

### Service Settings
Navigate to Railway → Affordabot Project → backend service → Settings:

**Build Configuration:**
- **Root Directory:** `backend`
- **Build Command:** (leave default - Railway will use Poetry)
- **Start Command:** `poetry run uvicorn main:app --host 0.0.0.0 --port $PORT`

**Environment Variables:**
Required variables (should already be set):
```bash
DATABASE_URL=<your-pgvector-postgres-connection-string>
MINIO_URL=<minio-service-url>
MINIO_ACCESS_KEY=<from-minio-service>
MINIO_SECRET_KEY=<from-minio-service>
MINIO_BUCKET=affordabot-artifacts
MINIO_SECURE=true
```

Feature flag (set initially to false):
```bash
USE_PGVECTOR_RAG=false
```

### Deploy Initial Version
1. Trigger a redeploy of the backend service
2. Wait for build to complete (~2-3 minutes)
3. Check logs for successful startup

## Phase 1: Verify Legacy Path (USE_PGVECTOR_RAG=false)

### Access Railway Shell
```bash
railway shell --service backend
```

### Verify Environment
```bash
# Check Python and Poetry
python --version  # Should be 3.13+
poetry --version  # Should be 2.2.1+

# Verify llm-common is installed
poetry run python -c "from llm_common.retrieval import RetrievalBackend; print('✓ llm-common imported')"

# Check database connectivity
poetry run python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('$DATABASE_URL')); print('✓ DB connected')"
```

### Test Legacy Ingestion
```bash
cd /app/backend

# Run universal harvester (should use SupabasePgVectorBackend)
poetry run python scripts/cron/run_universal_harvester.py

# Check logs for:
# - "Using SupabasePgVectorBackend" or similar
# - Successful document processing
# - No errors
```

### Verify MinIO Storage
```bash
# List artifacts in MinIO bucket
poetry run python -c "
from services.storage.s3_storage import S3Storage
import asyncio
import os

async def check():
    storage = S3Storage(
        endpoint=os.getenv('MINIO_URL'),
        access_key=os.getenv('MINIO_ACCESS_KEY'),
        secret_key=os.getenv('MINIO_SECRET_KEY'),
        bucket_name=os.getenv('MINIO_BUCKET'),
        secure=os.getenv('MINIO_SECURE', 'true').lower() == 'true'
    )
    files = await storage.list_files()
    print(f'✓ Found {len(files)} files in MinIO')
    for f in files[:5]:
        print(f'  - {f}')

asyncio.run(check())
"
```

## Phase 2: Enable PgVector RAG (USE_PGVECTOR_RAG=true)

### Update Environment Variable
In Railway dashboard:
1. Go to backend service → Variables
2. Set `USE_PGVECTOR_RAG=true`
3. Redeploy the service (or it will auto-redeploy)

### Verify PgVector Backend is Active
```bash
railway shell --service backend
cd /app/backend

# Check which backend is being used
poetry run python -c "
import os
os.environ['USE_PGVECTOR_RAG'] = 'true'
from services.vector_backend_factory import create_vector_backend

backend = create_vector_backend()
print(f'✓ Using backend: {backend.__class__.__name__}')
print(f'  Expected: PgVectorBackend')
"
```

### Run Ingestion with PgVector
```bash
# Run universal harvester with PgVector backend
poetry run python scripts/cron/run_universal_harvester.py

# Expected output:
# - "Using PgVectorBackend" or similar factory message
# - Document chunks being processed
# - Embeddings being generated (4096 dimensions)
# - Data written to pgvector DB
```

### Verify Data in Database
```bash
# Check documents table
poetry run python -c "
import asyncpg
import asyncio
import os

async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Count documents
    count = await conn.fetchval('SELECT COUNT(*) FROM documents')
    print(f'✓ Documents in pgvector: {count}')
    
    # Check embedding dimensions
    if count > 0:
        sample = await conn.fetchrow('SELECT id, array_length(embedding, 1) as dims FROM documents LIMIT 1')
        print(f'  Sample document: {sample[\"id\"]}')
        print(f'  Embedding dimensions: {sample[\"dims\"]} (expected: 4096)')
    
    await conn.close()

asyncio.run(check())
"
```

### Test RAG Search
```bash
# Run a test search query
poetry run python -c "
import asyncio
import os
os.environ['USE_PGVECTOR_RAG'] = 'true'

from services.search_pipeline_service import SearchPipelineService
from services.vector_backend_factory import create_vector_backend

async def test_search():
    backend = create_vector_backend()
    
    # Mock embedding function for testing
    async def mock_embed(text):
        return [0.1] * 4096  # Dummy 4096-dim vector
    
    # Search for documents
    results = await backend.search(
        query_embedding=[0.1] * 4096,
        limit=5
    )
    
    print(f'✓ Search returned {len(results)} results')
    for i, result in enumerate(results[:3], 1):
        print(f'  {i}. Score: {result.get(\"score\", \"N/A\")}')

asyncio.run(test_search())
"
```

## Phase 3: Monitor and Validate

### Check Logs
```bash
# In Railway dashboard, monitor backend service logs for:
# - Successful embedding generation
# - PgVector backend initialization
# - No errors during ingestion/search
```

### Verify MinIO Artifacts
Access MinIO console:
- URL: `<minio-console-url>` (from Railway service)
- Credentials: From `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`
- Check `affordabot-artifacts` bucket for new files

### Performance Baseline
Monitor:
- Response times for search queries
- Memory usage during ingestion
- Database query performance

## Rollback Plan

If issues arise:

### Quick Rollback
```bash
# In Railway dashboard:
# 1. Set USE_PGVECTOR_RAG=false
# 2. Redeploy
# System reverts to SupabasePgVectorBackend immediately
```

### Data Cleanup (if needed)
```bash
railway shell --service backend

# Clear pgvector documents table
poetry run python -c "
import asyncpg
import asyncio
import os

async def cleanup():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    await conn.execute('TRUNCATE TABLE documents')
    print('✓ Documents table cleared')
    await conn.close()

asyncio.run(cleanup())
"
```

## Success Criteria

- ✅ Backend deploys successfully with Root Directory = `backend`
- ✅ Legacy path works (USE_PGVECTOR_RAG=false)
- ✅ PgVector backend activates correctly (USE_PGVECTOR_RAG=true)
- ✅ Documents are stored with 4096-dimensional embeddings
- ✅ Search queries return relevant results
- ✅ MinIO artifacts are created correctly
- ✅ No errors in Railway logs

## Next Steps

Once dev environment is stable:
1. Monitor for 24-48 hours
2. Compare performance vs. legacy backend
3. Plan staging rollout
4. Prepare production deployment

## Troubleshooting

### Issue: "llm-common not found"
**Solution:** Verify `poetry.lock` includes llm-common git dependency
```bash
grep llm-common poetry.lock
```

### Issue: "Embedding dimension mismatch"
**Solution:** Check embedding service configuration
```bash
# Verify embedding model returns 4096 dimensions
poetry run python -c "
from llm_common.embeddings import get_embedding_service
import asyncio

async def check():
    service = get_embedding_service()
    embedding = await service.embed('test')
    print(f'Embedding dimensions: {len(embedding)}')

asyncio.run(check())
"
```

### Issue: "Database connection failed"
**Solution:** Verify DATABASE_URL and network connectivity
```bash
echo $DATABASE_URL
# Should show pgvector connection string
```

### Issue: "MinIO access denied"
**Solution:** Verify MinIO credentials
```bash
echo $MINIO_ACCESS_KEY
echo $MINIO_SECRET_KEY
# Verify these match MinIO service configuration
```
