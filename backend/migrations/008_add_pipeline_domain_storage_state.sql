-- Migration: 008_add_pipeline_domain_storage_state.sql
-- Additive schema for Windmill-domain persisted pipeline state.

CREATE TABLE IF NOT EXISTS public.search_result_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  jurisdiction_id text NOT NULL,
  source_family text NOT NULL,
  query text NOT NULL,
  query_hash text NOT NULL,
  results_hash text NOT NULL,
  result_count integer NOT NULL DEFAULT 0,
  snapshot_payload jsonb NOT NULL DEFAULT '[]'::jsonb,
  contract_version text NOT NULL,
  idempotency_key text NOT NULL,
  captured_at timestamp with time zone NOT NULL DEFAULT now(),
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_search_snapshots_scope_hash
  ON public.search_result_snapshots (jurisdiction_id, source_family, query_hash, results_hash);

CREATE UNIQUE INDEX IF NOT EXISTS idx_search_snapshots_idempotency
  ON public.search_result_snapshots (idempotency_key);

CREATE TABLE IF NOT EXISTS public.content_artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  jurisdiction_id text NOT NULL,
  source_family text NOT NULL,
  artifact_kind text NOT NULL,
  content_hash text NOT NULL,
  storage_uri text NOT NULL,
  media_type text NOT NULL,
  size_bytes integer NOT NULL,
  contract_version text NOT NULL,
  seen_count integer NOT NULL DEFAULT 1,
  first_seen_at timestamp with time zone NOT NULL DEFAULT now(),
  last_seen_at timestamp with time zone NOT NULL DEFAULT now(),
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_content_artifacts_scope_hash
  ON public.content_artifacts (jurisdiction_id, source_family, artifact_kind, content_hash);

CREATE INDEX IF NOT EXISTS idx_content_artifacts_content_hash
  ON public.content_artifacts (content_hash);

CREATE TABLE IF NOT EXISTS public.pipeline_command_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid REFERENCES public.pipeline_runs(id) ON DELETE CASCADE,
  command text NOT NULL,
  idempotency_key text NOT NULL,
  status text NOT NULL,
  decision_reason text,
  retry_class text,
  refs jsonb NOT NULL DEFAULT '{}'::jsonb,
  counts jsonb NOT NULL DEFAULT '{}'::jsonb,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  contract_version text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_command_results_idempotency
  ON public.pipeline_command_results (command, idempotency_key);

ALTER TABLE IF EXISTS public.pipeline_runs
  ADD COLUMN IF NOT EXISTS orchestrator text,
  ADD COLUMN IF NOT EXISTS windmill_workspace text,
  ADD COLUMN IF NOT EXISTS windmill_run_id text,
  ADD COLUMN IF NOT EXISTS windmill_job_id text,
  ADD COLUMN IF NOT EXISTS source_family text,
  ADD COLUMN IF NOT EXISTS contract_version text,
  ADD COLUMN IF NOT EXISTS idempotency_key text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_runs_windmill_scope
  ON public.pipeline_runs (windmill_run_id, source_family, jurisdiction)
  WHERE windmill_run_id IS NOT NULL;

ALTER TABLE IF EXISTS public.pipeline_steps
  ADD COLUMN IF NOT EXISTS command text,
  ADD COLUMN IF NOT EXISTS retry_class text,
  ADD COLUMN IF NOT EXISTS decision_reason text,
  ADD COLUMN IF NOT EXISTS alerts jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS refs jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS windmill_job_id text,
  ADD COLUMN IF NOT EXISTS idempotency_key text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_steps_run_command_idempotency
  ON public.pipeline_steps (run_id, command, idempotency_key)
  WHERE idempotency_key IS NOT NULL;
