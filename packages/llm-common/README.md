# llm-common

Shared LLM utilities for Affordabot and Prime-Radiant-AI.

## Features

- **LLMClient**: Unified wrapper around LiteLLM and Instructor for multi-provider support and structured outputs.
- **WebSearchClient**: z.ai web search with 2-tier caching (In-Memory + Supabase).
- **CostTracker**: Budget enforcement and cost tracking.

## Installation

```bash
pip install -e packages/llm-common
```

## Usage

### LLMClient

```python
from llm_common import LLMClient

client = LLMClient(provider="openrouter")
response = await client.chat(
    messages=[{"role": "user", "content": "Hello"}],
    model="gpt-4o"
)
print(response)
```
