
-- Add unique constraint for upsert support
ALTER TABLE sources ADD CONSTRAINT unique_sources_jurisdiction_url UNIQUE (jurisdiction_id, url);
