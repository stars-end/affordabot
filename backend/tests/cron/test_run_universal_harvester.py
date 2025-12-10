import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from scripts.cron.run_universal_harvester import UniversalHarvester

@pytest.mark.asyncio
async def test_harvester_flow():
    """Verify Universal Harvester logic with mocks."""
    
    # Mock DB
    mock_db = MagicMock()
    mock_db.client = MagicMock()
    
    # Mock Sources Response
    mock_sources = [
        {"id": "src_1", "name": "Test Web", "type": "web", "scrape_url": "http://example.com"}
    ]
    mock_db.client.table().select().eq().execute.return_value.data = mock_sources
    
    # Mock Ingestion Service
    with patch('services.ingestion_service.IngestionService') as MockIngestion, \
         patch('llm_common.embeddings.EmbeddingService') as _MockEmbed, \
         patch('services.vector_backend_factory.create_vector_backend') as _MockBackend, \
         patch.dict(sys.modules, {
             'llm_common.embeddings.mock': MagicMock(),
             'llm_common.embeddings.openai': MagicMock(),
             'services.storage': MagicMock(),
         }):
        
        instance = MockIngestion.return_value
        instance.process_raw_scrape = AsyncMock(return_value=5)
        
        # Mock HTTPX
        with patch('httpx.AsyncClient') as MockClient:
            mock_client_instance = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client_instance
            
            # Mock Z.ai Response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "# Clean Markdown Content"}}]
            }
            mock_client_instance.post.return_value = mock_response
            
            # Run
            runner = UniversalHarvester()
            runner.db = mock_db # Inject mock DB
            
            # Inject mock for SupabaseDB used inside run() if needed, 
            # but we patched IngestionService so it shouldn't hit real DB for vector stuff.
            # We need to mock raw_scrapes insert though.
            mock_db.client.table().insert().execute.return_value.data = [{"id": "scrape_123"}]
            
            await runner.run()
            
            # Verifications
            # 1. Check Source Fetch
            # (Implied by flow reaching loop)
            
            # 2. Check Z.ai Call
            mock_client_instance.post.assert_called_once()
            
            # 3. Check Raw Scrape Insert
            # table("raw_scrapes").insert(...)
            
            # 4. Check Ingestion Trigger
            instance.process_raw_scrape.assert_called_with("scrape_123")
