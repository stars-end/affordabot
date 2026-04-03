# Common LLM Framework - Comprehensive Implementation Plan
## z.ai + OpenRouter Integration for affordabot & prime-radiant-ai

**Date**: 2025-11-30
**Status**: Specification Complete - Ready for Implementation
**Version**: 1.0

---

## Executive Summary

This document specifies the complete architecture and implementation plan for a shared LLM framework (`llm-common`) that will serve both affordabot and prime-radiant-ai with different provider strategies:

**affordabot Strategy**:
- **Primary**: Direct z.ai API (leveraging paid subscription)
  - Web search for legislation research (1,000-1,500 searches/day)
  - GLM-4.6 models for analysis pipeline
  - Thinking mode for complex reasoning
- **Secondary**: OpenRouter for model comparison/experimentation
  - Test z.ai models via OpenRouter
  - Compare with GPT-4, Claude, Gemini
  - A/B testing for optimal model selection

**prime-radiant-ai Strategy**:
- **Primary**: OpenRouter (broad model access)
  - Financial analysis needs diverse models
  - Free tier available (cost optimization)
  - Access to 400+ models
- **Optional**: z.ai web search for financial news/research

**Shared Infrastructure**:
- `llm-common` Python package
- Unified abstractions and interfaces
- Shared utilities (caching, error handling, cost tracking)
- Zero code duplication between repos

---

## Table of Contents

1. [Requirements Analysis](#requirements-analysis)
2. [Architecture Overview](#architecture-overview)
3. [llm-common Package Design](#llm-common-package-design)
4. [Integration Specifications](#integration-specifications)
5. [Implementation Phases](#implementation-phases)
6. [Testing Strategy](#testing-strategy)
7. [Deployment Strategy](#deployment-strategy)
8. [Cost Analysis](#cost-analysis)
9. [Risk Mitigation](#risk-mitigation)
10. [Success Metrics](#success-metrics)

---

## Requirements Analysis

### affordabot Requirements

#### Functional Requirements

**FR-A1: Legislative Research**
- Must perform 20-30 web searches per legislation item
- Must process 50 legislation items per day (1,000-1,500 searches/day)
- Must support domain filtering (*.gov, *.ca.gov, etc.)
- Must support time-based filtering (last year, last month)
- Must cache search results to reduce costs (target: 80% cache hit rate)

**FR-A2: Analysis Pipeline**
- Three-step pipeline: Research → Generate → Review
- Each step may use different models
- Must support model override per step
- Must support structured outputs (Pydantic models)
- Must support thinking mode for complex reasoning

**FR-A3: Model Experimentation**
- Must support A/B testing across multiple models
- Must track performance metrics per model
- Must support cost comparison
- Must allow easy model switching

**FR-A4: Admin Dashboard Integration**
- Must integrate with existing model configuration system
- Must respect model priority ordering
- Must track task execution history
- Must provide real-time status updates

#### Non-Functional Requirements

**NFR-A1: Performance**
- Web search response time: < 2s per query
- LLM completion time: < 30s for standard analysis
- Pipeline throughput: 50 bills/day minimum
- Concurrent request support: 10 simultaneous analyses

**NFR-A2: Reliability**
- 99.5% uptime for core services
- Automatic retry on transient failures (3 retries with exponential backoff)
- Graceful degradation on provider failures
- Circuit breaker pattern for failing endpoints

**NFR-A3: Cost Management**
- Monthly budget: $500 for web search (with caching: $100)
- Monthly budget: $100-500 for LLM completions (depends on model selection)
- Cost tracking per request
- Budget alerts at 80% threshold

**NFR-A4: Security**
- API keys stored in environment variables (Railway secrets)
- No sensitive data in logs
- Rate limiting to prevent abuse
- Input validation for all LLM prompts

### prime-radiant-ai Requirements

#### Functional Requirements

**FR-P1: Financial Analysis**
- Must support diverse LLM models (GPT-4, Claude, Gemini, z.ai)
- Must provide AI advisor functionality
- Must integrate with existing LLM module
- Must support embeddings for similarity search

**FR-P2: Model Selection**
- Must support free-tier models for development
- Must allow model selection per use case
- Must support fallback to alternative models
- Must maintain existing LLMClient interface

**FR-P3: Cost Optimization**
- Must prioritize free-tier models where possible
- Must track costs per feature
- Must support model degradation (expensive → cheaper)
- Must cache responses where appropriate

#### Non-Functional Requirements

**NFR-P1: Performance**
- LLM response time: < 5s for AI advisor
- Embedding generation: < 1s per text
- Support for streaming responses
- Concurrent user support: 100+ users

**NFR-P2: Maintainability**
- Must preserve existing abstractions (LLMClient, LLMMessage, LLMResponse)
- Must minimize changes to existing code
- Must provide migration path from custom implementation
- Must maintain backward compatibility

**NFR-P3: Scalability**
- Support for increased user base (10x growth)
- Support for new model providers
- Support for new LLM features (multimodal, etc.)
- Horizontal scaling capability

### Shared Requirements

**SR-1: Code Reusability**
- Single source of truth for LLM abstractions
- No code duplication between repos
- Bug fixes propagate to both repos
- Feature additions benefit both repos

**SR-2: Provider Flexibility**
- Easy to add new providers (Anthropic direct, Google AI, etc.)
- Easy to switch providers
- Provider-agnostic application code
- Unified error handling across providers

**SR-3: Developer Experience**
- Clear documentation with examples
- Type hints throughout
- Intuitive API design
- Minimal boilerplate

**SR-4: Observability**
- Structured logging (JSON logs)
- Request/response tracing
- Performance metrics
- Cost tracking

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Applications                             │
├─────────────────────────┬───────────────────────────────────────┤
│     affordabot          │      prime-radiant-ai                 │
│                         │                                        │
│  ┌─────────────────┐   │   ┌─────────────────┐                │
│  │ Analysis        │   │   │ AI Advisor      │                │
│  │ Pipeline        │   │   │ Feature         │                │
│  └────────┬────────┘   │   └────────┬────────┘                │
│           │            │            │                           │
└───────────┼────────────┴────────────┼───────────────────────────┘
            │                         │
            └────────────┬────────────┘
                         │
            ┌────────────▼────────────┐
            │     llm-common          │
            │  (Shared Package)       │
            │                         │
            │  ┌──────────────────┐  │
            │  │ Unified Client   │  │
            │  │  - OpenRouter    │  │
            │  │  - z.ai Direct   │  │
            │  └──────────────────┘  │
            │                         │
            │  ┌──────────────────┐  │
            │  │ Web Search       │  │
            │  │  - z.ai Search   │  │
            │  │  - Result Cache  │  │
            │  └──────────────────┘  │
            │                         │
            │  ┌──────────────────┐  │
            │  │ Utilities        │  │
            │  │  - Error Handler │  │
            │  │  - Cost Tracker  │  │
            │  │  - Retry Logic   │  │
            │  └──────────────────┘  │
            └─────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼─────┐    ┌────▼─────┐    ┌────▼─────┐
   │ z.ai API │    │OpenRouter│    │ Postgres │
   │          │    │   API    │    │  Cache   │
   │ - GLM    │    │          │    │          │
   │ - Search │    │ - z.ai   │    │          │
   │          │    │ - GPT-4  │    │          │
   │          │    │ - Claude │    │          │
   └──────────┘    └──────────┘    └──────────┘
```

### Data Flow

#### affordabot: Legislation Analysis Flow

```
1. User triggers analysis via Admin Dashboard
   ↓
2. Analysis Pipeline (affordabot)
   ├─ Step 1: Research
   │  ├─ Generate research queries (10-30 queries)
   │  ├─ Check cache (Postgres)
   │  ├─ Call z.ai Web Search API (uncached queries)
   │  ├─ Cache results (24hr TTL)
   │  └─ Structure results for LLM consumption
   │
   ├─ Step 2: Generate Analysis
   │  ├─ Select model (z.ai GLM-4.6 direct OR OpenRouter model)
   │  ├─ Build prompt with research data
   │  ├─ Call LLM with structured output (Pydantic)
   │  ├─ Validate response
   │  └─ Store in database
   │
   └─ Step 3: Review
      ├─ Select reviewer model (may differ from generator)
      ├─ Build review prompt with analysis
      ├─ Call LLM with thinking mode (if z.ai)
      ├─ Validate review
      └─ Finalize and store
   ↓
3. Return results to user
```

#### prime-radiant-ai: AI Advisor Flow

```
1. User asks question
   ↓
2. AI Advisor Feature (prime-radiant-ai)
   ├─ Classify query intent
   ├─ Select appropriate model (OpenRouter)
   │  └─ Prefer free tier (z-ai/glm-4.7, deepseek)
   ├─ Check cache (if applicable)
   ├─ Build context with user data
   ├─ Call LLM via OpenRouter
   ├─ Parse response
   └─ Format for UI
   ↓
3. Stream response to user
```

### Component Interaction Matrix

| Component | affordabot | prime-radiant-ai | llm-common | z.ai Direct | OpenRouter | Postgres |
|-----------|------------|------------------|------------|-------------|------------|----------|
| **Analysis Pipeline** | Owner | - | Uses | Uses | Uses | Uses |
| **AI Advisor** | - | Owner | Uses | - | Uses | Uses |
| **Unified Client** | - | - | Owner | Wraps | Wraps | - |
| **Web Search** | Uses | Optional | Provides | Uses | - | Caches |
| **Cost Tracker** | Uses | Uses | Provides | Tracks | Tracks | Stores |
| **Error Handler** | Uses | Uses | Provides | Handles | Handles | - |

---

## llm-common Package Design

### Package Structure

```
llm-common/
├── pyproject.toml              # Poetry/pip configuration
├── README.md                   # Documentation
├── CHANGELOG.md                # Version history
├── LICENSE                     # MIT License
│
├── llm_common/
│   ├── __init__.py            # Public API exports
│   ├── version.py             # Version string
│   │
│   ├── core/                  # Core abstractions
│   │   ├── __init__.py
│   │   ├── client.py          # Abstract LLMClient
│   │   ├── models.py          # LLMMessage, LLMResponse, etc.
│   │   ├── config.py          # Configuration management
│   │   └── exceptions.py      # Custom exceptions
│   │
│   ├── providers/             # Provider implementations
│   │   ├── __init__.py
│   │   ├── base.py           # Base provider class
│   │   ├── zai.py            # z.ai direct client
│   │   ├── openrouter.py     # OpenRouter client
│   │   └── unified.py        # Unified client (facade)
│   │
│   ├── web_search/           # Web search functionality
│   │   ├── __init__.py
│   │   ├── client.py         # Web search client
│   │   ├── models.py         # SearchResult, SearchQuery
│   │   ├── cache.py          # Search result caching
│   │   └── formatters.py     # Format results for LLMs
│   │
│   ├── utils/                # Shared utilities
│   │   ├── __init__.py
│   │   ├── retry.py          # Retry logic with backoff
│   │   ├── cost.py           # Cost tracking utilities
│   │   ├── logging.py        # Structured logging
│   │   ├── validation.py     # Input/output validation
│   │   └── metrics.py        # Performance metrics
│   │
│   └── integrations/         # Framework integrations
│       ├── __init__.py
│       ├── instructor.py     # instructor integration
│       ├── pydantic.py       # Pydantic helpers
│       └── fastapi.py        # FastAPI middleware
│
├── tests/                    # Test suite
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── fixtures/            # Test data
│
├── examples/                # Example usage
│   ├── basic_usage.py
│   ├── structured_output.py
│   ├── web_search.py
│   ├── model_comparison.py
│   └── cost_tracking.py
│
└── docs/                    # Documentation
    ├── index.md
    ├── quickstart.md
    ├── api_reference.md
    ├── providers.md
    ├── web_search.md
    └── migration.md
```

### Core Abstractions

#### LLMClient Interface

**Purpose**: Abstract interface that all providers implement

**Key Methods**:
```python
class LLMClient(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_model: Optional[Type[BaseModel]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate chat completion."""
        pass

    @abstractmethod
    async def embedding(
        self,
        text: str,
        model: Optional[str] = None
    ) -> List[float]:
        """Generate text embedding."""
        pass

    @abstractmethod
    async def stream_completion(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider identifier."""
        pass
```

**Design Rationale**:
- Async by default (modern Python best practice)
- Optional structured output (Pydantic models)
- Streaming support for real-time UX
- Provider-agnostic kwargs for flexibility

#### Data Models

**LLMMessage**:
```python
@dataclass
class LLMMessage:
    """Standardized message format."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: Optional[str] = None  # For tool results
    tool_calls: Optional[List[Dict]] = None  # For assistant tool calls

    def to_dict(self) -> Dict[str, Any]:
        """Convert to OpenAI format."""
        pass

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMMessage":
        """Parse from API response."""
        pass
```

**LLMResponse**:
```python
@dataclass
class LLMResponse:
    """Standardized response format."""

    content: str  # Text content
    usage: Optional[TokenUsage] = None  # Token counts
    finish_reason: Optional[str] = None  # Why completion ended
    model: Optional[str] = None  # Model that generated response
    provider: Optional[str] = None  # Provider name
    cost: Optional[float] = None  # Calculated cost in USD
    latency_ms: Optional[int] = None  # Response time
    structured_data: Optional[BaseModel] = None  # Parsed Pydantic model
    raw_response: Optional[Dict] = field(default=None, repr=False)  # Full API response
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extra data
```

**TokenUsage**:
```python
@dataclass
class TokenUsage:
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def calculate_cost(self, model: str) -> float:
        """Calculate cost based on model pricing."""
        pass
```

**SearchResult**:
```python
@dataclass
class SearchResult:
    """Web search result."""

    title: str
    url: str
    snippet: str
    published_date: Optional[datetime] = None
    domain: Optional[str] = None
    relevance_score: Optional[float] = None
    media_type: Optional[str] = None  # "article", "pdf", etc.

    def to_llm_context(self) -> str:
        """Format for LLM consumption."""
        pass
```

### Provider Implementations

#### z.ai Direct Client

**Class**: `ZaiClient`

**Capabilities**:
- Direct z.ai API access (uses paid subscription)
- OpenAI-compatible interface (uses OpenAI SDK under the hood)
- z.ai-specific features (thinking mode, web search)
- Structured outputs via instructor

**Configuration**:
```python
class ZaiConfig:
    api_key: str  # From ZAI_API_KEY env var
    base_url: str = "https://api.z.ai/api/coding/paas/v4/"
    default_model: str = "glm-4.7"
    use_thinking_mode: bool = False  # Enable for complex reasoning
    timeout: int = 30  # Request timeout
    max_retries: int = 3
```

**Special Features**:
- `thinking` parameter: Enables z.ai's reasoning mode
- `web_search` method: Integrated web search (separate from completions)
- Cost tracking: Automatic cost calculation per request

**Usage Pattern**:
```python
client = ZaiClient(api_key="...")

# Standard completion
response = await client.chat_completion(
    messages=[...],
    model="glm-4.7",
    temperature=0.7
)

# With thinking mode
response = await client.chat_completion(
    messages=[...],
    model="glm-4.7",
    thinking=True  # z.ai-specific
)

# Structured output
response = await client.chat_completion(
    messages=[...],
    response_model=BillAnalysis  # Pydantic model
)
```

#### OpenRouter Client

**Class**: `OpenRouterClient`

**Capabilities**:
- Access to 400+ models (including z.ai via OpenRouter)
- Unified pricing across providers
- OpenAI-compatible interface
- Structured outputs via instructor

**Configuration**:
```python
class OpenRouterConfig:
    api_key: str  # From OPENROUTER_API_KEY env var
    base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "z-ai/glm-4.7"
    site_url: Optional[str] = None  # For rankings
    site_name: Optional[str] = None  # For rankings
    timeout: int = 30
    max_retries: int = 3
```

**Model Selection Strategy**:
```python
class ModelTier(Enum):
    FREE = "free"        # z-ai/glm-4.7, deepseek
    BUDGET = "budget"    # z-ai/glm-4.7, gpt-4o-mini
    STANDARD = "standard"  # gpt-4o, claude-3.5-sonnet
    PREMIUM = "premium"  # gpt-4-turbo, claude-opus
```

**Usage Pattern**:
```python
client = OpenRouterClient(api_key="...")

# Try free models first
response = await client.chat_completion(
    messages=[...],
    model="z-ai/glm-4.7"
)

# Compare models
results = await client.compare_models(
    messages=[...],
    models=["z-ai/glm-4.7", "openai/gpt-4o", "anthropic/claude-3.5-sonnet"],
    response_model=BillAnalysis
)
```

#### Unified Client (Facade)

**Class**: `UnifiedLLMClient`

**Purpose**: Single entry point that intelligently routes to best provider

**Routing Logic**:
```python
class ProviderStrategy(Enum):
    ZAI_FIRST = "zai_first"          # Try z.ai, fallback to OpenRouter
    OPENROUTER_FIRST = "openrouter_first"  # Try OpenRouter, fallback to z.ai
    COST_OPTIMIZED = "cost_optimized"      # Choose cheapest
    QUALITY_OPTIMIZED = "quality_optimized"  # Choose best quality
    AUTO = "auto"                     # Smart routing based on request
```

**Configuration**:
```python
class UnifiedConfig:
    strategy: ProviderStrategy = ProviderStrategy.AUTO
    zai_config: ZaiConfig
    openrouter_config: OpenRouterConfig
    prefer_direct_zai: bool = True  # Prefer direct z.ai when available
    enable_fallback: bool = True
```

**Smart Routing Rules**:
1. **z.ai-specific features** → Always use z.ai direct
   - Web search required
   - Thinking mode enabled
   - GLM-specific models

2. **Model comparison** → Always use OpenRouter
   - Multiple models requested
   - Non-z.ai models specified
   - Experimentation mode

3. **Cost optimization** → Use cheapest available
   - Development/testing
   - High-volume requests
   - Budget constraints

4. **Quality optimization** → Use best available
   - Production analysis
   - Critical decisions
   - User-facing responses

**Usage Pattern**:
```python
client = UnifiedLLMClient(
    zai_api_key="...",
    openrouter_api_key="...",
    strategy=ProviderStrategy.AUTO
)

# Automatically routes to best provider
response = await client.chat_completion(
    messages=[...],
    model="glm-4.7",  # Uses z.ai direct
    thinking=True  # z.ai feature detected → routes to z.ai
)

response = await client.chat_completion(
    messages=[...],
    model="gpt-4o"  # Not on z.ai → routes to OpenRouter
)
```

### Web Search Module

#### Web Search Client

**Class**: `WebSearchClient`

**Capabilities**:
- z.ai Web Search API integration
- Intelligent query generation
- Result caching (Postgres or Redis)
- Result formatting for LLM consumption
- Domain and time filtering

**Configuration**:
```python
class WebSearchConfig:
    api_key: str  # z.ai API key
    cache_backend: Literal["postgres", "redis", "memory"] = "postgres"
    cache_ttl: int = 86400  # 24 hours
    default_result_count: int = 10
    max_concurrent_searches: int = 5
    enable_caching: bool = True
```

**Search Parameters**:
```python
@dataclass
class SearchQuery:
    query: str
    count: int = 10  # Results to return
    domains: Optional[List[str]] = None  # ["*.gov", "*.ca.gov"]
    exclude_domains: Optional[List[str]] = None
    recency: Optional[str] = None  # "1d", "1w", "1m", "1y"
    search_engine: str = "search-prime"  # z.ai search engine
    language: str = "en"
```

**Cache Strategy**:
```python
class CacheStrategy:
    """Define when to use cache vs fresh search."""

    # Cache hits for identical queries within TTL
    enable_exact_match: bool = True

    # Cache hits for similar queries (fuzzy matching)
    enable_fuzzy_match: bool = False
    fuzzy_threshold: float = 0.85

    # Force bypass cache for critical queries
    force_fresh: bool = False

    # Preemptively refresh cache for popular queries
    enable_prefetch: bool = True
```

**Usage Pattern**:
```python
searcher = WebSearchClient(
    api_key="...",
    cache_backend="postgres"
)

# Single search with caching
results = await searcher.search(
    query="California AB 1234 housing regulations",
    domains=["*.gov"],
    recency="1y"
)

# Batch search (parallel with rate limiting)
queries = [f"AB 1234 {aspect}" for aspect in aspects]
results = await searcher.batch_search(queries)

# Format for LLM
context = searcher.format_results_for_llm(
    results,
    include_dates=True,
    include_sources=True,
    max_length=10000  # Token limit
)
```

#### Search Result Cache

**Implementation**: Postgres table or Redis

**Schema** (Postgres):
```sql
CREATE TABLE search_results_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_hash TEXT NOT NULL,  -- SHA256 of normalized query
    query_text TEXT NOT NULL,
    results JSONB NOT NULL,
    result_count INT NOT NULL,
    search_params JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    hit_count INT DEFAULT 0,
    last_accessed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_search_cache_hash ON search_results_cache(query_hash);
CREATE INDEX idx_search_cache_expires ON search_results_cache(expires_at);
```

**Cache Invalidation**:
- Time-based: Expire after TTL (default 24h)
- Manual: API endpoint to clear cache
- Automatic: LRU eviction when storage limit reached

**Cache Metrics**:
- Hit rate: % of queries served from cache
- Cost savings: Avoided search API calls
- Freshness: Average age of cached results

### Utilities

#### Retry Logic

**Class**: `RetryHandler`

**Features**:
- Exponential backoff with jitter
- Provider-specific retry policies
- Circuit breaker pattern
- Retry budget (max retries per time window)

**Configuration**:
```python
class RetryConfig:
    max_retries: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

    # Circuit breaker
    failure_threshold: int = 5  # Open circuit after N failures
    recovery_timeout: int = 60  # Seconds before attempting recovery
```

**Retry Policies by Error Type**:
```python
RETRY_POLICIES = {
    "rate_limit": {
        "retry": True,
        "use_retry_after_header": True,
        "max_delay": 300  # 5 minutes
    },
    "timeout": {
        "retry": True,
        "max_retries": 2
    },
    "server_error": {
        "retry": True,
        "status_codes": [500, 502, 503, 504]
    },
    "authentication": {
        "retry": False  # Don't retry auth failures
    },
    "invalid_request": {
        "retry": False  # Don't retry client errors
    }
}
```

#### Cost Tracker

**Class**: `CostTracker`

**Features**:
- Per-request cost calculation
- Aggregated cost reporting
- Budget alerts
- Cost breakdown by model/provider

**Storage**: Postgres table

**Schema**:
```sql
CREATE TABLE llm_costs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INT NOT NULL,
    completion_tokens INT NOT NULL,
    total_tokens INT NOT NULL,
    cost_usd DECIMAL(10, 6) NOT NULL,
    request_id TEXT,
    user_id TEXT,
    feature_name TEXT,
    metadata JSONB
);

CREATE INDEX idx_llm_costs_timestamp ON llm_costs(timestamp);
CREATE INDEX idx_llm_costs_provider ON llm_costs(provider);
CREATE INDEX idx_llm_costs_user ON llm_costs(user_id);
```

**Cost Calculation**:
```python
# Pricing table (updated periodically)
MODEL_PRICING = {
    "glm-4.7": {
        "input": 0.11,   # per 1M tokens
        "output": 0.28
    },
    "z-ai/glm-4.7": {
        "input": 0.0,
        "output": 0.0
    },
    "gpt-4o": {
        "input": 2.50,
        "output": 10.00
    },
    # ... more models
}
```

**Usage**:
```python
tracker = CostTracker(db_client=postgres)

# Track single request
await tracker.track_request(
    provider="z.ai",
    model="glm-4.7",
    prompt_tokens=1000,
    completion_tokens=500,
    user_id="user_123",
    feature_name="bill_analysis"
)

# Get cost summary
summary = await tracker.get_cost_summary(
    start_date="2025-11-01",
    end_date="2025-11-30",
    group_by="provider"
)
# Returns: {"z.ai": 450.23, "openrouter": 127.89}

# Budget alert
alert = await tracker.check_budget(
    budget_usd=500.0,
    period="month"
)
# Returns: {"spent": 425.50, "remaining": 74.50, "alert": True}
```

#### Structured Logging

**Class**: `LLMLogger`

**Format**: JSON logs for easy parsing

**Log Levels**:
- DEBUG: Detailed request/response data
- INFO: Request summaries, metrics
- WARNING: Retries, fallbacks, slow requests
- ERROR: Failures, exceptions
- CRITICAL: Service outages

**Log Structure**:
```json
{
    "timestamp": "2025-11-30T10:15:30Z",
    "level": "INFO",
    "event": "llm_request",
    "provider": "z.ai",
    "model": "glm-4.7",
    "tokens": {
        "prompt": 1000,
        "completion": 500
    },
    "cost_usd": 0.25,
    "latency_ms": 2500,
    "request_id": "req_abc123",
    "user_id": "user_456",
    "success": true
}
```

**Integration**: Structured logs sent to:
- Local: stdout (development)
- Production: Sentry, DataDog, or CloudWatch

---

## Integration Specifications

### affordabot Integration

#### Current State Analysis

**Existing Components**:
- Admin dashboard with model configuration UI
- Database schema with `model_configs`, `analysis_history` tables
- FastAPI backend with admin router
- Dependencies: `openai`, `instructor` already installed

**Integration Points**:
1. Analysis pipeline (new)
2. Admin router (modify)
3. Background tasks (modify)
4. Database queries (modify)

#### Integration Architecture

**Phase 1: Add llm-common Dependency**

**File**: `backend/requirements.txt`
```
# Add after existing dependencies
llm-common @ git+https://github.com/yourusername/llm-common.git@v1.0.0
# OR if local development:
# -e ../llm-common
```

**Phase 2: Create LLM Service Layer**

**New File**: `backend/services/llm_service.py`

**Purpose**: Facade between affordabot and llm-common

**Responsibilities**:
- Initialize LLM clients with affordabot-specific configuration
- Provide high-level methods for analysis pipeline
- Handle affordabot-specific error cases
- Integrate with existing database models

**Public Interface**:
```python
class LLMService:
    """affordabot LLM service facade."""

    def __init__(self, config: LLMServiceConfig):
        """Initialize with z.ai and OpenRouter clients."""
        pass

    async def research_bill(
        self,
        bill_id: str,
        jurisdiction: str
    ) -> ResearchPackage:
        """Perform web research for legislation."""
        pass

    async def analyze_bill(
        self,
        research: ResearchPackage,
        model: Optional[str] = None,
        use_thinking: bool = False
    ) -> BillAnalysis:
        """Generate bill analysis."""
        pass

    async def review_analysis(
        self,
        analysis: BillAnalysis,
        model: Optional[str] = None
    ) -> ReviewResult:
        """Review and validate analysis."""
        pass

    async def compare_models(
        self,
        research: ResearchPackage,
        models: List[str]
    ) -> Dict[str, BillAnalysis]:
        """A/B test multiple models."""
        pass
```

**Phase 3: Update Admin Router**

**File**: `backend/routers/admin.py` (modify existing)

**Changes**:
1. Import `LLMService` instead of placeholder TODOs
2. Replace background task implementations
3. Add model comparison endpoint
4. Add cost tracking endpoint

**New Endpoints**:
```python
# Already exists, update implementation
POST /admin/analyze
- Replace TODO with actual LLMService.analyze_bill() call

# New endpoint for model comparison
POST /admin/analyze/compare
- Body: {bill_id, jurisdiction, models: List[str]}
- Response: {results: Dict[str, BillAnalysis], recommendation: str}

# New endpoint for cost summary
GET /admin/costs
- Query: start_date, end_date, group_by
- Response: {summary: Dict, budget_status: Dict}
```

**Phase 4: Analysis Pipeline Implementation**

**New File**: `backend/services/analysis_pipeline.py`

**Purpose**: Orchestrate the three-step analysis process

**Pipeline Steps**:
```python
class AnalysisPipeline:
    """Three-step analysis pipeline."""

    async def run(
        self,
        bill_id: str,
        jurisdiction: str,
        config: PipelineConfig
    ) -> AnalysisResult:
        """
        Execute full pipeline:
        1. Research (web search)
        2. Generate (LLM analysis)
        3. Review (validation)
        """

        # Step 1: Research
        research = await self.research_step(bill_id, jurisdiction)

        # Step 2: Generate
        analysis = await self.generate_step(
            research,
            model=config.generation_model,
            use_thinking=config.use_thinking
        )

        # Step 3: Review
        review = await self.review_step(
            analysis,
            model=config.review_model
        )

        # Store results
        await self.store_results(bill_id, research, analysis, review)

        return AnalysisResult(
            research=research,
            analysis=analysis,
            review=review,
            metadata={
                "models_used": {...},
                "total_cost": ...,
                "total_time": ...
            }
        )
```

**Configuration**:
```python
class PipelineConfig:
    """Pipeline configuration."""

    # Model selection
    generation_model: str = "glm-4.7"  # z.ai direct
    review_model: str = "gpt-4o"  # OpenRouter

    # z.ai features
    use_thinking: bool = True  # Enable for generation step

    # Web search
    searches_per_bill: int = 25
    search_domains: List[str] = ["*.gov", "*.ca.gov"]
    search_recency: str = "1y"

    # Caching
    enable_search_cache: bool = True
    search_cache_ttl: int = 86400  # 24 hours

    # Cost control
    max_cost_per_bill: float = 2.00  # USD
    fallback_to_free_model: bool = True
```

#### Database Integration

**New Migrations**:

**Migration 1**: Add cost tracking columns
```sql
-- Add to existing analysis_history table
ALTER TABLE analysis_history ADD COLUMN cost_usd DECIMAL(10, 6);
ALTER TABLE analysis_history ADD COLUMN model_provider TEXT;
ALTER TABLE analysis_history ADD COLUMN tokens_used JSONB;

-- Add search cache table
CREATE TABLE IF NOT EXISTS search_results_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_hash TEXT NOT NULL,
    query_text TEXT NOT NULL,
    results JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);
```

**Migration 2**: Add model comparison results table
```sql
CREATE TABLE IF NOT EXISTS model_comparisons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bill_id TEXT NOT NULL,
    models_compared TEXT[] NOT NULL,
    results JSONB NOT NULL,
    winner_model TEXT,
    comparison_metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Environment Configuration

**File**: `backend/.env` (or Railway secrets)

```bash
# z.ai Configuration
ZAI_API_KEY=sk-your-zai-key-here
ZAI_DEFAULT_MODEL=glm-4.6
ZAI_ENABLE_THINKING=true

# OpenRouter Configuration
OPENROUTER_API_KEY=sk-or-your-openrouter-key
OPENROUTER_DEFAULT_MODEL=z-ai/glm-4.7
OPENROUTER_SITE_NAME=affordabot
OPENROUTER_SITE_URL=https://affordabot.com

# LLM Common Settings
LLM_STRATEGY=zai_first  # Prefer z.ai direct
LLM_ENABLE_FALLBACK=true
LLM_MAX_RETRIES=3

# Web Search Settings
WEB_SEARCH_CACHE_BACKEND=postgres
WEB_SEARCH_CACHE_TTL=86400
WEB_SEARCH_MAX_RESULTS=10

# Cost Control
MONTHLY_BUDGET_USD=500
COST_ALERT_THRESHOLD=0.8
ENABLE_BUDGET_ALERTS=true

# Feature Flags
ENABLE_MODEL_COMPARISON=true
ENABLE_THINKING_MODE=true
ENABLE_SEARCH_CACHING=true
```

### prime-radiant-ai Integration

#### Current State Analysis

**Existing Components**:
- Custom LLM module (`backend/llm/`)
  - `client.py` - Abstract LLMClient + OpenRouterClient
  - `config.py` - LLMConfig
  - `error_handling.py` - Retry logic
  - `cost_tracking.py` - Cost tracking
  - `caching.py` - Response caching
  - `memory.py` - Conversation memory
  - `prompts.py` - Prompt templates
  - `validation.py` - Response validation
- Dependencies: `httpx` (Poetry managed)

**Integration Strategy**: **Gradual Migration**

**Rationale**:
- Preserve working code
- Minimize risk
- Allow side-by-side comparison
- Easy rollback if issues

#### Integration Architecture

**Phase 1: Add llm-common as Dependency**

**File**: `backend/pyproject.toml` (modify)

```toml
[tool.poetry.dependencies]
# ... existing dependencies ...
llm-common = {git = "https://github.com/yourusername/llm-common.git", tag = "v1.0.0"}
# OR for local development:
# llm-common = {path = "../llm-common", develop = true}
```

**Phase 2: Create Compatibility Layer**

**Purpose**: Allow gradual migration without breaking existing code

**New File**: `backend/llm/llm_common_adapter.py`

**Responsibilities**:
- Implement existing `LLMClient` interface using llm-common
- Preserve existing method signatures
- Proxy calls to llm-common clients
- Allow feature flag to switch between old and new implementation

**Public Interface**:
```python
class LLMCommonAdapter(LLMClient):
    """
    Adapter that makes llm-common compatible with existing code.

    Implements prime-radiant-ai's LLMClient interface but
    delegates to llm-common's UnifiedLLMClient under the hood.
    """

    def __init__(self, api_key: str, default_model: str, base_url: str):
        """Initialize with existing signature."""
        # Detect provider from base_url
        if "openrouter" in base_url:
            self._provider = "openrouter"
        elif "z.ai" in base_url:
            self._provider = "zai"

        # Initialize llm-common client
        from llm_common import UnifiedLLMClient
        self._client = UnifiedLLMClient(...)

    async def chat_completion(self, messages, model=None, temperature=None, max_tokens=None, **kwargs):
        """Existing method signature preserved."""
        # Convert existing LLMMessage format to llm-common format
        # Call llm-common
        # Convert response back to existing format
        pass
```

**Phase 3: Feature Flag for Gradual Rollout**

**File**: `backend/config/llm_config.py` (modify)

```python
class LLMConfig:
    # ... existing config ...

    # NEW: Feature flag
    USE_LLM_COMMON: bool = os.getenv("USE_LLM_COMMON", "false").lower() == "true"
```

**File**: `backend/config/llm_config.py` - `get_llm_client()` (modify)

```python
def get_llm_client():
    """Factory function with feature flag."""

    if not LLMConfig.LLM_ENABLED:
        raise ValueError("LLM not enabled")

    # NEW: Check feature flag
    if LLMConfig.USE_LLM_COMMON:
        # Use new llm-common implementation
        from llm.llm_common_adapter import LLMCommonAdapter

        if LLMConfig.OPENROUTER_API_KEY:
            return LLMCommonAdapter(
                api_key=LLMConfig.OPENROUTER_API_KEY,
                default_model=LLMConfig.OPENROUTER_DEFAULT_MODEL,
                base_url=LLMConfig.OPENROUTER_BASE_URL
            )
    else:
        # Use existing implementation (current behavior)
        from llm.client import OpenRouterClient

        if LLMConfig.OPENROUTER_API_KEY:
            return OpenRouterClient(
                api_key=LLMConfig.OPENROUTER_API_KEY,
                default_model=LLMConfig.OPENROUTER_DEFAULT_MODEL,
                base_url=LLMConfig.OPENROUTER_BASE_URL
            )

    # ... rest of existing code ...
```

**Phase 4: Side-by-Side Testing**

**New File**: `backend/tests/test_llm_migration.py`

**Purpose**: Verify llm-common adapter produces same results as existing implementation

**Test Cases**:
1. Same input → same output
2. Error handling behaves identically
3. Cost tracking matches
4. Performance is comparable

**Phase 5: Complete Migration (Future)**

**Once validated**:
1. Set `USE_LLM_COMMON=true` in production
2. Monitor for issues
3. After stable period, remove old implementation
4. Update imports to use llm-common directly

#### Preserving Existing Features

**Features to Port**:

1. **Cost Tracking** (`cost_tracking.py`)
   - Already built into llm-common
   - Just need to configure storage backend

2. **Caching** (`caching.py`)
   - llm-common has caching for web search
   - May need to add response caching if missing

3. **Memory** (`memory.py`)
   - Conversation history management
   - Keep existing implementation (not in llm-common)

4. **Prompts** (`prompts.py`)
   - Prompt templates and management
   - Keep existing implementation (not in llm-common)

5. **Validation** (`validation.py`)
   - Response validation logic
   - Keep existing implementation (domain-specific)

**Migration Strategy**:
- **Migrate**: Client interface, API calls, error handling
- **Keep**: Domain-specific logic (prompts, memory, validation)
- **Enhance**: Cost tracking (use llm-common's improved version)

### Code Sharing Mechanism

#### Option 1: Git Submodule (Recommended for MVP)

**Setup**:
```bash
# In each repo
cd ~/affordabot
git submodule add https://github.com/yourusername/llm-common.git lib/llm-common

cd ~/prime-radiant-ai
git submodule add https://github.com/yourusername/llm-common.git lib/llm-common
```

**Installation**:
```bash
# affordabot
cd ~/affordabot
pip install -e lib/llm-common

# prime-radiant-ai
cd ~/prime-radiant-ai
poetry add lib/llm-common --develop
```

**Pros**:
- ✅ Simple setup
- ✅ Version pinning
- ✅ Works with existing repo structure
- ✅ Easy local development

**Cons**:
- ❌ Requires submodule awareness
- ❌ Extra git commands (`git submodule update`)

#### Option 2: Separate PyPI Package (Future)

**When to Use**: After MVP, when stable

**Setup**:
```bash
# Publish to PyPI
cd llm-common
poetry build
poetry publish

# Install in repos
pip install llm-common
poetry add llm-common
```

**Pros**:
- ✅ Standard Python workflow
- ✅ Version management via pip/poetry
- ✅ No git submodule complexity

**Cons**:
- ❌ Requires PyPI account
- ❌ Publishing overhead
- ❌ Slower iteration during development

#### Option 3: Monorepo (Not Recommended)

**Structure**:
```
workspace/
├── llm-common/
├── affordabot/
└── prime-radiant-ai/
```

**Pros**:
- ✅ Single repo
- ✅ Easy to make changes across projects

**Cons**:
- ❌ Restructuring existing repos
- ❌ Loss of independent histories
- ❌ Complex CI/CD
- ❌ Not recommended for this use case

**Decision**: Use **Git Submodule** for initial implementation

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Objective**: Create llm-common package with core functionality

**Tasks**:

1. **Setup Package Structure** (Day 1)
   - Create `llm-common` repository
   - Setup Poetry/pip configuration
   - Create directory structure
   - Initialize git repository
   - Setup CI/CD (GitHub Actions)

2. **Implement Core Abstractions** (Day 2-3)
   - `LLMClient` abstract class
   - `LLMMessage`, `LLMResponse` data classes
   - `TokenUsage`, `SearchResult` models
   - Configuration classes
   - Custom exceptions

3. **Implement z.ai Client** (Day 4-5)
   - `ZaiClient` class
   - OpenAI SDK integration
   - instructor integration
   - Thinking mode support
   - Unit tests

4. **Implement OpenRouter Client** (Day 6-7)
   - `OpenRouterClient` class
   - Model tier system
   - instructor integration
   - Unit tests

5. **Implement Unified Client** (Day 8-9)
   - `UnifiedLLMClient` facade
   - Smart routing logic
   - Fallback handling
   - Unit tests

6. **Implement Web Search** (Day 10-12)
   - `WebSearchClient` class
   - z.ai Web Search API integration
   - Cache implementation (Postgres)
   - Result formatting
   - Unit tests

7. **Implement Utilities** (Day 13-14)
   - Retry logic with backoff
   - Cost tracking
   - Structured logging
   - Performance metrics
   - Unit tests

**Deliverables**:
- ✅ Working llm-common package
- ✅ 100% unit test coverage
- ✅ Documentation (API reference)
- ✅ Example scripts
- ✅ PyPI-ready (but not published yet)

**Success Criteria**:
- All unit tests pass
- Can install via `pip install -e .`
- Example scripts run successfully
- Documentation is complete

### Phase 2: affordabot Integration (Week 3-4)

**Objective**: Integrate llm-common into affordabot and implement analysis pipeline

**Tasks**:

1. **Setup Integration** (Day 1)
   - Add llm-common as git submodule
   - Update requirements.txt
   - Configure environment variables
   - Test import in Python REPL

2. **Create Service Layer** (Day 2-3)
   - Implement `LLMService` facade
   - Implement `AnalysisPipeline`
   - Configure z.ai + OpenRouter clients
   - Unit tests for service layer

3. **Implement Research Step** (Day 4-5)
   - Generate research queries
   - Call web search API
   - Implement caching
   - Format results for LLMs
   - Integration tests

4. **Implement Generate Step** (Day 6-7)
   - Implement bill analysis prompts
   - Call LLM with structured output
   - Store results in database
   - Integration tests

5. **Implement Review Step** (Day 8-9)
   - Implement review prompts
   - Call LLM with thinking mode
   - Validate and store results
   - Integration tests

6. **Update Admin Router** (Day 10-11)
   - Replace TODO implementations
   - Add model comparison endpoint
   - Add cost tracking endpoint
   - API tests

7. **Database Migration** (Day 12)
   - Create migration files
   - Add cost tracking columns
   - Add search cache table
   - Test migrations

8. **End-to-End Testing** (Day 13-14)
   - Test full pipeline manually
   - Test via admin dashboard
   - Load testing (50 bills)
   - Bug fixes

**Deliverables**:
- ✅ Working analysis pipeline
- ✅ Admin dashboard integration
- ✅ Database migrations applied
- ✅ Integration tests passing
- ✅ Documentation updated

**Success Criteria**:
- Can analyze legislation end-to-end
- Web search caching works (80% hit rate target)
- Cost tracking accurate
- Admin dashboard shows results

### Phase 3: prime-radiant-ai Integration (Week 5-6)

**Objective**: Integrate llm-common into prime-radiant-ai with gradual migration

**Tasks**:

1. **Setup Integration** (Day 1)
   - Add llm-common as Poetry dependency
   - Configure environment variables
   - Test import

2. **Create Adapter** (Day 2-3)
   - Implement `LLMCommonAdapter`
   - Preserve existing interface
   - Unit tests

3. **Add Feature Flag** (Day 4)
   - Modify `get_llm_client()`
   - Add `USE_LLM_COMMON` config
   - Test both code paths

4. **Side-by-Side Testing** (Day 5-7)
   - Run both implementations in parallel
   - Compare outputs
   - Compare performance
   - Compare costs
   - Fix any discrepancies

5. **Enable in Development** (Day 8)
   - Set `USE_LLM_COMMON=true` in dev
   - Monitor for issues
   - Fix bugs

6. **Enable in Production** (Day 9-10)
   - Gradual rollout (10% → 50% → 100%)
   - Monitor metrics
   - Rollback plan ready

7. **Cleanup** (Day 11-12)
   - Remove old implementation (if stable)
   - Update imports
   - Remove feature flag
   - Update documentation

**Deliverables**:
- ✅ llm-common integrated
- ✅ Existing features preserved
- ✅ Adapter working correctly
- ✅ Production-ready

**Success Criteria**:
- AI advisor works identically
- No regressions in functionality
- Performance is comparable
- Cost tracking works

### Phase 4: Optimization & Polish (Week 7-8)

**Objective**: Optimize performance, reduce costs, improve observability

**Tasks**:

1. **Performance Optimization** (Day 1-3)
   - Profile slow requests
   - Optimize web search caching
   - Implement request batching
   - Add connection pooling
   - Load testing

2. **Cost Optimization** (Day 4-5)
   - Analyze cost breakdown
   - Implement smart model selection
   - Increase cache hit rate
   - Add cost budgets per feature
   - Cost alerts

3. **Observability** (Day 6-7)
   - Setup structured logging
   - Add performance metrics
   - Create monitoring dashboards
   - Setup alerts
   - Error tracking (Sentry)

4. **Documentation** (Day 8-10)
   - User guides for both repos
   - API documentation
   - Architecture diagrams
   - Troubleshooting guides
   - Video walkthrough

5. **Security Audit** (Day 11-12)
   - Review API key handling
   - Input validation
   - Rate limiting
   - Secrets management
   - Security best practices

6. **Final Testing** (Day 13-14)
   - End-to-end testing both repos
   - Load testing
   - Failover testing
   - Documentation review
   - Sign-off

**Deliverables**:
- ✅ Optimized performance
- ✅ Reduced costs
- ✅ Monitoring dashboards
- ✅ Complete documentation
- ✅ Production-ready

**Success Criteria**:
- 80% cache hit rate for web search
- < $200/month total LLM costs (with optimization)
- All metrics tracked
- Documentation complete

---

## Testing Strategy

### Unit Tests

**Scope**: Individual functions and classes

**Framework**: pytest

**Coverage Target**: 90%+

**Key Test Areas**:

1. **Client Implementations**
   ```python
   def test_zai_client_chat_completion():
       """Test z.ai client basic completion."""
       client = ZaiClient(api_key="test-key")
       response = await client.chat_completion(
           messages=[LLMMessage(role="user", content="Hello")]
       )
       assert isinstance(response, LLMResponse)
       assert response.provider == "z.ai"
   ```

2. **Web Search**
   ```python
   def test_web_search_caching():
       """Test search result caching."""
       searcher = WebSearchClient(cache_backend="memory")

       # First call - cache miss
       result1 = await searcher.search("test query")
       assert searcher.cache_stats["misses"] == 1

       # Second call - cache hit
       result2 = await searcher.search("test query")
       assert searcher.cache_stats["hits"] == 1
       assert result1 == result2
   ```

3. **Cost Tracking**
   ```python
   def test_cost_calculation():
       """Test cost calculation for different models."""
       usage = TokenUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)

       cost_glm = usage.calculate_cost("glm-4.7")
       assert cost_glm == 0.00025  # (1000*0.11 + 500*0.28) / 1M

       cost_gpt4 = usage.calculate_cost("gpt-4o")
       assert cost_gpt4 > cost_glm  # GPT-4 is more expensive
   ```

**Mock Strategy**:
- Mock external APIs (z.ai, OpenRouter)
- Use fixtures for common test data
- Avoid network calls in unit tests

### Integration Tests

**Scope**: Multiple components working together

**Environment**: Requires API keys (use test accounts)

**Key Test Areas**:

1. **End-to-End LLM Call**
   ```python
   @pytest.mark.integration
   async def test_zai_completion_with_instructor():
       """Test z.ai with structured output."""
       client = ZaiClient(api_key=os.getenv("ZAI_API_KEY"))

       class Analysis(BaseModel):
           summary: str
           sentiment: Literal["positive", "negative", "neutral"]

       response = await client.chat_completion(
           messages=[...],
           response_model=Analysis
       )

       assert isinstance(response.structured_data, Analysis)
       assert response.structured_data.sentiment in ["positive", "negative", "neutral"]
   ```

2. **Pipeline Integration**
   ```python
   @pytest.mark.integration
   async def test_full_analysis_pipeline():
       """Test complete affordabot pipeline."""
       pipeline = AnalysisPipeline(config=test_config)

       result = await pipeline.run(
           bill_id="AB 1234",
           jurisdiction="california"
       )

       assert result.research is not None
       assert result.analysis is not None
       assert result.review is not None
       assert result.metadata["total_cost"] > 0
   ```

3. **Fallback Testing**
   ```python
   @pytest.mark.integration
   async def test_provider_fallback():
       """Test fallback from z.ai to OpenRouter."""
       client = UnifiedLLMClient(strategy=ProviderStrategy.ZAI_FIRST)

       # Simulate z.ai failure
       with patch.object(client._zai_client, 'chat_completion', side_effect=ProviderError):
           response = await client.chat_completion(messages=[...])

           # Should fallback to OpenRouter
           assert response.provider == "openrouter"
   ```

### Load Tests

**Tool**: Locust or Apache Bench

**Scenarios**:

1. **affordabot Load Test**
   - Simulate 50 concurrent bill analyses
   - Target: Complete within 2 hours
   - Monitor: Cost, errors, latency

2. **Web Search Load Test**
   - 1,500 searches over 1 hour
   - Target: 80% cache hit rate
   - Monitor: Cache performance, API costs

3. **Sustained Load**
   - Run for 24 hours
   - Detect memory leaks
   - Verify error recovery

### Manual Testing Checklist

**affordabot**:
- [ ] Trigger analysis via admin dashboard
- [ ] Verify web search results cached
- [ ] Check database for stored results
- [ ] Verify cost tracking accurate
- [ ] Test model comparison feature
- [ ] Test with invalid bill ID (error handling)

**prime-radiant-ai**:
- [ ] Ask AI advisor question
- [ ] Verify response quality unchanged
- [ ] Check feature flag switching
- [ ] Verify cost tracking works
- [ ] Test with different models
- [ ] Test error scenarios

---

## Deployment Strategy

### Development Environment

**Setup**:
```bash
# Clone repos with submodules
git clone --recursive https://github.com/yourusername/affordabot.git
git clone --recursive https://github.com/yourusername/prime-radiant-ai.git

# Install llm-common in development mode
cd affordabot
pip install -e lib/llm-common

cd ../prime-radiant-ai
poetry install
```

**Environment Variables** (`.env.development`):
```bash
# Use test API keys with limited quotas
ZAI_API_KEY=sk-test-...
OPENROUTER_API_KEY=sk-test-...

# Enable debug logging
LOG_LEVEL=DEBUG

# Use memory cache for faster development
WEB_SEARCH_CACHE_BACKEND=memory

# Enable feature flags
USE_LLM_COMMON=true
ENABLE_MODEL_COMPARISON=true
```

### Staging Environment

**Hosted on**: Railway (same as production)

**Configuration**:
- Use production-like API keys (separate billing)
- Enable all features
- Use Postgres staging database
- Monitor costs

**Purpose**:
- Final testing before production
- Load testing
- Performance validation
- Cost estimation

### Production Deployment

#### affordabot Deployment

**Platform**: Railway

**Deployment Process**:
1. Merge to `master` branch
2. Railway auto-deploys via GitHub integration
3. Run database migrations automatically
4. Health check verifies deployment
5. Monitor for errors (first 24 hours)

**Environment Variables** (Railway Secrets):
```bash
# Production API keys
ZAI_API_KEY=${ZAI_PRODUCTION_KEY}
OPENROUTER_API_KEY=${OPENROUTER_PRODUCTION_KEY}

# Database
DATABASE_URL=${DATABASE_URL}

# Caching
WEB_SEARCH_CACHE_BACKEND=postgres
WEB_SEARCH_CACHE_TTL=86400

# Cost control
MONTHLY_BUDGET_USD=500
ENABLE_BUDGET_ALERTS=true

# Logging
LOG_LEVEL=INFO
SENTRY_DSN=${SENTRY_DSN}
```

**Health Checks**:
```python
# Endpoint: GET /health
{
    "status": "healthy",
    "llm_common_version": "1.0.0",
    "providers": {
        "zai": "connected",
        "openrouter": "connected"
    },
    "cache": {
        "backend": "postgres",
        "hit_rate": 0.82
    }
}
```

#### prime-radiant-ai Deployment

**Platform**: TBD (Railway or Vercel)

**Deployment Process**:
1. Merge to `master`
2. Auto-deploy via CI/CD
3. Feature flag gradual rollout:
   - 10% traffic → new implementation
   - Monitor for 24 hours
   - 50% traffic → if stable
   - Monitor for 24 hours
   - 100% traffic → full rollout

**Rollback Plan**:
- Set `USE_LLM_COMMON=false`
- Redeploy within 5 minutes
- Old implementation takes over

### Database Migrations

**Tool**: Postgres migrations or Alembic

**Process**:
```bash
# Generate migration
cd affordabot/postgres
postgres db diff --file 20251201_add_llm_features

# Review migration SQL
cat migrations/20251201_add_llm_features.sql

# Test migration in staging
postgres db push --staging

# Apply to production
postgres db push --production
```

**Rollback**:
- Keep reverse migrations ready
- Test rollback in staging first

### Monitoring Setup

**Metrics to Track**:

1. **Performance**
   - LLM request latency (p50, p95, p99)
   - Web search latency
   - Cache hit rate
   - Error rate

2. **Cost**
   - Daily spending
   - Cost per bill analyzed
   - Budget utilization %

3. **Usage**
   - Requests per day
   - Top models used
   - Cache hits/misses

**Alerting Rules**:
- Error rate > 5% → Page on-call
- Cost > 80% of budget → Email alert
- Cache hit rate < 70% → Email alert
- API downtime → Page on-call

**Dashboard**: Grafana or Datadog

---

## Cost Analysis

### Monthly Cost Projections

#### affordabot Costs

**Scenario 1: Free Models Only**

| Component | Provider | Model | Usage | Cost |
|-----------|----------|-------|-------|------|
| Web Search | z.ai | - | 1,500/day | $450 |
| Generation | OpenRouter | glm-4.7 | 50 bills/day | $0 |
| Review | OpenRouter | deepseek-r1:free | 50 bills/day | $0 |
| **Total** | | | | **$450/month** |

**With 80% cache hit rate**:
- Web Search: 300 actual searches/day = $90/month
- **Total: $90/month**

**Scenario 2: Mixed Models**

| Component | Provider | Model | Usage | Cost |
|-----------|----------|-------|-------|------|
| Web Search | z.ai | - | 300/day (80% cached) | $90 |
| Generation | z.ai Direct | glm-4.6 | 50 bills/day, 2M tokens | $300 |
| Review | OpenRouter | gpt-4o | 25 bills/day, 1M tokens | $62 |
| **Total** | | | | **$452/month** |

**Scenario 3: Premium Models**

| Component | Provider | Model | Usage | Cost |
|-----------|----------|-------|-------|------|
| Web Search | z.ai | - | 300/day (cached) | $90 |
| Generation | OpenRouter | gpt-4o | 50 bills/day, 2M tokens | $500 |
| Review | OpenRouter | claude-3.5-sonnet | 50 bills/day, 1M tokens | $450 |
| **Total** | | | | **$1,040/month** |

#### prime-radiant-ai Costs

**Current Usage**: Light (AI advisor feature)

**Projected**:

| Feature | Model | Usage | Cost |
|---------|-------|-------|------|
| AI Advisor | glm-4.7 | 1,000 requests/month | $0 |
| Embeddings | text-embedding-3-small | 100k texts/month | $1 |
| **Total** | | | **$1/month** |

#### Total Project Costs

**MVP (Free Models + Caching)**:
- affordabot: $90/month
- prime-radiant-ai: $1/month
- **Total: ~$91/month**

**Balanced (Mixed Models)**:
- affordabot: $450/month
- prime-radiant-ai: $1/month
- **Total: ~$451/month**

**Premium (Best Models)**:
- affordabot: $1,040/month
- prime-radiant-ai: $50/month
- **Total: ~$1,090/month**

### Cost Optimization Strategies

1. **Aggressive Caching**
   - Target: 90% cache hit rate
   - Savings: $360/month on web search

2. **Smart Model Selection**
   - Use free models for simple tasks
   - Use premium models only when needed
   - Savings: $500-700/month

3. **Batch Processing**
   - Process bills in batches
   - Reuse context across analyses
   - Savings: 20-30% on LLM costs

4. **Prompt Optimization**
   - Shorter prompts = fewer tokens
   - Better prompts = fewer retries
   - Savings: 10-20% on LLM costs

### Break-Even Analysis

**z.ai Subscription Cost**: ~$20-50/month (assumption)

**Alternative (Exa Search)**:
- Base: $225/month (45k searches)
- Content extraction: +$100-200/month
- Total: $325-425/month

**Conclusion**: Using z.ai web search saves $275-375/month vs alternatives, making the subscription a no-brainer.

---

## Risk Mitigation

### Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Provider API downtime** | High - System unusable | Medium | Implement fallback to alternative provider; Circuit breaker pattern |
| **Rate limiting** | Medium - Degraded performance | High | Implement retry with backoff; Request queueing; Monitor rate limits |
| **Cost overrun** | High - Budget exceeded | Medium | Cost tracking with alerts; Budget limits; Model degradation |
| **Cache invalidation bugs** | Low - Stale data | Low | Short TTL (24h); Manual invalidation endpoint; Version cache keys |
| **Migration bugs (prime-radiant-ai)** | High - Breaking changes | Low | Feature flag; Side-by-side testing; Gradual rollout |
| **Data quality issues** | Medium - Poor analysis | Medium | Structured outputs; Validation; Review step |

### Mitigation Strategies

**1. Provider Fallback**
```python
# Unified client handles this automatically
try:
    response = await zai_client.chat_completion(...)
except ProviderError:
    log.warning("z.ai failed, falling back to OpenRouter")
    response = await openrouter_client.chat_completion(...)
```

**2. Cost Guardrails**
```python
# Check budget before expensive operation
if cost_tracker.projected_monthly_cost() > BUDGET_LIMIT:
    # Fallback to cheaper model
    model = "glm-4.7"
else:
    model = "gpt-4o"
```

**3. Graceful Degradation**
```python
# If LLM fails, return cached/default response
try:
    analysis = await llm.analyze(...)
except Exception as e:
    log.error("LLM failed", error=e)
    analysis = get_cached_analysis() or default_analysis
```

### Operational Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Insufficient documentation** | High - Confusion | Medium | Comprehensive docs; Video tutorials; Examples |
| **Knowledge silos** | Medium - Bus factor | Low | Documentation; Code reviews; Pair programming |
| **Dependency updates** | Low - Breaking changes | High | Pin versions; Test updates in staging; Changelog review |
| **Security vulnerabilities** | High - Data breach | Low | Security audit; Input validation; Rate limiting |

---

## Success Metrics

### Key Performance Indicators (KPIs)

**Technical KPIs**:

1. **Reliability**
   - Uptime: > 99.5%
   - Error rate: < 1%
   - Cache hit rate: > 80%

2. **Performance**
   - LLM latency p95: < 5s
   - Web search latency p95: < 2s
   - Pipeline throughput: 50+ bills/day

3. **Cost**
   - Monthly LLM cost: < $500
   - Cost per bill: < $10
   - Budget utilization: 80-95%

**Business KPIs**:

1. **affordabot**
   - Bills analyzed per day: 50+
   - Analysis quality score: > 4.0/5
   - Time saved vs manual: > 90%

2. **prime-radiant-ai**
   - AI advisor usage: Maintained or increased
   - User satisfaction: No regression
   - Response quality: Maintained

### Success Criteria

**Phase 1 Success** (Foundation):
- ✅ llm-common package installable
- ✅ All unit tests pass
- ✅ Documentation complete
- ✅ Example scripts work

**Phase 2 Success** (affordabot):
- ✅ Analysis pipeline functional
- ✅ Web search caching works
- ✅ Cost tracking accurate
- ✅ Admin dashboard integrated

**Phase 3 Success** (prime-radiant-ai):
- ✅ No regressions in existing features
- ✅ Adapter works correctly
- ✅ Gradual rollout successful
- ✅ Old code removable

**Phase 4 Success** (Optimization):
- ✅ Cache hit rate > 80%
- ✅ Costs optimized (< $200/month)
- ✅ Monitoring dashboards live
- ✅ Documentation complete

---

## Appendices

### Appendix A: API Reference Outline

**llm-common API**:
- `LLMClient` - Abstract interface
- `ZaiClient` - z.ai direct
- `OpenRouterClient` - OpenRouter
- `UnifiedLLMClient` - Facade
- `WebSearchClient` - Web search
- `CostTracker` - Cost tracking
- `RetryHandler` - Retry logic

### Appendix B: Configuration Reference

**Environment Variables**:
- `ZAI_API_KEY` - z.ai API key
- `OPENROUTER_API_KEY` - OpenRouter API key
- `LLM_STRATEGY` - Provider strategy
- `WEB_SEARCH_CACHE_BACKEND` - Cache backend
- `MONTHLY_BUDGET_USD` - Budget limit
- [Full list in specification]

### Appendix C: Troubleshooting Guide

**Common Issues**:
1. Import errors → Check installation
2. API errors → Verify API keys
3. Cache misses → Check TTL settings
4. High costs → Review model selection
5. [Full guide to be written]

### Appendix D: Migration Checklist

**affordabot**:
- [ ] Add llm-common submodule
- [ ] Update requirements.txt
- [ ] Set environment variables
- [ ] Create LLMService
- [ ] Update admin router
- [ ] Run database migrations
- [ ] Test end-to-end
- [ ] Deploy to staging
- [ ] Deploy to production

**prime-radiant-ai**:
- [ ] Add llm-common dependency
- [ ] Create adapter
- [ ] Add feature flag
- [ ] Test side-by-side
- [ ] Enable in dev
- [ ] Enable in production
- [ ] Remove old code

---

## Document Approval

**Prepared By**: Claude (AI Assistant)
**Review Required**: Engineering Team, Product Owner
**Approval Required**: Technical Lead

**Version History**:
- v1.0 (2025-11-30): Initial comprehensive specification

---

**End of Specification**
