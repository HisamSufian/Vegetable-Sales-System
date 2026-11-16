-- =====================================================================
-- 010_backup_reminder.sql : remembers when you last downloaded a backup
-- Run once in Supabase -> SQL Editor. Run it BEFORE deploying the new code.
-- =====================================================================
ALTER TABLE settings ADD COLUMN last_backup_at TIMESTAMPTZ;
