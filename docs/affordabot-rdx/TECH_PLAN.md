# TECH_PLAN: Affordabot RAG Phase 1 (Supabase Retrieval Backend)

**Epic**: affordabot-rdx  
**Priority**: P2  
**Status**: Planning

## Goal

Introduce a shared `RetrievalBackend` abstraction in llm-common and implement a Supabase-backed retrieval layer for Affordabot's legislation analysis (Phase 1 of RAG).

## Background

Current state:
- Affordabot analyzes legislation using direct LLM calls
- No retrieval/context augmentation
- Limited by LLM context window

RAG Phase 1 will:
1. Add `RetrievalBackend` abstraction to llm-common
2. Implement Supabase vector store backend
3. Integrate retrieval into legislation analysis pipeline

## Dependencies

- **llm-common**: Must have `RetrievalBackend` abstraction
- **affordabot-i0x**: RAG-ready ingestion pipeline (embeddings)
- **Supabase**: pgvector extension enabled

## Implementation Phases

### Phase 1: llm-common Abstraction
- [ ] Design `RetrievalBackend` interface in llm-common
  ```python
  class RetrievalBackend(ABC):
      @abstractmethod
      async def retrieve(self, query: str, top_k: int) -> List[Document]:
          pass
      
      @abstractmethod
      async def add_documents(self, docs: List[Document]) -> None:
          pass
  ```
- [ ] Add to llm-common package
- [ ] Write tests

### Phase 2: Supabase Implementation
- [ ] Create `SupabaseRetrievalBackend` in Affordabot
- [ ] Implement vector similarity search using pgvector
- [ ] Add connection pooling and caching
- [ ] Test with real legislation data

### Phase 3: Integration with Analysis Pipeline
- [ ] Update `backend/services/llm/orchestrator.py` to use retrieval
- [ ] Modify analysis prompts to include retrieved context
- [ ] Add retrieval metrics (latency, relevance)
- [ ] Create admin UI for retrieval debugging

## Database Schema

**Leverage existing from affordabot-i0x**:
```sql
-- From affordabot-i0x
CREATE TABLE legislation_chunks (
  id UUID PRIMARY KEY,
  legislation_id UUID REFERENCES legislation(id),
  chunk_index INT,
  chunk_text TEXT,
  embedding VECTOR(1536),
  metadata JSONB
);

-- Add index for vector similarity
CREATE INDEX ON legislation_chunks 
USING ivfflat (embedding vector_cosine_ops);
```

## Retrieval Strategy

1. **Query embedding**: Embed user's analysis question
2. **Similarity search**: Find top-k most relevant chunks
3. **Context augmentation**: Inject chunks into LLM prompt
4. **Analysis**: LLM analyzes with augmented context

## Verification

- [ ] `RetrievalBackend` abstraction in llm-common
- [ ] `SupabaseRetrievalBackend` functional
- [ ] Retrieval integrated into analysis pipeline
- [ ] Metrics show improved analysis quality
- [ ] Admin UI for debugging retrieval

## Risks

- **Relevance**: Retrieved chunks may not be relevant
- **Latency**: Vector search adds overhead
- **Context window**: Too many chunks may exceed LLM limits

## Success Criteria

- ✅ `RetrievalBackend` abstraction in llm-common
- ✅ Supabase backend implemented
- ✅ Analysis pipeline uses retrieval
- ✅ Measurable improvement in analysis quality
- ✅ Retrieval latency <500ms p95
