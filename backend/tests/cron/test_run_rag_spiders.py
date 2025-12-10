from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from scripts.cron.run_rag_spiders import main

@patch('scripts.cron.run_rag_spiders.CrawlerProcess')
@patch('scripts.cron.run_rag_spiders.get_project_settings')
def test_main_runs_spiders(mock_get_settings, mock_crawler_process):
    """Verify that main schedules both spiders and starts the process."""
    
    # Setup Mocks
    mock_settings = MagicMock()
    mock_get_settings.return_value = mock_settings
    
    mock_process = MagicMock()
    mock_crawler_process.return_value = mock_process
    
    # Mock DB Module with Async Methods
    mock_db_module = MagicMock()
    mock_db_instance = MagicMock()
    mock_db_module.SupabaseDB.return_value = mock_db_instance
    mock_db_instance.get_or_create_jurisdiction = AsyncMock(return_value="jur-123")
    mock_db_instance.get_or_create_source = AsyncMock(return_value="source-123")
    
    # Mock runtime dependencies
    with patch.dict(sys.modules, {
        'affordabot_scraper.spiders.sanjose_meetings': MagicMock(),
        'affordabot_scraper.spiders.sanjose_municode': MagicMock(),
        'db.supabase_client': mock_db_module,
        'services.ingestion_service': MagicMock(),
        'services.storage': MagicMock(),
        'services.vector_backend_factory': MagicMock(),
        'llm_common.embeddings.openai': MagicMock(),
        'llm_common.embeddings.mock': MagicMock(),
    }):
        main()
    
    # Verify Settings Loaded
    mock_get_settings.assert_called_once()
    mock_settings.set.assert_any_call('TELNETCONSOLE_ENABLED', False)
    
    # Verify Process Created
    mock_crawler_process.assert_called_once_with(mock_settings)
    
    # Verify Spiders Added (San Jose Meetings & Municode)
    assert mock_process.crawl.call_count == 2
    
    # Verify Start
    mock_process.start.assert_called_once()
