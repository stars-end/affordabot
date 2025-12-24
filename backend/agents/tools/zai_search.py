from llm_common.agents.tools import (
    BaseTool,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)
from services.research.zai import ZaiResearchService, ResearchPackage


class ZaiSearchTool(BaseTool):
    """A tool for conducting exhaustive web searches using the Z.ai Research Service."""

    def __init__(self, service: ZaiResearchService | None = None):
        self._service = service or ZaiResearchService()

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="zai_search",
            description="Conducts an exhaustive web search on a given topic or legislative bill.",
            parameters=[
                ToolParameter(
                    name="bill_text",
                    type="string",
                    description="The full text of the legislative bill to research.",
                    required=True,
                ),
                ToolParameter(
                    name="bill_number",
                    type="string",
                    description="The official number of the bill (e.g., 'AB 123', 'SB 456').",
                    required=True,
                ),
            ],
        )

    async def execute(self, bill_text: str, bill_number: str) -> ToolResult:
        """
        Executes the Z.ai research service to perform an exhaustive search.

        Args:
            bill_text: The text of the bill.
            bill_number: The bill's official number.

        Returns:
            A ToolResult containing the research package, including a summary,
            key facts, and a list of sources.
        """
        try:
            research_package: ResearchPackage = await self._service.search_exhaustively(
                bill_text=bill_text, bill_number=bill_number
            )

            # Extract source URLs for citation
            source_urls = [source.url for source in research_package.sources if source.url]

            return ToolResult(
                success=True,
                data=research_package.model_dump(),
                source_urls=source_urls,
            )
        except Exception as e:
            return ToolResult(success=False, error=f"An unexpected error occurred: {e}")
