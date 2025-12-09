-- Add notes column to scrape_history
ALTER TABLE public.scrape_history ADD COLUMN IF NOT EXISTS notes TEXT;
