-- Template reviews table for LLM-suggested improvements
CREATE TABLE IF NOT EXISTS template_reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  jurisdiction_type VARCHAR(50) NOT NULL, -- 'city', 'county'
  category VARCHAR(50) NOT NULL, -- 'meetings', 'code', 'permits'
  current_template TEXT NOT NULL,
  suggested_template TEXT NOT NULL,
  reasoning TEXT,
  status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
  created_at TIMESTAMPTZ DEFAULT NOW(),
  reviewed_at TIMESTAMPTZ,
  reviewed_by UUID
);

-- Index for querying pending reviews
CREATE INDEX IF NOT EXISTS template_reviews_status_idx ON template_reviews(status);
