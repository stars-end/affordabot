import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.modules.setdefault("llm_common.core", SimpleNamespace(LLMConfig=MagicMock()))
sys.modules.setdefault("llm_common.providers", SimpleNamespace(ZaiClient=MagicMock()))
sys.modules.setdefault(
    "llm_common.core.models",
    SimpleNamespace(
        LLMMessage=lambda **kwargs: kwargs,
        MessageRole=SimpleNamespace(USER="user"),
    ),
)

from services.auto_discovery_service import AutoDiscoveryService  # noqa: E402


@pytest.mark.asyncio
async def test_generate_queries_uses_cache_before_provider():
    llm_client = MagicMock()
    llm_client.chat_completion = AsyncMock()
    db = MagicMock()
    db.get_system_prompt = AsyncMock(return_value={"system_prompt": "{jurisdiction}", "version": 3})
    db.get_discovery_query_cache = AsyncMock(return_value=["cached query"])

    service = AutoDiscoveryService(search_client=MagicMock(), llm_client=llm_client, db_client=db)

    queries = await service.generate_queries("San Jose", "city")

    assert queries == ["cached query"]
    llm_client.chat_completion.assert_not_called()
    assert service.last_discovery_stats["query_cache_hit"] is True


@pytest.mark.asyncio
async def test_generate_queries_respects_provider_budget_disable():
    llm_client = MagicMock()
    llm_client.chat_completion = AsyncMock()
    db = MagicMock()
    db.get_system_prompt = AsyncMock(return_value={"system_prompt": "{jurisdiction}", "version": 1})
    db.get_discovery_query_cache = AsyncMock(return_value=None)

    service = AutoDiscoveryService(search_client=MagicMock(), llm_client=llm_client, db_client=db)

    queries = await service.generate_queries(
        "San Jose",
        "city",
        allow_provider_query_generation=False,
    )

    assert queries
    llm_client.chat_completion.assert_not_called()
    assert service.last_discovery_stats["query_provider_used"] is False


@pytest.mark.asyncio
async def test_generate_queries_writes_cache_on_provider_success():
    llm_client = MagicMock()
    llm_client.chat_completion = AsyncMock(return_value=SimpleNamespace(content='["q1", "q2"]'))
    db = MagicMock()
    db.get_system_prompt = AsyncMock(return_value={"system_prompt": "{jurisdiction}", "version": 2})
    db.get_discovery_query_cache = AsyncMock(return_value=None)
    db.upsert_discovery_query_cache = AsyncMock(return_value=True)

    service = AutoDiscoveryService(search_client=MagicMock(), llm_client=llm_client, db_client=db)

    queries = await service.generate_queries("San Jose", "city")

    assert queries == ["q1", "q2"]
    db.upsert_discovery_query_cache.assert_awaited_once()
    assert service.last_discovery_stats["query_provider_used"] is True
