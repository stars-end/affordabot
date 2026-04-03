from typing import List
from .base import LegistarMatterScraper, ScrapedBill


class SantaClaraCountyScraper(LegistarMatterScraper):
    def __init__(self):
        super().__init__(
            "County of Santa Clara",
            legistar_clients=["sccgov"],
        )

    def _get_mock_data(self) -> List[ScrapedBill]:
        from datetime import date

        return [
            ScrapedBill(
                bill_number="2025-01",
                title="Resolution Regarding County Budget Allocation",
                text="The Board of Supervisors of Santa Clara County hereby resolves...",
                introduced_date=date(2025, 1, 15),
                status="Proposed",
                raw_html="<mock>"
            )
        ]
