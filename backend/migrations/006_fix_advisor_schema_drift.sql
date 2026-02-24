-- Migration: 006_fix_advisor_schema_drift.sql
-- Fix P0 schema drift: Add missing advisor_sessions.pinned_artifact_ids column
-- and create missing tool_invocation_ledger table
-- Related: bd-kexx.11, #863

-- 1. Add pinned_artifact_ids column to advisor_sessions if table exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'advisor_sessions') THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'advisor_sessions'
      AND column_name = 'pinned_artifact_ids'
    ) THEN
      ALTER TABLE advisor_sessions ADD COLUMN pinned_artifact_ids JSONB DEFAULT '[]'::jsonb;
      RAISE NOTICE 'Added pinned_artifact_ids column to advisor_sessions';
    ELSE
      RAISE NOTICE 'Column pinned_artifact_ids already exists in advisor_sessions';
    END IF;
  ELSE
    RAISE NOTICE 'Table advisor_sessions does not exist - skipping column addition';
  END IF;
END $$;

-- 2. Create tool_invocation_ledger table if it doesn't exist
CREATE TABLE IF NOT EXISTS tool_invocation_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID,
  tool_name VARCHAR(255) NOT NULL,
  tool_input JSONB NOT NULL,
  tool_output JSONB,
  invocation_timestamp TIMESTAMPTZ DEFAULT NOW(),
  duration_ms INTEGER,
  success BOOLEAN DEFAULT true,
  error_message TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add index on session_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_tool_invocation_ledger_session_id ON tool_invocation_ledger(session_id);

-- Add index on invocation_timestamp for time-based queries
CREATE INDEX IF NOT EXISTS idx_tool_invocation_ledger_timestamp ON tool_invocation_ledger(invocation_timestamp);

COMMENT ON TABLE tool_invocation_ledger IS 'Ledger for tracking tool invocations during advisor sessions';
COMMENT ON COLUMN tool_invocation_ledger.session_id IS 'Reference to the advisor session';
COMMENT ON COLUMN tool_invocation_ledger.tool_name IS 'Name of the tool invoked';
COMMENT ON COLUMN tool_invocation_ledger.tool_input IS 'Input parameters passed to the tool';
COMMENT ON COLUMN tool_invocation_ledger.tool_output IS 'Output returned by the tool';
COMMENT ON COLUMN tool_invocation_ledger.invocation_timestamp IS 'When the tool was invoked';
COMMENT ON COLUMN tool_invocation_ledger.duration_ms IS 'Duration of tool execution in milliseconds';
COMMENT ON COLUMN tool_invocation_ledger.success IS 'Whether the tool invocation succeeded';
COMMENT ON COLUMN tool_invocation_ledger.error_message IS 'Error message if invocation failed';
