from affordabot_scraper.spiders.sanjose_base import SanJoseBaseSpider
from affordabot_scraper.items import ContentItem

class SanJoseMinutesSpider(SanJoseBaseSpider):
    name = "sanjose_minutes"
    start_urls = ["https://sanjose.legistar.com/Calendar.aspx"]
    
    def parse(self, response):
        # Placeholder logic for Minutes
        # In a real implementation, this would use the same LinkExtractor patterns
        # but filter for "Minutes" columns instead of "Agenda"
        for row in response.css("table.rgMasterTable tr.rgRow, table.rgMasterTable tr.rgAltRow"):
            meeting_date = row.css("td:nth-child(2)::text").get()
            minutes_url = row.xpath(".//a[contains(text(), 'Minutes')]/@href").get()
            
            if minutes_url:
                yield {
                    "source": "sanjose_minutes",
                    "title": f"City Council Minutes {meeting_date}",
                    "url": response.urljoin(minutes_url),
                    "date": meeting_date,
                    "content_type": "minutes"
                }
