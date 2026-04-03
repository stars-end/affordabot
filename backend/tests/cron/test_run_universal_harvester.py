import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from scripts.cron.run_universal_harvester import UniversalHarvester


@pytest.mark.asyncio
async def test_harvester_flow():
    mock_db = MagicMock()
    mock_db.create_admin_task = AsyncMock()
    mock_db.update_admin_task = AsyncMock()
    mock_db.create_raw_scrape = AsyncMock(return_value="scrape_123")
    mock_db._fetch = AsyncMock(
        return_value=[
            {
                "id": "src_1",
                "name": "Test Web",
                "type": "web",
                "scrape_url": "http://example.com",
            }
        ]
    )

    with (
        patch("services.ingestion_service.IngestionService") as MockIngestion,
        patch.dict(
            os.environ,
            {"OPENROUTER_API_KEY": "test-key"},
        ),
    ):
        mock_embed_svc = MagicMock()
        mock_embed_svc.embed_query = MagicMock(
            return_value=AsyncMock(return_value=[0.1] * 4096)
        )
        with patch(
            "llm_common.embeddings.openai.OpenAIEmbeddingService",
            return_value=mock_embed_svc,
        ):
            instance = MockIngestion.return_value
            instance.process_raw_scrape = AsyncMock(return_value=5)

            with patch("httpx.AsyncClient") as MockClient:
                mock_client_instance = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_client_instance

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "# Clean Markdown Content"}}]
                }
                mock_client_instance.post.return_value = mock_response

                runner = UniversalHarvester()
                runner.db = mock_db

                await runner.run()

                mock_client_instance.post.assert_called_once()
                instance.process_raw_scrape.assert_called_with("scrape_123")

                MockIngestion.assert_called_once()
                call_kwargs = MockIngestion.call_args
                assert "postgres_client" in call_kwargs.kwargs or (
                    len(call_kwargs.args) >= 1
                ), "IngestionService must receive postgres_client"
                assert "legacy_storage_client" not in call_kwargs.kwargs, (
                    "IngestionService must not receive deprecated storage kwargs"
                )


@pytest.mark.asyncio
async def test_harvester_no_embedding_key_skips():
    mock_db = MagicMock()
    mock_db.create_admin_task = AsyncMock()
    mock_db.update_admin_task = AsyncMock()
    mock_db.create_raw_scrape = AsyncMock(return_value="scrape_123")
    mock_db._fetch = AsyncMock(
        return_value=[
            {
                "id": "src_1",
                "name": "Test Web",
                "type": "web",
                "scrape_url": "http://example.com",
            }
        ]
    )

    with (
        patch("httpx.AsyncClient") as MockClient,
        patch.dict(
            os.environ, {"OPENROUTER_API_KEY": "", "OPENAI_API_KEY": ""}, clear=False
        ),
    ):
        mock_client_instance = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client_instance
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "# Clean Markdown Content"}}]
        }
        mock_client_instance.post.return_value = mock_response

        runner = UniversalHarvester()
        runner.db = mock_db

        await runner.run()

        mock_db._fetch.assert_called_once()
