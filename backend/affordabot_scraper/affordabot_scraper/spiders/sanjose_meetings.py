from city_scrapers_core.spiders import LegistarSpider
from datetime import datetime

class SanJoseMeetingsSpider(LegistarSpider):
    name = "sanjose_meetings"
    agency = "San Jose"
    timezone = "America/Los_Angeles"
    allowed_domains = ["sanjose.legistar.com"]
    start_urls = ["https://sanjose.legistar.com/Calendar.aspx"]
    
    # LegistarSpider configuration
    link_types = [] # Scrape all links
    
    def parse_legistar(self, events):
        """
        Parse events yielded by LegistarSpider.
        """
        for event in events:
            # Add custom filtering or processing here if needed
            # For now, just pass through the structured data
            event["scraped_at"] = datetime.utcnow().isoformat()
            yield event

