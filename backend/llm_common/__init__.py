"""llm-common: Unified LLM and web search client."""

from llm_common.llm_client import LLMClient, AllModelsFailed
from llm_common.web_search import WebSearchClient, SearchResult
from llm_common.cost_tracker import CostTracker
from llm_common.exceptions import (
    BudgetExceededError,
    RateLimitError,
    SearchError,
)

__all__ = [
    "LLMClient",
    "AllModelsFailed",
    "WebSearchClient",
    "SearchResult",
    "CostTracker",
    "BudgetExceededError",
    "RateLimitError",
    "SearchError",
]
