from typing import Type, TypeVar
from pydantic import BaseModel
from urllib.parse import urlparse

from backend.contracts.extraction import ExtractorClient
from backend.services.extractors.zai import ZaiExtractor
from backend.services.extractors.playwright_extractor import PlaywrightExtractor

T = TypeVar("T", bound=BaseModel)

class ExtractionRouter:
    """
    Routes URLs to the appropriate extractor based on domain rules and content type.
    """
    
    def __init__(self, zai_api_key: str):
        self.zai_extractor = ZaiExtractor(api_key=zai_api_key)
        self.playwright_extractor = PlaywrightExtractor()
        
    async def extract(self, url: str, schema: Type[T]) -> T:
        """
        Route and extract data from the URL.
        """
        extractor = self._select_extractor(url)
        print(f"🔄 Routing {url} to {extractor.__class__.__name__}")
        
        try:
            return await extractor.extract(url, schema)
        except Exception as e:
            # Fallback Logic
            if isinstance(extractor, ZaiExtractor):
                print(f"⚠️ ZaiExtractor failed: {e}. Retrying with PlaywrightExtractor...")
                return await self.playwright_extractor.extract(url, schema)
            raise e

    def _select_extractor(self, url: str) -> ExtractorClient:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # Rule 1: Files (PDF, DOCX) -> Z.ai (Better OCR/Parsing)
        if path.endswith(('.pdf', '.docx', '.doc')):
            return self.zai_extractor
            
        # Rule 2: Known SPAs -> Playwright
        spa_domains = [
            "municode.com",
            "library.municode.com",
            "311.sanjoseca.gov",
            "sanjose.granicus.com" # Video players often fail in simple readers
        ]
        
        if any(d in domain for d in spa_domains):
            return self.playwright_extractor
            
        # Rule 3: Default -> Z.ai
        return self.zai_extractor
