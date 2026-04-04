"""Ingestion service to process raw scrapes into embedded document chunks."""

from __future__ import annotations
import re
import json
from typing import List, Dict, Any
from uuid import uuid4, UUID
from pydantic import ValidationError
from datetime import datetime, timezone

# LLM Common v0.4.0+ interfaces
from llm_common.retrieval import RetrievalBackend, RetrievedChunk
from llm_common.embeddings import EmbeddingService
from llm_common import WebSearchResult
# Use absolute import pattern relative to backend root (which is in path)
from contracts.storage import BlobStorage
from contracts.ingestion import RawScrape
from services.substrate_promotion import apply_promotion_decision
from services.substrate_promotion import evaluate_rules
from services.substrate_promotion import seed_capture_promotion_metadata
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

    def _utc_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _parse_json_object(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    async def _persist_ingestion_truth(
        self,
        *,
        scrape_id: str,
        metadata: Dict[str, Any],
        truth_updates: Dict[str, Any],
        processed: Optional[bool] = None,
        document_id: Optional[str] = None,
        error_message: Optional[str] = None,
        clear_error: bool = False,
    ) -> None:
        truth = self._parse_json_object(metadata.get("ingestion_truth"))
        truth.update(truth_updates)
        truth["last_updated_at"] = self._utc_iso()
        metadata["ingestion_truth"] = truth

        set_parts = ["metadata = $1"]
        args: List[Any] = [json.dumps(metadata)]

        if processed is not None:
            set_parts.append(f"processed = ${len(args) + 1}")
            args.append(processed)
        if document_id is not None:
            set_parts.append(f"document_id = ${len(args) + 1}")
            args.append(document_id)
        if error_message is not None:
            set_parts.append(f"error_message = ${len(args) + 1}")
            args.append(error_message)
        elif clear_error:
            set_parts.append("error_message = NULL")

        args.append(scrape_id)
        query = f"UPDATE raw_scrapes SET {', '.join(set_parts)} WHERE id = ${len(args)}"
        await self.pg._execute(query, *args)

    async def _chunk_count_for_document(self, document_id: Optional[str]) -> int:
        if not document_id:
            return 0
        stats = await self.pg.get_vector_stats(document_id)
        return int(stats.get("chunk_count") or 0)
    
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

        row_dict = dict(row)
        row_metadata = self._parse_json_object(row_dict.get("metadata"))
        await self._persist_ingestion_truth(
            scrape_id=scrape_id,
            metadata=row_metadata,
            truth_updates={
                "stage": "raw_captured",
                "raw_captured": True,
                "blob_stored": bool(row_dict.get("storage_uri")),
                "storage_uri_present": bool(row_dict.get("storage_uri")),
                "retrievable": False,
            },
        )
        
        # Idempotency Check (if hash already processed in verified legislation?)
        # For now, we trust 'processed' flag on the job. 
        # But if we want to dedupe:
        # if row['processed']: return 0
        
        try:
            # The row from the DB is a dict-like object, but Pydantic V2 model_validate needs an explicit dict
            scrape = RawScrape.model_validate(row_dict)
        except ValidationError as e:
            print(f"❌ Pydantic validation failed for scrape {scrape_id}: {e}")
            await self._persist_ingestion_truth(
                scrape_id=scrape_id,
                metadata=row_metadata,
                truth_updates={
                    "stage": "validation_failed",
                    "parsed": False,
                    "chunked": False,
                    "embedded": False,
                    "vector_upserted": False,
                    "retrievable": False,
                },
                processed=False,
                error_message=str(e),
            )
            return 0

        # 2. Extract text from data
        text = self._extract_text(scrape.data)
        scrape_meta = self._parse_json_object(scrape.metadata)
        if not scrape_meta:
            scrape_meta = row_metadata

        existing_document_id = row_dict.get("document_id")
        if row_dict.get("processed") and existing_document_id:
            existing_chunk_count = await self._chunk_count_for_document(str(existing_document_id))
            if existing_chunk_count > 0:
                await self._persist_ingestion_truth(
                    scrape_id=scrape_id,
                    metadata=scrape_meta,
                    truth_updates={
                        "stage": "retrievable_existing_row",
                        "vector_upserted": True,
                        "retrievable": True,
                        "retrievable_chunk_count": existing_chunk_count,
                        "document_id": str(existing_document_id),
                    },
                    processed=True,
                    document_id=str(existing_document_id),
                    clear_error=True,
                )
                return existing_chunk_count

        canonical_document_key = row_dict.get("canonical_document_key") or scrape_meta.get(
            "canonical_document_key"
        )
        if canonical_document_key and row_dict.get("content_hash"):
            prior_revision = await self.pg.find_retrievable_raw_scrape_by_content_identity(
                canonical_document_key,
                row_dict["content_hash"],
                exclude_scrape_id=scrape_id,
            )
            if prior_revision and prior_revision.get("document_id"):
                reused_document_id = str(prior_revision["document_id"])
                reused_chunk_count = await self._chunk_count_for_document(reused_document_id)
                if reused_chunk_count > 0:
                    await self._persist_ingestion_truth(
                        scrape_id=scrape_id,
                        metadata=scrape_meta,
                        truth_updates={
                            "stage": "retrievable_existing_revision_reused",
                            "vector_upserted": True,
                            "retrievable": True,
                            "retrievable_chunk_count": reused_chunk_count,
                            "document_id": reused_document_id,
                            "reused_existing_revision": True,
                            "reused_from_raw_scrape_id": str(prior_revision["id"]),
                            "reused_from_revision_number": prior_revision.get("revision_number"),
                        },
                        processed=True,
                        document_id=reused_document_id,
                        clear_error=True,
                    )
                    return reused_chunk_count

        if not text:
            print(f"⚠️ No text extracted for scrape {scrape_id}")
            await self._persist_ingestion_truth(
                scrape_id=scrape_id,
                metadata=scrape_meta,
                truth_updates={
                    "stage": "parse_failed_no_text",
                    "parsed": False,
                    "chunked": False,
                    "embedded": False,
                    "vector_upserted": False,
                    "retrievable": False,
                },
                processed=False,
                error_message="No text extracted from scrape payload",
            )
            return 0

        # 2.5 Upload to Blob Storage (New)
        blob_stored = bool(scrape.storage_uri)
        if self.storage_backend and scrape.data and not scrape.storage_uri:
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
                 blob_stored = True

             except Exception as e:
                 print(f"⚠️ Storage upload failed for scrape {scrape.id}: {e}")
                 # Non-blocking, continue ingestion
                 blob_stored = bool(scrape.storage_uri)

        await self._persist_ingestion_truth(
            scrape_id=scrape_id,
            metadata=scrape_meta,
            truth_updates={
                "stage": "parsed",
                "parsed": True,
                "blob_stored": blob_stored,
                "storage_uri_present": blob_stored,
            },
        )

        # 3. Chunk text
        chunks = self._chunk_text(text)
        if not chunks:
             print(f"⚠️ Chunks empty for scrape {scrape_id}. Text len: {len(text)}")
             await self._persist_ingestion_truth(
                 scrape_id=scrape_id,
                 metadata=scrape_meta,
                 truth_updates={
                     "stage": "chunk_failed_empty",
                     "chunked": False,
                     "chunk_count": 0,
                     "embedded": False,
                     "vector_upserted": False,
                     "retrievable": False,
                 },
                 processed=False,
                 error_message="Chunking produced zero chunks",
             )
             return 0

        print(f"✅ Chunked scrape {scrape_id} into {len(chunks)} chunks.")
        await self._persist_ingestion_truth(
            scrape_id=scrape_id,
            metadata=scrape_meta,
            truth_updates={
                "stage": "chunked",
                "chunked": True,
                "chunk_count": len(chunks),
            },
        )

        # 4. Generate embeddings
        try:
            embeddings = await self.embedding_service.embed_documents(chunks)
        except Exception as e:
            print(f"❌ Embedding failed: {e}")
            await self._persist_ingestion_truth(
                scrape_id=scrape_id,
                metadata=scrape_meta,
                truth_updates={
                    "stage": "embedding_failed",
                    "embedded": False,
                    "embedding_count": 0,
                    "vector_upserted": False,
                    "retrievable": False,
                },
                processed=False,
                error_message=f"Embedding failed: {e}",
            )
            return 0

        await self._persist_ingestion_truth(
            scrape_id=scrape_id,
            metadata=scrape_meta,
            truth_updates={
                "stage": "embedded",
                "embedded": True,
                "embedding_count": len(embeddings),
            },
        )
        
        # 5. Create RetrievedChunk objects
        document_id = str(uuid4())
        doc_chunks = []

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
            upsert_ok = await self.vector_backend.upsert(doc_chunks)
            if not upsert_ok:
                await self._persist_ingestion_truth(
                    scrape_id=scrape_id,
                    metadata=scrape_meta,
                    truth_updates={
                        "stage": "vector_upsert_failed",
                        "vector_upserted": False,
                        "retrievable": False,
                    },
                    processed=False,
                    error_message="Vector Upsert Failed: backend returned false",
                )
                return 0

            count_row = await self.pg._fetchrow(
                "SELECT COUNT(*) AS cnt FROM document_chunks WHERE document_id = $1",
                document_id,
            )
            retrievable_count = int(count_row["cnt"]) if count_row and count_row["cnt"] is not None else 0
            retrievable = retrievable_count > 0
            stage = "retrievable" if retrievable else "vector_upserted_not_retrievable"

            await self._persist_ingestion_truth(
                scrape_id=scrape_id,
                metadata=scrape_meta,
                truth_updates={
                    "stage": stage,
                    "vector_upserted": True,
                    "retrievable": retrievable,
                    "retrievable_chunk_count": retrievable_count,
                    "document_id": document_id,
                },
                processed=retrievable,
                document_id=document_id,
                error_message=(
                    None
                    if retrievable
                    else "Vector upsert completed but no retrievable chunks were found"
                ),
                clear_error=retrievable,
            )
        except Exception as e:
            await self._persist_ingestion_truth(
                scrape_id=scrape_id,
                metadata=scrape_meta,
                truth_updates={
                    "stage": "vector_upsert_exception",
                    "vector_upserted": False,
                    "retrievable": False,
                },
                processed=False,
                error_message=f"Vector Upsert Failed: {e}",
            )
            raise e

        return retrievable_count if retrievable_count > 0 else 0
    
    def _extract_text(self, data: Dict[str, Any]) -> str:
        """Extract text from scraped data."""
        if not data:
            return ""
        if isinstance(data, str):
            return self._clean_html(data)
        
        if isinstance(data, dict):
            # Prioritize common text fields
            for field in ['parsed_markdown', 'text', 'content', 'body', 'raw_html_snippet', 'description']:
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
            "canonical_url": result.url,
            "document_type": "web_reference",
            "source_type": "general",
            "content_class": "html_text",
            "capture_method": "web_search_ingest",
            "substrate_version": "poc-v1",
            "ingestion_truth": {
                "stage": "raw_captured",
                "raw_captured": True,
                "blob_stored": False,
                "storage_uri_present": False,
                "parsed": False,
                "chunked": False,
                "embedded": False,
                "vector_upserted": False,
                "retrievable": False,
                "ingest_attempted": False,
                "last_updated_at": self._utc_iso(),
            },
        }
        metadata = seed_capture_promotion_metadata(
            metadata=metadata,
            canonical_url=result.url,
            trust_tier=metadata.get("trust_tier"),
        )
        metadata = apply_promotion_decision(
            metadata=metadata,
            decision=evaluate_rules(metadata),
            canonical_url=result.url,
        )

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
