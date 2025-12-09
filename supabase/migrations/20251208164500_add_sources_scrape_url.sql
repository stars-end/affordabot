
-- Add scrape_url column to sources table
ALTER TABLE sources ADD COLUMN IF NOT EXISTS scrape_url TEXT;
COMMENT ON COLUMN sources.scrape_url IS 'Alternative URL for scraping if different from public Display URL';
