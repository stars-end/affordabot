-- Create pipeline_runs table
create table if not exists pipeline_runs (
    id uuid primary key default gen_random_uuid(),
    bill_id text not null,
    jurisdiction text,
    models jsonb, -- {"research": "...", "generate": "...", "review": "..."}
    status text not null default 'running' check (status in ('running', 'completed', 'failed')),
    result jsonb,
    error text,
    started_at timestamptz default now(),
    completed_at timestamptz,
    created_at timestamptz default now()
);

-- Indexes
create index if not exists idx_pipeline_runs_bill_id on pipeline_runs(bill_id);
create index if not exists idx_pipeline_runs_status on pipeline_runs(status);
create index if not exists idx_pipeline_runs_created_at on pipeline_runs(created_at desc);
