-- Rename sanmar_categories → vendor_categories on products
ALTER TABLE products RENAME COLUMN sanmar_categories TO vendor_categories;

-- Drop legacy vendor-specific mapping columns from product_categories
-- All mappings are now in the category_mappings table
ALTER TABLE product_categories DROP COLUMN IF EXISTS sanmar_mappings;
ALTER TABLE product_categories DROP COLUMN IF EXISTS ss_mappings;
