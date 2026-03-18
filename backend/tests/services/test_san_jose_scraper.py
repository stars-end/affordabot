import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.scraper.san_jose import SanJoseScraper


@pytest.mark.asyncio
async def test_san_jose_scraper_falls_back_when_matter_title_missing():
    scraper = SanJoseScraper()

    matter_response = MagicMock()
    matter_response.raise_for_status.return_value = None
    matter_response.json.return_value = [
        {
            "MatterId": 123,
            "MatterFile": "25-001",
            "MatterTitle": None,
            "MatterName": "Fallback Matter Name",
            "MatterStatusName": "Introduced",
            "MatterIntroDate": "2025-01-10T00:00:00Z",
        }
    ]

    text_response = MagicMock()
    text_response.status_code = 200
    text_response.json.return_value = []

    client = AsyncMock()
    client.get.side_effect = [matter_response, text_response]

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = client
        bills = await scraper.scrape()

    assert len(bills) == 1
    assert bills[0].title == "Fallback Matter Name"
    assert bills[0].text == "Fallback Matter Name"
