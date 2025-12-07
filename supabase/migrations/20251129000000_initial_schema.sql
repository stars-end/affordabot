-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- Jurisdictions (Cities, Counties, State)
create table if not exists jurisdictions (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    type text not null check (type in ('city', 'county', 'state')),
    scrape_url text,
    last_scraped_at timestamptz,
    created_at timestamptz default now()
);

-- Legislation (Bills, Ordinances)
create table if not exists legislation (
    id uuid primary key default gen_random_uuid(),
    jurisdiction_id uuid references jurisdictions(id) not null,
    bill_number text not null,
    title text not null,
    text text, -- Full text or summary
    introduced_date date,
    status text,
    raw_html text, -- For re-parsing if needed
    analysis_status text default 'pending' check (analysis_status in ('pending', 'completed', 'failed')),
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique(jurisdiction_id, bill_number)
);

-- Impacts (LLM Analysis Results)
create table if not exists impacts (
    id uuid primary key default gen_random_uuid(),
    legislation_id uuid references legislation(id) on delete cascade not null,
    impact_number int not null,
    relevant_clause text,
    description text not null,
    evidence jsonb, -- List of {source, url, excerpt}
    chain_of_causality text,
    confidence_factor float check (confidence_factor >= 0 and confidence_factor <= 1),
    
    -- Cost Distribution (2025 Dollars)
    p10 float,
    p25 float,
    p50 float,
    p75 float,
    p90 float,
    
    created_at timestamptz default now()
);

-- Indexes
create index if not exists idx_legislation_jurisdiction on legislation(jurisdiction_id);
create index if not exists idx_legislation_status on legislation(analysis_status);
create index if not exists idx_impacts_legislation on impacts(legislation_id);