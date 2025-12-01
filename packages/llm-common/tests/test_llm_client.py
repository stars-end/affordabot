from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from llm_common.llm_client import LLMClient, BudgetExceededError, AllModelsFailed

@pytest.fixture
def llm_client():
    return LLMClient(provider="openrouter", api_key="test-key")

@pytest.mark.asyncio
async def test_chat_completion(llm_client):
    with patch("llm_common.llm_client.acompletion") as mock_completion:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Hello world"
        mock_completion.return_value = mock_response
        
        with patch("llm_common.llm_client.completion_cost", return_value=0.001):
            response = await llm_client.chat(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o"
            )
            
            assert response == "Hello world"
            assert llm_client.daily_cost == 0.001

@pytest.mark.asyncio
async def test_budget_limit(llm_client):
    llm_client.budget_limit = 0.001
    llm_client.daily_cost = 0.002
    
    with pytest.raises(BudgetExceededError):
        await llm_client.chat(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o"
        )

@pytest.mark.asyncio
async def test_fallback_chain(llm_client):
    with patch("llm_common.llm_client.acompletion") as mock_completion:
        # First model fails, second succeeds
        success_mock = MagicMock()
        success_mock.choices[0].message.content = "Success"
        mock_completion.side_effect = [Exception("Fail"), success_mock]
        
        with patch("llm_common.llm_client.completion_cost", return_value=0.001):
            response = await llm_client.chat_with_fallback(
                messages=[{"role": "user", "content": "Hello"}],
                models=["model1", "model2"]
            )
            
            assert response == "Success"
            assert mock_completion.call_count == 2
