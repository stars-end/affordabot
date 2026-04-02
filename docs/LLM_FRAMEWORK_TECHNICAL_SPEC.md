# LLM Framework - Technical Specification

**Version:** 1.0  
**Date:** 2025-12-01  
**Status:** Implementation Ready  
**Related:** [PRD](./LLM_FRAMEWORK_PRD.md), [Migration Plan](./LLM_FRAMEWORK_MIGRATION.md)

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Shared Package (`llm-common`)](#shared-package-llm-common)
3. [Affordabot Implementation](#affordabot-implementation)
4. [Prime-Radiant-AI Implementation](#prime-radiant-ai-implementation)
5. [Database Schema](#database-schema)
6. [API Reference](#api-reference)
7. [Testing Strategy](#testing-strategy)

---

## Architecture Overview

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                      llm-common (Shared)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ WebSearch    │  │ LLMClient    │  │ Cost         │      │
│  │ Client       │  │ (LiteLLM)    │  │ Tracker      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
           ▲                                    ▲
           │                                    │
    ┌──────┴────────┐                  ┌────────┴────────┐
    │               │                  │                 │
┌───▼────────────┐  │              ┌───▼──────────────┐  │
│  affordabot    │  │              │ prime-radiant-ai │  │
│                │  │              │                  │  │
│ ┌────────────┐ │  │              │ ┌──────────────┐ │  │
│ │ Analysis   │ │  │              │ │ Conversation │ │  │
│ │ Pipeline   │ │  │              │ │ Memory       │ │  │
│ └────────────┘ │  │              │ └──────────────┘ │  │
│                │  │              │                  │  │
│ ┌────────────┐ │  │              │ ┌──────────────┐ │  │
│ │ Legislation│ │  │              │ │ Finance      │ │  │
│ │ Search     │ │  │              │ │ Search       │ │  │
│ └────────────┘ │  │              │ └──────────────┘ │  │
└────────────────┘  │              └──────────────────┘  │
                    │                                    │
                    └────────────────┬───────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │   Supabase          │
                          │  (State + Cache)    │
                          └─────────────────────┘
```

### Technology Stack

| Component | Technology | Justification |
|-----------|-----------|---------------|
| LLM Client | LiteLLM | Multi-provider support, battle-tested |
| Structured Outputs | instructor | Type-safe Pydantic models |
| Web Search | z.ai API | Intelligent search, legislation-optimized |
| Caching | Supabase + In-Memory | Cost reduction (80% hit rate) |
| Database | Supabase (PostgreSQL) | Already in use, supports JSONB |
| Package Management | Git Submodule | Solo dev, no CI/CD overhead |

---

## Shared Package (`llm-common`)

### Package Structure

```
llm-common/
├── llm_common/
│   ├── __init__.py
│   ├── llm_client.py       # LiteLLM wrapper
│   ├── web_search.py       # z.ai web search with caching
│   ├── cost_tracker.py     # Cost tracking and budgets
│   ├── models.py           # Shared Pydantic models
│   └── exceptions.py       # Custom exceptions
├── tests/
│   ├── test_llm_client.py
│   ├── test_web_search.py
│   └── test_cost_tracker.py
├── examples/
│   ├── basic_usage.py
│   └── web_search_usage.py
├── pyproject.toml
└── README.md
```

### Core Classes

#### 1. `LLMClient` (LiteLLM Wrapper)

**Purpose:** Thin wrapper around LiteLLM with instructor integration.

**File:** `llm_common/llm_client.py`

```python
from litellm import acompletion, completion_cost
import instructor
from openai import AsyncOpenAI
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class LLMClient:
    """
    Unified LLM client supporting multiple providers.
    
    Supports:
    - OpenRouter (400+ models)
    - z.ai (GLM-4.5, GLM-4.6)
    - OpenAI (direct)
    - Anthropic (direct)
    """
    
    def __init__(
        self,
        provider: str = "openrouter",
        api_key: Optional[str] = None,
        budget_limit_usd: Optional[float] = None
    ):
        """
        Initialize LLM client.
        
        Args:
            provider: "openrouter", "zai", "openai", or "anthropic"
            api_key: API key (or use env var)
            budget_limit_usd: Daily budget limit
        """
        self.provider = provider
        self.api_key = api_key or self._get_api_key(provider)
        self.budget_limit = budget_limit_usd
        self.daily_cost = 0.0
        
        # Initialize instructor client for structured outputs
        self.instructor_client = self._init_instructor()
    
    def _get_api_key(self, provider: str) -> str:
        """Get API key from environment."""
        import os
        keys = {
            "openrouter": os.getenv("OPENROUTER_API_KEY"),
            "zai": os.getenv("ZAI_API_KEY"),
            "openai": os.getenv("OPENAI_API_KEY"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY")
        }
        return keys.get(provider)
    
    def _init_instructor(self):
        """Initialize instructor client for structured outputs."""
        base_urls = {
            "openrouter": "https://openrouter.ai/api/v1",
            "zai": "https://api.z.ai/api/coding/paas/v4",
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1"
        }
        
        return instructor.from_openai(
            AsyncOpenAI(
                api_key=self.api_key,
                base_url=base_urls.get(self.provider)
            )
        )
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        response_model: Optional[type[BaseModel]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Any:
        """
        Generate chat completion.
        
        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}
            model: Model name (e.g., "gpt-4o", "z-ai/glm-4.7")
            response_model: Pydantic model for structured output
            temperature: 0.0-1.0
            max_tokens: Max output tokens
        
        Returns:
            Pydantic model instance (if response_model provided) or string
        
        Raises:
            BudgetExceededError: If daily budget exceeded
            RateLimitError: If rate limited by provider
        """
        # Check budget
        if self.budget_limit and self.daily_cost >= self.budget_limit:
            raise BudgetExceededError(
                f"Daily budget exceeded: ${self.daily_cost:.2f} >= ${self.budget_limit:.2f}"
            )
        
        # Structured output (via instructor)
        if response_model:
            response = await self.instructor_client.chat.completions.create(
                model=model,
                messages=messages,
                response_model=response_model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            # Track cost (instructor wraps response)
            cost = self._estimate_cost(model, messages, response)
            self.daily_cost += cost
            return response
        
        # Regular completion (via LiteLLM)
        response = await acompletion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        # Track cost
        cost = completion_cost(completion_response=response)
        self.daily_cost += cost
        
        return response.choices[0].message.content
    
    async def chat_with_fallback(
        self,
        messages: List[Dict[str, str]],
        models: List[str],
        response_model: Optional[type[BaseModel]] = None,
        **kwargs
    ) -> Any:
        """
        Try models in sequence until one succeeds.
        
        Args:
            messages: Chat messages
            models: List of model names to try (in order)
            response_model: Pydantic model for structured output
        
        Returns:
            Response from first successful model
        
        Raises:
            AllModelsFailed: If all models fail
        """
        last_error = None
        
        for model in models:
            try:
                return await self.chat(
                    messages=messages,
                    model=model,
                    response_model=response_model,
                    **kwargs
                )
            except Exception as e:
                print(f"Model {model} failed: {e}")
                last_error = e
                continue
        
        raise AllModelsFailed(f"All {len(models)} models failed. Last error: {last_error}")
    
    def _estimate_cost(self, model: str, messages: List, response: Any) -> float:
        """Estimate cost for instructor responses (no usage data)."""
        # Rough estimate: 1K tokens = $0.001 for cheap models
        # TODO: Use LiteLLM's cost calculation if possible
        return 0.001
```

**Key Features:**
- ✅ Multi-provider support (OpenRouter, z.ai, OpenAI, Anthropic)
- ✅ Structured outputs via `instructor`
- ✅ Budget enforcement
- ✅ Fallback chain
- ✅ Cost tracking

---

#### 2. `WebSearchClient` (z.ai Web Search)

**Purpose:** z.ai web search with 2-tier caching.

**File:** `llm_common/web_search.py`

```python
import httpx
import hashlib
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

class SearchResult(BaseModel):
    """Single search result."""
    title: str
    url: str
    snippet: str
    published_date: Optional[str] = None
    relevance_score: Optional[float] = None

class WebSearchClient:
    """
    z.ai web search with intelligent caching.
    
    Caching Strategy:
    - L1: In-memory cache (TTL: 1 hour)
    - L2: Supabase cache (TTL: 24 hours)
    
    Cost Savings:
    - Target: 80% cache hit rate
    - Estimated: $450/month → $90/month
    """
    
    def __init__(
        self,
        api_key: str,
        supabase_client: Any,
        memory_cache_ttl: int = 3600,  # 1 hour
        db_cache_ttl: int = 86400       # 24 hours
    ):
        """
        Initialize web search client.
        
        Args:
            api_key: z.ai API key
            supabase_client: Supabase client for persistent cache
            memory_cache_ttl: In-memory cache TTL (seconds)
            db_cache_ttl: Database cache TTL (seconds)
        """
        self.api_key = api_key
        self.supabase = supabase_client
        self.memory_cache: Dict[str, tuple[List[SearchResult], datetime]] = {}
        self.memory_ttl = memory_cache_ttl
        self.db_ttl = db_cache_ttl
        
        self.base_url = "https://api.z.ai/api/paas/v4/web-search"
        self.http_client = httpx.AsyncClient()
    
    def _generate_cache_key(
        self,
        query: str,
        count: int,
        domains: Optional[List[str]],
        recency: Optional[str]
    ) -> str:
        """Generate cache key from search parameters."""
        params = {
            "query": query,
            "count": count,
            "domains": sorted(domains) if domains else [],
            "recency": recency
        }
        return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    
    async def search(
        self,
        query: str,
        count: int = 10,
        domains: Optional[List[str]] = None,
        recency: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Search with caching.
        
        Args:
            query: Search query
            count: Number of results (1-25)
            domains: Filter by domains (e.g., ["*.gov", "*.edu"])
            recency: Time filter ("1d", "1w", "1m", "1y")
        
        Returns:
            List of search results
        
        Raises:
            RateLimitError: If z.ai rate limit exceeded
            SearchError: If search fails
        """
        cache_key = self._generate_cache_key(query, count, domains, recency)
        
        # L1: Check memory cache
        if cache_key in self.memory_cache:
            results, cached_at = self.memory_cache[cache_key]
            if datetime.now() - cached_at < timedelta(seconds=self.memory_ttl):
                print(f"✅ L1 cache hit: {query}")
                return results
        
        # L2: Check Supabase cache
        db_result = self.supabase.table('web_search_cache').select('*').eq(
            'cache_key', cache_key
        ).execute()
        
        if db_result.data:
            row = db_result.data[0]
            cached_at = datetime.fromisoformat(row['cached_at'])
            if datetime.now() - cached_at < timedelta(seconds=self.db_ttl):
                print(f"✅ L2 cache hit: {query}")
                results = [SearchResult(**r) for r in row['results']]
                # Populate L1 cache
                self.memory_cache[cache_key] = (results, datetime.now())
                return results
        
        # Cache miss: Call z.ai API
        print(f"🔍 Cache miss, calling z.ai: {query}")
        results = await self._call_zai_api(query, count, domains, recency)
        
        # Store in both caches
        self.memory_cache[cache_key] = (results, datetime.now())
        self.supabase.table('web_search_cache').upsert({
            'cache_key': cache_key,
            'query': query,
            'results': [r.model_dump() for r in results],
            'cached_at': datetime.now().isoformat()
        }).execute()
        
        return results
    
    async def _call_zai_api(
        self,
        query: str,
        count: int,
        domains: Optional[List[str]],
        recency: Optional[str]
    ) -> List[SearchResult]:
        """Call z.ai web search API."""
        payload = {
            "query": query,
            "count": count
        }
        
        if domains:
            payload["domains"] = domains
        if recency:
            payload["recency"] = recency
        
        response = await self.http_client.post(
            self.base_url,
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        
        if response.status_code == 429:
            raise RateLimitError("z.ai rate limit exceeded")
        
        response.raise_for_status()
        data = response.json()
        
        return [SearchResult(**item) for item in data.get("results", [])]
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache hit rate statistics."""
        # Query Supabase for cache stats
        result = self.supabase.rpc('get_cache_stats').execute()
        return result.data
```

**Key Features:**
- ✅ 2-tier caching (memory + Supabase)
- ✅ Cost tracking
- ✅ Cache hit rate stats
- ✅ Domain filtering
- ✅ Recency filtering

---

#### 3. `CostTracker`

**Purpose:** Track and enforce budget limits.

**File:** `llm_common/cost_tracker.py`

```python
from datetime import datetime, date
from typing import Dict, Optional
from pydantic import BaseModel

class CostMetrics(BaseModel):
    """Cost metrics for a single request."""
    model: str
    step: Optional[str] = None  # "research", "generate", "review"
    cost_usd: float
    tokens_used: Optional[int] = None
    timestamp: datetime = datetime.now()

class CostTracker:
    """
    Track LLM and web search costs.
    
    Features:
    - Daily/monthly budget enforcement
    - Cost breakdown by model and step
    - Alert thresholds
    """
    
    def __init__(
        self,
        supabase_client: Any,
        daily_budget_usd: Optional[float] = None,
        monthly_budget_usd: Optional[float] = None,
        alert_threshold: float = 0.8
    ):
        """
        Initialize cost tracker.
        
        Args:
            supabase_client: Supabase client for cost storage
            daily_budget_usd: Daily budget limit
            monthly_budget_usd: Monthly budget limit
            alert_threshold: Alert when cost reaches this % of budget
        """
        self.supabase = supabase_client
        self.daily_budget = daily_budget_usd
        self.monthly_budget = monthly_budget_usd
        self.alert_threshold = alert_threshold
    
    async def log_cost(self, metrics: CostMetrics):
        """Log cost to database."""
        self.supabase.table('cost_tracking').insert({
            'model': metrics.model,
            'step': metrics.step,
            'cost_usd': metrics.cost_usd,
            'tokens_used': metrics.tokens_used,
            'timestamp': metrics.timestamp.isoformat()
        }).execute()
        
        # Check budget
        await self._check_budget()
    
    async def _check_budget(self):
        """Check if budget limits are exceeded."""
        today = date.today()
        
        # Daily budget check
        if self.daily_budget:
            daily_cost = await self.get_daily_cost(today)
            if daily_cost >= self.daily_budget:
                raise BudgetExceededError(
                    f"Daily budget exceeded: ${daily_cost:.2f} >= ${self.daily_budget:.2f}"
                )
            elif daily_cost >= self.daily_budget * self.alert_threshold:
                print(f"⚠️  Daily budget alert: ${daily_cost:.2f} / ${self.daily_budget:.2f}")
        
        # Monthly budget check
        if self.monthly_budget:
            monthly_cost = await self.get_monthly_cost(today.year, today.month)
            if monthly_cost >= self.monthly_budget:
                raise BudgetExceededError(
                    f"Monthly budget exceeded: ${monthly_cost:.2f} >= ${self.monthly_budget:.2f}"
                )
    
    async def get_daily_cost(self, date: date) -> float:
        """Get total cost for a specific date."""
        result = self.supabase.rpc('get_daily_cost', {'target_date': date.isoformat()}).execute()
        return result.data[0]['total_cost'] if result.data else 0.0
    
    async def get_monthly_cost(self, year: int, month: int) -> float:
        """Get total cost for a specific month."""
        result = self.supabase.rpc('get_monthly_cost', {
            'target_year': year,
            'target_month': month
        }).execute()
        return result.data[0]['total_cost'] if result.data else 0.0
    
    async def get_cost_breakdown(
        self,
        start_date: date,
        end_date: date,
        group_by: str = "model"
    ) -> Dict[str, float]:
        """
        Get cost breakdown by model or step.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            group_by: "model" or "step"
        
        Returns:
            Dict mapping model/step to total cost
        """
        result = self.supabase.rpc('get_cost_breakdown', {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'group_by': group_by
        }).execute()
        
        return {row['group_key']: row['total_cost'] for row in result.data}
```

---

## Affordabot Implementation

### 1. Analysis Pipeline

**File:** `affordabot/backend/services/llm/orchestrator.py`

```python
from llm_common import LLMClient, WebSearchClient, CostTracker
from typing import List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class BillAnalysis(BaseModel):
    """Structured analysis output."""
    summary: str
    impacts: List[Dict[str, Any]]
    confidence: float
    sources: List[str]

class ReviewCritique(BaseModel):
    """Review output."""
    passed: bool
    critique: str
    missing_impacts: List[str]
    factual_errors: List[str]

class AnalysisPipeline:
    """
    Orchestrate multi-step legislation analysis.
    
    Workflow:
    1. Research: z.ai web search (20-30 queries)
    2. Generate: LLM analysis with structured output
    3. Review: LLM critique
    4. Refine: Regenerate if review failed
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        search_client: WebSearchClient,
        cost_tracker: CostTracker,
        db_client: Any
    ):
        """
        Initialize pipeline.
        
        Args:
            llm_client: LLM client (LiteLLM wrapper)
            search_client: Web search client (z.ai)
            cost_tracker: Cost tracking client
            db_client: Supabase client for logging
        """
        self.llm = llm_client
        self.search = search_client
        self.cost = cost_tracker
        self.db = db_client
    
    async def run(
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        models: Dict[str, str]
    ) -> BillAnalysis:
        """
        Run full pipeline.
        
        Args:
            bill_id: Bill identifier (e.g., "AB-1234")
            bill_text: Full bill text
            jurisdiction: Jurisdiction (e.g., "California")
            models: {"research": "gpt-4o-mini", "generate": "claude-3.5-sonnet", "review": "glm-4.7"}
        
        Returns:
            Final analysis (validated BillAnalysis)
        """
        run_id = await self._create_pipeline_run(bill_id, models)
        
        try:
            # Step 1: Research
            research_data = await self._research_step(bill_id, bill_text, models["research"])
            await self._log_step(run_id, "research", models["research"], research_data)
            
            # Step 2: Generate
            analysis = await self._generate_step(
                bill_id, bill_text, jurisdiction, research_data, models["generate"]
            )
            await self._log_step(run_id, "generate", models["generate"], analysis)
            
            # Step 3: Review
            review = await self._review_step(bill_id, analysis, research_data, models["review"])
            await self._log_step(run_id, "review", models["review"], review)
            
            # Step 4: Refine (if needed)
            if not review.passed:
                analysis = await self._refine_step(
                    bill_id, analysis, review, bill_text, models["generate"]
                )
                await self._log_step(run_id, "refine", models["generate"], analysis)
            
            # Mark run as complete
            await self._complete_pipeline_run(run_id, analysis, review)
            
            return analysis
        
        except Exception as e:
            await self._fail_pipeline_run(run_id, str(e))
            raise
    
    async def _research_step(
        self,
        bill_id: str,
        bill_text: str,
        model: str
    ) -> List[Dict[str, Any]]:
        """
        Research step: Generate queries and search.
        
        Returns:
            List of search results
        """
        # Generate research queries using LLM
        queries = await self._generate_research_queries(bill_id, bill_text, model)
        
        # Execute searches (with caching)
        results = []
        for query in queries:
            search_results = await self.search.search(
                query=query,
                count=10,
                domains=["*.gov", "*.edu", "*.org"],
                recency="1y"
            )
            results.extend(search_results)
        
        return [r.model_dump() for r in results]
    
    async def _generate_research_queries(
        self,
        bill_id: str,
        bill_text: str,
        model: str
    ) -> List[str]:
        """Generate 20-30 research queries using LLM."""
        class ResearchQueries(BaseModel):
            queries: List[str]
        
        response = await self.llm.chat(
            messages=[
                {"role": "system", "content": "Generate research queries for legislation analysis."},
                {"role": "user", "content": f"Bill: {bill_id}\nText: {bill_text[:1000]}..."}
            ],
            model=model,
            response_model=ResearchQueries
        )
        
        return response.queries
    
    async def _generate_step(
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        research_data: List[Dict],
        model: str
    ) -> BillAnalysis:
        """
        Generate analysis using LLM.
        
        Returns:
            Validated BillAnalysis
        """
        system_prompt = """
        You are an expert policy analyst. Analyze legislation for cost-of-living impacts.
        Use the provided research data to support your analysis.
        """
        
        user_message = f"""
        Bill: {bill_id} ({jurisdiction})
        
        Research Data:
        {research_data}
        
        Bill Text:
        {bill_text}
        """
        
        return await self.llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model=model,
            response_model=BillAnalysis
        )
    
    async def _review_step(
        self,
        bill_id: str,
        analysis: BillAnalysis,
        research_data: List[Dict],
        model: str
    ) -> ReviewCritique:
        """
        Review analysis using LLM.
        
        Returns:
            Validated ReviewCritique
        """
        system_prompt = """
        You are a strict auditor. Review the analysis for accuracy and completeness.
        Check for hallucinations and missing impacts.
        """
        
        user_message = f"""
        Analysis to Review:
        {analysis.model_dump_json()}
        
        Research Data:
        {research_data}
        """
        
        return await self.llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model=model,
            response_model=ReviewCritique
        )
    
    async def _refine_step(
        self,
        bill_id: str,
        draft: BillAnalysis,
        critique: ReviewCritique,
        bill_text: str,
        model: str
    ) -> BillAnalysis:
        """
        Refine analysis based on critique.
        
        Returns:
            Refined BillAnalysis
        """
        system_prompt = """
        You are an expert policy analyst. Update your analysis based on the auditor's critique.
        """
        
        user_message = f"""
        Previous Draft:
        {draft.model_dump_json()}
        
        Critique:
        {critique.model_dump_json()}
        
        Provide the final corrected analysis.
        """
        
        return await self.llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model=model,
            response_model=BillAnalysis
        )
    
    async def _create_pipeline_run(self, bill_id: str, models: Dict[str, str]) -> str:
        """Create pipeline run record in database."""
        result = self.db.table('pipeline_runs').insert({
            'bill_id': bill_id,
            'research_model': models.get("research"),
            'generate_model': models["generate"],
            'review_model': models["review"],
            'status': 'running',
            'started_at': datetime.now().isoformat()
        }).execute()
        
        return result.data[0]['id']
    
    async def _log_step(
        self,
        run_id: str,
        step: str,
        model: str,
        output: Any
    ):
        """Log pipeline step to database."""
        self.db.table('pipeline_steps').insert({
            'run_id': run_id,
            'step': step,
            'model': model,
            'output': output.model_dump() if hasattr(output, 'model_dump') else output,
            'timestamp': datetime.now().isoformat()
        }).execute()
    
    async def _complete_pipeline_run(
        self,
        run_id: str,
        analysis: BillAnalysis,
        review: ReviewCritique
    ):
        """Mark pipeline run as complete."""
        self.db.table('pipeline_runs').update({
            'status': 'completed',
            'completed_at': datetime.now().isoformat(),
            'analysis_json': analysis.model_dump(),
            'review_json': review.model_dump(),
            'review_passed': review.passed
        }).eq('id', run_id).execute()
    
    async def _fail_pipeline_run(self, run_id: str, error: str):
        """Mark pipeline run as failed."""
        self.db.table('pipeline_runs').update({
            'status': 'failed',
            'completed_at': datetime.now().isoformat(),
            'error_message': error
        }).eq('id', run_id).execute()
```

**Key Features:**
- ✅ Sequential pipeline (Research → Generate → Review → Refine)
- ✅ Different models per step
- ✅ Structured outputs (Pydantic)
- ✅ Database logging (every step)
- ✅ Error handling

---

### 2. Legislation Search Service

**File:** `affordabot/backend/services/research/legislation_search.py`

```python
from llm_common import WebSearchClient
from typing import List, Dict, Any

class LegislationSearchService:
    """
    Domain-specific search service for legislation.
    
    Generates legislation-specific queries and packages results for LLM consumption.
    """
    
    def __init__(self, search_client: WebSearchClient):
        """
        Initialize service.
        
        Args:
            search_client: Shared web search client
        """
        self.search = search_client
    
    def _generate_queries(self, bill_id: str, bill_text: str) -> List[str]:
        """
        Generate legislation-specific queries.
        
        Returns:
            20-30 queries for comprehensive research
        """
        queries = [
            # Core queries
            f"{bill_id} full text",
            f"{bill_id} legislative intent",
            f"{bill_id} fiscal impact analysis",
            f"{bill_id} stakeholder positions",
            
            # Impact queries
            f"{bill_id} cost of living impact",
            f"{bill_id} housing affordability",
            f"{bill_id} tax implications",
            
            # Comparative queries
            f"similar legislation {bill_id}",
            f"{bill_id} precedent cases",
            
            # TODO: Generate more queries based on bill content
        ]
        
        return queries
    
    async def search_exhaustively(
        self,
        bill_id: str,
        bill_text: str
    ) -> Dict[str, Any]:
        """
        Perform exhaustive research on a bill.
        
        Args:
            bill_id: Bill identifier
            bill_text: Full bill text
        
        Returns:
            Research package for LLM consumption
        """
        queries = self._generate_queries(bill_id, bill_text)
        
        all_results = []
        for query in queries:
            results = await self.search.search(
                query=query,
                count=10,
                domains=["*.gov", "*.ca.gov", "*.edu"],
                recency="1y"
            )
            all_results.extend(results)
        
        # Package for LLM
        return {
            "bill_id": bill_id,
            "total_sources": len(all_results),
            "sources": [r.model_dump() for r in all_results],
            "summary": self._summarize_sources(all_results)
        }
    
    def _summarize_sources(self, results: List) -> str:
        """Create a summary of sources for LLM context."""
        # TODO: Implement summarization
        return f"Found {len(results)} sources"
```

---

## Prime-Radiant-AI Implementation

### 1. Conversation Memory

**File:** `prime-radiant-ai/backend/services/memory.py`

```python
from llm_common import LLMClient
from typing import List, Dict, Any, Optional
from datetime import datetime

class ConversationMemory:
    """
    Manage conversation history for stateful chat.
    
    Features:
    - Persist conversations to Supabase
    - Retrieve last N messages
    - Context injection based on page navigation
    - Conversation summarization (for long histories)
    """
    
    def __init__(
        self,
        db_client: Any,
        user_id: str,
        max_history: int = 20
    ):
        """
        Initialize memory.
        
        Args:
            db_client: Supabase client
            user_id: User identifier
            max_history: Max messages to retrieve
        """
        self.db = db_client
        self.user_id = user_id
        self.max_history = max_history
    
    async def get_context(
        self,
        page: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Get conversation history + page-specific context.
        
        Args:
            page: Current page (e.g., "portfolio", "tax_planning")
        
        Returns:
            List of messages for LLM
        """
        # Retrieve conversation history
        result = self.db.table('conversations').select('*').eq(
            'user_id', self.user_id
        ).order('timestamp', desc=True).limit(self.max_history).execute()
        
        messages = [
            {"role": row['role'], "content": row['content']}
            for row in reversed(result.data)
        ]
        
        # Add page-specific context
        if page:
            context = await self._get_page_context(page)
            if context:
                messages.insert(0, {"role": "system", "content": context})
        
        return messages
    
    async def save_message(
        self,
        role: str,
        content: str
    ):
        """
        Save message to database.
        
        Args:
            role: "user" or "assistant"
            content: Message content
        """
        self.db.table('conversations').insert({
            'user_id': self.user_id,
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        }).execute()
    
    async def _get_page_context(self, page: str) -> Optional[str]:
        """
        Get page-specific context.
        
        Args:
            page: Page identifier
        
        Returns:
            Context string for LLM
        """
        if page == "portfolio":
            portfolio = await self._get_user_portfolio()
            return f"User's current portfolio: {portfolio}"
        
        elif page == "tax_planning":
            tax_info = await self._get_user_tax_info()
            return f"User's tax information: {tax_info}"
        
        # Add more page-specific contexts
        return None
    
    async def _get_user_portfolio(self) -> Dict[str, Any]:
        """Fetch user's portfolio data."""
        result = self.db.table('portfolios').select('*').eq(
            'user_id', self.user_id
        ).execute()
        
        return result.data[0] if result.data else {}
    
    async def _get_user_tax_info(self) -> Dict[str, Any]:
        """Fetch user's tax information."""
        result = self.db.table('user_profiles').select('state, income_bracket').eq(
            'user_id', self.user_id
        ).execute()
        
        return result.data[0] if result.data else {}
    
    async def summarize_history(self, llm_client: LLMClient) -> str:
        """
        Summarize long conversation history.
        
        Args:
            llm_client: LLM client for summarization
        
        Returns:
            Summary string
        """
        # Get full history
        result = self.db.table('conversations').select('*').eq(
            'user_id', self.user_id
        ).order('timestamp').execute()
        
        messages = [
            {"role": row['role'], "content": row['content']}
            for row in result.data
        ]
        
        # Summarize using LLM
        summary = await llm_client.chat(
            messages=[
                {"role": "system", "content": "Summarize this conversation concisely."},
                {"role": "user", "content": str(messages)}
            ],
            model="gpt-4o-mini"  # Cheap model for summarization
        )
        
        return summary
```

---

### 2. Finance Search Service

**File:** `prime-radiant-ai/backend/services/research/finance_search.py`

```python
from llm_common import WebSearchClient
from typing import List, Dict, Any

class FinanceSearchService:
    """
    Domain-specific search service for financial information.
    
    Use cases:
    - Tax brackets by state
    - Retirement account rules
    - Fund prospectuses
    - Economic indicators
    """
    
    def __init__(self, search_client: WebSearchClient):
        """
        Initialize service.
        
        Args:
            search_client: Shared web search client
        """
        self.search = search_client
    
    async def search_tax_rules(self, state: str, year: int = 2024) -> Dict[str, Any]:
        """
        Search for state tax rules.
        
        Args:
            state: State name (e.g., "California")
            year: Tax year
        
        Returns:
            Tax rule data
        """
        queries = [
            f"{state} state tax brackets {year}",
            f"{state} income tax rates {year}",
            f"{state} tax deductions {year}",
            f"{state} capital gains tax {year}"
        ]
        
        results = []
        for query in queries:
            search_results = await self.search.search(
                query=query,
                count=5,
                domains=["*.gov", "*.irs.gov", "*.ftb.ca.gov"],
                recency="1y"
            )
            results.extend(search_results)
        
        return {
            "state": state,
            "year": year,
            "sources": [r.model_dump() for r in results]
        }
    
    async def search_retirement_rules(self, account_type: str) -> Dict[str, Any]:
        """
        Search for retirement account rules.
        
        Args:
            account_type: "401k", "IRA", "Roth IRA", etc.
        
        Returns:
            Retirement rule data
        """
        queries = [
            f"{account_type} contribution limits 2024",
            f"{account_type} withdrawal rules",
            f"{account_type} tax implications",
            f"{account_type} eligibility requirements"
        ]
        
        results = []
        for query in queries:
            search_results = await self.search.search(
                query=query,
                count=5,
                domains=["*.gov", "*.irs.gov"],
                recency="1y"
            )
            results.extend(search_results)
        
        return {
            "account_type": account_type,
            "sources": [r.model_dump() for r in results]
        }
    
    async def search_fund_prospectus(self, ticker: str) -> Dict[str, Any]:
        """
        Search for fund prospectus.
        
        Args:
            ticker: Fund ticker symbol
        
        Returns:
            Prospectus data
        """
        queries = [
            f"{ticker} fund prospectus",
            f"{ticker} expense ratio",
            f"{ticker} holdings",
            f"{ticker} performance history"
        ]
        
        results = []
        for query in queries:
            search_results = await self.search.search(
                query=query,
                count=5,
                domains=["*.sec.gov", "*.morningstar.com"],
                recency="1y"
            )
            results.extend(search_results)
        
        return {
            "ticker": ticker,
            "sources": [r.model_dump() for r in results]
        }
```

---

## Database Schema

### Shared Tables (Supabase)

#### 1. `web_search_cache`

**Purpose:** Persistent cache for web search results.

```sql
CREATE TABLE web_search_cache (
    cache_key TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    results JSONB NOT NULL,
    cached_at TIMESTAMP NOT NULL DEFAULT NOW(),
    hit_count INTEGER DEFAULT 0,
    
    -- Indexes
    INDEX idx_cached_at (cached_at),
    INDEX idx_query (query)
);

-- Cleanup old cache entries (TTL: 24 hours)
CREATE OR REPLACE FUNCTION cleanup_search_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM web_search_cache
    WHERE cached_at < NOW() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql;

-- Schedule cleanup (run daily)
SELECT cron.schedule('cleanup-search-cache', '0 0 * * *', 'SELECT cleanup_search_cache()');
```

---

#### 2. `cost_tracking`

**Purpose:** Track LLM and web search costs.

```sql
CREATE TABLE cost_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model TEXT NOT NULL,
    step TEXT,  -- "research", "generate", "review", "refine"
    cost_usd DECIMAL(10, 6) NOT NULL,
    tokens_used INTEGER,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Metadata
    project TEXT,  -- "affordabot" or "prime-radiant-ai"
    
    -- Indexes
    INDEX idx_timestamp (timestamp),
    INDEX idx_model (model),
    INDEX idx_step (step)
);

-- Get daily cost
CREATE OR REPLACE FUNCTION get_daily_cost(target_date DATE)
RETURNS TABLE(total_cost DECIMAL) AS $$
BEGIN
    RETURN QUERY
    SELECT SUM(cost_usd)::DECIMAL
    FROM cost_tracking
    WHERE DATE(timestamp) = target_date;
END;
$$ LANGUAGE plpgsql;

-- Get monthly cost
CREATE OR REPLACE FUNCTION get_monthly_cost(target_year INT, target_month INT)
RETURNS TABLE(total_cost DECIMAL) AS $$
BEGIN
    RETURN QUERY
    SELECT SUM(cost_usd)::DECIMAL
    FROM cost_tracking
    WHERE EXTRACT(YEAR FROM timestamp) = target_year
      AND EXTRACT(MONTH FROM timestamp) = target_month;
END;
$$ LANGUAGE plpgsql;

-- Get cost breakdown
CREATE OR REPLACE FUNCTION get_cost_breakdown(
    start_date DATE,
    end_date DATE,
    group_by TEXT
)
RETURNS TABLE(group_key TEXT, total_cost DECIMAL) AS $$
BEGIN
    IF group_by = 'model' THEN
        RETURN QUERY
        SELECT model, SUM(cost_usd)::DECIMAL
        FROM cost_tracking
        WHERE DATE(timestamp) BETWEEN start_date AND end_date
        GROUP BY model;
    ELSIF group_by = 'step' THEN
        RETURN QUERY
        SELECT step, SUM(cost_usd)::DECIMAL
        FROM cost_tracking
        WHERE DATE(timestamp) BETWEEN start_date AND end_date
        GROUP BY step;
    END IF;
END;
$$ LANGUAGE plpgsql;
```

---

### Affordabot Tables

#### 3. `pipeline_runs`

**Purpose:** Track analysis pipeline runs for model comparison.

```sql
CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_id TEXT NOT NULL,
    jurisdiction TEXT,
    
    -- Models used
    research_model TEXT,
    generate_model TEXT NOT NULL,
    review_model TEXT NOT NULL,
    
    -- Status
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    
    -- Outputs (JSONB for flexibility)
    analysis_json JSONB,
    review_json JSONB,
    
    -- Quality metrics
    review_passed BOOLEAN,
    quality_score DECIMAL(3, 2),  -- Manual scoring (0.00-1.00)
    
    -- Error tracking
    error_message TEXT,
    
    -- Indexes
    INDEX idx_bill_id (bill_id),
    INDEX idx_status (status),
    INDEX idx_started_at (started_at),
    INDEX idx_generate_model (generate_model),
    INDEX idx_review_model (review_model)
);

-- Model comparison query
CREATE OR REPLACE FUNCTION compare_models(
    start_date DATE,
    end_date DATE,
    step TEXT  -- "generate" or "review"
)
RETURNS TABLE(
    model TEXT,
    avg_quality DECIMAL,
    total_runs BIGINT,
    pass_rate DECIMAL
) AS $$
BEGIN
    IF step = 'generate' THEN
        RETURN QUERY
        SELECT 
            generate_model,
            AVG(quality_score)::DECIMAL,
            COUNT(*)::BIGINT,
            (SUM(CASE WHEN review_passed THEN 1 ELSE 0 END)::DECIMAL / COUNT(*))::DECIMAL
        FROM pipeline_runs
        WHERE DATE(started_at) BETWEEN start_date AND end_date
          AND status = 'completed'
        GROUP BY generate_model;
    ELSIF step = 'review' THEN
        RETURN QUERY
        SELECT 
            review_model,
            AVG(quality_score)::DECIMAL,
            COUNT(*)::BIGINT,
            (SUM(CASE WHEN review_passed THEN 1 ELSE 0 END)::DECIMAL / COUNT(*))::DECIMAL
        FROM pipeline_runs
        WHERE DATE(started_at) BETWEEN start_date AND end_date
          AND status = 'completed'
        GROUP BY review_model;
    END IF;
END;
$$ LANGUAGE plpgsql;
```

---

#### 4. `pipeline_steps`

**Purpose:** Log individual pipeline steps for debugging.

```sql
CREATE TABLE pipeline_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step TEXT NOT NULL CHECK (step IN ('research', 'generate', 'review', 'refine')),
    model TEXT NOT NULL,
    output JSONB,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_run_id (run_id),
    INDEX idx_step (step),
    INDEX idx_timestamp (timestamp)
);
```

---

### Prime-Radiant-AI Tables

#### 5. `conversations`

**Purpose:** Store conversation history for stateful chat.

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Metadata
    page TEXT,  -- Page context (e.g., "portfolio", "tax_planning")
    
    -- Indexes
    INDEX idx_user_id (user_id),
    INDEX idx_timestamp (timestamp)
);

-- Cleanup old conversations (TTL: 90 days)
CREATE OR REPLACE FUNCTION cleanup_conversations()
RETURNS void AS $$
BEGIN
    DELETE FROM conversations
    WHERE timestamp < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;

-- Schedule cleanup (run weekly)
SELECT cron.schedule('cleanup-conversations', '0 0 * * 0', 'SELECT cleanup_conversations()');
```

---

## API Reference

### `llm-common` API

#### `LLMClient`

```python
# Initialize
client = LLMClient(
    provider="openrouter",  # or "zai", "openai", "anthropic"
    api_key="your-key",
    budget_limit_usd=10.0
)

# Chat completion
response = await client.chat(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    model="gpt-4o"
)

# Structured output
class Analysis(BaseModel):
    summary: str
    confidence: float

analysis = await client.chat(
    messages=[...],
    model="claude-3.5-sonnet",
    response_model=Analysis
)

# Fallback chain
response = await client.chat_with_fallback(
    messages=[...],
    models=["gpt-4o", "claude-3.5-sonnet", "glm-4.7"]
)
```

---

#### `WebSearchClient`

```python
# Initialize
search = WebSearchClient(
    api_key="zai-key",
    supabase_client=supabase,
    memory_cache_ttl=3600,  # 1 hour
    db_cache_ttl=86400       # 24 hours
)

# Search
results = await search.search(
    query="California AB 1234 housing",
    count=10,
    domains=["*.gov", "*.edu"],
    recency="1y"
)

# Cache stats
stats = await search.get_cache_stats()
# {"hit_rate": 0.82, "total_searches": 1500, "cache_hits": 1230}
```

---

#### `CostTracker`

```python
# Initialize
tracker = CostTracker(
    supabase_client=supabase,
    daily_budget_usd=10.0,
    monthly_budget_usd=300.0,
    alert_threshold=0.8
)

# Log cost
await tracker.log_cost(CostMetrics(
    model="gpt-4o",
    step="generate",
    cost_usd=0.05,
    tokens_used=1000
))

# Get daily cost
cost = await tracker.get_daily_cost(date.today())

# Get cost breakdown
breakdown = await tracker.get_cost_breakdown(
    start_date=date(2024, 12, 1),
    end_date=date(2024, 12, 31),
    group_by="model"
)
# {"gpt-4o": 50.25, "claude-3.5-sonnet": 30.10, ...}
```

---

## Testing Strategy

### Unit Tests

**Coverage Target:** 80%

**Test Files:**
- `llm-common/tests/test_llm_client.py`
- `llm-common/tests/test_web_search.py`
- `llm-common/tests/test_cost_tracker.py`

**Example:**
```python
import pytest
from llm_common import LLMClient

@pytest.mark.asyncio
async def test_chat_with_structured_output(mocker):
    """Test structured output via instructor."""
    client = LLMClient(provider="openrouter")
    
    # Mock instructor response
    mock_response = BillAnalysis(
        summary="Test summary",
        impacts=[],
        confidence=0.9
    )
    mocker.patch.object(
        client.instructor_client.chat.completions,
        'create',
        return_value=mock_response
    )
    
    # Call
    result = await client.chat(
        messages=[{"role": "user", "content": "Test"}],
        model="gpt-4o",
        response_model=BillAnalysis
    )
    
    # Assert
    assert isinstance(result, BillAnalysis)
    assert result.confidence == 0.9
```

---

### Integration Tests

**Test Scenarios:**
1. **End-to-End Pipeline:** Research → Generate → Review → Refine
2. **Cache Hit Rate:** Verify 80% cache hit rate with realistic queries
3. **Cost Tracking:** Verify costs are logged correctly
4. **Fallback Chain:** Verify fallback works when primary model fails

**Example:**
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline():
    """Test full analysis pipeline."""
    # Setup
    llm = LLMClient(provider="openrouter")
    search = WebSearchClient(api_key="test-key", supabase_client=supabase)
    tracker = CostTracker(supabase_client=supabase)
    
    pipeline = AnalysisPipeline(llm, search, tracker, supabase)
    
    # Run
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
    
    # Assert
    assert isinstance(result, BillAnalysis)
    assert result.confidence > 0.5
    
    # Verify logging
    runs = supabase.table('pipeline_runs').select('*').eq('bill_id', 'AB-1234').execute()
    assert len(runs.data) == 1
```

---

### Manual Testing

**Test Cases:**
1. **Model Comparison:** Run same bill through 3 different models, compare results
2. **Cache Performance:** Monitor cache hit rate over 1 week
3. **Cost Tracking:** Verify daily/monthly costs match expectations
4. **Conversation Memory:** Test conversation continuity across sessions (prime-radiant-ai)

---

## Implementation Checklist

### Phase 1: Shared Package (Week 1)
- [ ] Create `llm-common` package structure
- [ ] Implement `LLMClient` (LiteLLM wrapper)
- [ ] Implement `WebSearchClient` (z.ai + caching)
- [ ] Implement `CostTracker`
- [ ] Write unit tests (80% coverage)
- [ ] Create examples and documentation

### Phase 2: Affordabot Integration (Week 2)
- [ ] Create `AnalysisPipeline` class
- [ ] Create `LegislationSearchService`
- [ ] Update database schema (migrations)
- [ ] Migrate existing `DualModelAnalyzer` to new pipeline
- [ ] Update admin dashboard to use new pipeline
- [ ] Integration tests

### Phase 3: Prime-Radiant-AI Integration (Week 3)
- [ ] Create `ConversationMemory` class
- [ ] Create `FinanceSearchService`
- [ ] Update database schema (migrations)
- [ ] Replace custom LLM client with `llm-common`
- [ ] Update chat endpoints to use memory
- [ ] Integration tests

### Phase 4: Optimization & Documentation (Week 4)
- [ ] Performance testing (latency, throughput)
- [ ] Cost optimization (cache tuning)
- [ ] Model comparison experiments
- [ ] Final documentation
- [ ] Deployment guide

---

## Next Steps

1. **Review this spec** with stakeholders
2. **Create migration plan** (see [LLM_FRAMEWORK_MIGRATION.md](./LLM_FRAMEWORK_MIGRATION.md))
3. **Set up `llm-common` repo** (git submodule)
4. **Begin Phase 1 implementation**

---

## Appendix

### Dependencies

**`llm-common/pyproject.toml`:**
```toml
[tool.poetry.dependencies]
python = "^3.10"
litellm = "^1.0.0"
instructor = "^1.0.0"
openai = "^1.0.0"
pydantic = "^2.0.0"
httpx = "^0.27.0"
tenacity = "^8.0.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
pytest-mock = "^3.0.0"
pytest-cov = "^4.0.0"
```

**Affordabot additions:**
```txt
# Add to backend/requirements.txt
litellm
```

**Prime-Radiant-AI additions:**
```toml
# Add to backend/pyproject.toml
[tool.poetry.dependencies]
litellm = "^1.0.0"
```

---

### Environment Variables

**Shared:**
```bash
# LLM Providers
OPENROUTER_API_KEY=sk-or-...
ZAI_API_KEY=...
OPENAI_API_KEY=sk-...  # Optional
ANTHROPIC_API_KEY=sk-ant-...  # Optional

# Database
SUPABASE_URL=https://...
SUPABASE_SERVICE_ROLE_KEY=...

# Budgets
DAILY_BUDGET_USD=10.0
MONTHLY_BUDGET_USD=300.0
```

**Affordabot-specific:**
```bash
PROJECT_NAME=affordabot
```

**Prime-Radiant-AI-specific:**
```bash
PROJECT_NAME=prime-radiant-ai
```
