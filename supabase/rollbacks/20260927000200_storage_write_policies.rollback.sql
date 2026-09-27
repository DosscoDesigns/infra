-- ROLLBACK for 20260927000200_storage_write_policies.sql — restores the prior (insecure) state.
BEGIN;
CREATE POLICY "Service role upload" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'decorations');
CREATE POLICY "Service role update" ON storage.objects FOR UPDATE USING (bucket_id = 'decorations');
CREATE POLICY "Service role delete" ON storage.objects FOR DELETE USING (bucket_id = 'decorations');
COMMIT;
