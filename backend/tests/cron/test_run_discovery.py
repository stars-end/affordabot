import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault(
    "asyncpg",
    SimpleNamespace(Record=object, Pool=object, create_pool=MagicMock()),
)
sys.modules.setdefault("llm_common", SimpleNamespace(WebSearchClient=MagicMock()))
sys.modules.setdefault("llm_common.core", SimpleNamespace(LLMConfig=MagicMock()))
sys.modules.setdefault("llm_common.providers", SimpleNamespace(ZaiClient=MagicMock()))
sys.modules.setdefault(
    "llm_common.core.models",
    SimpleNamespace(LLMMessage=MagicMock(), MessageRole=SimpleNamespace(USER="user")),
)
sys.modules.setdefault("instructor", SimpleNamespace(from_openai=MagicMock()))
sys.modules.setdefault("openai", SimpleNamespace(AsyncOpenAI=MagicMock()))

from scripts.cron import run_discovery  # noqa: E402


@patch("scripts.cron.run_discovery._load_classifier_validation_contract")
@patch("scripts.cron.run_discovery.DiscoveryClassifierService")
@patch("scripts.cron.run_discovery.SearchDiscoveryService")
@patch("scripts.cron.run_discovery.WebSearchClient")
@patch("scripts.cron.run_discovery.PostgresDB")
async def test_run_discovery_wires_search_client(
    mock_db_cls,
    mock_search_client_cls,
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
    _, kwargs = mock_search_service_cls.call_args
    assert kwargs["search_client"] is mock_search_client_cls.return_value
    assert kwargs["db_client"] is mock_db


@patch("scripts.cron.run_discovery._load_classifier_validation_contract")
@patch("scripts.cron.run_discovery.DiscoveryClassifierService")
@patch("scripts.cron.run_discovery.SearchDiscoveryService")
@patch("scripts.cron.run_discovery.WebSearchClient")
@patch("scripts.cron.run_discovery.PostgresDB")
async def test_run_discovery_fail_closed_when_batch_gate_fails(
    mock_db_cls,
    _mock_search_client_cls,
    mock_search_service_cls,
    mock_classifier_cls,
    mock_gate_loader,
):
    mock_db = MagicMock()
    mock_db.create_admin_task = AsyncMock()
    mock_db._fetch = AsyncMock(return_value=[{"id": "jur-1", "name": "San Jose", "type": "city"}])
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
@patch("scripts.cron.run_discovery.WebSearchClient")
@patch("scripts.cron.run_discovery.PostgresDB")
async def test_run_discovery_creates_single_source_write_with_classifier_gate(
    mock_db_cls,
    _mock_search_client_cls,
    mock_search_service_cls,
    mock_classifier_cls,
    mock_gate_loader,
):
    mock_db = MagicMock()
    mock_db.create_admin_task = AsyncMock()
    mock_db._fetch = AsyncMock(return_value=[{"id": "jur-1", "name": "San Jose", "type": "city"}])
    mock_db._fetchrow = AsyncMock(return_value=None)
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
    mock_db.create_source.assert_called_once()
    create_payload = mock_db.create_source.call_args.args[0]
    assert create_payload["url"] == "https://example.gov/agenda"
    assert create_payload["metadata"]["classifier"]["confidence"] == 0.91
