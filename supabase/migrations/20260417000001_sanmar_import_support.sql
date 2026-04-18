-- Support on-demand SanMar product import via upsert
-- Requires unique constraint on style_code for conflict resolution

-- Unique index on products.style_code for upsert support
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_style_code ON products (style_code);

-- Index on variants.sanmar_unique_key for faster lookup during import
CREATE INDEX IF NOT EXISTS idx_variants_sanmar_unique_key ON variants (sanmar_unique_key);
