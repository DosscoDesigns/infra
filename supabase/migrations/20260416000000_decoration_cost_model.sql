-- Decoration Cost Model
-- New tables: vendor_price_tables, decoration_surcharges
-- Modified: decorations (add vendor link, images_per_sheet), decoration_sets (add labor_cost, charge)

-- 1. vendor_price_tables — stores vendor pricing matrices
CREATE TABLE vendor_price_tables (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vendor TEXT NOT NULL,
  name TEXT NOT NULL,
  decoration_type TEXT NOT NULL,
  category TEXT,
  artwork_type TEXT,
  colors INTEGER,
  sheet_size TEXT,
  tiers JSONB NOT NULL,
  notes TEXT,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. decoration_surcharges — per-type surcharges by product category or product
CREATE TABLE decoration_surcharges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  decoration_type TEXT NOT NULL,
  product_category_id UUID REFERENCES product_categories(id),
  product_id UUID REFERENCES products(id),
  amount DECIMAL(10,2) NOT NULL,
  description TEXT,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Add columns to decorations
ALTER TABLE decorations
  ADD COLUMN active BOOLEAN DEFAULT true,
  ADD COLUMN vendor_price_table_id UUID REFERENCES vendor_price_tables(id),
  ADD COLUMN images_per_sheet INTEGER DEFAULT 1,
  ADD COLUMN price_breaks JSONB DEFAULT '[]';

-- 3b. Relax location to nullable (placement codes are optional)
ALTER TABLE decorations ALTER COLUMN location DROP NOT NULL;

-- 3c. Drop overly strict colors constraint (color_type 'multiple' vs 'multi' mismatch, allow empty)
ALTER TABLE decorations DROP CONSTRAINT IF EXISTS chk_decoration_colors;

-- 4. Add columns to decoration_sets
ALTER TABLE decoration_sets
  ADD COLUMN labor_cost DECIMAL(10,2) DEFAULT 0,
  ADD COLUMN charge DECIMAL(10,2);

-- 5. Migrate run_charge to set-level labor_cost
-- For each decoration_set, sum run_charge from its decorations
UPDATE decoration_sets ds
SET labor_cost = COALESCE((
  SELECT SUM(COALESCE(d.run_charge, 0))
  FROM decoration_set_items dsi
  JOIN decorations d ON d.id = dsi.decoration_id
  WHERE dsi.decoration_set_id = ds.id
), 0);

-- 6. Indexes
CREATE INDEX idx_vendor_price_tables_type ON vendor_price_tables(decoration_type);
CREATE INDEX idx_vendor_price_tables_vendor ON vendor_price_tables(vendor);
CREATE INDEX idx_decoration_surcharges_type ON decoration_surcharges(decoration_type);
CREATE INDEX idx_decorations_vendor_price_table ON decorations(vendor_price_table_id);
