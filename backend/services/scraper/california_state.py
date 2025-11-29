from typing import List
from datetime import datetime, date
from .base import BaseScraper, ScrapedBill
import httpx
import os

class CaliforniaStateScraper(BaseScraper):
    def __init__(self):
        super().__init__("State of California")
        self.api_key = os.getenv("OPENSTATES_API_KEY")
        self.base_url = "https://v3.openstates.org"
    
    async def scrape(self) -> List[ScrapedBill]:
        """
        Scrape California State Legislature via Open States API.
        Fetches recent bills from current session.
        """
        if not self.api_key:
            print("OPENSTATES_API_KEY not set, using mock data")
            return self._get_mock_data()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Get recent CA bills
                response = await client.get(
                    f"{self.base_url}/bills",
                    params={
                        "jurisdiction": "ca",
                        "session": "20252026",  # Current session
                        "per_page": 10,
                        "sort": "updated_desc"
                    },
                    headers={"X-API-KEY": self.api_key}
                )
                response.raise_for_status()
                data = response.json()
                
                bills = []
                for bill in data.get("results", []):
                    # Get full bill text
                    bill_id = bill.get("id")
                    detail_response = await client.get(
                        f"{self.base_url}/bills/{bill_id}",
                        headers={"X-API-KEY": self.api_key}
                    )
                    bill_detail = detail_response.json()
                    
                    # Extract text from versions
                    versions = bill_detail.get("versions", [])
                    full_text = ""
                    if versions:
                        # Get latest version text
                        latest = versions[0]
                        full_text = latest.get("note", "") or bill_detail.get("title", "")
                    
                    bills.append(ScrapedBill(
                        bill_number=bill.get("identifier", "Unknown"),
                        title=bill.get("title", "Untitled"),
                        text=full_text or bill.get("title", ""),
                        introduced_date=datetime.fromisoformat(bill["created_at"].replace("Z", "+00:00")).date() if bill.get("created_at") else None,
                        status=bill.get("latest_action_description", "Unknown"),
                        raw_html=str(bill)
                    ))
                
                return bills
            
            except Exception as e:
                print(f"Open States API error: {e}")
                return self._get_mock_data()
    
    def _get_mock_data(self) -> List[ScrapedBill]:
        return [
            ScrapedBill(
                bill_number="AB 100",
                title="An act to amend Section 1234 of the Health and Safety Code, relating to housing affordability.",
                text="The people of the State of California do enact as follows: SECTION 1. Section 1234 of the Health and Safety Code is amended to read...",
                introduced_date=date(2025, 1, 20),
                status="In Committee",
                raw_html="<mock>"
            )
        ]
