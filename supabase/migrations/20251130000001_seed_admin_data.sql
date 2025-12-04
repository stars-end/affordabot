-- Seed default models
INSERT INTO model_configs (provider, model_name, priority, enabled, use_case)
VALUES 
    ('zai', 'glm-4', 1, true, 'generation'),
    ('openrouter', 'anthropic/claude-3-opus', 2, true, 'generation'),
    ('openrouter', 'openai/gpt-4o', 3, true, 'review')
ON CONFLICT (provider, model_name, use_case) DO NOTHING;

-- Seed default prompts
-- Seed default prompts
INSERT INTO system_prompts (prompt_type, system_prompt, updated_at, is_active, version)
VALUES 
    ('generation', 'You are an expert legislative analyst. Analyze the following bill text and identify potential impacts on the cost of living for families in the specified jurisdiction. Focus on housing, utilities, transportation, and taxes. Provide a confidence score for each impact.', NOW(), true, 1),
    ('review', 'You are a senior policy reviewer. Review the following impact analysis for accuracy, bias, and evidence. Flag any speculative claims that lack citation. Adjust confidence scores based on the strength of the evidence provided.', NOW(), true, 1)
ON CONFLICT (prompt_type) WHERE is_active = true DO UPDATE 
SET system_prompt = EXCLUDED.system_prompt, updated_at = NOW();
