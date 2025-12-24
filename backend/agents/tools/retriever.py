"""
RetrieverTool for RAG-based semantic search.

This tool wraps the PgVector backend for semantic similarity search
across ingested documents for policy analysis.
"""

import logging
from typing import Any, List, Optional

from llm_common.agents.tools import (
    BaseTool,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)
from llm_common.agents.provenance import Evidence, EvidenceEnvelope

logger = logging.getLogger(__name__)


class RetrieverTool(BaseTool):
    """
    A tool for semantic search using PgVector backend.
    
    Performs RAG-style retrieval to find relevant documents
    for policy analysis and question answering.
    """

    def __init__(self, retrieval_backend: Any = None, embedding_client: Any = None):
        """
        Initialize RetrieverTool.
        
        Args:
            retrieval_backend: PgVector or other retrieval backend instance.
            embedding_client: Client for generating query embeddings.
        """
        self._retriever = retrieval_backend
        self._embedder = embedding_client

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="retriever",
            description=(
                "Searches the knowledge base for relevant documents. "
                "Use this for policy-related questions to find legislation, "
                "meeting minutes, and official documents."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="The search query to find relevant documents.",
                    required=True,
                ),
                ToolParameter(
                    name="k",
                    type="integer",
                    description="Number of documents to retrieve (default: 5).",
                    required=False,
                ),
                ToolParameter(
                    name="filters",
                    type="object",
                    description="Optional filters (e.g., {'jurisdiction': 'San Jose'}).",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        query: str,
        k: int = 5,
        filters: Optional[dict] = None,
    ) -> ToolResult:
        """
        Searches the knowledge base for relevant documents.

        Args:
            query: The search query.
            k: Number of documents to retrieve.
            filters: Optional filter criteria.

        Returns:
            A ToolResult containing retrieved documents and evidence.
        """
        logger.info(f"RetrieverTool: Searching for '{query}' (k={k})")
        
        try:
            if self._retriever:
                # Use real retrieval backend
                documents = await self._retriever.retrieve(
                    query=query,
                    k=k,
                    filters=filters or {},
                )
            else:
                # Mock mode for testing
                logger.warning("RetrieverTool: Using mock mode (no retrieval_backend)")
                documents = [
                    {
                        "content": f"[Mock Document 1] Relevant content for: {query}",
                        "url": "https://example.org/doc1",
                        "title": "Mock Policy Document",
                        "score": 0.95,
                    },
                    {
                        "content": f"[Mock Document 2] Additional context for: {query}",
                        "url": "https://example.org/doc2",
                        "title": "Mock Legislation",
                        "score": 0.88,
                    },
                ]
            
            # Extract source URLs and create evidence
            source_urls: List[str] = []
            evidence_items: List[Evidence] = []
            
            for i, doc in enumerate(documents):
                if hasattr(doc, "url"):
                    url = doc.url
                    content = doc.content
                    title = getattr(doc, "title", f"Document {i+1}")
                elif isinstance(doc, dict):
                    url = doc.get("url", "")
                    content = doc.get("content", "")
                    title = doc.get("title", f"Document {i+1}")
                else:
                    continue
                
                if url:
                    source_urls.append(url)
                
                evidence_items.append(Evidence(
                    kind="internal",
                    label=title,
                    url=url,
                    content=content[:500] if content else "",
                    excerpt=content[:200] if content else "",
                    metadata={"rank": i + 1},
                ))
            
            # Create evidence envelope
            evidence = EvidenceEnvelope(
                source_tool="retriever",
                source_query=query,
                evidence=evidence_items,
            )
            
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "documents": [
                        {
                            "content": e.content,
                            "url": e.url,
                            "title": e.label,
                        }
                        for e in evidence_items
                    ],
                    "count": len(evidence_items),
                },
                source_urls=source_urls,
                evidence=[evidence],
            )
            
        except Exception as e:
            logger.error(f"RetrieverTool failed for '{query}': {e}")
            return ToolResult(
                success=False,
                error=str(e),
            )
