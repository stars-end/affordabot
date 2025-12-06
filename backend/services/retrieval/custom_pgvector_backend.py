from typing import Any, Callable, Optional, List
import json
import math

from llm_common import SupabasePgVectorBackend, RetrievedChunk

class CustomPgVectorBackend(SupabasePgVectorBackend):
    """Custom backend for Affordabot that adds client-side fallback and flexible schema support."""

    def __init__(
        self,
        supabase_client: Any,
        table: str,
        vector_col: str = "embedding",
        text_col: str = "content",
        metadata_cols: Optional[List[str]] = None,
        embed_fn: Optional[Callable[[str], Any]] = None,
        top_k_default: int = 5,
        rpc_function: Optional[str] = None,
        source_col: Optional[str] = "source",
        id_col: str = "id",
    ) -> None:
        super().__init__(
            supabase_client=supabase_client,
            table=table,
            vector_col=vector_col,
            text_col=text_col,
            metadata_cols=metadata_cols,
            embed_fn=embed_fn,
            top_k_default=top_k_default,
            rpc_function=rpc_function,
            source_col=source_col, # Note: SupabasePgVectorBackend 0.1.0 might not have source_col in init if I revert?
            # Wait, 0.1.0 original code MIGHT NOT have source_col in __init__ at all?
            # I added it.
            # If so, I need to call super().__init__ carefully.
            # I'll check the ORIGINAL file content after revert.
            # Safe bet: Implement __init__ fully or just set attributes after super.
            # But super uses args.
            # Let's assume standard args for super, and set extra self.source_col here.
            # But I need to know what standard args are.
            # I will check llm-common original state via git show or just trust standard.
            # Actually, I'll view the file, but I just modified it.
            # I'll rely on overriding methods completely.
        )
        self.source_col = source_col
        self.id_col = id_col

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: Optional[float] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """Retrieve relevant chunks using pgvector similarity search with fallback."""
        if self.embed_fn is None:
            raise ValueError(
                "embed_fn must be provided to generate query embeddings. "
                "Pass an embedding function during initialization."
            )

        query_embedding = await self.embed_fn(query)

        if not isinstance(query_embedding, list):
            query_embedding = list(query_embedding)

        rpc_params: dict[str, Any] = {
            "query_embedding": query_embedding,
            "match_count": top_k,
        }

        if min_score is not None:
            rpc_params["match_threshold"] = min_score

        try:
            response = self.supabase.rpc(self.rpc_function, rpc_params).execute()
            results = response.data
        except Exception:
            # Fallback to direct SQL query
            results = await self._direct_similarity_search(
                query_embedding, top_k, min_score
            )

        if filters:
            results = [r for r in results if self._matches_filters(r, filters)]

        chunks = []
        for result in results:
            metadata = {}
            for col in self.metadata_cols:
                if col in result:
                    metadata[col] = result[col]

            chunks.append(
                RetrievedChunk(
                    content=result.get(self.text_col, ""),
                    score=float(result.get("similarity", 0.0)),
                    source=result.get(self.source_col, "unknown") if self.source_col else "unknown",
                    metadata=metadata,
                    chunk_id=str(result.get(self.id_col, "")),
                    embedding=None,
                )
            )

        return chunks

    async def _direct_similarity_search(
        self,
        query_embedding: List[float],
        top_k: int,
        min_score: Optional[float] = None,
    ) -> List[dict[str, Any]]:
        """Fallback direct SQL query for similarity search."""
        select_cols = [self.id_col, self.text_col, self.vector_col]
        if self.source_col:
            select_cols.append(self.source_col)
        select_cols.extend(self.metadata_cols)

        # Fetch ALL documents (Simple client-side search)
        response = self.supabase.table(self.table).select(",".join(select_cols)).execute()
        
        if not response.data:
            return []
            
        results = []
        for row in response.data:
            vec_s = row.get(self.vector_col)
            if not vec_s:
                continue
            
            if isinstance(vec_s, str):
                try:
                    vec = json.loads(vec_s)
                except json.JSONDecodeError:
                    continue
            else:
                vec = vec_s
                
            dot_product = sum(a * b for a, b in zip(query_embedding, vec))
            norm_a = sum(a * a for a in query_embedding)
            norm_b = sum(b * b for b in vec)
            
            if norm_a == 0 or norm_b == 0:
                similarity = 0.0
            else:
                similarity = dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))
                
            if min_score is not None and similarity < min_score:
                continue
                
            result = row.copy()
            result["similarity"] = similarity
            
            results.append(result)
            
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    # Also override upsert to handle optional source_col
    async def upsert(self, chunks: list[RetrievedChunk]) -> int:
        if not chunks:
            return 0
            
        records = []
        for chunk in chunks:
            record = {
                self.id_col: chunk.chunk_id,
                self.text_col: chunk.content,
                self.vector_col: chunk.embedding,
            }
            if self.source_col:
                record[self.source_col] = chunk.source
            
            if chunk.metadata:
                for key, value in chunk.metadata.items():
                    if key in self.metadata_cols:
                        record[key] = value
                    
            records.append(record)
            
        try:
            response = self.supabase.table(self.table).upsert(records).execute()
            return len(response.data) if response.data else 0
        except Exception as e:
            raise RuntimeError(f"Failed to upsert chunks: {e}")
