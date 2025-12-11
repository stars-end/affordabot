-- ============================================================================
-- Update Enums for Research Use Case
-- Migration: 20251212000000_update_enums_for_research.sql
-- 
-- Updates check constraints to include 'research' as a valid type for:
-- - model_configs.use_case
-- - system_prompts.prompt_type
-- ============================================================================

-- Update model_configs.use_case
ALTER TABLE model_configs DROP CONSTRAINT IF EXISTS model_configs_use_case_check;
ALTER TABLE model_configs ADD CONSTRAINT model_configs_use_case_check 
    CHECK (use_case IN ('generation', 'review', 'research', 'both'));

-- Update system_prompts.prompt_type
ALTER TABLE system_prompts DROP CONSTRAINT IF EXISTS system_prompts_prompt_type_check;
ALTER TABLE system_prompts ADD CONSTRAINT system_prompts_prompt_type_check
    CHECK (prompt_type IN ('generation', 'review', 'research'));

-- Insert default research prompt
INSERT INTO system_prompts (prompt_type, version, system_prompt, description, is_active, activated_at) VALUES
    ('research', 1, 
     'You are a legislative researcher. Your goal is to find all relevant documents, news articles, and context related to the bill. Use valid sources and cross-reference information.',
     'Initial research prompt',
     true,
     NOW())
ON CONFLICT DO NOTHING;

-- Insert default research model config (optional, reusing existing generation model if not present)
-- We can add a Z.ai model for research specifically if desired
INSERT INTO model_configs (provider, model_name, use_case, priority, enabled, config) VALUES
    ('zai', 'gemini-1.5-flash', 'research', 1, true, '{"temperature": 0.3, "max_tokens": 4000}'::jsonb)
ON CONFLICT (provider, model_name, use_case) DO NOTHING;
