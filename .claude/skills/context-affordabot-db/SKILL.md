---
name: context-affordabot-db
description: Affordabot database schema, scraping tables, and RAG validation queries. Use when working with jurisdictions, sources, documents, embeddings, or mentions "sources table", "raw_scrapes", "document embeddings", "legislation", "pipeline_runs".
tags: [database, schema, affordabot, postgres, rag]
allowed-tools:
  - Bash(railway:*)
  - Read
---

# Affordabot Database

Affordabot database schema for legislation scraping and RAG pipeline.

## Purpose

Quick reference for Affordabot's scraping and RAG database without reading migration files.

## When to Use This Skill

**Trigger phrases:**
- "check sources"
- "raw_scrapes"
- "document embeddings"
- "legislation data"
- "pipeline runs"
- "orphaned scrapes"
- "stale embeddings"

**Use when:**
- Querying scraping pipeline data
- Validating RAG embeddings
- Debugging legislation processing
- Checking pipeline job status

## Key Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| **jurisdictions** | Cities/counties/states | id (uuid), name, type (city/county/state), api_type |
| **sources** | Scrape targets | id, jurisdiction_id, status (active/inactive), url, last_scraped_at |
| **raw_scrapes** | Scraped content | id, source_id, content_hash, data (jsonb), created_at |
| **document_chunks** | RAG embeddings | id, document_id, embedding (vector), content |
| **legislation** | Processed bills | id, jurisdiction_id, bill_number, title, status, analysis_status |
| **impacts** | Analysis results | id, legislation_id, impact_number, confidence_score, evidence |
| **pipeline_runs** | Job tracking | id, bill_id, jurisdiction, status, started_at, completed_at |
| **admin_tasks** | Async jobs | id, task_type, status, config |

## Database Connection

**Framework:** asyncpg (direct)
**Service:** `affordabot-pgvector` (Railway)
**Migration:** Raw SQL files

```python
# From backend/db/postgres_client.py
from db.postgres_client import PostgresDB

db = PostgresDB()
await db.connect()
result = await db.get_jurisdiction_by_name("San Jose")
```

## Migration Command

```bash
# Affordabot uses raw SQL migrations
cp backend/migrations/006_new.sql /tmp/migrate.sql
railway run --service affordabot-pgvector -- psql "$DATABASE_URL" -f /tmp/migrate.sql
```

## Common Validation Queries

### Sources needing scrape
```sql
SELECT id, name, type, last_scraped_at
FROM sources
WHERE status = 'active'
AND (last_scraped_at IS NULL OR last_scraped_at < NOW() - INTERVAL '24 hours')
ORDER BY last_scraped_at NULLS FIRST;
```

### Documents without embeddings (broken RAG)
```sql
SELECT id, title, created_at
FROM documents
WHERE embedding IS NULL
LIMIT 50;
```

### Stale embeddings (content changed after embedding)
```sql
SELECT d.id, d.title, d.updated_at, dc.created_at
FROM documents d
JOIN document_chunks dc ON d.id = dc.document_id
WHERE d.updated_at > dc.created_at;
```

### Orphaned raw_scrapes (source deleted)
```sql
SELECT rs.id, rs.created_at, rs.url
FROM raw_scrapes rs
LEFT JOIN sources s ON rs.source_id = s.id
WHERE s.id IS NULL;
```

### Jurisdictions by type
```sql
SELECT name, type, api_type
FROM jurisdictions
WHERE type = 'city'
ORDER BY name;
```

### Latest scrape for a bill
```sql
SELECT rs.id, rs.url, rs.created_at, (rs.metadata->>'bill_number')::text as bill_number
FROM raw_scrapes rs
JOIN sources s ON rs.source_id = s.id
WHERE s.jurisdiction_id = (SELECT id FROM jurisdictions WHERE name = 'San Jose')
AND (rs.metadata->>'bill_number')::text = '2024-001'
ORDER BY rs.created_at DESC
LIMIT 1;
```

### Pipeline run status
```sql
SELECT id, bill_id, status, started_at, completed_at
FROM pipeline_runs
WHERE status != 'completed'
ORDER BY started_at DESC;
```

### Failed admin tasks
```sql
SELECT id, task_type, error_message, created_at
FROM admin_tasks
WHERE status = 'failed'
ORDER BY created_at DESC
LIMIT 20;
```

## Schema Relationships

```
jurisdictions (1) ----< (N) sources (1) ----< (N) raw_scrapes
                                              |
                                              v
                                          documents (1) ----< (N) document_chunks

jurisdictions (1) ----< (N) legislation (1) ----< (N) impacts
```

## Best Practices

### Do

✅ Check sources.status before scraping
✅ Use content_hash for deduplication
✅ Validate JSONB metadata before query
✅ Use JOINs for jurisdiction lookups
✅ Check analysis_status before re-processing

### Don't

❌ Don't scrape inactive sources
❌ Don't DELETE raw_scrapes (keep for audit)
❌ Don't assume embeddings exist
❌ Don't run pipeline without creating admin_task

## What This Skill Does

✅ Affordabot table schema reference
✅ Scraping pipeline validation queries
✅ RAG embedding integrity checks
✅ Legislation/impacts query patterns

## What This Skill DOESN'T Do

❌ Railway connection basics (use database-quickref)
❌ Migration file patterns (see backend/migrations/)
❌ Scraping orchestration (see backend/services/)
❌ RAG configuration (see backend/services/retrieval/)

## Examples

### Example 1: Find stale sources
```
User: "Which sources need scraping?"

AI execution:
SELECT s.name, s.url, s.last_scraped_at,
  EXTRACT(EPOCH FROM (NOW() - s.last_scraped_at))/3600 as hours_since_scrape
FROM sources s
WHERE s.status = 'active'
AND s.last_scraped_at < NOW() - INTERVAL '24 hours'
ORDER BY s.last_scraped_at;

Outcome: ✅ Returns sources needing update
```

### Example 2: Check RAG integrity
```
User: "Are there documents without embeddings?"

AI execution:
SELECT 'missing_embeddings' as issue, COUNT(*) FROM documents WHERE embedding IS NULL
UNION ALL
SELECT 'stale_embeddings', COUNT(*) FROM documents d
JOIN document_chunks dc ON d.id = dc.document_id
WHERE d.updated_at > dc.created_at;

Outcome: ✅ Returns RAG health status
```

### Example 3: Find failed pipelines
```
User: "Show failed pipeline runs"

AI execution:
SELECT pr.id, pr.bill_id, pr.status, pr.error_message,
  pr.started_at, pr.completed_at
FROM pipeline_runs pr
WHERE pr.status = 'failed'
ORDER BY pr.started_at DESC
LIMIT 10;

Outcome: ✅ Returns recent failures
```

## Troubleshooting

### "relation does not exist"
**Cause:** Table doesn't exist or migration not applied

**Fix:**
```bash
# Check existing tables
railway run --service affordabot-pgvector -- psql "$DATABASE_URL" -c "\dt"

# Apply missing migration
ls backend/migrations/*.sql
# Apply the latest numbered migration
```

### SSL connection errors
**Cause:** Railway internal vs external connection

**Fix:**
```python
# From postgres_client.py - SSL handled automatically
use_ssl = 'railway.internal' not in database_url
```

## Related Skills

- **database-quickref**: Railway Postgres connection
- **context-affordabot-scraping**: Scraping orchestration
- **context-affordabot-rag**: RAG pipeline details

---

**Last Updated:** 2025-02-08
**Skill Type:** Context (affordabot)
**Related Docs:**
- backend/db/postgres_client.py (connection)
- backend/migrations/ (schema files)
