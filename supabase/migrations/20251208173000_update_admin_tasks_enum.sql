
-- Update admin_tasks task_type check constraint
ALTER TABLE admin_tasks DROP CONSTRAINT IF EXISTS admin_tasks_task_type_check;

ALTER TABLE admin_tasks ADD CONSTRAINT admin_tasks_task_type_check 
  CHECK (task_type IN ('scrape', 'research', 'generate', 'review', 'universal_harvest'));
