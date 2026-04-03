# Admin Dashboard V2 Database Schema

## Overview

The Admin Dashboard V2 schema provides comprehensive tracking and management for AffordaBot's administrative operations, following 2025 Postgres best practices.

## Tables

### 1. `admin_tasks`
**Purpose**: Tracks background tasks for scraping and analysis operations

**Key Features**:
- Task type validation (scrape, research, generate, review)
- Status tracking with lifecycle management
- Auto-calculated duration metrics
- JSONB config for flexible task parameters
- Comprehensive error tracking

**Common Queries**:
```sql
-- Get running tasks
SELECT * FROM admin_tasks WHERE status IN ('queued', 'running') ORDER BY created_at;

-- Get task history for a bill
SELECT * FROM admin_tasks WHERE bill_id = 'SB-123' ORDER BY created_at DESC;

-- Get failed tasks for debugging
SELECT * FROM admin_tasks WHERE status = 'failed' ORDER BY created_at DESC LIMIT 10;
```

### 2. `model_configs`
**Purpose**: Manages LLM model priority and configuration

**Key Features**:
- Multi-provider support (OpenRouter, Z.ai, Anthropic, OpenAI)
- Priority-based model selection
- Health monitoring integration
- Usage statistics tracking
- Unique constraint per provider+model+use_case

**Common Queries**:
```sql
-- Get active models for generation (by priority)
SELECT * FROM model_configs
WHERE use_case IN ('generation', 'both') AND enabled = true
ORDER BY priority;

-- Update model priority
UPDATE model_configs SET priority = 1 WHERE provider = 'openrouter' AND model_name = 'x-ai/grok-beta';

-- Track model health
UPDATE model_configs SET
    health_status = 'healthy',
    last_health_check_at = NOW(),
    health_details = '{"latency_ms": 234, "success_rate": 0.98}'::jsonb
WHERE id = '...';
```

### 3. `system_prompts`
**Purpose**: Versioned system prompts for generation and review

**Key Features**:
- Version control for prompts
- Only one active prompt per type (enforced by constraint)
- Performance tracking (usage count, quality scores)
- Deferred constraint for safe activation swaps

**Common Queries**:
```sql
-- Get active generation prompt
SELECT * FROM system_prompts WHERE prompt_type = 'generation' AND is_active = true;

-- Create new prompt version
INSERT INTO system_prompts (prompt_type, version, system_prompt, description)
VALUES ('generation', 2, 'New improved prompt...', 'Added quantification requirements');

-- Activate new prompt (atomic swap)
BEGIN;
UPDATE system_prompts SET is_active = false WHERE prompt_type = 'generation' AND is_active = true;
UPDATE system_prompts SET is_active = true, activated_at = NOW() WHERE id = '...';
COMMIT;

-- View prompt history
SELECT version, description, activated_at, usage_count, avg_quality_score
FROM system_prompts
WHERE prompt_type = 'generation'
ORDER BY version DESC;
```

### 4. `analysis_history`
**Purpose**: Historical record of all analysis pipeline executions

**Key Features**:
- Stores complete analysis outputs (research, generation, review)
- Tracks model and prompt versions used
- Performance metrics (latency, tokens, cost)
- Links to originating task

**Common Queries**:
```sql
-- Get analysis history for a bill
SELECT step, model_name, confidence_score, created_at
FROM analysis_history
WHERE jurisdiction = 'san_jose' AND bill_id = 'SB-123'
ORDER BY created_at DESC;

-- Calculate average costs by model
SELECT model_provider, model_name,
       AVG(cost_usd) as avg_cost,
       SUM(cost_usd) as total_cost,
       COUNT(*) as executions
FROM analysis_history
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY model_provider, model_name;

-- Find low-confidence analyses for review
SELECT * FROM analysis_history
WHERE step = 'generate' AND confidence_score < 0.7
ORDER BY created_at DESC;
```

### 5. `scrape_history`
**Purpose**: Historical record of all scraping operations

**Key Features**:
- Tracks bills found, new, and updated
- Status and error tracking
- Performance metrics
- Links to originating task

**Common Queries**:
```sql
-- Get recent scrapes by jurisdiction
SELECT jurisdiction, bills_found, bills_new, status, created_at
FROM scrape_history
ORDER BY created_at DESC
LIMIT 20;

-- Calculate scraping success rate
SELECT jurisdiction,
       COUNT(*) as total_scrapes,
       SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
       ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM scrape_history
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY jurisdiction;
```

## Indexes

All tables include optimized indexes for common query patterns:

- **admin_tasks**: Status, type+jurisdiction, created_at, bill_id
- **model_configs**: Priority ordering, unique provider+model+use_case
- **system_prompts**: Active prompts, version history
- **analysis_history**: Bill lookups, model performance, time-series
- **scrape_history**: Jurisdiction lookups, status filtering

## Row Level Security (RLS)

All tables have RLS enabled with placeholder admin policies. **TODO**: Update policies based on your authentication system (Clerk, Postgres Auth, etc.).

Example policy update:
```sql
-- Replace placeholder with actual admin check
DROP POLICY "Admin full access to admin_tasks" ON admin_tasks;

CREATE POLICY "Admin full access to admin_tasks"
    ON admin_tasks
    FOR ALL
    USING (
        -- Example: Check if user has admin role
        EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_id = auth.uid() AND role = 'admin'
        )
    );
```

## Triggers

All tables with `updated_at` columns have automatic update triggers using the `update_updated_at_column()` function.

## Migration Application

### Development (Local Postgres)
```bash
postgres db reset  # Reset and apply all migrations
postgres db push   # Push schema changes
```

### Production (Railway)
```bash
# Using Railway CLI
railway run psql $DATABASE_URL -f backend/migrations/20251130_admin_dashboard_v2_schema.sql

# Or using apply_migration_railway.py
python apply_migration_railway.py backend/migrations/20251130_admin_dashboard_v2_schema.sql
```

## Integration with Backend

The admin router (`backend/routers/admin.py`) is ready to use these tables. Update the TODO comments to integrate with actual database queries:

```python
# Example: Get scrape history
@router.get("/scrapes", response_model=List[ScrapeHistory])
async def get_scrape_history(
    jurisdiction: Optional[str] = None,
    limit: int = 50
):
    query = """
        SELECT id, jurisdiction, created_at as timestamp,
               bills_found, status, error_message
        FROM scrape_history
        WHERE ($1::text IS NULL OR jurisdiction = $1)
        ORDER BY created_at DESC
        LIMIT $2
    """
    # Execute with your DB client
    results = await db.fetch(query, jurisdiction, limit)
    return [ScrapeHistory(**row) for row in results]
```

## Best Practices

1. **Always use transactions** for multi-step operations (e.g., activating new prompts)
2. **Monitor index usage** with `pg_stat_user_indexes`
3. **Archive old data** periodically (e.g., analysis_history older than 1 year)
4. **Update RLS policies** before deploying to production
5. **Use JSONB indexes** if querying specific JSON fields frequently:
   ```sql
   CREATE INDEX idx_admin_tasks_config_model
   ON admin_tasks((config->>'model_override'));
   ```

## Schema Evolution

When adding new columns or tables:
1. Create a new migration file with timestamp
2. Update this documentation
3. Test locally with `postgres db reset`
4. Apply to production with Railway
5. Update `golden_schema.sql` after successful deployment
