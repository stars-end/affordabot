-- Migration: 007_add_revision_identity_columns.sql
-- Phase-1 schema groundwork for revision-first substrate identity.

ALTER TABLE IF EXISTS public.raw_scrapes
  ADD COLUMN IF NOT EXISTS canonical_document_key text,
  ADD COLUMN IF NOT EXISTS previous_raw_scrape_id uuid,
  ADD COLUMN IF NOT EXISTS revision_number integer NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS last_seen_at timestamp with time zone NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS seen_count integer NOT NULL DEFAULT 1;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'raw_scrapes_previous_raw_scrape_id_fkey'
  ) THEN
    ALTER TABLE public.raw_scrapes
      ADD CONSTRAINT raw_scrapes_previous_raw_scrape_id_fkey
      FOREIGN KEY (previous_raw_scrape_id) REFERENCES public.raw_scrapes(id);
  END IF;
END $$;

ALTER TABLE IF EXISTS public.raw_scrapes
  DROP CONSTRAINT IF EXISTS raw_scrapes_revision_number_check;

ALTER TABLE IF EXISTS public.raw_scrapes
  ADD CONSTRAINT raw_scrapes_revision_number_check CHECK (revision_number >= 1);

ALTER TABLE IF EXISTS public.raw_scrapes
  DROP CONSTRAINT IF EXISTS raw_scrapes_seen_count_check;

ALTER TABLE IF EXISTS public.raw_scrapes
  ADD CONSTRAINT raw_scrapes_seen_count_check CHECK (seen_count >= 1);

CREATE INDEX IF NOT EXISTS idx_raw_scrapes_canonical_document_key
  ON public.raw_scrapes (canonical_document_key);

CREATE INDEX IF NOT EXISTS idx_raw_scrapes_canonical_document_key_created_at
  ON public.raw_scrapes (canonical_document_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_raw_scrapes_previous_raw_scrape_id
  ON public.raw_scrapes (previous_raw_scrape_id);
