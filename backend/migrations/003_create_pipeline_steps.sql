CREATE TABLE IF NOT EXISTS pipeline_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step_number INT NOT NULL,
    step_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    input_context JSONB,
    output_result JSONB,
    model_config JSONB,
    duration_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(run_id, step_number)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_steps_run_id ON pipeline_steps(run_id);
