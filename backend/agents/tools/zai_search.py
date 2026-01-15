from llm_common.agents.tools import BaseTool, ToolMetadata, ToolParameter, ToolResult
from llm_common.agents.provenance import Evidence, EvidenceEnvelope
from services.research.zai import ZaiResearchService

class ZaiSearchTool(BaseTool):
    """A tool to perform exhaustive research using the Z.ai service."""

    def __init__(self, zai_service: ZaiResearchService | None = None):
        self._zai_service = zai_service or ZaiResearchService()

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="zai_search",
            description="Performs exhaustive web research on a legislative bill using the Z.ai service.",
            parameters=[
                ToolParameter(
                    name="bill_text",
                    type="string",
                    description="The full text of the bill to research.",
                    required=True,
                ),
                ToolParameter(
                    name="bill_number",
                    type="string",
                    description="The official number of the bill (e.g., 'AB-123').",
                    required=True,
                ),
            ],
        )

    async def execute(self, bill_text: str, bill_number: str) -> ToolResult:
        """
        Executes the Z.ai research and wraps the results in an EvidenceEnvelope.
        """
        try:
            research_package = await self._zai_service.search_exhaustively(
                bill_text=bill_text, bill_number=bill_number
            )

            evidence_items = []
            for source in research_package.sources:
                evidence_items.append(
                    Evidence(
                        kind="url",
                        label=source.title or "Web Search Result",
                        url=source.url or "",
                        content=source.snippet or "",
                        tool_name=self.metadata.name,
                    )
                )

            envelope = EvidenceEnvelope(
                evidence=evidence_items,
                source_tool=self.metadata.name,
                source_query=f"Research on {bill_number}",
            )

            return ToolResult(
                success=True,
                data={"summary": research_package.summary, "key_facts": research_package.key_facts},
                evidence=[envelope],
                source_urls=[source.url for source in research_package.sources if source.url],
            )
        except Exception as e:
            return ToolResult(success=False, error=f"ZaiSearchTool failed: {str(e)}")
