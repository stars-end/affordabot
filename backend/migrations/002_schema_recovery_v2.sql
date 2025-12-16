-- Migration: 002_schema_recovery_v2.sql
-- Recovered schema for Admin Dashboard, Sources, and Analysis Pipeline
-- Generated from Supabase dump and consolidated.

CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Enums and Types
DO $$ BEGIN
    CREATE TYPE source_status AS ENUM ('active', 'inactive', 'archived', 'error');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 2. Core Tables (Jurisdictions, Sources)
CREATE TABLE IF NOT EXISTS public.jurisdictions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  type text NOT NULL CHECK (type = ANY (ARRAY['city'::text, 'county'::text, 'state'::text])),
  scrape_url text,
  last_scraped_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT now(),
  api_type character varying CHECK (api_type::text = ANY (ARRAY['openstates'::character varying, 'legistar'::character varying, NULL::character varying]::text[])),
  api_key_env character varying,
  openstates_jurisdiction_id character varying,
  scraper_class character varying,
  use_web_scraper_fallback boolean DEFAULT false,
  source_priority character varying DEFAULT 'api_first'::character varying CHECK (source_priority::text = ANY (ARRAY['api_first'::character varying, 'web_first'::character varying, 'api_only'::character varying, 'web_only'::character varying, 'both_merge'::character varying]::text[])),
  CONSTRAINT jurisdictions_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.sources (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  jurisdiction_id text NOT NULL,
  url text NOT NULL,
  type text NOT NULL, -- Changed from USER-DEFINED to text for simplicity in recovery, ideally enum
  status source_status NOT NULL DEFAULT 'active'::source_status,
  last_scraped_at timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  source_method character varying DEFAULT 'scrape'::character varying CHECK (source_method::text = ANY (ARRAY['scrape'::character varying, 'api'::character varying, 'manual'::character varying]::text[])),
  handler character varying,
  metadata jsonb DEFAULT '{}'::jsonb,
  name text,
  scrape_url text,
  CONSTRAINT sources_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.raw_scrapes (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  source_id uuid NOT NULL,
  content_hash text NOT NULL,
  content_type text NOT NULL,
  data jsonb NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  scrape_duration_ms integer,
  http_status_code integer,
  error_message text,
  scraped_by character varying,
  processed boolean,
  document_id uuid,
  storage_uri text,
  metadata jsonb DEFAULT '{}'::jsonb,
  url text,
  CONSTRAINT raw_scrapes_pkey PRIMARY KEY (id),
  CONSTRAINT raw_scrapes_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id)
);

CREATE TABLE IF NOT EXISTS public.documents (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL,
  content text NOT NULL,
  embedding vector(1536), -- Assumed 1536 from history, adjusting if needed
  metadata jsonb DEFAULT '{}'::jsonb,
  chunk_index integer,
  created_at timestamp with time zone DEFAULT now(),
  source text,
  CONSTRAINT documents_pkey PRIMARY KEY (id)
);

-- 3. Admin & Analysis Tables
CREATE TABLE IF NOT EXISTS public.admin_tasks (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  task_type character varying NOT NULL CHECK (task_type::text = ANY (ARRAY['scrape'::character varying, 'research'::character varying, 'generate'::character varying, 'review'::character varying, 'universal_harvest'::character varying, 'rag_scrape'::character varying]::text[])),
  jurisdiction character varying,
  bill_id character varying,
  status character varying NOT NULL DEFAULT 'queued'::character varying CHECK (status::text = ANY (ARRAY['queued'::character varying, 'running'::character varying, 'completed'::character varying, 'failed'::character varying, 'cancelled'::character varying]::text[])),
  config jsonb DEFAULT '{}'::jsonb,
  model_override character varying,
  result jsonb,
  error_message text,
  error_stack text,
  started_at timestamp with time zone,
  completed_at timestamp with time zone,
  duration_ms integer,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  created_by character varying DEFAULT 'system'::character varying,
  CONSTRAINT admin_tasks_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.analysis_history (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  jurisdiction character varying NOT NULL,
  bill_id character varying NOT NULL,
  step character varying NOT NULL CHECK (step::text = ANY (ARRAY['research'::character varying, 'generate'::character varying, 'review'::character varying]::text[])),
  model_provider character varying,
  model_name character varying,
  prompt_version integer,
  result jsonb NOT NULL,
  confidence_score numeric,
  latency_ms integer,
  tokens_used integer,
  cost_usd numeric,
  status character varying NOT NULL DEFAULT 'success'::character varying CHECK (status::text = ANY (ARRAY['success'::character varying, 'partial'::character varying, 'failed'::character varying]::text[])),
  error_message text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  task_id uuid,
  CONSTRAINT analysis_history_pkey PRIMARY KEY (id),
  CONSTRAINT analysis_history_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.admin_tasks(id)
);

CREATE TABLE IF NOT EXISTS public.scrape_history (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  jurisdiction character varying NOT NULL,
  bills_found integer NOT NULL DEFAULT 0,
  bills_new integer DEFAULT 0,
  bills_updated integer DEFAULT 0,
  status character varying NOT NULL DEFAULT 'success'::character varying CHECK (status::text = ANY (ARRAY['success'::character varying, 'partial'::character varying, 'failed'::character varying]::text[])),
  error_message text,
  error_details jsonb,
  duration_ms integer,
  scraper_version character varying,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  task_id uuid,
  notes text,
  CONSTRAINT scrape_history_pkey PRIMARY KEY (id),
  CONSTRAINT scrape_history_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.admin_tasks(id)
);

-- 4. Configurations & Prompts
CREATE TABLE IF NOT EXISTS public.model_configs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  provider character varying NOT NULL CHECK (provider::text = ANY (ARRAY['openrouter'::character varying, 'zai'::character varying, 'anthropic'::character varying, 'openai'::character varying]::text[])),
  model_name character varying NOT NULL,
  use_case character varying NOT NULL CHECK (use_case::text = ANY (ARRAY['generation'::character varying, 'review'::character varying, 'both'::character varying]::text[])),
  priority integer NOT NULL DEFAULT 999,
  enabled boolean NOT NULL DEFAULT true,
  config jsonb DEFAULT '{}'::jsonb,
  last_health_check_at timestamp with time zone,
  health_status character varying DEFAULT 'unknown'::character varying CHECK (health_status::text = ANY (ARRAY['healthy'::character varying, 'degraded'::character varying, 'unhealthy'::character varying, 'unknown'::character varying]::text[])),
  health_details jsonb,
  total_requests integer DEFAULT 0,
  successful_requests integer DEFAULT 0,
  failed_requests integer DEFAULT 0,
  avg_latency_ms numeric,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  created_by character varying DEFAULT 'admin'::character varying,
  CONSTRAINT model_configs_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.system_prompts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  prompt_type character varying NOT NULL CHECK (prompt_type::text = ANY (ARRAY['generation'::character varying, 'review'::character varying]::text[])),
  version integer NOT NULL,
  system_prompt text NOT NULL,
  description text,
  is_active boolean NOT NULL DEFAULT false,
  activated_at timestamp with time zone,
  usage_count integer DEFAULT 0,
  avg_quality_score numeric,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  created_by character varying DEFAULT 'admin'::character varying,
  CONSTRAINT system_prompts_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.template_reviews (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  jurisdiction_type character varying NOT NULL,
  category character varying NOT NULL,
  current_template text NOT NULL,
  suggested_template text NOT NULL,
  reasoning text,
  status character varying DEFAULT 'pending'::character varying,
  created_at timestamp with time zone DEFAULT now(),
  reviewed_at timestamp with time zone,
  reviewed_by uuid,
  CONSTRAINT template_reviews_pkey PRIMARY KEY (id)
);

-- 5. Legislation & Impacts (Existing but included for FKs)
CREATE TABLE IF NOT EXISTS public.legislation (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  jurisdiction_id uuid NOT NULL,
  bill_number text NOT NULL,
  title text NOT NULL,
  text text,
  introduced_date date,
  status text,
  raw_html text,
  analysis_status text DEFAULT 'pending'::text CHECK (analysis_status = ANY (ARRAY['pending'::text, 'completed'::text, 'failed'::text])),
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT legislation_pkey PRIMARY KEY (id),
  CONSTRAINT legislation_jurisdiction_id_fkey FOREIGN KEY (jurisdiction_id) REFERENCES public.jurisdictions(id)
);

CREATE TABLE IF NOT EXISTS public.impacts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  legislation_id uuid NOT NULL,
  impact_number integer NOT NULL,
  relevant_clause text,
  description text NOT NULL,
  evidence jsonb,
  chain_of_causality text,
  confidence_factor double precision CHECK (confidence_factor >= 0::double precision AND confidence_factor <= 1::double precision),
  p10 double precision,
  p25 double precision,
  p50 double precision,
  p75 double precision,
  p90 double precision,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT impacts_pkey PRIMARY KEY (id),
  CONSTRAINT impacts_legislation_id_fkey FOREIGN KEY (legislation_id) REFERENCES public.legislation(id)
);
