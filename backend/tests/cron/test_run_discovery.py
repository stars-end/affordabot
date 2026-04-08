import sys
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

@dataclass
class _WebSearchResultStub:
    url: str
    title: str = ""
    snippet: str = ""
    content: str | None = None
    published_date: str | None = None
    domain: str | None = None
    score: float | None = None
    source: str | None = None


sys.modules.setdefault(
    "playwright.async_api",
    SimpleNamespace(async_playwright=MagicMock()),
)
sys.modules.setdefault(
    "asyncpg",
    SimpleNamespace(Record=object, Pool=object, create_pool=MagicMock()),
)
sys.modules.setdefault("llm_common", SimpleNamespace(WebSearchClient=MagicMock()))
sys.modules.setdefault("llm_common.core", SimpleNamespace(LLMConfig=MagicMock()))
sys.modules.setdefault("llm_common.providers", SimpleNamespace(ZaiClient=MagicMock()))
sys.modules.setdefault(
    "llm_common.core.models",
    SimpleNamespace(
        LLMMessage=MagicMock(),
        MessageRole=SimpleNamespace(USER="user"),
        WebSearchResult=_WebSearchResultStub,
    ),
)
sys.modules.setdefault("instructor", SimpleNamespace(from_openai=MagicMock()))
sys.modules.setdefault("openai", SimpleNamespace(AsyncOpenAI=MagicMock()))

from scripts.cron import run_discovery  # noqa: E402


@patch("scripts.cron.run_discovery._load_classifier_validation_contract")
@patch("scripts.cron.run_discovery.DiscoveryClassifierService")
@patch("scripts.cron.run_discovery.SearchDiscoveryService")
@patch("scripts.cron.run_discovery.LegacySearchDiscoveryService")
@patch("scripts.cron.run_discovery.WebSearchClient")
@patch("scripts.cron.run_discovery.PostgresDB")
async def test_run_discovery_wires_search_client(
    mock_db_cls,
    mock_search_client_cls,
    mock_legacy_search_cls,
    mock_search_service_cls,
    mock_classifier_cls,
    mock_gate_loader,
):
    mock_db = MagicMock()
    mock_db.create_admin_task = AsyncMock()
    mock_db._fetch = AsyncMock(return_value=[])
    mock_db.update_admin_task = AsyncMock()
    mock_db_cls.return_value = mock_db

    mock_search_service = MagicMock()
    mock_search_service.discover_sources = AsyncMock(return_value=[])
    mock_search_service_cls.return_value = mock_search_service

    mock_classifier = MagicMock()
    mock_classifier.client = object()
    mock_classifier_cls.return_value = mock_classifier
    mock_gate_loader.return_value = (True, {"status": "passed", "min_confidence": 0.75})

    await run_discovery.main()

    mock_search_client_cls.assert_called_once()
    mock_legacy_search_cls.assert_called_once()
    create_task_kwargs = mock_db.create_admin_task.await_args.kwargs
    assert create_task_kwargs["task_type"] == "research"
    assert create_task_kwargs["jurisdiction"] == "all"
    assert create_task_kwargs["status"] == "running"
    _, kwargs = mock_search_service_cls.call_args
    resilient_client = kwargs["search_client"]
    assert resilient_client.primary_client is mock_search_client_cls.return_value
    assert resilient_client.fallback_service is mock_legacy_search_cls.return_value
    assert kwargs["db_client"] is mock_db


@patch("scripts.cron.run_discovery._load_classifier_validation_contract")
@patch("scripts.cron.run_discovery.DiscoveryClassifierService")
@patch("scripts.cron.run_discovery.SearchDiscoveryService")
@patch("scripts.cron.run_discovery.LegacySearchDiscoveryService")
@patch("scripts.cron.run_discovery.WebSearchClient")
@patch("scripts.cron.run_discovery.PostgresDB")
async def test_run_discovery_fail_closed_when_batch_gate_fails(
    mock_db_cls,
    _mock_search_client_cls,
    _mock_legacy_search_cls,
    mock_search_service_cls,
    mock_classifier_cls,
    mock_gate_loader,
):
    mock_db = MagicMock()
    mock_db.create_admin_task = AsyncMock()
    mock_db._fetch = AsyncMock(
        return_value=[{"id": uuid.UUID("a23f2953-8ade-4c43-a287-eb03f06b2501"), "name": "San Jose", "type": "city"}]
    )
    mock_db._fetchrow = AsyncMock()
    mock_db.create_source = AsyncMock()
    mock_db.update_admin_task = AsyncMock()
    mock_db_cls.return_value = mock_db

    mock_search_service = MagicMock()
    mock_search_service.discover_sources = AsyncMock(
        return_value=[
            {
                "url": "https://example.gov/agenda",
                "title": "Agenda Center",
                "category": "agenda",
                "snippet": "meeting agendas",
            }
        ]
    )
    mock_search_service_cls.return_value = mock_search_service

    mock_classifier = MagicMock()
    mock_classifier.client = object()
    mock_classifier.discover_url = AsyncMock()
    mock_classifier_cls.return_value = mock_classifier
    mock_gate_loader.return_value = (False, {"status": "failed", "reason": "acceptance_gate_failed"})

    await run_discovery.main()

    mock_classifier.discover_url.assert_not_called()
    mock_db.create_source.assert_not_called()
    update_kwargs = mock_db.update_admin_task.call_args.kwargs
    assert update_kwargs["result"]["rejected_by_reason"]["batch_gate_fail_closed"] == 1


@patch("scripts.cron.run_discovery._load_classifier_validation_contract")
@patch("scripts.cron.run_discovery.DiscoveryClassifierService")
@patch("scripts.cron.run_discovery.SearchDiscoveryService")
@patch("scripts.cron.run_discovery.LegacySearchDiscoveryService")
@patch("scripts.cron.run_discovery.WebSearchClient")
@patch("scripts.cron.run_discovery.PostgresDB")
async def test_run_discovery_creates_single_source_write_with_classifier_gate(
    mock_db_cls,
    _mock_search_client_cls,
    _mock_legacy_search_cls,
    mock_search_service_cls,
    mock_classifier_cls,
    mock_gate_loader,
):
    mock_db = MagicMock()
    mock_db.create_admin_task = AsyncMock()
    mock_db._fetch = AsyncMock(
        return_value=[{"id": uuid.UUID("a23f2953-8ade-4c43-a287-eb03f06b2501"), "name": "San Jose", "type": "city"}]
    )
    mock_db._fetchrow = AsyncMock(return_value=None)
    mock_db.get_discovery_classifier_cache = AsyncMock(return_value=None)
    mock_db.upsert_discovery_classifier_cache = AsyncMock(return_value=True)
    mock_db.get_or_create_source = AsyncMock()
    mock_db.create_source = AsyncMock()
    mock_db.update_admin_task = AsyncMock()
    mock_db_cls.return_value = mock_db

    mock_search_service = MagicMock()
    mock_search_service.discover_sources = AsyncMock(
        return_value=[
            {
                "url": "https://example.gov/agenda",
                "title": "Agenda Center",
                "category": "agenda",
                "snippet": "meeting agendas and minutes",
                "discovery_query": "San Jose city council meetings",
            }
        ]
    )
    mock_search_service_cls.return_value = mock_search_service

    mock_classifier = MagicMock()
    mock_classifier.client = object()
    mock_classifier.discover_url = AsyncMock(
        return_value=MagicMock(
            is_scrapable=True,
            confidence=0.91,
            source_type="agenda",
            recommended_spider="generic",
            reasoning="Official agenda index",
        )
    )
    mock_classifier_cls.return_value = mock_classifier
    mock_gate_loader.return_value = (True, {"status": "passed", "min_confidence": 0.75})

    await run_discovery.main()

    mock_db.get_or_create_source.assert_not_called()
    mock_db._fetchrow.assert_awaited_once_with(
        "SELECT id FROM sources WHERE jurisdiction_id = $1 AND url = $2",
        "a23f2953-8ade-4c43-a287-eb03f06b2501",
        "https://example.gov/agenda",
    )
    mock_db.get_discovery_classifier_cache.assert_awaited_once()
    mock_db.upsert_discovery_classifier_cache.assert_awaited_once()
    mock_db.create_source.assert_called_once()
    create_payload = mock_db.create_source.call_args.args[0]
    assert create_payload["url"] == "https://example.gov/agenda"
    assert create_payload["metadata"]["classifier"]["confidence"] == 0.91


@patch("scripts.cron.run_discovery._load_classifier_validation_contract")
@patch("scripts.cron.run_discovery.DiscoveryClassifierService")
@patch("scripts.cron.run_discovery.SearchDiscoveryService")
@patch("scripts.cron.run_discovery.LegacySearchDiscoveryService")
@patch("scripts.cron.run_discovery.WebSearchClient")
@patch("scripts.cron.run_discovery.PostgresDB")
async def test_run_discovery_respects_jurisdiction_scope_filter(
    mock_db_cls,
    _mock_search_client_cls,
    _mock_legacy_search_cls,
    mock_search_service_cls,
    mock_classifier_cls,
    mock_gate_loader,
):
    mock_db = MagicMock()
    mock_db.create_admin_task = AsyncMock()
    mock_db._fetch = AsyncMock(
        return_value=[
            {"id": "jur-1", "name": "San Jose", "type": "city"},
            {"id": "jur-2", "name": "Milpitas", "type": "city"},
        ]
    )
    mock_db._fetchrow = AsyncMock(return_value={"id": "src-1"})
    mock_db.create_source = AsyncMock()
    mock_db.update_admin_task = AsyncMock()
    mock_db_cls.return_value = mock_db

    mock_search_service = MagicMock()
    mock_search_service.discover_sources = AsyncMock(
        return_value=[
            {
                "url": "https://example.gov/agenda",
                "title": "Agenda Center",
                "category": "agenda",
                "snippet": "meeting agendas and minutes",
            }
        ]
    )
    mock_search_service_cls.return_value = mock_search_service

    mock_classifier = MagicMock()
    mock_classifier.client = object()
    mock_classifier.discover_url = AsyncMock(
        return_value=MagicMock(
            is_scrapable=True,
            confidence=0.91,
            source_type="agenda",
            recommended_spider="generic",
            reasoning="Official agenda index",
        )
    )
    mock_classifier_cls.return_value = mock_classifier
    mock_gate_loader.return_value = (True, {"status": "passed", "min_confidence": 0.75})

    await run_discovery.main(
        jurisdiction_scope={"milpitas"},
        max_queries_per_jurisdiction=2,
    )

    mock_search_service.discover_sources.assert_awaited_once_with(
        "Milpitas",
        "city",
        max_queries=2,
        allow_provider_query_generation=True,
        query_cache_ttl_hours=72,
    )
    update_kwargs = mock_db.update_admin_task.call_args.kwargs
    assert update_kwargs["result"]["jurisdictions_processed"] == 1
    assert update_kwargs["result"]["jurisdiction_scope"] == ["milpitas"]
    assert update_kwargs["result"]["max_queries_per_jurisdiction"] == 2


@patch("scripts.cron.run_discovery._load_classifier_validation_contract")
@patch("scripts.cron.run_discovery.DiscoveryClassifierService")
@patch("scripts.cron.run_discovery.SearchDiscoveryService")
@patch("scripts.cron.run_discovery.LegacySearchDiscoveryService")
@patch("scripts.cron.run_discovery.WebSearchClient")
@patch("scripts.cron.run_discovery.PostgresDB")
async def test_run_discovery_rejects_obvious_junk_before_classifier(
    mock_db_cls,
    _mock_search_client_cls,
    _mock_legacy_search_cls,
    mock_search_service_cls,
    mock_classifier_cls,
    mock_gate_loader,
):
    mock_db = MagicMock()
    mock_db.create_admin_task = AsyncMock()
    mock_db._fetch = AsyncMock(
        return_value=[{"id": "jur-1", "name": "San Jose", "type": "city"}]
    )
    mock_db._fetchrow = AsyncMock(return_value=None)
    mock_db.create_source = AsyncMock()
    mock_db.update_admin_task = AsyncMock()
    mock_db_cls.return_value = mock_db

    mock_search_service = MagicMock()
    mock_search_service.last_discovery_stats = {}
    mock_search_service.discover_sources = AsyncMock(
        return_value=[
            {"url": "https://www.youtube.com/watch?v=123", "title": "junk", "snippet": "video"}
        ]
    )
    mock_search_service_cls.return_value = mock_search_service

    mock_classifier = MagicMock()
    mock_classifier.client = object()
    mock_classifier.discover_url = AsyncMock()
    mock_classifier_cls.return_value = mock_classifier
    mock_gate_loader.return_value = (True, {"status": "passed", "min_confidence": 0.75})

    await run_discovery.main()

    mock_classifier.discover_url.assert_not_called()
    update_kwargs = mock_db.update_admin_task.call_args.kwargs
    assert update_kwargs["result"]["rejected_by_reason"]["heuristic_obvious_junk"] == 1


@patch("scripts.cron.run_discovery._load_classifier_validation_contract")
@patch("scripts.cron.run_discovery.DiscoveryClassifierService")
@patch("scripts.cron.run_discovery.SearchDiscoveryService")
@patch("scripts.cron.run_discovery.LegacySearchDiscoveryService")
@patch("scripts.cron.run_discovery.WebSearchClient")
@patch("scripts.cron.run_discovery.PostgresDB")
async def test_run_discovery_uses_cached_positive_classifier_without_provider_call(
    mock_db_cls,
    _mock_search_client_cls,
    _mock_legacy_search_cls,
    mock_search_service_cls,
    mock_classifier_cls,
    mock_gate_loader,
):
    mock_db = MagicMock()
    mock_db.create_admin_task = AsyncMock()
    mock_db._fetch = AsyncMock(
        return_value=[{"id": "jur-1", "name": "San Jose", "type": "city"}]
    )
    mock_db._fetchrow = AsyncMock(return_value=None)
    mock_db.get_discovery_classifier_cache = AsyncMock(
        return_value={
            "is_scrapable": True,
            "jurisdiction_name": "San Jose",
            "source_type": "agenda",
            "recommended_spider": "generic",
            "confidence": 0.99,
            "reasoning": "cached pass",
        }
    )
    mock_db.upsert_discovery_classifier_cache = AsyncMock(return_value=True)
    mock_db.create_source = AsyncMock()
    mock_db.update_admin_task = AsyncMock()
    mock_db_cls.return_value = mock_db

    mock_search_service = MagicMock()
    mock_search_service.last_discovery_stats = {}
    mock_search_service.discover_sources = AsyncMock(
        return_value=[
            {
                "url": "https://example.gov/agenda",
                "title": "Agenda Center",
                "category": "agenda",
                "snippet": "meeting agendas",
            }
        ]
    )
    mock_search_service_cls.return_value = mock_search_service

    mock_classifier = MagicMock()
    mock_classifier.client = object()
    mock_classifier.classifier_version = "discovery-classifier-v1"
    mock_classifier.response_from_cache_payload = MagicMock(
        return_value=MagicMock(
            is_scrapable=True,
            confidence=0.99,
            source_type="agenda",
            recommended_spider="generic",
            reasoning="cached pass",
        )
    )
    mock_classifier.response_to_cache_payload = MagicMock(return_value={})
    mock_classifier.discover_url = AsyncMock()
    mock_classifier_cls.return_value = mock_classifier
    mock_gate_loader.return_value = (True, {"status": "passed", "min_confidence": 0.75})

    await run_discovery.main(classifier_provider_budget=0)

    mock_classifier.discover_url.assert_not_called()
    mock_db.create_source.assert_called_once()
    update_kwargs = mock_db.update_admin_task.call_args.kwargs
    assert update_kwargs["result"]["classifier_cache_hits"] == 1
    assert update_kwargs["result"]["classifier_provider_calls_used"] == 0
