-- Discovery resilience cache tables (Phase 1: bd-ss6db)
-- Keep schema reference aligned with migration 008.

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

CREATE TABLE IF NOT EXISTS public.discovery_deferred_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  jurisdiction_id text NOT NULL,
  jurisdiction_name text NOT NULL,
  stage text NOT NULL CHECK (stage IN ('query_generation', 'search', 'classification')),
  reason_code text NOT NULL CHECK (reason_code IN ('rate_limit', 'dns_failure', 'provider_unavailable', 'provider_budget_exhausted')),
  payload jsonb NOT NULL,
  retry_count integer NOT NULL DEFAULT 0,
  next_attempt_at timestamptz NOT NULL DEFAULT now(),
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (jurisdiction_id, stage, reason_code, payload)
);

CREATE INDEX IF NOT EXISTS idx_discovery_deferred_queue_due
  ON public.discovery_deferred_queue (next_attempt_at);
