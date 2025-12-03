-- ============================================================================
-- AffordaBot Admin Dashboard: Jurisdiction Multi-Source Configuration
-- Migration: 20251202000000_jurisdiction_multi_source.sql
-- 
-- Adds multi-source data fetching support to jurisdictions table:
-- - API configuration (OpenStates, Legistar)
-- - Web scraper fallback
-- - Source priority strategies (api_first, web_first, both_merge, etc.)
-- 
-- Following context-database-schema best practices:
-- - Idempotent DDL with IF NOT EXISTS
-- - Proper YYYYMMDD timestamp format
-- - Comments for documentation
-- ============================================================================

-- Add API configuration and multi-source support to jurisdictions table
ALTER TABLE jurisdictions 
ADD COLUMN IF NOT EXISTS api_type VARCHAR(50) CHECK (api_type IN ('openstates', 'legistar', NULL)),
ADD COLUMN IF NOT EXISTS api_key_env VARCHAR(100),
ADD COLUMN IF NOT EXISTS openstates_jurisdiction_id VARCHAR(10),
ADD COLUMN IF NOT EXISTS scraper_class VARCHAR(100),
ADD COLUMN IF NOT EXISTS use_web_scraper_fallback BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS source_priority VARCHAR(20) DEFAULT 'api_first' 
    CHECK (source_priority IN ('api_first', 'web_first', 'api_only', 'web_only', 'both_merge'));

-- Add comments for documentation
COMMENT ON COLUMN jurisdictions.api_type IS 'API type: openstates or legistar. NULL if web scraper only';
COMMENT ON COLUMN jurisdictions.api_key_env IS 'Environment variable name containing API key (e.g., OPENSTATES_API_KEY)';
COMMENT ON COLUMN jurisdictions.openstates_jurisdiction_id IS 'OpenStates jurisdiction ID for API calls (e.g., ca for California)';
COMMENT ON COLUMN jurisdictions.scraper_class IS 'Python scraper class name (e.g., SanJoseScraper, CaliforniaStateScraper)';
COMMENT ON COLUMN jurisdictions.use_web_scraper_fallback IS 'If true, use web scraper when API data is incomplete';
COMMENT ON COLUMN jurisdictions.source_priority IS 'Multi-source strategy: api_first (API with fallback), web_first, api_only, web_only, both_merge (synthesize both)';

-- Update existing jurisdictions with multi-source configuration
-- San Jose: Uses Legistar API only
UPDATE jurisdictions SET 
    api_type = 'legistar',
    scraper_class = 'SanJoseScraper',
    source_priority = 'api_only'
WHERE name = 'City of San Jose';

-- California State: Uses OpenStates API with web scraper fallback
UPDATE jurisdictions SET 
    api_type = 'openstates',
    api_key_env = 'OPENSTATES_API_KEY',
    openstates_jurisdiction_id = 'ca',
    scrape_url = 'https://leginfo.legislature.ca.gov/',
    scraper_class = 'CaliforniaStateScraper',
    use_web_scraper_fallback = true,
    source_priority = 'api_first'
WHERE name = 'State of California';

-- Santa Clara County: Web scraper only (if exists)
UPDATE jurisdictions SET 
    api_type = NULL,
    scraper_class = 'SantaClaraCountyScraper',
    source_priority = 'web_only'
WHERE name LIKE '%Santa Clara County%';

-- Saratoga: Web scraper only (if exists)
UPDATE jurisdictions SET 
    api_type = NULL,
    scraper_class = 'SaratogaScraper',
    source_priority = 'web_only'
WHERE name LIKE '%Saratoga%';
