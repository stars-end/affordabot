from typing import List

from .base import LegistarMatterScraper, ScrapedBill


class SanJoseScraper(LegistarMatterScraper):
    def __init__(self):
        super().__init__(
            "City of San Jose",
            legistar_clients=["sanjose"],
        )

    def _get_mock_data(self) -> List[ScrapedBill]:
        from datetime import date

        return [
            ScrapedBill(
                bill_number="25-001",
                title="Ordinance Regarding Affordable Housing Requirements",
                text="The City Council of San Jose hereby ordains...",
                introduced_date=date(2025, 1, 10),
                status="Proposed",
                raw_html="<mock>"
            )
        ]
