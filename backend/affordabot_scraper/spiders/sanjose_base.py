import scrapy
from typing import Generator, Dict, Any

class SanJoseBaseSpider(scrapy.Spider):
    """
    Base spider for San Jose Legistar scraping.
    Provides common parsing logic for Calendar/Agendas tables.
    """
    allowed_domains = ["sanjose.legistar.com"]
    
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        raise NotImplementedError("Subclasses must implement parse method")
