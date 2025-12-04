-- Add source_method and handler columns to sources table

ALTER TABLE sources ADD COLUMN source_method VARCHAR(20) 
  CHECK (source_method IN ('scrape', 'api', 'manual')) 
  DEFAULT 'scrape';

ALTER TABLE sources ADD COLUMN handler VARCHAR(100);

-- Update existing sources with handlers
UPDATE sources SET handler = 'sanjose_meetings' 
WHERE url LIKE '%legistar.com%';

UPDATE sources SET handler = 'sanjose_municode'
WHERE url LIKE '%municode.com%';

-- Add debugging fields to raw_scrapes
ALTER TABLE raw_scrapes ADD COLUMN scrape_duration_ms INTEGER;
ALTER TABLE raw_scrapes ADD COLUMN http_status_code INTEGER;
ALTER TABLE raw_scrapes ADD COLUMN error_message TEXT;
ALTER TABLE raw_scrapes ADD COLUMN scraped_by VARCHAR(50);

-- Create source_health table for monitoring
CREATE TABLE IF NOT EXISTS source_health (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id),
  checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status VARCHAR(20) CHECK (status IN ('success', 'failed', 'timeout')),
  error_message TEXT,
  response_time_ms INTEGER,
  items_scraped INTEGER
);

CREATE INDEX IF NOT EXISTS idx_source_health_source_id ON source_health(source_id, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_health_status ON source_health(status, checked_at DESC);

COMMENT ON TABLE source_health IS 'Tracks scrape execution health and performance metrics';
COMMENT ON COLUMN sources.source_method IS 'Data acquisition method: scrape, api, or manual';
COMMENT ON COLUMN sources.handler IS 'Spider name, API client, or upload handler';
