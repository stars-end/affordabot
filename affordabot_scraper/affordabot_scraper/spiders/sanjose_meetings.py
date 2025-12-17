from city_scrapers_core.spiders import LegistarSpider
from city_scrapers_core.constants import CITY_COUNCIL, BOARD, COMMISSION
from datetime import datetime
from typing import Dict, Any

class SanJoseMeetingsSpider(LegistarSpider):
    name = "sanjose_meetings"
    agency = "City of San Jose"
    timezone = "America/Los_Angeles"
    start_urls = ["https://sanjose.legistar.com/Calendar.aspx"]
    
    # Configure Legistar options (defaults usually work for standard sites)
    link_types = [] 

    def parse_legistar(self, events: Any) -> Any:
        # LegistarSpider.parse typically iterates events and calls _parse_id, etc.
        # But LegistarSpider implementation might vary. 
        # Actually LegistarSpider usually implements parse() to hit the API or page.
        # We just need to define cleaner methods if we want custom data.
        # For now, let's rely on default behavior or basic overrides.
        return super().parse(events)

    def _parse_classification(self, name):
        """Parse or generate classification from allowed constants."""
        if "Council" in name:
            return CITY_COUNCIL
        if "Commission" in name:
            return COMMISSION
        return BOARD
