from __future__ import annotations
from litellm import acompletion, completion_cost
import instructor
from openai import AsyncOpenAI
from typing import Optional, List, Dict, Any, Union, Type
from pydantic import BaseModel
from .exceptions import BudgetExceededError, AllModelsFailed

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
    
    def _get_api_key(self, provider: str) -> Optional[str]:
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
            "zai": "https://api.z.ai/api/paas/v4",
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
        response_model: Optional[Type[BaseModel]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Any:
        """
        Generate chat completion.
        
        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}
            model: Model name (e.g., "gpt-4o", "z-ai/glm-4.5")
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
        response_model: Optional[Type[BaseModel]] = None,
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
