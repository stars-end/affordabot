
-- Add name column to sources table
ALTER TABLE sources ADD COLUMN IF NOT EXISTS name TEXT;
COMMENT ON COLUMN sources.name IS 'Human-readable name/title of the source';
