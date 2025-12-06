-- Add source column to documents table for llm-common compatibility
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source TEXT;

-- Create index for filtering by source
CREATE INDEX IF NOT EXISTS documents_source_idx ON documents(source);
