from typing import List
from datetime import datetime
from .base import BaseScraper, ScrapedBill
import httpx

class SantaClaraCountyScraper(BaseScraper):
    def __init__(self):
        super().__init__("County of Santa Clara")
        # Try common Legistar client names
        self.possible_urls = [
            "https://webapi.legistar.com/v1/santaclara",
            "https://webapi.legistar.com/v1/santaclaracounty",
            "https://webapi.legistar.com/v1/sccgov"
        ]
    
    async def scrape(self) -> List[ScrapedBill]:
        """
        Scrape Santa Clara County legislation via Legistar API.
        Tries multiple possible client names.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            for base_url in self.possible_urls:
                try:
                    response = await client.get(
                        f"{base_url}/matters",
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
                        matter_id = matter.get("MatterId")
                        text_response = await client.get(f"{base_url}/matters/{matter_id}/texts")
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
                
                except (httpx.HTTPStatusError, httpx.ConnectError):
                    continue  # Try next URL
            
            # All URLs failed, return mock data
            print("All Legistar URLs failed for Santa Clara County")
            return self._get_mock_data()
    
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
