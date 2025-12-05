"""Ingestion service to process raw scrapes into embedded document chunks."""

from __future__ import annotations
import re
from typing import List, Dict, Any, Optional
from uuid import uuid4
from supabase import Client

# LLM Common v0.3.0 interfaces
from llm_common import LLMClient
from llm_common.retrieval import SupabasePgVectorBackend, RetrievedChunk
from llm_common.embeddings import EmbeddingService

class IngestionService:
    """
    Process raw scrapes into chunked, embedded documents.
    
    Workflow:
    1. Fetch unprocessed raw_scrapes
    2. Extract and clean text
    3. Chunk text
    4. Generate embeddings (via EmbeddingService)
    5. Store in vector backend (via SupabasePgVectorBackend)
    """
    
    def __init__(
        self,
        supabase_client: Client,
        vector_backend: SupabasePgVectorBackend,
        embedding_service: EmbeddingService,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self.supabase = supabase_client
        self.vector_backend = vector_backend
        self.embedding_service = embedding_service
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    async def process_raw_scrape(self, scrape_id: str) -> int:
        """
        Process a single raw scrape into embedded chunks.
        
        Args:
            scrape_id: ID of raw_scrape to process
            
        Returns:
            Number of chunks created
        """
        # 1. Fetch raw scrape
        result = self.supabase.table('raw_scrapes').select('*').eq('id', scrape_id).single().execute()
        scrape = result.data
        
        if not scrape:
             print(f"⚠️ Raw scrape {scrape_id} not found.")
             return 0

        # 2. Extract text from data
        text = self._extract_text(scrape['data'])
        
        if not text:
            print(f"⚠️ No text extracted for scrape {scrape_id}")
            return 0

        # 3. Chunk text
        chunks = self._chunk_text(text)
        if not chunks:
             return 0
        
        # 4. Generate embeddings
        try:
            embeddings = await self.embedding_service.embed_documents(chunks)
        except Exception as e:
            print(f"❌ Embedding failed: {e}")
            return 0
        
        # 5. Create RetrievedChunk objects
        document_id = str(uuid4())
        doc_chunks = []
        
        # Ensure scrape metadata is valid
        scrape_meta = scrape.get('metadata') or {}
        
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            # Construct metadata
            metadata = {
                "source_id": scrape['source_id'],
                "scrape_id": scrape_id,
                "content_type": scrape.get('content_type', 'text/html'),
                **scrape_meta
            }
            
            doc_chunk = RetrievedChunk(
                id=str(uuid4()),
                content=chunk_text,
                embedding=embedding,
                metadata=metadata,
                document_id=document_id,
                chunk_id=str(uuid4()), # Explicit chunk ID
                source=scrape.get('url', 'unknown'), # Add source URL
                score=1.0 # Default score (not relevant for storage)
            )
            doc_chunks.append(doc_chunk)
        
        # 6. Store in vector backend
        await self.vector_backend.upsert(doc_chunks)
        
        # 7. Mark scrape as processed
        self.supabase.table('raw_scrapes').update({
            'processed': True,
            'document_id': document_id
        }).eq('id', scrape_id).execute()
        
        return len(doc_chunks)
    
    def _extract_text(self, data: Dict[str, Any]) -> str:
        """Extract text from scraped data."""
        if isinstance(data, str):
            return self._clean_html(data)
        
        if isinstance(data, dict):
            # Try common text fields
            for field in ['text', 'content', 'body', 'raw_html_snippet', 'description']:
                if field in data and data.get(field):
                    return self._clean_html(str(data[field]))
            
            # Fallback: concatenate all string values
            texts = [str(v) for v in data.values() if isinstance(v, (str, int, float))]
            return ' '.join(texts)
        
        return str(data)
    
    def _clean_html(self, html: str) -> str:
        """Clean HTML tags and normalize whitespace."""
        # Simple regex clean - okay for now, ideally use BS4 or trafilatura
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _chunk_text(self, text: str) -> List[str]:
        """Chunk text into overlapping segments."""
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end < len(text):
                # Look for sentence end
                search_start = max(start, end - 100)
                match = re.search(r'[.!?]\s', text[search_start:end])
                if match:
                    end = search_start + match.end()
            
            chunks.append(text[start:end].strip())
            start = end - self.chunk_overlap
        
        return [c for c in chunks if c]
