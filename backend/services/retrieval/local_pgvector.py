
from typing import List, Dict, Any, Optional
import json
from llm_common.retrieval import RetrievalBackend, RetrievedChunk

class LocalPgVectorBackend(RetrievalBackend):
    """
    Local implementation of PgVectorBackend using our PostgresDB client.
    Used when llm-common generic backend is unavailable.
    """
    
    def __init__(self, table_name: str = "document_chunks", postgres_client: Any = None):
        self.table_name = table_name
        self.db = postgres_client
        
    async def upsert(self, chunks: List[Dict[str, Any]]) -> bool:
        """
        Upsert chunks into Postgres using pgvector.
        """
        if not chunks:
            return True
            
        if not self.db:
            print("❌ LocalPgVectorBackend: No DB client provided")
            return False
            
        # Prepare data for insertion
        # Schema expected: id, document_id, chunk_index, chunk_content, embedding, metadata
        # But 'document_chunks' table schema might differ from 'chunks' dict keys.
        # Chunks dict keys from IngestionService: 
        # id, content, embedding, metadata, document_id, chunk_id, source, score
        
        # We need to map to table columns.
        # Let's assume standard schema for now or inspect table.
        # Standard schema usually: id, content, embedding, metadata
        
        try:
            for chunk in chunks:
                # Naive loop insert for verification (slow but functional)
                # Production should use COPY or batch insert
                
                query = f"""
                INSERT INTO {self.table_name} 
                (id, content, embedding, metadata, document_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata;
                """
                
                # Check formatting of embedding (list of floats -> string for pgvector?)
                # asyncpg handles list[float] for vector type usually if adapter set up,
                # OR we format as string "[1.0, 2.0, ...]"
                embedding_val = str(chunk['embedding'])
                
                from uuid import UUID
                def json_serial(obj):
                    if isinstance(obj, UUID):
                        return str(obj)
                    raise TypeError(f"Type {type(obj)} not serializable")
                
                await self.db._execute(
                    query,
                    chunk['id'],
                    chunk['content'],
                    embedding_val,
                    json.dumps(chunk['metadata'], default=json_serial), # JSONB + UUID fix
                    chunk.get('document_id')
                )
                
            return True
            
        except Exception as e:
            print(f"❌ LocalPgVectorBackend upsert failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def query(self, embedding: List[float], k: int = 5, filter: Optional[Dict] = None) -> List[RetrievedChunk]:
        if not self.db:
            return []
            
        try:
            # Basic pgvector KNN query
            # Expecting embedding as string "[0.1, ...]" for asyncpg to cast to vector
            embedding_val = str(embedding)
            
            query_sql = f"""
            SELECT id, content, metadata, embedding, document_id, 
                   1 - (embedding <=> $1) as similarity
            FROM {self.table_name}
            ORDER BY embedding <=> $1
            LIMIT $2
            """
            
            rows = await self.db._fetch(query_sql, embedding_val, k)
            
            results = []
            for row in rows:
                # Map back to RetrievedChunk
                meta = row.get('metadata')
                if isinstance(meta, str):
                    meta = json.loads(meta)
                
                chunk = RetrievedChunk(
                    chunk_id=str(row['id']) if row.get('id') else None,
                    content=row['content'],
                    embedding=None, # Optimize: don't return embedding unless needed
                    metadata=meta or {},
                    score=float(row['similarity']) if row.get('similarity') else 0.0,
                    document_id=row.get('document_id'),
                    source=meta.get('url') or meta.get('source_id') or "unknown"
                )
                results.append(chunk)
                
            return results
            
        except Exception as e:
            print(f"❌ LocalPgVectorBackend query failed: {e}")
            return []

    async def retrieve(self, query: str, k: int = 5, filter: Optional[Dict] = None) -> List[RetrievedChunk]:
        """
        Abstract method from RetrievalBackend.
        """
        return []
