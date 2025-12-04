-- ============================================================================
-- AffordaBot Admin Dashboard V2 Schema
-- Migration: 20251130_admin_dashboard_v2_schema.sql
-- 
-- Creates tables for:
-- - Admin task tracking (scraping & analysis)
-- - Model configuration & priority management
-- - System prompt versioning
-- - Analysis history (research, generate, review outputs)
-- - Scrape history
--
-- Following 2025 Supabase best practices:
-- - UUID primary keys with gen_random_uuid()
-- - Timestamptz for all timestamps
-- - JSONB for flexible metadata
-- - Proper indexes for query performance
-- - Row Level Security (RLS) policies
-- - Triggers for updated_at automation
-- - Comments for documentation
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Reuse update_updated_at_column trigger function if not exists
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_updated_at_column() IS 'Automatically updates updated_at timestamp on row modification';

-- ============================================================================
-- Admin Tasks Table
-- Tracks background tasks for scraping and analysis
-- ============================================================================

CREATE TABLE IF NOT EXISTS admin_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('scrape', 'research', 'generate', 'review')),
    jurisdiction VARCHAR(100),
    bill_id VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    
    -- Task configuration
    config JSONB DEFAULT '{}'::jsonb,
    model_override VARCHAR(100),
    
    -- Results and errors
    result JSONB,
    error_message TEXT,
    error_stack TEXT,
    
    -- Metrics
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER GENERATED ALWAYS AS (
        CASE 
            WHEN completed_at IS NOT NULL AND started_at IS NOT NULL 
            THEN EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000
            ELSE NULL
        END
    ) STORED,
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system'
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_admin_tasks_status ON admin_tasks(status) WHERE status IN ('queued', 'running');
CREATE INDEX IF NOT EXISTS idx_admin_tasks_type_jurisdiction ON admin_tasks(task_type, jurisdiction);
CREATE INDEX IF NOT EXISTS idx_admin_tasks_created_at ON admin_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_tasks_bill_id ON admin_tasks(bill_id) WHERE bill_id IS NOT NULL;

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_admin_tasks_updated_at ON admin_tasks;
CREATE TRIGGER update_admin_tasks_updated_at
    BEFORE UPDATE ON admin_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE admin_tasks IS 'Tracks background tasks for scraping and analysis operations';
COMMENT ON COLUMN admin_tasks.task_type IS 'Type of task: scrape, research, generate, review';
COMMENT ON COLUMN admin_tasks.config IS 'Task-specific configuration (e.g., force_refresh, model_params)';
COMMENT ON COLUMN admin_tasks.duration_ms IS 'Task duration in milliseconds (auto-calculated)';

-- ============================================================================
-- Model Configurations Table
-- Manages LLM model priority and settings
-- ============================================================================

CREATE TABLE IF NOT EXISTS model_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('openrouter', 'zai', 'anthropic', 'openai')),
    model_name VARCHAR(100) NOT NULL,
    use_case VARCHAR(50) NOT NULL CHECK (use_case IN ('generation', 'review', 'both')),
    
    -- Priority and availability
    priority INTEGER NOT NULL DEFAULT 999,
    enabled BOOLEAN NOT NULL DEFAULT true,
    
    -- Model-specific configuration
    config JSONB DEFAULT '{}'::jsonb,
    
    -- Health tracking
    last_health_check_at TIMESTAMPTZ,
    health_status VARCHAR(50) DEFAULT 'unknown' CHECK (health_status IN ('healthy', 'degraded', 'unhealthy', 'unknown')),
    health_details JSONB,
    
    -- Usage statistics
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    avg_latency_ms DECIMAL(10, 2),
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'admin'
);

-- Unique constraint: one config per provider+model+use_case
CREATE UNIQUE INDEX IF NOT EXISTS idx_model_configs_unique 
    ON model_configs(provider, model_name, use_case);

-- Index for priority ordering
CREATE INDEX IF NOT EXISTS idx_model_configs_priority 
    ON model_configs(use_case, priority, enabled) 
    WHERE enabled = true;

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_model_configs_updated_at ON model_configs;
CREATE TRIGGER update_model_configs_updated_at
    BEFORE UPDATE ON model_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE model_configs IS 'LLM model configuration and priority management';
COMMENT ON COLUMN model_configs.priority IS 'Lower number = higher priority (1 is highest)';
COMMENT ON COLUMN model_configs.config IS 'Model-specific settings (temperature, max_tokens, etc.)';
COMMENT ON COLUMN model_configs.health_details IS 'Latest health check results and metrics';

-- ============================================================================
-- System Prompts Table
-- Manages versioned system prompts for generation and review
-- ============================================================================

CREATE TABLE IF NOT EXISTS system_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_type VARCHAR(50) NOT NULL CHECK (prompt_type IN ('generation', 'review')),
    version INTEGER NOT NULL,
    
    -- Prompt content
    system_prompt TEXT NOT NULL,
    description TEXT,
    
    -- Activation status
    is_active BOOLEAN NOT NULL DEFAULT false,
    activated_at TIMESTAMPTZ,
    
    -- Performance tracking
    usage_count INTEGER DEFAULT 0,
    avg_quality_score DECIMAL(3, 2),
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'admin'
);

-- Partial unique index: only one active prompt per type
CREATE UNIQUE INDEX IF NOT EXISTS idx_system_prompts_unique_active 
    ON system_prompts(prompt_type) 
    WHERE is_active = true;

-- Index for active prompts
CREATE INDEX IF NOT EXISTS idx_system_prompts_active 
    ON system_prompts(prompt_type, is_active) 
    WHERE is_active = true;

-- Index for version history
CREATE INDEX IF NOT EXISTS idx_system_prompts_version 
    ON system_prompts(prompt_type, version DESC);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_system_prompts_updated_at ON system_prompts;
CREATE TRIGGER update_system_prompts_updated_at
    BEFORE UPDATE ON system_prompts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE system_prompts IS 'Versioned system prompts for LLM generation and review';
COMMENT ON COLUMN system_prompts.version IS 'Incremental version number per prompt_type';
COMMENT ON COLUMN system_prompts.is_active IS 'Only one prompt per type can be active (enforced by partial unique index)';

-- ============================================================================
-- Analysis History Table
-- Stores historical outputs from research, generation, and review steps
-- ============================================================================

CREATE TABLE IF NOT EXISTS analysis_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction VARCHAR(100) NOT NULL,
    bill_id VARCHAR(255) NOT NULL,
    step VARCHAR(50) NOT NULL CHECK (step IN ('research', 'generate', 'review')),
    
    -- Model and prompt used
    model_provider VARCHAR(50),
    model_name VARCHAR(100),
    prompt_version INTEGER,
    
    -- Analysis results
    result JSONB NOT NULL,
    confidence_score DECIMAL(3, 2),
    
    -- Performance metrics
    latency_ms INTEGER,
    tokens_used INTEGER,
    cost_usd DECIMAL(10, 4),
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'partial', 'failed')),
    error_message TEXT,
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    task_id UUID REFERENCES admin_tasks(id) ON DELETE SET NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_analysis_history_bill 
    ON analysis_history(jurisdiction, bill_id, step, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_history_model 
    ON analysis_history(model_provider, model_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_history_created_at 
    ON analysis_history(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_history_task_id 
    ON analysis_history(task_id) WHERE task_id IS NOT NULL;

COMMENT ON TABLE analysis_history IS 'Historical record of all analysis pipeline executions';
COMMENT ON COLUMN analysis_history.result IS 'Full analysis output (research findings, generated analysis, or review feedback)';
COMMENT ON COLUMN analysis_history.confidence_score IS 'Model confidence score (0.00 to 1.00)';
COMMENT ON COLUMN analysis_history.cost_usd IS 'Estimated API cost in USD';

-- ============================================================================
-- Scrape History Table
-- Tracks scraping operations and results
-- ============================================================================

CREATE TABLE IF NOT EXISTS scrape_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction VARCHAR(100) NOT NULL,
    
    -- Scrape results
    bills_found INTEGER NOT NULL DEFAULT 0,
    bills_new INTEGER DEFAULT 0,
    bills_updated INTEGER DEFAULT 0,
    
    -- Status and errors
    status VARCHAR(50) NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'partial', 'failed')),
    error_message TEXT,
    error_details JSONB,
    
    -- Performance metrics
    duration_ms INTEGER,
    scraper_version VARCHAR(50),
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    task_id UUID REFERENCES admin_tasks(id) ON DELETE SET NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_scrape_history_jurisdiction 
    ON scrape_history(jurisdiction, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_scrape_history_status 
    ON scrape_history(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_scrape_history_task_id 
    ON scrape_history(task_id) WHERE task_id IS NOT NULL;

COMMENT ON TABLE scrape_history IS 'Historical record of all scraping operations';
COMMENT ON COLUMN scrape_history.bills_new IS 'Number of new bills discovered in this scrape';
COMMENT ON COLUMN scrape_history.bills_updated IS 'Number of existing bills updated in this scrape';

-- ============================================================================
-- Row Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE admin_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE scrape_history ENABLE ROW LEVEL SECURITY;

-- Admin-only access policies (adjust based on your auth setup)
-- These are placeholder policies - customize based on your authentication

DROP POLICY IF EXISTS "Admin full access to admin_tasks" ON admin_tasks;
CREATE POLICY "Admin full access to admin_tasks"
    ON admin_tasks
    FOR ALL
    USING (true)  -- TODO: Replace with actual admin check
    WITH CHECK (true);

DROP POLICY IF EXISTS "Admin full access to model_configs" ON model_configs;
CREATE POLICY "Admin full access to model_configs"
    ON model_configs
    FOR ALL
    USING (true)  -- TODO: Replace with actual admin check
    WITH CHECK (true);

DROP POLICY IF EXISTS "Admin full access to system_prompts" ON system_prompts;
CREATE POLICY "Admin full access to system_prompts"
    ON system_prompts
    FOR ALL
    USING (true)  -- TODO: Replace with actual admin check
    WITH CHECK (true);

DROP POLICY IF EXISTS "Admin full access to analysis_history" ON analysis_history;
CREATE POLICY "Admin full access to analysis_history"
    ON analysis_history
    FOR ALL
    USING (true)  -- TODO: Replace with actual admin check
    WITH CHECK (true);

DROP POLICY IF EXISTS "Admin full access to scrape_history" ON scrape_history;
CREATE POLICY "Admin full access to scrape_history"
    ON scrape_history
    FOR ALL
    USING (true)  -- TODO: Replace with actual admin check
    WITH CHECK (true);

-- ============================================================================
-- Initial Data
-- ============================================================================

-- Insert default model configurations
INSERT INTO model_configs (provider, model_name, use_case, priority, enabled, config) VALUES
    ('openrouter', 'x-ai/grok-beta', 'generation', 1, true, '{"temperature": 0.7, "max_tokens": 4000}'::jsonb),
    ('zai', 'glm-4.6', 'review', 1, true, '{"temperature": 0.3, "max_tokens": 2000}'::jsonb),
    ('openrouter', 'anthropic/claude-3.5-sonnet', 'both', 2, true, '{"temperature": 0.5, "max_tokens": 4000}'::jsonb)
ON CONFLICT (provider, model_name, use_case) DO NOTHING;

-- Insert default system prompts
INSERT INTO system_prompts (prompt_type, version, system_prompt, description, is_active, activated_at) VALUES
    ('generation', 1, 
     'You are an expert policy analyst specializing in local government legislation. Analyze the provided bill and identify specific impacts on homeowners, renters, and businesses. Be precise, cite specific sections, and quantify impacts where possible.',
     'Initial generation prompt',
     true,
     NOW()),
    ('review', 1,
     'You are a senior policy reviewer. Evaluate the analysis for accuracy, completeness, and clarity. Identify any missing impacts, unsupported claims, or areas needing additional research. Provide a confidence score from 0.0 to 1.0.',
     'Initial review prompt',
     true,
     NOW())
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Grants (adjust based on your service role setup)
-- ============================================================================

-- Grant access to authenticated users (customize as needed)
GRANT SELECT, INSERT, UPDATE ON admin_tasks TO authenticated;
GRANT SELECT ON model_configs TO authenticated;
GRANT SELECT ON system_prompts TO authenticated;
GRANT SELECT ON analysis_history TO authenticated;
GRANT SELECT ON scrape_history TO authenticated;

-- Grant full access to service role
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO service_role;
