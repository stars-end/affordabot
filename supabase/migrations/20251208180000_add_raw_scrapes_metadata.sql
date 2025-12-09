
-- Add metadata column to raw_scrapes table
ALTER TABLE raw_scrapes ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
