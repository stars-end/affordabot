from llm_common.agents.provenance import Evidence, EvidenceEnvelope
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
            A ToolResult containing an EvidenceEnvelope with the research results.
        """
        try:
            research_package: ResearchPackage = await self._service.search_exhaustively(
                bill_text=bill_text, bill_number=bill_number
            )

            envelope = EvidenceEnvelope(
                source_tool=self.metadata.name,
                metadata={"bill_number": bill_number},
            )

            for source in research_package.sources:
                if source.url:
                    evidence = Evidence(
                        kind="url",
                        label=source.title or "Source",
                        url=source.url,
                        content=source.content or "",
                        excerpt=source.content[:500] if source.content else "",
                        metadata={
                            "publisher": source.publisher,
                            "publish_date": str(source.publish_date)
                            if source.publish_date
                            else None,
                        },
                    )
                    envelope.add(evidence)

            # Also add summary and key facts as evidence
            envelope.add(
                Evidence(
                    kind="summary",
                    label="Research Summary",
                    content=research_package.summary,
                    excerpt=research_package.summary[:500],
                )
            )
            for i, fact in enumerate(research_package.key_facts):
                envelope.add(
                    Evidence(
                        kind="fact",
                        label=f"Key Fact {i+1}",
                        content=fact,
                        excerpt=fact[:500],
                    )
                )

            return ToolResult(
                success=True,
                data={"envelope": envelope.model_dump()},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"An unexpected error occurred: {e}")
