-- Create sources table
DO $$ BEGIN
    CREATE TYPE source_type AS ENUM ('meeting', 'code', 'general');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE source_status AS ENUM ('active', 'broken', 'review');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

create table if not exists sources (
    id uuid primary key default gen_random_uuid(),
    jurisdiction_id text not null, -- e.g. "san_jose_ca"
    url text not null,
    type source_type not null,
    status source_status not null default 'active',
    last_scraped_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Create raw_scrapes table
create table if not exists raw_scrapes (
    id uuid primary key default gen_random_uuid(),
    source_id uuid not null references sources(id),
    content_hash text not null, -- SHA256
    content_type text not null, -- 'text/html', 'application/pdf'
    data jsonb not null, -- { "html": "...", "text": "..." }
    created_at timestamptz not null default now()
);

-- Indexes
create index if not exists idx_sources_jurisdiction_id on sources(jurisdiction_id);
create index if not exists idx_raw_scrapes_source_id on raw_scrapes(source_id);
create index if not exists idx_raw_scrapes_content_hash on raw_scrapes(content_hash);