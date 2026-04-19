-- Vendor-neutral reference tables
-- Replaces vendor-specific columns (sanmar_unique_key, sanmar_mappings, ss_mappings)

-- 1. Category mappings (replaces sanmar_mappings/ss_mappings columns)
CREATE TABLE category_mappings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID NOT NULL REFERENCES product_categories(id) ON DELETE CASCADE,
  vendor TEXT NOT NULL,
  vendor_category TEXT NOT NULL,
  UNIQUE (category_id, vendor, vendor_category)
);

CREATE INDEX idx_category_mappings_vendor ON category_mappings(vendor);

-- 2. Vendor product refs (links our products to vendor's product IDs)
CREATE TABLE vendor_product_refs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  vendor TEXT NOT NULL,
  vendor_ref TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (product_id, vendor),
  UNIQUE (vendor, vendor_ref)
);

-- 3. Vendor variant refs (links our variants to vendor's SKU IDs + their pricing)
CREATE TABLE vendor_variant_refs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  variant_id UUID NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
  vendor TEXT NOT NULL,
  vendor_ref TEXT NOT NULL,
  vendor_cost DECIMAL(10,2),
  vendor_msrp DECIMAL(10,2),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (variant_id, vendor),
  UNIQUE (vendor, vendor_ref)
);

-- 4. Migrate existing SanMar data

-- Category mappings from sanmar_mappings column
INSERT INTO category_mappings (category_id, vendor, vendor_category)
SELECT pc.id, 'SanMar', unnest(pc.sanmar_mappings)
FROM product_categories pc
WHERE pc.sanmar_mappings IS NOT NULL AND array_length(pc.sanmar_mappings, 1) > 0
ON CONFLICT DO NOTHING;

-- S&S category mappings
INSERT INTO category_mappings (category_id, vendor, vendor_category) VALUES
  ((SELECT id FROM product_categories WHERE name = 'TEES'), 'S&S Activewear', 'T-Shirts - Premium'),
  ((SELECT id FROM product_categories WHERE name = 'TEES'), 'S&S Activewear', 'T-Shirts - Core'),
  ((SELECT id FROM product_categories WHERE name = 'TEES'), 'S&S Activewear', 'T-Shirts - Long Sleeve'),
  ((SELECT id FROM product_categories WHERE name = 'POLOS'), 'S&S Activewear', 'Polos'),
  ((SELECT id FROM product_categories WHERE name = 'SWEATERS'), 'S&S Activewear', 'Fleece - Premium - Hood'),
  ((SELECT id FROM product_categories WHERE name = 'SWEATERS'), 'S&S Activewear', 'Fleece - Premium - Crew'),
  ((SELECT id FROM product_categories WHERE name = 'SWEATERS'), 'S&S Activewear', 'Fleece - Core - Hood'),
  ((SELECT id FROM product_categories WHERE name = 'SWEATERS'), 'S&S Activewear', 'Fleece - Core - Crew'),
  ((SELECT id FROM product_categories WHERE name = 'JACKETS'), 'S&S Activewear', 'Outerwear'),
  ((SELECT id FROM product_categories WHERE name = 'JACKETS'), 'S&S Activewear', 'Knits & Layering'),
  ((SELECT id FROM product_categories WHERE name = 'HATS'), 'S&S Activewear', 'Headwear'),
  ((SELECT id FROM product_categories WHERE name = 'WOVEN'), 'S&S Activewear', 'Wovens'),
  ((SELECT id FROM product_categories WHERE name = 'SHORTS'), 'S&S Activewear', 'Bottoms'),
  ((SELECT id FROM product_categories WHERE name = 'BAGS'), 'S&S Activewear', 'Bags'),
  ((SELECT id FROM product_categories WHERE name = 'BAGS'), 'S&S Activewear', 'Accessories')
ON CONFLICT DO NOTHING;

-- Vendor product refs from existing SanMar products
-- Using style_code as vendor_ref for SanMar (they don't have a separate numeric ID in our data)
INSERT INTO vendor_product_refs (product_id, vendor, vendor_ref)
SELECT id, vendor, style_code FROM products
WHERE vendor = 'SanMar'
ON CONFLICT DO NOTHING;

-- S&S product refs for existing S&S products
INSERT INTO vendor_product_refs (product_id, vendor, vendor_ref)
SELECT id, 'S&S Activewear', style_code FROM products
WHERE vendor = 'S&S Activewear'
ON CONFLICT DO NOTHING;

-- Vendor variant refs from sanmar_unique_key
INSERT INTO vendor_variant_refs (variant_id, vendor, vendor_ref, vendor_cost, vendor_msrp)
SELECT v.id, 'SanMar', v.sanmar_unique_key, v.cost, v.msrp
FROM variants v
WHERE v.sanmar_unique_key IS NOT NULL
ON CONFLICT DO NOTHING;
