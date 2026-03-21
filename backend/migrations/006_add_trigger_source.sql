-- Add trigger_source column to pipeline_runs for manual/cron discrimination
ALTER TABLE pipeline_runs
  ADD COLUMN IF NOT EXISTS trigger_source TEXT DEFAULT 'manual';

-- Index for filtering manual runs
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_trigger_source
  ON pipeline_runs(trigger_source);
