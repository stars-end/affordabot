class LLMError(Exception):
    """Base exception for LLM errors."""
    pass

class BudgetExceededError(LLMError):
    """Raised when budget limit is exceeded."""
    pass

class RateLimitError(LLMError):
    """Raised when rate limit is exceeded."""
    pass

class AllModelsFailed(LLMError):
    """Raised when all models in a fallback chain fail."""
    pass

class SearchError(Exception):
    """Base exception for search errors."""
    pass
