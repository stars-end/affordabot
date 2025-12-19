from services.scraper.saratoga import SaratogaScraper
from services.scraper.san_jose import SanJoseScraper
from services.scraper.santa_clara_county import SantaClaraCountyScraper
from services.scraper.california_state import CaliforniaStateScraper
from services.scraper.city_scrapers_adapter import SanJoseCSAdapter
from services.scraper.nyc import NYCScraper

SCRAPERS = {
    "saratoga": (SaratogaScraper, "city"),
    "san-jose-cityscrapers": (SanJoseCSAdapter, "city"), # Keep new for later fix
    "san-jose": (SanJoseScraper, "city"), # Revert to reliable API scraper for pilot
    "sanjose": (SanJoseScraper, "city"), # Alias for legacy/frontend compatibility
    "santa-clara-county": (SantaClaraCountyScraper, "county"),
    "california": (CaliforniaStateScraper, "state"),
    "nyc": (NYCScraper, "city")
}
