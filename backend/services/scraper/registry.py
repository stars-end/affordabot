from services.scraper.saratoga import SaratogaScraper
from services.scraper.san_jose import SanJoseScraper
from services.scraper.santa_clara_county import SantaClaraCountyScraper
from services.scraper.california_state import CaliforniaStateScraper

SCRAPERS = {
    "saratoga": (SaratogaScraper, "city"),
    "san-jose": (SanJoseScraper, "city"),
    "santa-clara-county": (SantaClaraCountyScraper, "county"),
    "california": (CaliforniaStateScraper, "state")
}
