-- DD Platform — Initial Schema
-- Based on Schema-Design.md (2026-03-26)
-- Migration: Create all business tables, indexes, views, and RLS policies

-- ============================================================================
-- TABLES (in dependency order)
-- ============================================================================

-- 1. orgs
CREATE TABLE orgs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_code TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  collect_taxes BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. suppliers
CREATE TABLE suppliers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  url TEXT,
  account_number TEXT,
  contact_email TEXT,
  phone TEXT,
  lead_time_days INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. product_categories
CREATE TABLE product_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  sort_order INTEGER DEFAULT 0,
  sanmar_mappings TEXT[],
  ss_mappings TEXT[],
  decoration_options TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. products
CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  style_code TEXT NOT NULL,
  display_name TEXT NOT NULL,
  name TEXT NOT NULL,
  brand TEXT,
  vendor TEXT NOT NULL,
  category_id UUID REFERENCES product_categories(id),
  decoration_options TEXT[],
  image_url TEXT,
  sanmar_categories TEXT,
  revision_count INTEGER DEFAULT 0,
  base_price DECIMAL(10,2),
  sale_price DECIMAL(10,2),
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. variants
CREATE TABLE variants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  color TEXT NOT NULL,
  size TEXT NOT NULL,
  cost DECIMAL(10,2),
  cost_case DECIMAL(10,2),
  case_size INTEGER,
  minimum_sale DECIMAL(10,2),
  msrp DECIMAL(10,2),
  piece_weight DECIMAL(8,2),
  sanmar_unique_key INTEGER,
  color_swatch_url TEXT,
  color_product_url TEXT,
  color_product_thumb_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(product_id, color, size)
);

-- 6. customers
CREATE TABLE customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_type TEXT NOT NULL DEFAULT 'Individual',
  status TEXT DEFAULT 'active',
  business_name TEXT,
  first_name TEXT,
  last_name TEXT,
  title TEXT,
  phone TEXT,
  email TEXT,
  shipping_address TEXT,
  shipping_address_line2 TEXT,
  shipping_city TEXT,
  shipping_state TEXT,
  shipping_postal_code TEXT,
  shipping_country TEXT,
  notes TEXT,
  business_org_id UUID REFERENCES orgs(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. events
CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID REFERENCES orgs(id),
  event_code TEXT NOT NULL,
  name TEXT NOT NULL,
  active BOOLEAN DEFAULT true,
  date_start TIMESTAMPTZ,
  date_end TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. decorations
CREATE TABLE decorations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID REFERENCES orgs(id),
  name TEXT NOT NULL,
  code TEXT NOT NULL,
  category TEXT,
  method TEXT NOT NULL,
  location TEXT NOT NULL,
  width_in DECIMAL(5,2),
  height_in DECIMAL(5,2),
  color_type TEXT NOT NULL DEFAULT 'single',
  colors TEXT[],
  color_count INTEGER GENERATED ALWAYS AS (
    CASE WHEN color_type = 'full_color' THEN 0
         ELSE coalesce(array_length(colors, 1), 0)
    END
  ) STORED,
  stitches INTEGER,
  cost DECIMAL(8,2),
  run_charge DECIMAL(8,2),
  image_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_decoration_colors CHECK (
    (color_type = 'single' AND array_length(colors, 1) = 1) OR
    (color_type = 'multi' AND array_length(colors, 1) > 1) OR
    (color_type = 'full_color')
  )
);

-- 9. decoration_sets
CREATE TABLE decoration_sets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID REFERENCES orgs(id),
  name TEXT NOT NULL,
  decoration_type TEXT NOT NULL,
  mockup_url TEXT,
  front_url TEXT,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE decoration_set_items (
  decoration_set_id UUID NOT NULL REFERENCES decoration_sets(id) ON DELETE CASCADE,
  decoration_id UUID NOT NULL REFERENCES decorations(id) ON DELETE CASCADE,
  PRIMARY KEY (decoration_set_id, decoration_id)
);

-- 10. price_rules
CREATE TABLE price_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES orgs(id),
  event_id UUID REFERENCES events(id),
  category_id UUID REFERENCES product_categories(id),
  description TEXT,
  override_price DECIMAL(10,2) NOT NULL,
  org_cut_type TEXT DEFAULT 'flat',
  org_cut DECIMAL(10,2) DEFAULT 0,
  priority INTEGER DEFAULT 0,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE price_rule_products (
  price_rule_id UUID NOT NULL REFERENCES price_rules(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  PRIMARY KEY (price_rule_id, product_id)
);

-- 11. org_products
CREATE TABLE org_products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  listing_name TEXT,
  description TEXT,
  sort_order INTEGER DEFAULT 0,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, product_id)
);

-- 12. orders
CREATE TABLE orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  seq INTEGER GENERATED ALWAYS AS IDENTITY,
  customer_id UUID REFERENCES customers(id),
  org_id UUID REFERENCES orgs(id),
  event_id UUID REFERENCES events(id),
  status TEXT DEFAULT 'Draft',
  payment_method TEXT,
  delivery_method TEXT,
  po_number TEXT,
  summary TEXT,
  tax_exempt BOOLEAN DEFAULT false,
  setup_fee DECIMAL(10,2) DEFAULT 0,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 13. order_item_batches
CREATE TABLE order_item_batches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_number INTEGER GENERATED ALWAYS AS IDENTITY,
  batch_name TEXT,
  status TEXT DEFAULT 'decorating',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 14. order_items
CREATE TABLE order_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id UUID REFERENCES products(id),
  variant_id UUID REFERENCES variants(id),
  decoration_set_id UUID REFERENCES decoration_sets(id),
  matched_rule_id UUID REFERENCES price_rules(id),
  batch_id UUID REFERENCES order_item_batches(id),
  qty INTEGER NOT NULL DEFAULT 1,
  unit_price DECIMAL(10,2),
  size_upcharge DECIMAL(10,2) DEFAULT 0,
  org_cut DECIMAL(10,2) DEFAULT 0,
  ordered BOOLEAN DEFAULT true,
  decorated BOOLEAN DEFAULT false,
  defect BOOLEAN DEFAULT false,
  bagged BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 15. payments
CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID REFERENCES orders(id),
  customer_id UUID REFERENCES customers(id),
  method TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  amount DECIMAL(10,2) NOT NULL,
  tax_amount DECIMAL(10,2) DEFAULT 0,
  processing_fees DECIMAL(10,2),
  net_amount DECIMAL(10,2),
  stripe_session_id TEXT,
  stripe_payment_intent_id TEXT,
  stripe_receipt_url TEXT,
  square_payment_id TEXT,
  square_device_id TEXT,
  qb_invoice_id TEXT,
  qb_invoice_number TEXT,
  payment_url TEXT,
  note TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 16. inventory
CREATE TABLE inventory (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inventory_number INTEGER GENERATED ALWAYS AS IDENTITY,
  org_id UUID REFERENCES orgs(id),
  product_id UUID REFERENCES products(id),
  variant_id UUID REFERENCES variants(id),
  decoration_set_id UUID REFERENCES decoration_sets(id),
  supplier_id UUID REFERENCES suppliers(id),
  inventory_type TEXT NOT NULL,
  purpose TEXT DEFAULT 'stock',
  is_decorated BOOLEAN DEFAULT false,
  raw_cost DECIMAL(8,2),
  list_price DECIMAL(8,2),
  qty_on_hand INTEGER DEFAULT 0,
  qty_on_order INTEGER DEFAULT 0,
  reserved_qty INTEGER DEFAULT 0,
  reorder_point INTEGER DEFAULT 0,
  reorder_qty INTEGER DEFAULT 0,
  bin_number TEXT,
  last_counted DATE,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 17. purchase_orders (new — not in Airtable)
CREATE TABLE purchase_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  po_number INTEGER GENERATED ALWAYS AS IDENTITY,
  supplier_id UUID NOT NULL REFERENCES suppliers(id),
  status TEXT DEFAULT 'draft',
  order_date DATE,
  expected_date DATE,
  received_date DATE,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE po_line_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  po_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
  product_id UUID REFERENCES products(id),
  variant_id UUID REFERENCES variants(id),
  qty_ordered INTEGER NOT NULL,
  qty_received INTEGER DEFAULT 0,
  unit_cost DECIMAL(10,2),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- SYNC INFRASTRUCTURE
-- ============================================================================

CREATE TABLE airtable_id_map (
  airtable_table TEXT NOT NULL,
  airtable_id TEXT NOT NULL,
  supabase_table TEXT NOT NULL,
  supabase_id UUID NOT NULL,
  PRIMARY KEY (airtable_table, airtable_id)
);

CREATE INDEX idx_airtable_map_supabase ON airtable_id_map(supabase_table, supabase_id);

CREATE TABLE sync_state (
  table_name TEXT PRIMARY KEY,
  last_polled_at TIMESTAMPTZ,
  last_record_count INTEGER,
  status TEXT DEFAULT 'active',
  notes TEXT
);

CREATE TABLE sync_error_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  table_name TEXT NOT NULL,
  airtable_id TEXT,
  error_message TEXT,
  payload JSONB,
  resolved BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- CONFIG TABLES
-- ============================================================================

CREATE TABLE pricing_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  config_type TEXT NOT NULL,
  label TEXT NOT NULL,
  size TEXT,
  min_qty INTEGER,
  max_qty INTEGER,
  amount DECIMAL(10,2),
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE tax_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  state TEXT NOT NULL UNIQUE,
  state_rate DECIMAL(6,4) NOT NULL,
  county_surtax DECIMAL(6,4) DEFAULT 0,
  has_nexus BOOLEAN DEFAULT false,
  nexus_type TEXT,
  notes TEXT,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX idx_variants_product ON variants(product_id);
CREATE INDEX idx_variants_sanmar_key ON variants(sanmar_unique_key);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_batch ON order_items(batch_id);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_org ON orders(org_id);
CREATE INDEX idx_orders_event ON orders(event_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_decorations_org ON decorations(org_id);
CREATE INDEX idx_decoration_sets_org ON decoration_sets(org_id);
CREATE INDEX idx_inventory_org ON inventory(org_id);
CREATE INDEX idx_inventory_type ON inventory(inventory_type);
CREATE INDEX idx_customers_phone ON customers(phone);
CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_products_style ON products(style_code);
CREATE INDEX idx_org_products_org ON org_products(org_id);

-- ============================================================================
-- VIEWS
-- ============================================================================

CREATE VIEW v_products AS
SELECT
  p.*,
  pc.name AS category_name,
  pc.display_name AS category_display_name,
  min(v.cost) AS min_cost,
  max(v.cost) AS max_cost,
  count(v.id) AS variant_count
FROM products p
LEFT JOIN product_categories pc ON p.category_id = pc.id
LEFT JOIN variants v ON p.id = v.product_id
GROUP BY p.id, pc.name, pc.display_name;

CREATE VIEW v_orders AS
SELECT
  o.*,
  c.first_name, c.last_name, c.business_name, c.phone AS customer_phone,
  org.org_code, org.name AS org_name,
  e.event_code, e.name AS event_name,
  count(oi.id) AS item_count,
  sum(oi.qty) AS total_qty,
  count(oi.id) FILTER (WHERE oi.decorated) AS decorated_count,
  count(oi.id) FILTER (WHERE oi.bagged) AS bagged_count
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.id
LEFT JOIN orgs org ON o.org_id = org.id
LEFT JOIN events e ON o.event_id = e.id
LEFT JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id, c.id, org.id, e.id;

-- ============================================================================
-- UPDATED_AT TRIGGERS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_orgs_updated_at BEFORE UPDATE ON orgs FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_suppliers_updated_at BEFORE UPDATE ON suppliers FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_product_categories_updated_at BEFORE UPDATE ON product_categories FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_products_updated_at BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_variants_updated_at BEFORE UPDATE ON variants FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_customers_updated_at BEFORE UPDATE ON customers FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_events_updated_at BEFORE UPDATE ON events FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_decorations_updated_at BEFORE UPDATE ON decorations FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_decoration_sets_updated_at BEFORE UPDATE ON decoration_sets FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_price_rules_updated_at BEFORE UPDATE ON price_rules FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_orders_updated_at BEFORE UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_order_item_batches_updated_at BEFORE UPDATE ON order_item_batches FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_order_items_updated_at BEFORE UPDATE ON order_items FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_payments_updated_at BEFORE UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_inventory_updated_at BEFORE UPDATE ON inventory FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_purchase_orders_updated_at BEFORE UPDATE ON purchase_orders FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_po_line_items_updated_at BEFORE UPDATE ON po_line_items FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_pricing_config_updated_at BEFORE UPDATE ON pricing_config FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_tax_config_updated_at BEFORE UPDATE ON tax_config FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

-- Enable RLS on all tables (policies will be added as auth features are built)
ALTER TABLE orgs ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE variants ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE decorations ENABLE ROW LEVEL SECURITY;
ALTER TABLE decoration_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE decoration_set_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_rule_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_item_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE po_line_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE pricing_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE airtable_id_map ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_error_log ENABLE ROW LEVEL SECURITY;

-- Service role bypass — allows worker backend (service_role key) full access
-- Public/anon policies will be added when auth features are built
CREATE POLICY "Service role full access" ON orgs FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON suppliers FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON product_categories FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON products FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON variants FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON customers FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON events FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON decorations FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON decoration_sets FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON decoration_set_items FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON price_rules FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON price_rule_products FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON org_products FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON orders FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON order_item_batches FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON order_items FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON payments FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON inventory FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON purchase_orders FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON po_line_items FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON pricing_config FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON tax_config FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON airtable_id_map FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON sync_state FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON sync_error_log FOR ALL USING (auth.role() = 'service_role');

-- Public read access for store-facing tables (products, categories, orgs, etc.)
CREATE POLICY "Public read products" ON products FOR SELECT USING (true);
CREATE POLICY "Public read variants" ON variants FOR SELECT USING (true);
CREATE POLICY "Public read product_categories" ON product_categories FOR SELECT USING (true);
CREATE POLICY "Public read orgs" ON orgs FOR SELECT USING (true);
CREATE POLICY "Public read events" ON events FOR SELECT USING (true);
CREATE POLICY "Public read decoration_sets" ON decoration_sets FOR SELECT USING (true);
CREATE POLICY "Public read decoration_set_items" ON decoration_set_items FOR SELECT USING (true);
CREATE POLICY "Public read org_products" ON org_products FOR SELECT USING (true);
CREATE POLICY "Public read pricing_config" ON pricing_config FOR SELECT USING (true);
CREATE POLICY "Public read tax_config" ON tax_config FOR SELECT USING (true);
