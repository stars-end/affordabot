
-- Add meetings and code to source_type enum
ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'meetings';
ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'code';
