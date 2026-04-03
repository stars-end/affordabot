from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.scraper.city_scrapers_adapter import CityScrapersAdapter, SunnyvaleCSAdapter
from services.scraper.registry import SCRAPERS
from services.scraper.san_jose import SanJoseScraper
from services.scraper.santa_clara_county import SantaClaraCountyScraper


@pytest.mark.asyncio
async def test_san_jose_scraper_uses_attachment_fallback_when_text_unsupported():
    scraper = SanJoseScraper()

    matter_response = MagicMock()
    matter_response.raise_for_status.return_value = None
    matter_response.json.return_value = [
        {
            "MatterId": 42,
            "MatterFile": "25-042",
            "MatterTitle": "Housing Policy Update",
            "MatterStatusName": "Introduced",
            "MatterIntroDate": "2025-01-10T00:00:00Z",
        }
    ]

    text_response = MagicMock()
    text_response.status_code = 405

    attachment_response = MagicMock()
    attachment_response.status_code = 200
    attachment_response.json.return_value = [
        {
            "MatterAttachmentName": "Agenda Packet",
            "MatterAttachmentHyperlink": "https://example.gov/packet.pdf",
        }
    ]

    client = AsyncMock()
    client.get.side_effect = [matter_response, text_response, attachment_response]

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = client
        bills = await scraper.scrape()

    assert len(bills) == 1
    assert "Attachment: Agenda Packet" in (bills[0].text or "")
    assert "https://example.gov/packet.pdf" in (bills[0].text or "")


@pytest.mark.asyncio
async def test_santa_clara_scraper_uses_common_title_fallback():
    scraper = SantaClaraCountyScraper()

    matter_response = MagicMock()
    matter_response.raise_for_status.return_value = None
    matter_response.json.return_value = [
        {
            "MatterId": 7,
            "MatterFile": "2025-07",
            "MatterTitle": None,
            "MatterName": "County Budget Session",
            "MatterStatusName": "Scheduled",
            "MatterIntroDate": "2025-02-01T00:00:00Z",
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
    assert bills[0].title == "County Budget Session"


def test_city_scrapers_adapter_maps_links_to_text():
    bill = CityScrapersAdapter._item_to_scraped_bill(
        {
            "id": "sunnyvale-1",
            "title": "City Council Meeting",
            "description": "Meeting artifacts",
            "start": "2025-03-01T00:00:00Z",
            "links": [{"title": "Agenda", "href": "https://example.gov/a.pdf"}],
            "source": "https://sunnyvaleca.legistar.com/Calendar.aspx",
        }
    )

    assert bill.bill_number == "sunnyvale-1"
    assert bill.introduced_date == date(2025, 3, 1)
    assert "Agenda" in (bill.text or "")
    assert "https://example.gov/a.pdf" in (bill.text or "")


def test_registry_exposes_sunnyvale_pack_a_lane():
    scraper_class, jurisdiction_type = SCRAPERS["sunnyvale"]
    assert jurisdiction_type == "city"
    assert scraper_class is SunnyvaleCSAdapter
