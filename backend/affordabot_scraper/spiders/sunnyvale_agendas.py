import scrapy

class SunnyvaleAgendasSpider(scrapy.Spider):
    name = "sunnyvale_agendas"
    allowed_domains = ["sunnyvaleca.legistar.com"]
    start_urls = ["https://sunnyvaleca.legistar.com/Calendar.aspx"]

    def parse(self, response):
        # Placeholder for MVP V2
        # Real logic would extract rows from Legistar grid
        for row in response.css("table.rgMasterTable tr.rgRow"):
            meeting_date = row.css("td:nth-child(2)::text").get()
            agenda_url = row.xpath(".//a[contains(text(), 'Agenda')]/@href").get()
            
            if agenda_url:
                yield {
                    "source": "sunnyvale_agendas",
                    "title": f"City Council Agenda {meeting_date}",
                    "url": response.urljoin(agenda_url),
                    "date": meeting_date
                }
