-- Add legislation_api to source_type enum
ALTER TYPE public.source_type ADD VALUE IF NOT EXISTS 'legislation_api';
