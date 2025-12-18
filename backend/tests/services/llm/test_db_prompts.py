import pytest
import os
from unittest.mock import AsyncMock, patch
from services.llm.pipeline import DualModelAnalyzer

@pytest.mark.asyncio
async def test_prompt_fetch_fallback():
    """Test that pipeline uses default prompt if DB fetch fails."""
    # Mock DB
    mock_db = AsyncMock()
    mock_db.connect = AsyncMock()
    # Simulate fetch returning None
    mock_db.get_system_prompt.return_value = None
    
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy", "ZAI_API_KEY": "dummy"}), \
         patch("services.llm.pipeline.instructor.from_openai"), \
         patch("services.llm.pipeline.AsyncOpenAI"), \
         patch("services.llm.pipeline.PostgresDB", return_value=mock_db):
        
        analyzer = DualModelAnalyzer()
        
        # Manually force db init (since analyze usually handles it)
        analyzer.db = mock_db
        
        default = "DEFAULT_PROMPT"
        result = await analyzer._get_system_prompt("missing_key", default)
        
        assert result == default
        mock_db.get_system_prompt.assert_called_with("missing_key")

@pytest.mark.asyncio
async def test_prompt_fetch_success():
    """Test that pipeline uses DB prompt if available."""
    mock_db = AsyncMock()
    mock_db.connect = AsyncMock()
    # Simulate success
    mock_db.get_system_prompt.return_value = {"system_prompt": "DB_PROMPT"}
    
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy", "ZAI_API_KEY": "dummy"}), \
         patch("services.llm.pipeline.instructor.from_openai"), \
         patch("services.llm.pipeline.AsyncOpenAI"), \
         patch("services.llm.pipeline.PostgresDB", return_value=mock_db):
        
        analyzer = DualModelAnalyzer()
        analyzer.db = mock_db
        
        default = "DEFAULT_PROMPT"
        result = await analyzer._get_system_prompt("existing_key", default)
        
        assert result == "DB_PROMPT"
        mock_db.get_system_prompt.assert_called_with("existing_key")
