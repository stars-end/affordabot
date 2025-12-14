-- 1. Drop constraints and indexes that depend on the column dimensions
DROP INDEX IF EXISTS documents_embedding_idx;
DROP FUNCTION IF EXISTS match_documents(vector(1536), float, int, jsonb);

-- 2. Truncate documents to remove incompatible vectors
TRUNCATE TABLE documents;

-- 3. Update column dimensions
ALTER TABLE documents ALTER COLUMN embedding TYPE vector(4096);

-- 4. Create HNSW index (supports higher dimensions than IVFFlat)
-- CREATE INDEX IF NOT EXISTS documents_embedding_idx ON documents USING hnsw (embedding vector_cosine_ops);

-- 5. Reset processed status to re-ingest everything
UPDATE raw_scrapes SET processed = NULL, document_id = NULL;

-- 6. Recreate match function with new dimensions
CREATE OR REPLACE FUNCTION match_documents(
  query_embedding vector(4096),
  match_threshold float,
  match_count int,
  filter jsonb
)
RETURNS TABLE (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id,
    d.content,
    d.metadata,
    1 - (d.embedding <=> query_embedding) AS similarity
  FROM documents d
  WHERE 1 - (d.embedding <=> query_embedding) > match_threshold
  AND d.metadata @> filter
  ORDER BY d.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
