-- Migration: 009_add_policy_evidence_package_storage.sql
-- Additive storage table for PolicyEvidencePackage persistence proof (bd-3wefe.10).

CREATE TABLE IF NOT EXISTS public.policy_evidence_packages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  package_id text NOT NULL,
  idempotency_key text NOT NULL,
  content_hash text NOT NULL,
  schema_version text NOT NULL,
  jurisdiction text NOT NULL,
  canonical_document_key text NOT NULL,
  policy_identifier text NOT NULL,
  package_status text NOT NULL,
  economic_handoff_ready boolean NOT NULL DEFAULT false,
  fail_closed boolean NOT NULL DEFAULT true,
  gate_state text NOT NULL,
  insufficiency_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  storage_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  package_payload jsonb NOT NULL,
  artifact_write_status text NOT NULL DEFAULT 'not_configured',
  artifact_readback_status text NOT NULL DEFAULT 'unproven',
  pgvector_truth_role text NOT NULL DEFAULT 'derived_index',
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_evidence_packages_package_id
  ON public.policy_evidence_packages (package_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_evidence_packages_idempotency
  ON public.policy_evidence_packages (idempotency_key);

CREATE INDEX IF NOT EXISTS idx_policy_evidence_packages_jurisdiction_status
  ON public.policy_evidence_packages (jurisdiction, package_status);

CREATE INDEX IF NOT EXISTS idx_policy_evidence_packages_content_hash
  ON public.policy_evidence_packages (content_hash);
