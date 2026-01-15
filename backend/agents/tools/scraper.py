from llm_common.agents.tools import BaseTool, ToolMetadata, ToolParameter, ToolResult
from llm_common.agents.provenance import Evidence, EvidenceEnvelope
from services.scraper.registry import SCRAPERS
from services.scraper.base import ScrapedBill

class ScraperTool(BaseTool):
    """A tool to scrape legislative bills from a specific jurisdiction."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="scrape_legislation",
            description="Scrapes legislative bills from a specified jurisdiction.",
            parameters=[
                ToolParameter(
                    name="jurisdiction",
                    type="string",
                    description="The jurisdiction to scrape (e.g., 'california', 'san-jose').",
                    required=True,
                ),
            ],
        )

    async def execute(self, jurisdiction: str) -> ToolResult:
        """
        Executes the scraper for the given jurisdiction and wraps the results.

        Args:
            jurisdiction: The jurisdiction to scrape.

        Returns:
            A ToolResult containing the scraped bills and an EvidenceEnvelope.
        """
        if jurisdiction not in SCRAPERS:
            return ToolResult(success=False, error=f"Invalid jurisdiction: {jurisdiction}")

        try:
            scraper_class, _ = SCRAPERS[jurisdiction]
            scraper_instance = scraper_class(jurisdiction_name=jurisdiction)
            scraped_bills: list[ScrapedBill] = await scraper_instance.scrape()

            evidence_items = []
            for bill in scraped_bills:
                evidence_items.append(
                    Evidence(
                        kind="legislation",
                        label=f"{bill.bill_number}: {bill.title}",
                        content=bill.text or "",
                        metadata={
                            "bill_number": bill.bill_number,
                            "title": bill.title,
                            "introduced_date": str(bill.introduced_date),
                            "status": bill.status,
                        },
                        tool_name=self.metadata.name,
                    )
                )

            envelope = EvidenceEnvelope(
                evidence=evidence_items,
                source_tool=self.metadata.name,
                source_query=f"Scrape legislation from {jurisdiction}",
            )

            return ToolResult(
                success=True,
                data=[bill.model_dump() for bill in scraped_bills],
                evidence=[envelope],
            )
        except Exception as e:
            return ToolResult(success=False, error=f"ScraperTool failed for {jurisdiction}: {str(e)}")
