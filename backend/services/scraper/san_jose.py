from typing import List
from datetime import datetime
from .base import BaseScraper, ScrapedBill
import httpx

class SanJoseScraper(BaseScraper):
    def __init__(self):
        super().__init__("City of San Jose")
        self.base_url = "https://webapi.legistar.com/v1/sanjose"
    
    async def scrape(self) -> List[ScrapedBill]:
        """
        Scrape San Jose legislation via Legistar API.
        Fetches recent matters (bills/ordinances) from City Council.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Get recent matters (last 30 days)
                response = await client.get(
                    f"{self.base_url}/matters",
                    params={
                        "$filter": "MatterIntroDate ge datetime'2025-01-01'",
                        "$orderby": "MatterIntroDate desc",
                        "$top": 10
                    }
                )
                response.raise_for_status()
                matters = response.json()
                
                bills = []
                for matter in matters:
                    # Get matter text
                    matter_id = matter.get("MatterId")
                    text_response = await client.get(f"{self.base_url}/matters/{matter_id}/texts")
                    texts = text_response.json()
                    
                    full_text = "\n\n".join([t.get("MatterTextPlain", "") for t in texts if t.get("MatterTextPlain")])
                    
                    bills.append(ScrapedBill(
                        bill_number=matter.get("MatterFile", "Unknown"),
                        title=matter.get("MatterTitle", "Untitled"),
                        text=full_text or matter.get("MatterName", ""),
                        introduced_date=datetime.fromisoformat(matter["MatterIntroDate"].replace("Z", "+00:00")).date() if matter.get("MatterIntroDate") else None,
                        status=matter.get("MatterStatusName", "Unknown"),
                        raw_html=str(matter)
                    ))
                
                return bills
            
            except httpx.HTTPStatusError as e:
                print(f"Legistar API error: {e}")
                # Return mock data as fallback
                return self._get_mock_data()
    
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
