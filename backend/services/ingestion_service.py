"""Ingestion service to process raw scrapes into embedded document chunks."""

from __future__ import annotations
import re
from typing import List, Dict, Any
from uuid import uuid4
import json

# LLM Common v0.4.0+ interfaces
from llm_common.retrieval import RetrievalBackend, RetrievedChunk
from llm_common.embeddings import EmbeddingService
from llm_common import WebSearchResult
# Use absolute import pattern relative to backend root (which is in path)
from contracts.storage import BlobStorage
from typing import Optional

class IngestionService:
    """
    Process raw scrapes into chunked, embedded documents.
    
    Workflow:
    1. Fetch unprocessed raw_scrapes
    2. Extract and clean text
    3. Chunk text
    4. Generate embeddings (via EmbeddingService)
    5. Store in vector backend (via RetrievalBackend)
    """
    
    def __init__(
        self,
        postgres_client: Any, # Required
        vector_backend: RetrievalBackend = None,
        embedding_service: EmbeddingService = None,
        storage_backend: Optional["BlobStorage"] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self.pg = postgres_client
        self.vector_backend = vector_backend
        self.embedding_service = embedding_service
        self.storage_backend = storage_backend
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
        scrape = None
        
        # 1. Fetch raw scrape (Postgres)
        row = await self.pg._fetchrow("SELECT * FROM raw_scrapes WHERE id = $1", scrape_id)
        if row:
            scrape = dict(row)
            # Ensure data is dict if coming from JSONB
            if isinstance(scrape.get('data'), str):
                    try:
                        scrape['data'] = json.loads(scrape['data'])
                    except Exception:
                        pass
            if isinstance(scrape.get('metadata'), str):
                    try:
                        scrape['metadata'] = json.loads(scrape['metadata'])
                    except Exception:
                        pass
            
        if not scrape:
             print(f"⚠️ Raw scrape {scrape_id} not found.")
             return 0

        # 2. Extract text from data
        text = self._extract_text(scrape['data'])
        
        if not text:
            print(f"⚠️ No text extracted for scrape {scrape_id}")
            return 0

        # 2.5 Upload to Blob Storage (New)
        if self.storage_backend and scrape.get('data'):
             try:
                 # Construct path: jurisdiction/YYYY/MM/scrape_id.html
                 from datetime import datetime
                 now = datetime.now()
                 ext = ".html" # Default
                 if scrape.get('content_type') == 'application/pdf':
                     ext = ".pdf"
                 
                 # Handle source_id potentially being UUID in PG
                 source_identifier = str(scrape.get('source_id', 'unknown'))
                 path = f"{source_identifier}/{now.year}/{now.month}/{scrape_id}{ext}"
                 
                 content_bytes = str(scrape['data']).encode('utf-8') # Simple for now
                 if isinstance(scrape['data'], dict) and 'content' in scrape['data']:
                     content_bytes = str(scrape['data']['content']).encode('utf-8')
                     
                 uri = await self.storage_backend.upload(path, content_bytes)
                 
                 # Update raw_scrape with storage URI
                 await self.pg._execute("UPDATE raw_scrapes SET storage_uri = $1 WHERE id = $2", uri, scrape_id)
                 
             except Exception as e:
                 print(f"⚠️ Storage upload failed: {e}")
                 # Non-blocking, continue ingestion

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
        if not isinstance(scrape_meta, dict):
            scrape_meta = {}
        
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            # Construct metadata
            metadata = {
                "source_id": str(scrape['source_id']),
                "scrape_id": scrape_id,
                "document_id": document_id, # Required for 'documents' table column mapping
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
            doc_chunks.append(doc_chunk.model_dump())
        
        # 6. Store in vector backend
        await self.vector_backend.upsert(doc_chunks)
        
        # 7. Mark scrape as processed
        await self.pg._execute(
            "UPDATE raw_scrapes SET processed = $1, document_id = $2 WHERE id = $3",
            True, document_id, scrape_id
        )
        
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
    async def ingest_from_search_result(self, result: 'WebSearchResult', source_id: str = "web_search") -> Optional[str]:
        """
        Ingest a WebSearchResult into the system.
        """
        import hashlib
        
        try:
            # 1. Resolve Source ID (Check 'sources' table)
            row = await self.pg._fetchrow("SELECT id FROM sources WHERE url = $1", result.url)
            
            if row:
                db_source_id = row['id']
            else:
                # Create source
                db_source_id = await self.pg.get_or_create_source(
                    jurisdiction_id="web", # generic - TODO: Ensure 'web' jurisdiction exists or handle UUID
                    name=result.title,
                    type="general"
                )
                if not db_source_id:
                    print(f"❌ Failed to create source for {result.url}")
                    return None

            # Prepare Data
            active_content = result.content or result.snippet or ""
            content_hash = hashlib.sha256(active_content.encode('utf-8')).hexdigest()
            
            data_payload = {
                "active_content": active_content,
                "title": result.title,
                "snippet": result.snippet,
                "published_date": str(result.published_date) if result.published_date else None,
                "metadata": {
                    "title": result.title,
                    "domain": result.domain
                }
            }
            
            raw_data = {
                "source_id": db_source_id,
                "content_hash": content_hash,
                "content_type": "text/html",
                "data": data_payload,
                "url": result.url,
                "metadata": data_payload["metadata"]
            }
            
            # Insert Raw Scrape via PG
            scrape_id = await self.pg.create_raw_scrape(raw_data)
            
            if not scrape_id:
                 return None
            
            # 3. Process
            chunks = await self.process_raw_scrape(scrape_id)
            if chunks > 0:
                # Fetch updated document_id
                try:
                    row = await self.pg._fetchrow("SELECT document_id FROM raw_scrapes WHERE id = $1", scrape_id)
                    return row['document_id'] if row else None
                except Exception:
                    return None
            
            return None

        except Exception as e:
            print(f"❌ Ingestion error for {result.url}: {e}")
            return None
