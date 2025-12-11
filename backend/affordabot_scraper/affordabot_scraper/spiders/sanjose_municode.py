import scrapy
from datetime import datetime
from scrapy_playwright.page import PageMethod

class SanJoseMunicodeSpider(scrapy.Spider):
    name = "sanjose_municode"
    allowed_domains = ["library.municode.com"]
    start_urls = ["https://library.municode.com/ca/san_jose/codes/code_of_ordinances?nodeId=TIT24ZO"]

    custom_settings = {
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
        },
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    }

    def __init__(self, source_id=None, *args, **kwargs):
        super(SanJoseMunicodeSpider, self).__init__(*args, **kwargs)
        self.source_id = source_id # Required by RawScrapePipeline

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        # Wait for the specific content pane to load
                        PageMethod("wait_for_selector", "div.chunk-content"),
                    ],
                },
                callback=self.parse
            )

    async def parse(self, response):
        page = response.meta["playwright_page"]
        
        # Extract title
        title = await page.title()
        
        # Extract main content (Municode usually puts code text in .chunk-content or similar)
        # We'll take the text content of the visible node
        content = await page.inner_text("div.chunk-content")
        
        # We can also scrape sub-nodes if we want more granularity, but for RAG, 
        # ingesting the whole Title 24 landing page is a good start. 
        # Ideally we would crawl children, but let's start with the specific node aimed at.
        
        await page.close()
        
        # Yield item structure expected by processing pipeline
        # (The RawScrapePipeline will wrap this to JSON)
        yield {
            "title": title,
            "url": response.url,
            "text": content, # Raw extracted text
            "content": content, # Normalized field
            "scraped_at": datetime.utcnow().isoformat(),
            "domain": "library.municode.com"
        }
