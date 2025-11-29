from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from pydantic import BaseModel

class ScrapedBill(BaseModel):
    bill_number: str
    title: str
    text: Optional[str] = None
    introduced_date: Optional[date] = None
    status: Optional[str] = None
    raw_html: Optional[str] = None

class BaseScraper(ABC):
    def __init__(self, jurisdiction_name: str):
        self.jurisdiction_name = jurisdiction_name

    @abstractmethod
    async def scrape(self) -> List[ScrapedBill]:
        """
        Scrape legislation from the jurisdiction's source.
        Returns a list of ScrapedBill objects.
        """
        pass
