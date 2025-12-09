-- Add metadata column to sources table for flexible configuration
ALTER TABLE sources ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN sources.metadata IS 'Flexible metadata for source configuration/state';
