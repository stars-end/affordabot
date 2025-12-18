import scrapy

class SantaClaraLegislationSpider(scrapy.Spider):
    name = "santa_clara_legislation"
    allowed_domains = ["santaclara.legistar.com"]
    start_urls = ["https://santaclara.legistar.com/Legislation.aspx"]

    def parse(self, response):
        # Placeholder for MVP V2
        # Real logic would extract rows from Legistar grid
        for row in response.css("table.rgMasterTable tr.rgRow"):
            file_number = row.css("td:nth-child(1) a::text").get()
            url = row.css("td:nth-child(1) a::attr(href)").get()
            
            if file_number and url:
                yield {
                    "source": "santa_clara_legislation",
                    "title": f"File {file_number}",
                    "url": response.urljoin(url),
                    "file_number": file_number
                }
