import logging
import asyncio
from typing import List, Any
from dataclasses import dataclass

from llm_common import WebSearchResult, LLMClient, LLMMessage, MessageRole

from services.ingestion_service import IngestionService
from services.discovery.search_discovery import SearchDiscoveryService
from services.retrieval.custom_pgvector_backend import CustomPgVectorBackend

logger = logging.getLogger(__name__)

@dataclass
class SearchResponse:
    answer: str
    citations: List[WebSearchResult]
    context_used: List[Any]

class SearchPipelineService:
    """
    Orchestrates the End-to-End Search Pipeline:
    1. Discovery (Find Sources)
    2. Ingestion (Index Sources)
    3. Retrieval (Find Relevant Chunks)
    4. Synthesis (Generate Answer)
    """

    def __init__(
        self,
        discovery: SearchDiscoveryService,
        ingestion: IngestionService,
        retrieval: CustomPgVectorBackend, # Custom backend for Affordabot
        llm: LLMClient
    ):
        self.discovery = discovery
        self.ingestion = ingestion
        self.retrieval = retrieval
        self.llm = llm

    async def search(self, query: str, limit_sources: int = 5) -> SearchResponse:
        """
        Execute full search pipeline for a user query.
        """
        logger.info(f"🔎 Pipeline executing for: '{query}'")

        # 1. Discovery
        # For now, we use SearchDiscoveryService (Z.ai) as primary
        # Logic to route to CityScrapers/Municode could sit here or in a wrapper Router
        logger.info("   ↳ Step 1: Discovery...")
        results = await self.discovery.find_urls(query)
        
        # Filter / Limit
        valid_results = [r for r in results if r.url][:limit_sources]
        logger.info(f"     Found {len(valid_results)} sources.")

        # 2. Ingestion (Parallel)
        logger.info("   ↳ Step 2: Ingestion & Indexing...")
        doc_ids = []
        
        # Run ingestion in parallel
        ingest_tasks = [
            self.ingestion.ingest_from_search_result(res, source_id="pipeline_search")
            for res in valid_results
        ]
        
        # Use return_exceptions=True to prevent one failure killing all
        ingested_ids = await asyncio.gather(*ingest_tasks, return_exceptions=True)
        
        for doc_id in ingested_ids:
            if isinstance(doc_id, str):
                doc_ids.append(doc_id)
            elif isinstance(doc_id, Exception):
                logger.warning(f"     Ingestion error: {doc_id}")

        logger.info(f"     Indexed {len(doc_ids)} documents.")
        
        if not doc_ids:
            return SearchResponse(
                answer="I couldn't find any relevant sources to answer your question.",
                citations=[],
                context_used=[]
            )

        # 3. Retrieval
        # We retrieve from the docs we just found (doc_ids) + potentially others?
        # Standard RAG usually searches the whole KB.
        # But here valid_results are the "Fresh" context.
        # Let's search specifically within these documents if possible, or global?
        # Global is better if we have historical data. 
        # But for specific "Search" query, we want the fresh results.
        # SupabasePgVectorBackend.query doesn't typically support 'filter by doc_ids' in pure semantic search 
        # unless we implemented metadata filtering.
        # Let's assume global search for now, picking up new chunks because they embed similarly to query.
        
        logger.info("   ↳ Step 3: Retrieval...")
        chunks = await self.retrieval.retrieve(query, top_k=8) # Top 8 chunks
        
        # Optional: Boost chunks from doc_ids?
        # For now, pure semantic.
        
        # 4. Synthesis
        logger.info("   ↳ Step 4: Synthesis...")
        
        context_str = "\n\n".join([c.content for c in chunks])
        
        system_prompt = (
            "You are Affordabot, a helpful housing policy assistant for San Jose.\n"
            "Answer the user's question based ONLY on the provided context.\n"
            "If the context doesn't contain the answer, say you don't know.\n"
            "Cite your sources using [1], [2] etc. where possible."
        )
        
        user_prompt = f"Context:\n{context_str}\n\nQuestion: {query}"
        
        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content=system_prompt),
            LLMMessage(role=MessageRole.USER, content=user_prompt)
        ]
        
        response = await self.llm.chat_completion(
            messages=messages,
            model="gpt-4o" # or configured model
        )
        answer = response.content
        
        return SearchResponse(
            answer=answer,
            citations=valid_results,
            context_used=chunks
        )
