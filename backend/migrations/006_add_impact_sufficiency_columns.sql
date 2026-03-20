-- Migration: 006_add_impact_sufficiency_columns.sql
-- Add sufficiency and quantification gating columns to impacts table.
-- Required by bd-tytc.2 evidence-gated quantification contract.

ALTER TABLE impacts
  ADD COLUMN IF NOT EXISTS sufficiency_state TEXT,
  ADD COLUMN IF NOT EXISTS quantification_eligible BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS numeric_basis TEXT,
  ADD COLUMN IF NOT EXISTS estimate_method TEXT;

-- Add bill-level sufficiency columns to legislation table
-- so the frontend can render sufficiency banners on bill detail.
ALTER TABLE legislation
  ADD COLUMN IF NOT EXISTS sufficiency_state TEXT,
  ADD COLUMN IF NOT EXISTS insufficiency_reason TEXT,
  ADD COLUMN IF NOT EXISTS quantification_eligible BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS total_impact_p50 DOUBLE PRECISION;
