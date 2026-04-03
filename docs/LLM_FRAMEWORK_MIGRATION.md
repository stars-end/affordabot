# LLM Framework - Migration Plan

**Version:** 1.0
**Date:** 2025-12-01
**Status:** Implementation Ready
**Related:** [PRD](./LLM_FRAMEWORK_PRD.md), [Technical Spec](./LLM_FRAMEWORK_TECHNICAL_SPEC.md)

---

## Table of Contents
1. [Migration Overview](#migration-overview)
2. [Affordabot Migration](#affordabot-migration)
3. [Prime-Radiant-AI Migration](#prime-radiant-ai-migration)
4. [Database Migrations](#database-migrations)
5. [Testing & Validation](#testing--validation)
6. [Rollback Plan](#rollback-plan)

---

## Migration Overview

### Goals
1. **Zero Downtime:** Migrate without service interruption
2. **Data Preservation:** Maintain all existing data
3. **Gradual Rollout:** Feature flags for safe migration
4. **Rollback Ready:** Easy revert if issues arise

### Timeline
- **Week 1:** Create `llm-common` package + tests
- **Week 2:** Migrate `affordabot` (feature flag)
- **Week 3:** Migrate `prime-radiant-ai` (feature flag)
- **Week 4:** Remove old code, cleanup

### Migration Strategy

```
Current State                    Transition State                 Final State
┌────────────┐                  ┌────────────┐                  ┌────────────┐
│ affordabot │                  │ affordabot │                  │ affordabot │
│            │                  │            │                  │            │
│ Custom     │                  │ Custom     │  Feature Flag   │ llm-common │
│ Dual       │  ─────────────>  │ Dual       │  ───────────>   │ Pipeline   │
│ Model      │                  │ Model      │                  │            │
│ Analyzer   │                  │ Analyzer   │                  │            │
│            │                  │     +      │                  │            │
│            │                  │ llm-common │                  │            │
└────────────┘                  └────────────┘                  └────────────┘
```

---

## Affordabot Migration

### Current State Analysis

**Existing Code:**
- `backend/services/llm/pipeline.py` - `DualModelAnalyzer` (250 lines)
- `backend/services/llm/analyzer.py` - `LegislationAnalyzer` (106 lines)
- `backend/services/research/zai.py` - `ZaiResearchService`

**Dependencies:**
- `instructor` ✅ (keep)
- `openai` ✅ (keep)
- Custom fallback logic ❌ (replace with LiteLLM)

**Pain Points:**
- Hardcoded model priorities
- No performance tracking
- No multi-round evaluation

---

### Migration Steps

#### Step 1: Set Up `llm-common` Package (Week 1, Day 1-2)

**1.1 Create Package Structure**

```bash
cd ~
mkdir llm-common
cd llm-common

# Initialize git
git init
git add .
git commit -m "feat: Initial llm-common package"

# Optional: Push to GitHub
gh repo create llm-common --private
git remote add origin git@github.com:fengning-starsend/llm-common.git
git push -u origin master
```

**1.2 Add as Submodule to Affordabot**

```bash
cd ~/affordabot
git submodule add ../llm-common packages/llm-common
# or if on GitHub:
# git submodule add git@github.com:fengning-starsend/llm-common.git packages/llm-common

# Install in backend
cd backend
pip install -e ../packages/llm-common

# Or add to requirements.txt
echo "-e ../packages/llm-common" >> requirements.txt
```

**1.3 Install Dependencies**

```bash
cd ~/llm-common
pip install litellm instructor openai pydantic httpx tenacity pytest pytest-asyncio pytest-mock
```

---

#### Step 2: Implement Core Classes (Week 1, Day 3-5)

**2.1 Create `LLMClient`**

Copy implementation from [Technical Spec](./LLM_FRAMEWORK_TECHNICAL_SPEC.md#1-llmclient-litellm-wrapper).

**File:** `llm-common/llm_common/llm_client.py`

**2.2 Create `WebSearchClient`**

Copy implementation from [Technical Spec](./LLM_FRAMEWORK_TECHNICAL_SPEC.md#2-websearchclient-zai-web-search).

**File:** `llm-common/llm_common/web_search.py`

**2.3 Create `CostTracker`**

Copy implementation from [Technical Spec](./LLM_FRAMEWORK_TECHNICAL_SPEC.md#3-costtracker).

**File:** `llm-common/llm_common/cost_tracker.py`

**2.4 Write Tests**

```bash
cd ~/llm-common
pytest tests/ -v --cov=llm_common
# Target: 80% coverage
```

---

#### Step 3: Database Migrations (Week 1, Day 5)

**3.1 Create Migration File**

```bash
cd ~/affordabot/backend/migrations
touch 20251201_llm_framework_schema.sql
```

**3.2 Add Schema**

```sql
-- Web search cache
CREATE TABLE IF NOT EXISTS web_search_cache (
    cache_key TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    results JSONB NOT NULL,
    cached_at TIMESTAMP NOT NULL DEFAULT NOW(),
    hit_count INTEGER DEFAULT 0
);

CREATE INDEX idx_web_search_cached_at ON web_search_cache(cached_at);
CREATE INDEX idx_web_search_query ON web_search_cache(query);

-- Cost tracking
CREATE TABLE IF NOT EXISTS cost_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model TEXT NOT NULL,
    step TEXT,
    cost_usd DECIMAL(10, 6) NOT NULL,
    tokens_used INTEGER,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    project TEXT DEFAULT 'affordabot'
);

CREATE INDEX idx_cost_timestamp ON cost_tracking(timestamp);
CREATE INDEX idx_cost_model ON cost_tracking(model);
CREATE INDEX idx_cost_step ON cost_tracking(step);

-- Pipeline runs (for model comparison)
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_id TEXT NOT NULL,
    jurisdiction TEXT,
    research_model TEXT,
    generate_model TEXT NOT NULL,
    review_model TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    analysis_json JSONB,
    review_json JSONB,
    review_passed BOOLEAN,
    quality_score DECIMAL(3, 2),
    error_message TEXT
);

CREATE INDEX idx_pipeline_bill_id ON pipeline_runs(bill_id);
CREATE INDEX idx_pipeline_status ON pipeline_runs(status);
CREATE INDEX idx_pipeline_started_at ON pipeline_runs(started_at);

-- Pipeline steps (for debugging)
CREATE TABLE IF NOT EXISTS pipeline_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step TEXT NOT NULL CHECK (step IN ('research', 'generate', 'review', 'refine')),
    model TEXT NOT NULL,
    output JSONB,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pipeline_steps_run_id ON pipeline_steps(run_id);

-- Helper functions
CREATE OR REPLACE FUNCTION get_daily_cost(target_date DATE)
RETURNS TABLE(total_cost DECIMAL) AS $$
BEGIN
    RETURN QUERY
    SELECT COALESCE(SUM(cost_usd), 0)::DECIMAL
    FROM cost_tracking
    WHERE DATE(timestamp) = target_date;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_monthly_cost(target_year INT, target_month INT)
RETURNS TABLE(total_cost DECIMAL) AS $$
BEGIN
    RETURN QUERY
    SELECT COALESCE(SUM(cost_usd), 0)::DECIMAL
    FROM cost_tracking
    WHERE EXTRACT(YEAR FROM timestamp) = target_year
      AND EXTRACT(MONTH FROM timestamp) = target_month;
END;
$$ LANGUAGE plpgsql;

-- Cleanup function for cache
CREATE OR REPLACE FUNCTION cleanup_search_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM web_search_cache
    WHERE cached_at < NOW() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql;
```

**3.3 Apply Migration**

```bash
# Local development
psql $DATABASE_URL -f backend/migrations/20251201_llm_framework_schema.sql

# Production (via Railway)
railway run psql $DATABASE_URL -f backend/migrations/20251201_llm_framework_schema.sql
```

---

#### Step 4: Create New Pipeline (Week 2, Day 1-3)

**4.1 Create `AnalysisPipeline`**

Copy implementation from [Technical Spec](./LLM_FRAMEWORK_TECHNICAL_SPEC.md#1-analysis-pipeline).

**File:** `affordabot/backend/services/llm/orchestrator.py`

**4.2 Create `LegislationSearchService`**

Copy implementation from [Technical Spec](./LLM_FRAMEWORK_TECHNICAL_SPEC.md#2-legislation-search-service).

**File:** `affordabot/backend/services/research/legislation_search.py`

---

#### Step 5: Add Feature Flag (Week 2, Day 3)

**5.1 Environment Variable**

```bash
# Add to .env
USE_NEW_LLM_FRAMEWORK=false  # Start disabled
```

**5.2 Update Admin Router**

**File:** `affordabot/backend/routers/admin.py`

```python
import os
from services.llm.pipeline import DualModelAnalyzer  # Old
from services.llm.orchestrator import AnalysisPipeline  # New
from llm_common import LLMClient, WebSearchClient, CostTracker

# Feature flag
USE_NEW_FRAMEWORK = os.getenv("USE_NEW_LLM_FRAMEWORK", "false").lower() == "true"

# Initialize clients
if USE_NEW_FRAMEWORK:
    llm_client = LLMClient(provider="openrouter")
    search_client = WebSearchClient(api_key=os.getenv("ZAI_API_KEY"), postgres_client=postgres)
    cost_tracker = CostTracker(postgres_client=postgres, daily_budget_usd=10.0)
    analyzer = AnalysisPipeline(llm_client, search_client, cost_tracker, postgres)
else:
    analyzer = DualModelAnalyzer()  # Old implementation

@router.post("/analyze")
async def run_analysis_step(request: AnalysisStepRequest):
    """Run analysis (supports both old and new implementations)."""
    if USE_NEW_FRAMEWORK:
        # New pipeline
        result = await analyzer.run(
            bill_id=request.bill_id,
            bill_text="...",  # Fetch from DB
            jurisdiction=request.jurisdiction,
            models={
                "research": "gpt-4o-mini",
                "generate": request.model_override or "gpt-4o",
                "review": "claude-3.5-sonnet"
            }
        )
        return {"analysis": result.model_dump()}
    else:
        # Old pipeline
        result = await analyzer.analyze(
            bill_text="...",
            bill_number=request.bill_id,
            jurisdiction=request.jurisdiction
        )
        return {"analysis": result.model_dump()}
```

---

#### Step 6: Testing (Week 2, Day 4-5)

**6.1 Unit Tests**

```bash
cd ~/affordabot/backend
pytest tests/test_orchestrator.py -v
```

**6.2 Integration Test**

```python
# tests/test_orchestrator.py
import pytest
from services.llm.orchestrator import AnalysisPipeline
from llm_common import LLMClient, WebSearchClient, CostTracker

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline(postgres_client):
    """Test full pipeline with real models."""
    llm = LLMClient(provider="openrouter")
    search = WebSearchClient(api_key=os.getenv("ZAI_API_KEY"), postgres_client=postgres_client)
    tracker = CostTracker(postgres_client=postgres_client)

    pipeline = AnalysisPipeline(llm, search, tracker, postgres_client)

    result = await pipeline.run(
        bill_id="AB-1234",
        bill_text="Test bill text...",
        jurisdiction="California",
        models={
            "research": "gpt-4o-mini",
            "generate": "gpt-4o",
            "review": "claude-3.5-sonnet"
        }
    )

    assert result.confidence > 0.5

    # Verify logging
    runs = postgres_client.table('pipeline_runs').select('*').eq('bill_id', 'AB-1234').execute()
    assert len(runs.data) == 1
```

**6.3 Manual Testing**

```bash
# Enable feature flag
export USE_NEW_LLM_FRAMEWORK=true

# Run dev server
cd ~/affordabot/backend
uvicorn main:app --reload

# Test via admin dashboard
# Navigate to https://frontend-dev-5093.up.railway.app/admin
# Trigger analysis, verify it works
```

---

#### Step 7: Gradual Rollout (Week 2, Day 5 - Week 3)

**7.1 Deploy with Feature Flag Disabled**

```bash
# Deploy to Railway (feature flag OFF)
git add .
git commit -m "feat: Add new LLM framework (feature flag disabled)"
git push origin master

# Verify deployment
railway logs
```

**7.2 Enable for 10% of Requests**

```python
# Probabilistic feature flag
import random

USE_NEW_FRAMEWORK = random.random() < 0.1  # 10% traffic
```

**7.3 Monitor Metrics**

```sql
-- Compare old vs new pipeline
SELECT
    CASE WHEN research_model IS NULL THEN 'old' ELSE 'new' END as pipeline,
    COUNT(*) as total_runs,
    AVG(quality_score) as avg_quality
FROM pipeline_runs
WHERE started_at >= NOW() - INTERVAL '1 day'
GROUP BY pipeline;
```

**7.4 Increase to 50%, then 100%**

```bash
# Week 3, Day 1: 50%
export USE_NEW_LLM_FRAMEWORK_PERCENTAGE=50

# Week 3, Day 3: 100%
export USE_NEW_LLM_FRAMEWORK=true
```

---

#### Step 8: Cleanup (Week 4)

**8.1 Remove Old Code**

```bash
# Delete old files
rm backend/services/llm/pipeline.py
rm backend/services/llm/analyzer.py

# Remove feature flag
# (Update admin.py to only use new pipeline)
```

**8.2 Update Documentation**

```bash
# Update README
# Update API docs
# Update deployment guide
```

---

## Prime-Radiant-AI Migration

### Current State Analysis

**Existing Code:**
- `backend/llm/client.py` - Custom LLM client (8 files, ~1,000 LOC)
- `backend/llm/memory.py` - No implementation (needs to be built)

**Dependencies:**
- `httpx` ✅ (keep for other uses)
- Custom abstractions ❌ (replace with `llm-common`)

**Pain Points:**
- Heavy custom implementation
- No conversation memory
- No context injection

---

### Migration Steps

#### Step 1: Add `llm-common` Submodule (Week 3, Day 1)

```bash
cd ~/prime-radiant-ai
git submodule add ../llm-common packages/llm-common

# Install in backend
cd backend
poetry add -e ../packages/llm-common
```

---

#### Step 2: Create Conversation Memory (Week 3, Day 2)

**2.1 Database Migration**

```bash
cd ~/prime-radiant-ai/backend/migrations
touch 20251201_conversation_memory.sql
```

```sql
-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    page TEXT
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);

-- Cleanup function
CREATE OR REPLACE FUNCTION cleanup_conversations()
RETURNS void AS $$
BEGIN
    DELETE FROM conversations
    WHERE timestamp < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;
```

**2.2 Apply Migration**

```bash
psql $DATABASE_URL -f backend/migrations/20251201_conversation_memory.sql
```

**2.3 Implement `ConversationMemory`**

Copy implementation from [Technical Spec](./LLM_FRAMEWORK_TECHNICAL_SPEC.md#1-conversation-memory).

**File:** `prime-radiant-ai/backend/services/memory.py`

---

#### Step 3: Create Finance Search Service (Week 3, Day 3)

Copy implementation from [Technical Spec](./LLM_FRAMEWORK_TECHNICAL_SPEC.md#2-finance-search-service).

**File:** `prime-radiant-ai/backend/services/research/finance_search.py`

---

#### Step 4: Update Chat Endpoint (Week 3, Day 4)

**File:** `prime-radiant-ai/backend/routers/chat.py`

```python
from llm_common import LLMClient
from services.memory import ConversationMemory

@router.post("/chat")
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    """Chat endpoint with conversation memory."""
    # Initialize memory
    memory = ConversationMemory(db_client=postgres, user_id=user_id)

    # Get context (history + page-specific)
    messages = await memory.get_context(page=request.page)

    # Add user message
    messages.append({"role": "user", "content": request.message})

    # Call LLM
    llm = LLMClient(provider="openrouter")
    response = await llm.chat(
        messages=messages,
        model="gpt-4o"
    )

    # Save messages
    await memory.save_message("user", request.message)
    await memory.save_message("assistant", response)

    return {"response": response}
```

---

#### Step 5: Feature Flag & Testing (Week 3, Day 5)

Similar to affordabot:
1. Add feature flag
2. Test with 10% traffic
3. Increase to 100%
4. Remove old code

---

## Database Migrations

### Affordabot Migrations

**File:** `affordabot/backend/migrations/20251201_llm_framework_schema.sql`

See [Step 3.2](#32-add-schema) above.

---

### Prime-Radiant-AI Migrations

**File:** `prime-radiant-ai/backend/migrations/20251201_conversation_memory.sql`

See [Step 2.1](#21-database-migration) above.

---

### Shared Schema (Both Projects)

Both projects share:
- `web_search_cache`
- `cost_tracking`

**Note:** Use `project` column to distinguish between `affordabot` and `prime-radiant-ai`.

---

## Testing & Validation

### Pre-Migration Checklist

- [ ] Backup database
- [ ] Document current behavior (screenshots, API responses)
- [ ] Set up monitoring (error rates, latency)
- [ ] Create rollback plan

---

### Migration Validation

**Affordabot:**
- [ ] Pipeline runs successfully (Research → Generate → Review)
- [ ] Results match old implementation (quality check)
- [ ] Cost tracking works
- [ ] Cache hit rate ≥ 80%
- [ ] Admin dashboard displays model comparison

**Prime-Radiant-AI:**
- [ ] Conversation history persists across sessions
- [ ] Context injection works (portfolio, tax pages)
- [ ] Chat responses are coherent
- [ ] No memory leaks (long conversations)

---

### Performance Benchmarks

**Affordabot:**
- **Latency:** P95 < 10s (full pipeline)
- **Throughput:** 50 bills/day
- **Cache Hit Rate:** ≥ 80%
- **Error Rate:** < 1%

**Prime-Radiant-AI:**
- **Latency:** P95 < 3s (single chat response)
- **Conversation Load Time:** < 500ms
- **Error Rate:** < 1%

---

## Rollback Plan

### If Issues Arise

**1. Disable Feature Flag**

```bash
# Affordabot
export USE_NEW_LLM_FRAMEWORK=false

# Prime-Radiant-AI
export USE_NEW_LLM_FRAMEWORK=false
```

**2. Revert Code**

```bash
git revert <commit-hash>
git push origin master
```

**3. Database Rollback**

```sql
-- Drop new tables (if needed)
DROP TABLE IF EXISTS pipeline_runs CASCADE;
DROP TABLE IF EXISTS pipeline_steps CASCADE;
DROP TABLE IF EXISTS conversations CASCADE;
DROP TABLE IF EXISTS web_search_cache CASCADE;
DROP TABLE IF EXISTS cost_tracking CASCADE;
```

**Note:** Only drop tables if they're causing issues. Otherwise, keep them for future retry.

---

### Rollback Triggers

Rollback if:
- Error rate > 5%
- Latency P95 > 20s
- Cost > 2x expected
- Data loss detected

---

## Post-Migration

### Monitoring

**Metrics to Track:**
- Pipeline success rate
- Model performance (quality scores)
- Cost per bill
- Cache hit rate
- Conversation continuity (prime-radiant-ai)

**Dashboards:**
- Postgres: Query `pipeline_runs` for model comparison
- Railway: Monitor logs for errors
- Admin UI: Display model performance charts

---

### Optimization

**Week 5+:**
- [ ] Tune cache TTLs (optimize hit rate vs freshness)
- [ ] Experiment with model combinations
- [ ] Add multi-round evaluation (Generate v2 → Review v2)
- [ ] Implement conversation summarization (prime-radiant-ai)

---

## Summary

### Migration Timeline

| Week | Focus | Deliverables |
|------|-------|--------------|
| 1 | `llm-common` package | LLMClient, WebSearchClient, CostTracker, Tests |
| 2 | Affordabot migration | AnalysisPipeline, Feature flag, Testing |
| 3 | Prime-Radiant-AI migration | ConversationMemory, Finance search, Testing |
| 4 | Cleanup & optimization | Remove old code, Documentation, Tuning |

### Success Criteria

- ✅ Zero downtime during migration
- ✅ No data loss
- ✅ Performance meets benchmarks
- ✅ Cost within budget ($300/month)
- ✅ 50% code reduction (vs. custom implementations)

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Set up `llm-common` repo** (Week 1, Day 1)
3. **Begin implementation** (follow steps above)
4. **Monitor progress** (weekly check-ins)

---

## Appendix

### Useful Commands

**Update submodule:**
```bash
cd ~/affordabot
git submodule update --remote packages/llm-common
git commit -m "chore: Update llm-common"
```

**Run tests:**
```bash
cd ~/llm-common
pytest tests/ -v --cov=llm_common

cd ~/affordabot/backend
pytest tests/ -v
```

**Apply migrations:**
```bash
# Local
psql $DATABASE_URL -f backend/migrations/<file>.sql

# Production
railway run psql $DATABASE_URL -f backend/migrations/<file>.sql
```

**Monitor costs:**
```sql
SELECT * FROM cost_tracking ORDER BY timestamp DESC LIMIT 100;
SELECT get_daily_cost(CURRENT_DATE);
SELECT get_monthly_cost(2024, 12);
```
