-- =====================================================================
-- 000_reset.sql : wipes the OLD test tables so the new system starts clean.
-- Run once in Supabase -> SQL Editor.
-- Deletes everything in the "public" schema (old test data only).
-- Your login user (Authentication -> Users) is NOT affected.
-- =====================================================================
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres, anon, authenticated, service_role;
