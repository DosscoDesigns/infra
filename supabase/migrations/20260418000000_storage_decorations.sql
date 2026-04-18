-- Storage bucket for decoration images
INSERT INTO storage.buckets (id, name, public) VALUES ('decorations', 'decorations', true)
ON CONFLICT (id) DO NOTHING;

-- Allow public read access
CREATE POLICY "Public read access" ON storage.objects FOR SELECT
  USING (bucket_id = 'decorations');

-- Allow authenticated uploads (service role)
CREATE POLICY "Service role upload" ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'decorations');

CREATE POLICY "Service role update" ON storage.objects FOR UPDATE
  USING (bucket_id = 'decorations');

CREATE POLICY "Service role delete" ON storage.objects FOR DELETE
  USING (bucket_id = 'decorations');
