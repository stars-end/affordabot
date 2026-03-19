"""
RetrieverTool for RAG-based semantic search.

This tool wraps the PgVector backend for semantic similarity search
across ingested documents for policy analysis.
"""

import logging
import os
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

    In production mode (ENVIRONMENT=production), the tool fails closed
    if no retrieval backend is configured, returning zero chunks instead
    of falling back to mock data.
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
        self._is_production = (
            os.environ.get("ENVIRONMENT", "development").lower() == "production"
        )

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

        if not self._retriever:
            if self._is_production:
                logger.error(
                    "RetrieverTool: No retrieval_backend in production mode. "
                    "Returning zero results (fail closed)."
                )
                return ToolResult(
                    success=False,
                    data={"query": query, "documents": [], "count": 0},
                    source_urls=[],
                    evidence=[],
                    error="No retrieval backend configured in production",
                )
            logger.warning(
                "RetrieverTool: Using mock mode (no retrieval_backend, non-production)"
            )
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
        else:
            try:
                documents = await self._retriever.retrieve(
                    query=query,
                    top_k=k,
                    filters=filters or {},
                )
            except Exception as e:
                logger.error(f"RetrieverTool retrieval failed for '{query}': {e}")
                if self._is_production:
                    return ToolResult(
                        success=False,
                        data={"query": query, "documents": [], "count": 0},
                        source_urls=[],
                        evidence=[],
                        error=f"Retrieval failed: {e}",
                    )
                documents = []

        source_urls: List[str] = []
        evidence_items: List[Evidence] = []

        for i, doc in enumerate(documents):
            if hasattr(doc, "source"):
                url = doc.source
                content = doc.content
                title = getattr(doc, "metadata", {}).get("title", f"Document {i + 1}")
                score = getattr(doc, "score", 0.0)
            elif isinstance(doc, dict):
                url = doc.get("url", "")
                content = doc.get("content", "")
                title = doc.get("title", f"Document {i + 1}")
                score = doc.get("score", 0.0)
            else:
                continue

            if url:
                source_urls.append(url)

            evidence_items.append(
                Evidence(
                    kind="internal",
                    label=title,
                    url=url,
                    content=content[:500] if content else "",
                    excerpt=content[:200] if content else "",
                    confidence=score,
                    metadata={"rank": i + 1},
                )
            )

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
