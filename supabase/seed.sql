-- DD Platform — Seed Data
-- Pre-populates config tables and the DD org

-- ============================================================================
-- DD Org (anchor org for general store at /store)
-- ============================================================================

INSERT INTO orgs (org_code, name, collect_taxes) VALUES
  ('DD', 'Dossco Designs', true);

-- ============================================================================
-- Product Categories (from Schema-Design.md)
-- ============================================================================

INSERT INTO product_categories (name, display_name, sort_order, sanmar_mappings, ss_mappings, decoration_options) VALUES
  ('TEES', 'T-Shirts', 1, '{T-Shirts}', '{}', '{heat_applied,embroidery,screen_print}'),
  ('POLOS', 'Polos', 2, '{Polos,Knits}', '{}', '{heat_applied,embroidery}'),
  ('SWEATERS', 'Hoodies & Sweatshirts', 3, '{Sweatshirts,Fleece}', '{}', '{heat_applied,embroidery,screen_print}'),
  ('JACKETS', 'Jackets & Outerwear', 4, '{Outerwear}', '{}', '{heat_applied,embroidery}'),
  ('HATS', 'Hats', 5, '{Caps}', '{}', '{heat_applied,embroidery,leather_patch}'),
  ('PERFORMANCE', 'Performance', 6, '{Activewear}', '{}', '{heat_applied,embroidery}'),
  ('WOVEN', 'Button-Downs', 7, '{Wovens}', '{}', '{embroidery}'),
  ('SHORTS', 'Bottoms', 8, '{Bottoms}', '{}', '{heat_applied,embroidery}'),
  ('BAGS', 'Bags & Accessories', 9, '{Bags}', '{}', '{heat_applied,embroidery}');

-- ============================================================================
-- Pricing Config — Size Upcharges
-- ============================================================================

INSERT INTO pricing_config (config_type, label, size, amount) VALUES
  ('size_upcharge', '2XL upcharge', '2XL', 1.50),
  ('size_upcharge', '3XL upcharge', '3XL', 3.00),
  ('size_upcharge', '4XL upcharge', '4XL', 5.00),
  ('size_upcharge', '5XL upcharge', '5XL', 7.50);

-- ============================================================================
-- Pricing Config — Quantity Discounts
-- ============================================================================

INSERT INTO pricing_config (config_type, label, min_qty, max_qty, amount) VALUES
  ('quantity_discount', 'Base decoration markup', 1, 24, 4.00),
  ('quantity_discount', '25+ discount', 25, 49, 3.50),
  ('quantity_discount', '50+ discount', 50, 99, 3.00),
  ('quantity_discount', '100+ discount', 100, 999999, 2.50);

-- ============================================================================
-- Tax Config — Sales Tax
-- ============================================================================

INSERT INTO tax_config (state, state_rate, county_surtax, has_nexus, nexus_type, notes) VALUES
  ('FL', 0.0600, 0, true, 'physical', 'Home state. Collect on all non-exempt orders.'),
  ('NC', 0.0475, 0, false, NULL, '1 client, below $100K/200 txn threshold. Monitor.'),
  ('VA', 0.0530, 0, false, NULL, '1 client, below threshold. Monitor.');

-- ============================================================================
-- Sync State — Initialize all syncable tables
-- ============================================================================

INSERT INTO sync_state (table_name, status, notes) VALUES
  ('orgs', 'active', 'Rarely changes'),
  ('products', 'active', 'SanMar sync writes here'),
  ('variants', 'active', 'SanMar sync writes here'),
  ('customers', 'active', 'Until customer site live'),
  ('orders', 'active', 'Until order mgmt built'),
  ('order_items', 'active', 'Same as orders'),
  ('order_item_batches', 'active', 'Same as orders'),
  ('payments', 'active', 'Stripe webhook writes here'),
  ('decorations', 'active', 'Until decoration mgmt built'),
  ('decoration_sets', 'active', 'Same as decorations'),
  ('events', 'active', 'Until admin settings built'),
  ('price_rules', 'active', 'Same as events'),
  ('suppliers', 'active', 'Rarely changes'),
  ('product_categories', 'active', 'Rarely changes');
