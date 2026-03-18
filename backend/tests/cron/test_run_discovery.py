from unittest.mock import AsyncMock, MagicMock, patch

from scripts.cron import run_discovery


@patch("scripts.cron.run_discovery.AutoDiscoveryService")
@patch("scripts.cron.run_discovery.WebSearchClient")
@patch("scripts.cron.run_discovery.PostgresDB")
async def test_run_discovery_wires_search_client(mock_db_cls, mock_search_client_cls, mock_service_cls):
    mock_db = MagicMock()
    mock_db.create_admin_task = AsyncMock()
    mock_db._fetch = AsyncMock(return_value=[])
    mock_db.update_admin_task = AsyncMock()
    mock_db_cls.return_value = mock_db

    mock_service = MagicMock()
    mock_service.discover_sources = AsyncMock(return_value=[])
    mock_service_cls.return_value = mock_service

    await run_discovery.main()

    mock_search_client_cls.assert_called_once()
    _, kwargs = mock_service_cls.call_args
    assert kwargs["search_client"] is mock_search_client_cls.return_value
    assert kwargs["db_client"] is mock_db

