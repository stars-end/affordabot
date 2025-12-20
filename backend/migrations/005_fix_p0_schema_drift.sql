-- Rename impacts.confidence_factor to confidence_score to match Pydantic
DO $$
BEGIN
  IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='impacts' AND column_name='confidence_factor') THEN
    ALTER TABLE impacts RENAME COLUMN confidence_factor TO confidence_score;
  END IF;
END $$;

-- Add missing pipeline_runs columns (result JSONB, models JSONB, completed_at TIMESTAMPTZ)
ALTER TABLE pipeline_runs
  ADD COLUMN IF NOT EXISTS result JSONB,
  ADD COLUMN IF NOT EXISTS models JSONB,
  ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
