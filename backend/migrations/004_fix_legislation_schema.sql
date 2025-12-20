ALTER TABLE legislation ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE legislation ADD COLUMN IF NOT EXISTS file_number TEXT;

DO $$
BEGIN
    IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='legislation' AND column_name='text')
    AND NOT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='legislation' AND column_name='text_content')
    THEN
        ALTER TABLE legislation RENAME COLUMN text TO text_content;
    END IF;
END $$;
