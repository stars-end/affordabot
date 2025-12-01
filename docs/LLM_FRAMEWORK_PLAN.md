# Common LLM Framework Plan
## Analysis for prime-radiant-ai and affordabot

**Date**: 2025-11-30
**Status**: Research Complete - Ready for Discussion

---

## Executive Summary

After analyzing both repos and researching modern LLM frameworks, **I recommend using OpenRouter + instructor** as a shared lightweight approach that avoids reinventing the wheel while supporting all required providers (OpenRouter models, z.ai, OpenAI, Anthropic).

---

## Current State Analysis

### prime-radiant-ai

**Status**: ✅ Custom LLM abstraction implemented

**Implementation**:
- **Location**: `backend/llm/` module (8 files)
- **Architecture**: Abstract `LLMClient` base class with provider-specific implementations
- **Providers**: OpenRouter (implemented), OpenAI (stub)
- **Features**:
  - Standardized `LLMMessage` and `LLMResponse` data classes
  - Error handling with retry logic (`llm/error_handling.py`)
  - Cost tracking (`llm/cost_tracking.py`)
  - Caching (`llm/caching.py`)
  - Memory management (`llm/memory.py`)
  - Configuration management (`config/llm_config.py`)
- **HTTP Client**: Custom `httpx.AsyncClient` implementation
- **Dependencies**: `httpx` (Poetry managed)
- **Test Coverage**: `tests/test_llm.py`, `tests/manual/test_openrouter_live.py`

**Key Code**:
```python
# Factory pattern for client selection
def get_llm_client() -> LLMClient:
    if LLMConfig.OPENROUTER_API_KEY:
        return OpenRouterClient(...)
    if LLMConfig.OPENAI_API_KEY:
        return OpenAIClient(...)
```

### affordabot

**Status**: ⏳ Dependencies ready, implementation pending

**Dependencies** (in `requirements.txt`):
- `openai` - OpenAI Python SDK
- `instructor` - Structured LLM outputs library

**Current Usage**:
- Admin dashboard has model configuration management (`backend/routers/admin.py`)
- Database schema ready (`model_configs` table)
- No actual LLM client implementation yet

**Intended Use Cases** (from admin router):
- Analysis pipeline (research → generate → review steps)
- Model selection with priority ordering
- Background task processing

---

## Requirements Summary

Both repos need to support:

1. **OpenRouter** - Access to 100+ models through single API
2. **z.ai** - GLM-4.5 models (available via OpenRouter or direct API)
3. **Future flexibility** - Easy to add OpenAI, Anthropic, or custom endpoints
4. **Structured outputs** - Type-safe responses (Pydantic models)
5. **Cost tracking** - Monitor spending per request
6. **Error handling** - Retries, rate limiting, fallbacks
7. **Caching** - Reduce redundant calls
8. **No code duplication** - Share implementation between repos

---

## Research Findings

### Framework Option 1: LiteLLM

**What it is**: Open-source unified LLM gateway (100+ providers)

**Pros**:
- ✅ Unified OpenAI-compatible interface
- ✅ Supports OpenRouter, z.ai, OpenAI, Anthropic, 100+ others
- ✅ Built-in cost tracking, caching, load balancing
- ✅ Fallback/retry logic included
- ✅ Proxy server option for centralized management
- ✅ 3M+ monthly downloads, well-maintained

**Cons**:
- ❌ Heavyweight dependency (brings many sub-dependencies)
- ❌ May be overkill for simple use cases
- ❌ Adds abstraction layer on top of providers
- ❌ Learning curve for advanced features

**Installation**: `pip install litellm`

**Sources**:
- [LiteLLM GitHub](https://github.com/BerriAI/litellm) - 100+ LLM APIs
- [LiteLLM Docs](https://docs.litellm.ai/)
- [OpenRouter Support](https://docs.litellm.ai/docs/providers/openrouter)

### Framework Option 2: OpenRouter + instructor

**What it is**: OpenRouter API + instructor for structured outputs

**Pros**:
- ✅ **Simple**: Just use OpenAI SDK with custom base_url
- ✅ **Comprehensive**: OpenRouter gives access to 400+ models
- ✅ **z.ai included**: GLM-4.5 models available (free tier!)
- ✅ **instructor already in use**: affordabot already has it installed
- ✅ **Structured outputs**: Type-safe Pydantic responses
- ✅ **Minimal dependencies**: openai + instructor (both lightweight)
- ✅ **Cost-effective**: OpenRouter handles billing, pay-per-use
- ✅ **Battle-tested**: instructor has 11k+ stars, 3M+ monthly downloads

**Cons**:
- ❌ Need to implement own caching (but simple with Redis/Supabase)
- ❌ Need to implement own cost tracking (but OpenRouter provides usage data)
- ❌ Fallback logic is manual (but easy to implement)

**Installation**:
```bash
pip install openai instructor
```

**Example Code**:
```python
import instructor
from openai import OpenAI
from pydantic import BaseModel

# OpenRouter client with instructor
client = instructor.from_openai(
    OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )
)

class Analysis(BaseModel):
    summary: str
    key_points: list[str]
    confidence: float

# Structured output automatically validated
result = client.chat.completions.create(
    model="z-ai/glm-4.5-air:free",  # Free z.ai model!
    messages=[{"role": "user", "content": "Analyze this..."}],
    response_model=Analysis
)
```

**Sources**:
- [OpenRouter + instructor guide](https://python.useinstructor.com/integrations/openrouter/)
- [instructor library](https://github.com/567-labs/instructor)
- [z.ai on OpenRouter](https://openrouter.ai/z-ai/glm-4.5-air:free)

### Framework Option 3: Direct z.ai SDK

**What it is**: Official z.ai Python SDK

**Pros**:
- ✅ Official support from z.ai
- ✅ OpenAI-compatible interface
- ✅ Latest GLM models

**Cons**:
- ❌ Only supports z.ai models (no OpenRouter, Anthropic, etc.)
- ❌ Vendor lock-in
- ❌ Need separate clients for other providers
- ❌ Doesn't meet "support multiple providers" requirement

**Installation**: `pip install zai-sdk`

**Sources**:
- [z.ai Python SDK](https://github.com/zai-org/z-ai-sdk-python)
- [z.ai API Docs](https://docs.z.ai/guides/develop/openai/python)

---

## Architecture Options

### Option A: Adopt LiteLLM (Replace prime-radiant-ai's custom implementation)

**Approach**:
1. Remove `prime-radiant-ai/backend/llm/client.py`
2. Replace with LiteLLM client
3. Keep existing abstractions (prompts, memory, cost tracking)
4. Use LiteLLM in affordabot too

**Pros**:
- Comprehensive solution
- All providers supported out-of-box
- Built-in advanced features

**Cons**:
- Throws away existing work in prime-radiant-ai
- Heavyweight dependency
- May not need all features

**Code Sharing**: Install `litellm` in both repos

### Option B: Adopt OpenRouter + instructor (Recommended ⭐)

**Approach**:
1. **Keep prime-radiant-ai's abstractions** (LLMClient, LLMMessage, etc.)
2. **Update implementations** to use OpenRouter + instructor
3. **Create shared library**: `llm-common` package with:
   - Base abstractions (`LLMClient`, `LLMMessage`, `LLMResponse`)
   - OpenRouter client implementation
   - instructor integration
   - Error handling, retries
   - Cost tracking helpers
4. **Both repos import** from `llm-common`

**Pros**:
- ✅ Lightweight (just openai + instructor)
- ✅ Reuses prime-radiant-ai's good abstractions
- ✅ No code duplication between repos
- ✅ Supports all requirements (OpenRouter, z.ai, future providers)
- ✅ Simple to understand and maintain
- ✅ affordabot already has instructor installed

**Cons**:
- Need to create shared package
- Manual implementation of some features (caching, advanced fallback)

**Implementation Plan**:

**Phase 1**: Create shared package
```
llm-common/
├── pyproject.toml
├── llm_common/
│   ├── __init__.py
│   ├── models.py          # LLMMessage, LLMResponse
│   ├── client.py          # Abstract LLMClient
│   ├── openrouter.py      # OpenRouterClient with instructor
│   ├── error_handling.py  # Retry logic, error types
│   ├── config.py          # Configuration management
│   └── utils.py           # Helpers (cost calc, etc.)
└── tests/
```

**Phase 2**: Update prime-radiant-ai
```bash
# Add llm-common as dependency
poetry add llm-common --path=../llm-common

# Update imports
from llm_common import LLMClient, LLMMessage, OpenRouterClient
```

**Phase 3**: Update affordabot
```bash
# Add llm-common to requirements.txt
-e ../llm-common

# Implement analysis pipeline
from llm_common import OpenRouterClient
```

**Code Sharing**:
```python
# llm_common/openrouter.py
import instructor
from openai import OpenAI
from llm_common.client import LLMClient
from llm_common.models import LLMMessage, LLMResponse

class OpenRouterClient(LLMClient):
    """OpenRouter client with instructor for structured outputs."""

    def __init__(self, api_key: str, default_model: str = "z-ai/glm-4.5-air:free"):
        self.client = instructor.from_openai(
            OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key
            )
        )
        self.default_model = default_model

    async def chat_completion(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        response_model: Optional[Type[BaseModel]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion with optional structured output."""
        model = model or self.default_model

        # Convert LLMMessage to OpenAI format
        openai_messages = [msg.to_dict() for msg in messages]

        # With structured output
        if response_model:
            result = self.client.chat.completions.create(
                model=model,
                messages=openai_messages,
                response_model=response_model,
                **kwargs
            )
            # result is already a Pydantic model
            return LLMResponse(
                content=result.model_dump_json(),
                structured_data=result,
                model=model
            )

        # Regular completion
        response = await self.client.chat.completions.create(
            model=model,
            messages=openai_messages,
            **kwargs
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            usage=response.usage.model_dump(),
            model=response.model
        )
```

### Option C: Keep prime-radiant-ai Custom, Duplicate to affordabot

**Approach**:
1. Copy `prime-radiant-ai/backend/llm/` to `affordabot/backend/llm/`
2. Maintain separately

**Pros**:
- Each repo is independent
- No shared package needed

**Cons**:
- ❌ **Violates DRY principle**
- ❌ Bug fixes need to be applied twice
- ❌ Features diverge over time
- ❌ **Not recommended**

---

## z.ai Integration Analysis

### Via OpenRouter (Recommended)

**Available Models**:
- `z-ai/glm-4.5-air:free` - FREE tier (131K context)
- `z-ai/glm-4.5` - Paid tier (better quality)

**Capabilities**:
- ✅ 131,072 token context window
- ✅ Tool use / function calling
- ✅ Reasoning mode (controllable)
- ✅ Structured outputs supported
- ✅ MoE architecture (efficient)

**Pricing**: $0/M tokens for free tier!

**Example**:
```python
client = OpenRouterClient(api_key="...")

response = await client.chat_completion(
    messages=[LLMMessage(role="user", content="Analyze this bill...")],
    model="z-ai/glm-4.5-air:free"
)
```

### Via Direct z.ai API

**Base URL**: `https://api.z.ai/api/paas/v4/`

**Authentication**: Bearer token

**Compatibility**: OpenAI SDK compatible (just change base_url)

**When to use**:
- Need latest unreleased models
- Need enterprise support
- Need dedicated throughput

**Example**:
```python
client = OpenAI(
    base_url="https://api.z.ai/api/paas/v4/",
    api_key=os.getenv("ZAI_API_KEY")
)
```

**Sources**:
- [z.ai OpenAI Compatibility](https://docs.z.ai/guides/develop/openai/python)

---

## Cost Analysis

### OpenRouter Pricing

**Free Tier Models** (Perfect for development):
- z-ai/glm-4.5-air:free - $0/M tokens
- deepseek/deepseek-r1:free - $0/M tokens
- google/gemini-flash-1.5-8b:free - $0/M tokens

**Paid Models** (Production):
- GPT-4o: ~$2.50-5.00/M tokens
- Claude Sonnet: ~$3.00-15.00/M tokens
- z-ai/glm-4.5: Competitive pricing

**Billing**: Single invoice across all models

### LiteLLM Costs

**Software**: Free (open-source)

**Hosting**: Self-hosted (free) or proxy server (requires infrastructure)

**API costs**: Pass-through from providers

### Custom Implementation Costs

**Development Time**: ~40 hours to replicate prime-radiant-ai's features

**Maintenance**: Ongoing (bug fixes, provider updates)

---

## Recommendation: Option B (OpenRouter + instructor) ⭐

### Why This is Best

1. **Meets all requirements**:
   - ✅ OpenRouter (400+ models)
   - ✅ z.ai (via OpenRouter or direct)
   - ✅ OpenAI, Anthropic (via OpenRouter)
   - ✅ Structured outputs (instructor)

2. **Avoids reinventing the wheel**:
   - ✅ Uses battle-tested libraries (OpenAI SDK, instructor)
   - ✅ OpenRouter handles provider complexity
   - ✅ No custom HTTP client needed

3. **Avoids code duplication**:
   - ✅ Shared `llm-common` package
   - ✅ Both repos import same code
   - ✅ Bug fixes in one place

4. **Simple and maintainable**:
   - Minimal dependencies (openai + instructor)
   - Easy to understand
   - Well-documented

5. **Cost-effective**:
   - Free tier available (z.ai GLM-4.5-air)
   - Pay-per-use (no infrastructure costs)

6. **Preserves good work**:
   - Keeps prime-radiant-ai's abstractions (LLMClient, etc.)
   - Just updates implementation to use better tools

### Implementation Roadmap

**Week 1**: Create `llm-common` package
- Set up pyproject.toml
- Port abstractions from prime-radiant-ai
- Implement OpenRouterClient with instructor
- Add tests

**Week 2**: Update prime-radiant-ai
- Add llm-common dependency
- Update imports
- Test existing features
- Deploy

**Week 3**: Update affordabot
- Add llm-common dependency
- Implement analysis pipeline
- Test admin dashboard integration
- Deploy

**Week 4**: Documentation & polish
- Write integration guides
- Add examples
- Performance testing

---

## Alternative Recommendation: LiteLLM (If Advanced Features Needed)

**When to choose LiteLLM instead**:
- Need advanced load balancing
- Need centralized proxy server
- Want built-in observability
- Have budget for infrastructure

**Implementation**: Simpler (just install litellm), but heavier dependency

---

## Open Questions for Discussion

1. **Package distribution**: Should `llm-common` be:
   - Git submodule?
   - Separate PyPI package?
   - Monorepo with both projects?

2. **Caching strategy**: Where should we cache?
   - Redis (requires infrastructure)
   - Supabase (already using)
   - Simple file cache (development)

3. **Cost tracking granularity**:
   - Per-request tracking?
   - Daily aggregates?
   - Store in database?

4. **Error handling philosophy**:
   - Automatic retries (how many)?
   - Fallback to cheaper models?
   - Circuit breaker pattern?

5. **Testing strategy**:
   - Mock responses for CI?
   - Use free tier models for integration tests?
   - Separate test API keys?

---

## Next Steps

1. **Discuss this plan** with stakeholders
2. **Decide on Option B vs LiteLLM**
3. **Answer open questions**
4. **Create `llm-common` package** (if Option B)
5. **Update prime-radiant-ai**
6. **Update affordabot**

---

## References

### Documentation
- [LiteLLM Docs](https://docs.litellm.ai/)
- [LiteLLM GitHub](https://github.com/BerriAI/litellm)
- [OpenRouter Docs](https://openrouter.ai/docs)
- [instructor Docs](https://python.useinstructor.com/)
- [instructor GitHub](https://github.com/567-labs/instructor)
- [z.ai API Docs](https://docs.z.ai/guides/overview/quick-start)
- [z.ai Python SDK](https://github.com/zai-org/z-ai-sdk-python)
- [z.ai on OpenRouter](https://openrouter.ai/z-ai/glm-4.5-air:free)

### Comparisons
- [LiteLLM vs OpenRouter](https://www.truefoundry.com/blog/litellm-vs-openrouter)
- [Best LLM Gateways 2025](https://www.pomerium.com/blog/best-llm-gateways-in-2025)
- [Top 5 LLM Gateways](https://www.helicone.ai/blog/top-llm-gateways-comparison-2025)

### Integration Guides
- [OpenRouter + instructor](https://python.useinstructor.com/integrations/openrouter/)
- [z.ai OpenAI Compatibility](https://docs.z.ai/guides/develop/openai/python)
- [LiteLLM OpenRouter Provider](https://docs.litellm.ai/docs/providers/openrouter)
