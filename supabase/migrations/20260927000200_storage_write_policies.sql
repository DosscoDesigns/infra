-- 20260927000200_storage_write_policies.sql
-- Security audit, 2026-09-26 (JARVIS-dd). Separate from ..000100 on purpose: storage.objects is
-- owned by supabase_storage_admin, so if this ever fails on permissions it must not roll back
-- the view/table fix with it.
--
-- Three policies NAMED "Service role upload/update/delete" checked only bucket_id, for role
-- public — so the PUBLIC anon key could upload any file of any type and size into the
-- `decorations` bucket, overwrite existing customer-facing art, or delete it. The bucket is
-- public-read, so an upload is immediately served from our storage domain.
--
-- Only the worker writes storage (apps/worker/src/sanmar/sftp.js), server-side as service_role,
-- which bypasses RLS and never needed these. "Public read access" is kept: the art must stay
-- viewable. Rollback: supabase/rollbacks/20260927000200_storage_write_policies.rollback.sql
BEGIN;
DROP POLICY IF EXISTS "Service role upload" ON storage.objects;
DROP POLICY IF EXISTS "Service role update" ON storage.objects;
DROP POLICY IF EXISTS "Service role delete" ON storage.objects;
COMMIT;
