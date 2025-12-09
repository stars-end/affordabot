"""LLM Common - Shared LLM framework."""

from llm_common.core import (
    APIKeyError,
    BudgetExceededError,
    CacheError,
    CostMetrics,
    LLMClient,
    LLMConfig,
    LLMError,
    LLMMessage,
    LLMResponse,
    LLMUsage,
    MessageRole,
    ModelNotFoundError,
    RateLimitError,
    TimeoutError,
    WebSearchResponse,
    WebSearchResult,
)
from llm_common.providers import OpenRouterClient, ZaiClient
from llm_common.retrieval import RetrievalBackend, RetrievedChunk, SupabasePgVectorBackend
from llm_common.web_search import WebSearchClient

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Core
    "LLMClient",
    "LLMConfig",
    "LLMMessage",
    "LLMResponse",
    "LLMUsage",
    "MessageRole",
    "CostMetrics",
    "WebSearchResponse",
    "WebSearchResult",
    # Exceptions
    "LLMError",
    "BudgetExceededError",
    "APIKeyError",
    "ModelNotFoundError",
    "RateLimitError",
    "TimeoutError",
    "CacheError",
    # Providers
    "ZaiClient",
    "OpenRouterClient",
    # Web Search
    "WebSearchClient",
    # Retrieval
    "RetrievalBackend",
    "RetrievedChunk",
    "SupabasePgVectorBackend",
]
