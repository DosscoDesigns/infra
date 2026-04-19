-- 1. Vendors lookup table
CREATE TABLE vendors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  api_type TEXT,  -- 'soap', 'rest', null
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO vendors (code, name, api_type) VALUES
  ('SANMAR', 'SanMar', 'soap'),
  ('SS', 'S&S Activewear', 'rest'),
  ('AKWA', 'Akwa', null);

-- 2. Add vendor_id FK to products (keep vendor text for now, backfill, then we can drop later)
ALTER TABLE products ADD COLUMN vendor_id UUID REFERENCES vendors(id);

-- Backfill vendor_id from vendor text
UPDATE products SET vendor_id = (SELECT id FROM vendors WHERE name = products.vendor);

-- 3. Add vendor_id to ref tables (replace vendor text)
ALTER TABLE category_mappings ADD COLUMN vendor_id UUID REFERENCES vendors(id);
ALTER TABLE vendor_product_refs ADD COLUMN vendor_id UUID REFERENCES vendors(id);
ALTER TABLE vendor_variant_refs ADD COLUMN vendor_id UUID REFERENCES vendors(id);

-- Backfill
UPDATE category_mappings SET vendor_id = (SELECT id FROM vendors WHERE name = category_mappings.vendor);
UPDATE vendor_product_refs SET vendor_id = (SELECT id FROM vendors WHERE name = vendor_product_refs.vendor);
UPDATE vendor_variant_refs SET vendor_id = (SELECT id FROM vendors WHERE name = vendor_variant_refs.vendor);

-- 4. RLS on new tables
ALTER TABLE vendors ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE vendor_product_refs ENABLE ROW LEVEL SECURITY;
ALTER TABLE vendor_variant_refs ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (same pattern as other tables)
CREATE POLICY "Service role full access" ON vendors FOR ALL USING (true);
CREATE POLICY "Service role full access" ON category_mappings FOR ALL USING (true);
CREATE POLICY "Service role full access" ON vendor_product_refs FOR ALL USING (true);
CREATE POLICY "Service role full access" ON vendor_variant_refs FOR ALL USING (true);
