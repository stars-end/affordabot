from services.scraper.saratoga import SaratogaScraper
from services.scraper.san_jose import SanJoseScraper
from services.scraper.santa_clara_county import SantaClaraCountyScraper
from services.scraper.california_state import CaliforniaStateScraper
from services.scraper.city_scrapers_adapter import SanJoseCSAdapter

SCRAPERS = {
    "saratoga": (SaratogaScraper, "city"),
    "san-jose-legacy": (SanJoseScraper, "city"), # Keep legacy as backup
    "san-jose": (SanJoseCSAdapter, "city"), # New CityScrapers implementation
    "santa-clara-county": (SantaClaraCountyScraper, "county"),
    "california": (CaliforniaStateScraper, "state")
}
