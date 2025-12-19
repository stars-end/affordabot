"""Ingestion service to process raw scrapes into embedded document chunks."""

from __future__ import annotations
import re
from typing import List, Dict, Any
from uuid import uuid4, UUID
from pydantic import ValidationError

# LLM Common v0.4.0+ interfaces
from llm_common.retrieval import RetrievalBackend, RetrievedChunk
from llm_common.embeddings import EmbeddingService
from llm_common import WebSearchResult
# Use absolute import pattern relative to backend root (which is in path)
from contracts.storage import BlobStorage
from contracts.ingestion import RawScrape
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
        # 1. Fetch and validate raw scrape from Postgres
        row = await self.pg._fetchrow("SELECT * FROM raw_scrapes WHERE id = $1", scrape_id)
        if not row:
            print(f"⚠️ Raw scrape {scrape_id} not found.")
            return 0
        
        # Idempotency Check (if hash already processed in verified legislation?)
        # For now, we trust 'processed' flag on the job. 
        # But if we want to dedupe:
        # if row['processed']: return 0
        
        try:
            # The row from the DB is a dict-like object, but Pydantic V2 model_validate needs an explicit dict
            scrape = RawScrape.model_validate(dict(row))
        except ValidationError as e:
            print(f"❌ Pydantic validation failed for scrape {scrape_id}: {e}")
            await self.pg._execute(
                "UPDATE raw_scrapes SET processed = false, error_message = $1 WHERE id = $2",
                str(e), scrape_id
            )
            return 0

        # 2. Extract text from data
        text = self._extract_text(scrape.data)
        
        if not text:
            print(f"⚠️ No text extracted for scrape {scrape_id}")
            return 0

        # 2.5 Upload to Blob Storage (New)
        if self.storage_backend and scrape.data:
             try:
                 # Construct path: jurisdiction/YYYY/MM/scrape_id.html
                 from datetime import datetime
                 now = datetime.now()
                 ext = ".html" # Default
                 if scrape.content_type == 'application/pdf':
                     ext = ".pdf"
                 
                 source_identifier = str(scrape.source_id)
                 path = f"{source_identifier}/{now.year}/{now.month}/{scrape_id}{ext}"
                 
                 # Get content as bytes
                 if isinstance(scrape.data, dict) and 'content' in scrape.data:
                     content_bytes = str(scrape.data['content']).encode('utf-8')
                 else:
                     content_bytes = str(scrape.data).encode('utf-8')
                     
                 uri = await self.storage_backend.upload(path, content_bytes)
                 
                 # Update raw_scrape with storage URI
                 await self.pg._execute("UPDATE raw_scrapes SET storage_uri = $1 WHERE id = $2", uri, scrape_id)
                 
             except Exception as e:
                 print(f"⚠️ Storage upload failed for scrape {scrape.id}: {e}")
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

        # Scrape metadata is already validated by Pydantic, default_factory ensures it's a dict
        scrape_meta = scrape.metadata
        
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            # Construct metadata
            metadata = {
                "source_id": str(scrape.source_id),
                "scrape_id": scrape.id,
                "document_id": document_id,
                "content_type": scrape.content_type,
                **scrape_meta
            }
            
            doc_chunk = RetrievedChunk(
                content=chunk_text,
                embedding=embedding,
                metadata=metadata,
                chunk_id=str(uuid4()), # Explicit chunk ID
                source=scrape.url,
                score=1.0 # Default score (not relevant for storage)
            )
            
            # Pydantic dump
            chunk_data = doc_chunk.model_dump()
            
            # Inject generic fields that LocalPgVectorBackend expects
            # (RetrievedChunk defines 'chunk_id', but Postgres uses 'id')
            chunk_data['id'] = chunk_data['chunk_id']
            chunk_data['document_id'] = document_id
            
            doc_chunks.append(chunk_data)
        
        # 6. Store in vector backend
        try:
            await self.vector_backend.upsert(doc_chunks)
            
            # 7. Mark scrape as processed
            await self.pg._execute(
                "UPDATE raw_scrapes SET processed = $1, document_id = $2, error_message = NULL WHERE id = $3",
                True, document_id, scrape_id
            )
        except Exception as e:
            await self.pg._execute(
                "UPDATE raw_scrapes SET processed = false, error_message = $1 WHERE id = $2",
                f"Vector Upsert Failed: {e}", scrape_id
            )
            raise e
        
        return len(doc_chunks)
    
    def _extract_text(self, data: Dict[str, Any]) -> str:
        """Extract text from scraped data."""
        if not data:
            return ""
        if isinstance(data, str):
            return self._clean_html(data)
        
        if isinstance(data, dict):
            # Prioritize common text fields
            for field in ['text', 'content', 'body', 'raw_html_snippet', 'description']:
                if field in data and data.get(field) and isinstance(data[field], str):
                    cleaned_text = self._clean_html(data[field])
                    if cleaned_text:
                        return cleaned_text
            
            # Fallback: concatenate all string values, but only if they are not just whitespace
            texts = [str(v).strip() for v in data.values() if isinstance(v, str)]
            non_empty_texts = [t for t in texts if t and t.strip()]
            if non_empty_texts:
                return ' '.join(non_empty_texts)
        
        # If data is not a dict or no text was found, return empty string
        return ""
    
    def _clean_html(self, html: str) -> str:
        """Clean HTML tags and normalize whitespace."""
        # Simple regex clean - okay for now, ideally use BS4 or trafilatura
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _chunk_text(self, text: str) -> List[str]:
        """Chunk text into overlapping segments."""
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            
            # If this is not the last chunk, try to find a natural break
            if end < len(text):
                # Find the last space to avoid splitting words
                last_space = chunk.rfind(' ')
                if last_space != -1:
                    end = start + last_space
            
            chunks.append(text[start:end].strip())
            
            # Move start for the next chunk
            start += self.chunk_size - self.chunk_overlap
            
            # If the next start is past the last chunk end, we're done
            if start >= end:
                break
        
        return [c for c in chunks if c]
    async def create_raw_scrape_from_search(self, result: 'WebSearchResult', source_id_uuid: UUID) -> str:
        """
        Creates a raw_scrape record from a WebSearchResult and returns its ID.
        """
        import hashlib
        
        active_content = result.content or result.snippet or ""
        content_hash = hashlib.sha256(active_content.encode('utf-8')).hexdigest()
        
        data_payload = {
            "content": active_content,
            "title": result.title,
            "published_date": str(result.published_date) if result.published_date else None,
        }
        
        metadata = {
            "title": result.title,
            "domain": result.domain,
            "original_snippet": result.snippet,
        }

        # This assumes self.pg has a method `create_raw_scrape` that takes a dictionary
        # and inserts it into the `raw_scrapes` table, returning the new ID.
        scrape_id = await self.pg.create_raw_scrape({
            "source_id": source_id_uuid,
            "url": result.url,
            "data": data_payload,
            "metadata": metadata,
            "content_type": "text/html",
            "content_hash": content_hash,
        })
        
        if not scrape_id:
            raise Exception("Failed to create raw_scrape in database.")
            
        return scrape_id

    async def ingest_from_search_result(self, result: 'WebSearchResult', source_id: str = "web_search") -> int:
        """
        Ingest a WebSearchResult into the system. Returns number of chunks ingested.
        """
        try:
            # 1. Resolve Source ID
            source_id_uuid = await self.pg.get_or_create_source(
                jurisdiction_id="web",
                name=result.title or result.domain,
                type="general",
                url=result.url
            )
            
            if not source_id_uuid:
                print(f"❌ Failed to get or create source for {result.url}")
                return 0

            # 2. Create Raw Scrape
            scrape_id = await self.create_raw_scrape_from_search(result, source_id_uuid)
            
            # 3. Process
            return await self.process_raw_scrape(scrape_id)

        except Exception as e:
            print(f"❌ Ingestion error for {result.url}: {e}")
            return 0
