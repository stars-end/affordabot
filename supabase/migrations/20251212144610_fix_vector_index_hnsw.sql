-- Fix: Replace ivfflat (limit 2000 dims) with hnsw (supports 4096 dims in newer pgvector)
-- Linked to: affordabot-8xn

DROP INDEX IF EXISTS documents_embedding_idx;

CREATE INDEX IF NOT EXISTS documents_embedding_idx 
ON documents USING hnsw (embedding vector_cosine_ops);
