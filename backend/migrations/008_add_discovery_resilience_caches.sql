-- Phase 1 discovery resilience caches (bd-ss6db).
-- Keeps provider-heavy query generation/classification work bounded per run.

CREATE TABLE IF NOT EXISTS public.discovery_query_cache (
  jurisdiction_name text NOT NULL,
  jurisdiction_type text NOT NULL,
  prompt_version text NOT NULL,
  queries jsonb NOT NULL,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (jurisdiction_name, jurisdiction_type, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_discovery_query_cache_expires_at
  ON public.discovery_query_cache (expires_at);

CREATE TABLE IF NOT EXISTS public.discovery_classifier_cache (
  normalized_url text NOT NULL,
  classifier_version text NOT NULL,
  decision jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (normalized_url, classifier_version)
);
