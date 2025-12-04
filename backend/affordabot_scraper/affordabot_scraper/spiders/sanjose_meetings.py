import scrapy
from datetime import datetime

class SanJoseMeetingsSpider(scrapy.Spider):
    name = "sanjose_meetings"
    allowed_domains = ["sanjose.legistar.com"]
    start_urls = ["https://sanjose.legistar.com/Calendar.aspx"]

    def parse(self, response):
        # This is a simplified parser for the skeleton.
        # In a real implementation, we'd handle pagination and detailed parsing.
        
        # Legistar usually has a main table with id="ctl00_ContentPlaceHolder1_gridCalendar_ctl00"
        # We'll just grab the rows for now.
        
        rows = response.css("table.rgMasterTable tr.rgRow, table.rgMasterTable tr.rgAltRow")
        
        if not rows:
            self.logger.warning("No rows found with specific selector. Yielding page title as fallback.")
            yield {
                "type": "meeting_fallback",
                "name": response.css("title::text").get(),
                "scraped_at": datetime.utcnow().isoformat(),
                "raw_html_snippet": response.text[:200]
            }
        
        for row in rows:
            # Extract basic info
            name = row.css("td:nth-child(1) a::text").get()
            date = row.css("td:nth-child(2)::text").get()
            time = row.css("td:nth-child(3)::text").get()
            meeting_details_url = row.css("td:nth-child(5) a::attr(href)").get()
            agenda_url = row.css("td:nth-child(6) a::attr(href)").get()
            minutes_url = row.css("td:nth-child(7) a::attr(href)").get()

            if name:
                yield {
                    "type": "meeting",
                    "name": name.strip(),
                    "date": date.strip() if date else None,
                    "time": time.strip() if time else None,
                    "links": {
                        "meeting_details": response.urljoin(meeting_details_url) if meeting_details_url else None,
                        "agenda": response.urljoin(agenda_url) if agenda_url else None,
                        "minutes": response.urljoin(minutes_url) if minutes_url else None,
                    },
                    "scraped_at": datetime.utcnow().isoformat()
                }
