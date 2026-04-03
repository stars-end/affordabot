import scrapy


class SunnyvaleAgendasSpider(scrapy.Spider):
    name = "sunnyvale_agendas"
    allowed_domains = ["sunnyvaleca.legistar.com"]
    start_urls = ["https://sunnyvaleca.legistar.com/Calendar.aspx"]

    def parse(self, response):
        # Legistar renders alternating row classes.
        rows = response.css("table.rgMasterTable tr.rgRow, table.rgMasterTable tr.rgAltRow")
        for index, row in enumerate(rows):
            meeting_date = (row.css("td:nth-child(2)::text").get() or "").strip()
            body_name = (row.css("td:nth-child(1)::text").get() or "City Council").strip()

            links = []
            for label in ("Agenda", "Minutes", "Packet", "Video"):
                href = row.xpath(f".//a[contains(normalize-space(), '{label}')]/@href").get()
                if href:
                    links.append({"title": label, "href": response.urljoin(href)})

            if not links:
                continue

            yield {
                "source": response.url,
                "id": f"sunnyvale-{meeting_date or 'unknown'}-{index}",
                "title": f"{body_name} Meeting {meeting_date}".strip(),
                "description": f"Sunnyvale meeting artifacts for {meeting_date}".strip(),
                "start": None,
                "links": links,
                "source_url": response.url,
            }
