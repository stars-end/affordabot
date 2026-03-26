from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_common.core import LLMError
from schemas.analysis import ReviewCritique
from services.llm.orchestrator import (
    AnalysisPipeline,
    DEFAULT_OPENROUTER_FALLBACK_MODEL,
)


def _make_pipeline(primary_side_effect, fallback_default_model=None):
    primary_llm = MagicMock()
    primary_llm.chat_completion = AsyncMock(side_effect=primary_side_effect)
    primary_llm.config = SimpleNamespace(default_model="glm-4.7")

    fallback_llm = MagicMock()
    fallback_llm.chat_completion = AsyncMock(
        return_value=MagicMock(
            content='{"passed": true, "critique": "ok", "missing_impacts": [], "factual_errors": []}'
        )
    )
    fallback_llm.config = SimpleNamespace(default_model=fallback_default_model)

    search_client = MagicMock()
    db_client = MagicMock()
    return AnalysisPipeline(
        primary_llm,
        search_client,
        db_client,
        fallback_client=fallback_llm,
    )


@pytest.mark.asyncio
async def test_chat_fallback_uses_default_openrouter_auto(monkeypatch):
    monkeypatch.delenv("LLM_MODEL_FALLBACK_OPENROUTER", raising=False)
    pipeline = _make_pipeline(
        primary_side_effect=LLMError("primary failed", provider="zai"),
        fallback_default_model=None,
    )

    result = await pipeline._chat(
        messages=[{"role": "user", "content": "review this"}],
        model="glm-4.7",
        response_model=ReviewCritique,
    )

    assert isinstance(result, ReviewCritique)
    assert pipeline.fallback_llm.chat_completion.await_args.kwargs["model"] == (
        DEFAULT_OPENROUTER_FALLBACK_MODEL
    )


@pytest.mark.asyncio
async def test_chat_fallback_uses_env_override(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_FALLBACK_OPENROUTER", "openrouter/custom-test")
    pipeline = _make_pipeline(
        primary_side_effect=LLMError("primary failed", provider="zai"),
        fallback_default_model=None,
    )

    await pipeline._chat(
        messages=[{"role": "user", "content": "review this"}],
        model="glm-4.7",
        response_model=ReviewCritique,
    )

    assert (
        pipeline.fallback_llm.chat_completion.await_args.kwargs["model"]
        == "openrouter/custom-test"
    )
