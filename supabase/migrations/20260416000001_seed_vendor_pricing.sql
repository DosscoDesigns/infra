-- Seed: Vendor Pricing Data
-- Transfer Express 2025 + iDex 2026

-- ============================================================================
-- Transfer Express — Goof Proof Single Image
-- ============================================================================

INSERT INTO vendor_price_tables (vendor, name, decoration_type, category, sheet_size, tiers) VALUES
  ('Transfer Express', 'Goof Proof Single Image — Small (9×12.75)', 'heat applied', 'single_image', 'small',
   '[{"min_qty":25,"cost":1.95},{"min_qty":50,"cost":0.99},{"min_qty":100,"cost":0.79},{"min_qty":150,"cost":0.69},{"min_qty":300,"cost":0.39},{"min_qty":500,"cost":0.29}]'),

  ('Transfer Express', 'Goof Proof Single Image — Large (11×14)', 'heat applied', 'single_image', 'large',
   '[{"min_qty":25,"cost":2.35},{"min_qty":50,"cost":1.19},{"min_qty":100,"cost":1.09},{"min_qty":150,"cost":0.89},{"min_qty":300,"cost":0.69},{"min_qty":500,"cost":0.49}]');

-- ============================================================================
-- Transfer Express — Screen Printed Gang Sheets (Standard 11.25×14)
-- Easy Prints artwork
-- ============================================================================

INSERT INTO vendor_price_tables (vendor, name, decoration_type, category, artwork_type, colors, sheet_size, tiers) VALUES
  ('Transfer Express', 'Gang Sheet — Easy Prints, 1 Color', 'heat applied', 'gang_sheet', 'easy_prints', 1, 'standard',
   '[{"min_qty":6,"cost":9.26},{"min_qty":12,"cost":5.00},{"min_qty":18,"cost":4.44},{"min_qty":24,"cost":3.14},{"min_qty":36,"cost":2.74},{"min_qty":48,"cost":2.50},{"min_qty":72,"cost":1.89},{"min_qty":90,"cost":1.82},{"min_qty":144,"cost":1.32},{"min_qty":180,"cost":1.25},{"min_qty":288,"cost":1.06},{"min_qty":360,"cost":1.00},{"min_qty":576,"cost":0.81},{"min_qty":2500,"cost":0.72}]'),

  ('Transfer Express', 'Gang Sheet — Easy Prints, 2 Colors', 'heat applied', 'gang_sheet', 'easy_prints', 2, 'standard',
   '[{"min_qty":6,"cost":11.57},{"min_qty":12,"cost":6.25},{"min_qty":18,"cost":5.56},{"min_qty":24,"cost":3.92},{"min_qty":36,"cost":3.42},{"min_qty":48,"cost":3.12},{"min_qty":72,"cost":2.36},{"min_qty":90,"cost":2.28},{"min_qty":144,"cost":1.65},{"min_qty":180,"cost":1.56},{"min_qty":288,"cost":1.32},{"min_qty":360,"cost":1.25},{"min_qty":576,"cost":1.01},{"min_qty":2500,"cost":0.89}]'),

  ('Transfer Express', 'Gang Sheet — Easy Prints, 3 Colors', 'heat applied', 'gang_sheet', 'easy_prints', 3, 'standard',
   '[{"min_qty":6,"cost":13.89},{"min_qty":12,"cost":7.50},{"min_qty":18,"cost":6.67},{"min_qty":24,"cost":4.71},{"min_qty":36,"cost":4.11},{"min_qty":48,"cost":3.75},{"min_qty":72,"cost":2.83},{"min_qty":90,"cost":2.73},{"min_qty":144,"cost":1.98},{"min_qty":180,"cost":1.88},{"min_qty":288,"cost":1.59},{"min_qty":360,"cost":1.50},{"min_qty":576,"cost":1.21},{"min_qty":2500,"cost":1.07}]'),

  ('Transfer Express', 'Gang Sheet — Easy Prints, 4 Colors', 'heat applied', 'gang_sheet', 'easy_prints', 4, 'standard',
   '[{"min_qty":6,"cost":16.20},{"min_qty":12,"cost":8.75},{"min_qty":18,"cost":7.78},{"min_qty":24,"cost":5.49},{"min_qty":36,"cost":4.79},{"min_qty":48,"cost":4.38},{"min_qty":72,"cost":3.30},{"min_qty":90,"cost":3.19},{"min_qty":144,"cost":2.31},{"min_qty":180,"cost":2.19},{"min_qty":288,"cost":1.85},{"min_qty":360,"cost":1.75},{"min_qty":576,"cost":1.42},{"min_qty":2500,"cost":1.25}]');

-- ============================================================================
-- Transfer Express — Gang Sheets — Vector artwork
-- ============================================================================

INSERT INTO vendor_price_tables (vendor, name, decoration_type, category, artwork_type, colors, sheet_size, tiers) VALUES
  ('Transfer Express', 'Gang Sheet — Vector, 1 Color', 'heat applied', 'gang_sheet', 'vector', 1, 'standard',
   '[{"min_qty":6,"cost":11.57},{"min_qty":12,"cost":6.25},{"min_qty":18,"cost":5.56},{"min_qty":24,"cost":3.92},{"min_qty":36,"cost":3.42},{"min_qty":48,"cost":3.12},{"min_qty":72,"cost":2.36},{"min_qty":90,"cost":2.28},{"min_qty":144,"cost":1.65},{"min_qty":180,"cost":1.56},{"min_qty":288,"cost":1.32},{"min_qty":360,"cost":1.25},{"min_qty":576,"cost":1.01},{"min_qty":2500,"cost":0.89}]'),

  ('Transfer Express', 'Gang Sheet — Vector, 2 Colors', 'heat applied', 'gang_sheet', 'vector', 2, 'standard',
   '[{"min_qty":6,"cost":13.89},{"min_qty":12,"cost":7.50},{"min_qty":18,"cost":6.67},{"min_qty":24,"cost":4.71},{"min_qty":36,"cost":4.11},{"min_qty":48,"cost":3.75},{"min_qty":72,"cost":2.83},{"min_qty":90,"cost":2.73},{"min_qty":144,"cost":1.98},{"min_qty":180,"cost":1.88},{"min_qty":288,"cost":1.59},{"min_qty":360,"cost":1.50},{"min_qty":576,"cost":1.21},{"min_qty":2500,"cost":1.07}]'),

  ('Transfer Express', 'Gang Sheet — Vector, 3 Colors', 'heat applied', 'gang_sheet', 'vector', 3, 'standard',
   '[{"min_qty":6,"cost":16.20},{"min_qty":12,"cost":8.75},{"min_qty":18,"cost":7.78},{"min_qty":24,"cost":5.49},{"min_qty":36,"cost":4.79},{"min_qty":48,"cost":4.38},{"min_qty":72,"cost":3.30},{"min_qty":90,"cost":3.19},{"min_qty":144,"cost":2.31},{"min_qty":180,"cost":2.19},{"min_qty":288,"cost":1.85},{"min_qty":360,"cost":1.75},{"min_qty":576,"cost":1.42},{"min_qty":2500,"cost":1.25}]'),

  ('Transfer Express', 'Gang Sheet — Vector, 4 Colors', 'heat applied', 'gang_sheet', 'vector', 4, 'standard',
   '[{"min_qty":6,"cost":18.52},{"min_qty":12,"cost":10.00},{"min_qty":18,"cost":8.89},{"min_qty":24,"cost":6.27},{"min_qty":36,"cost":5.48},{"min_qty":48,"cost":5.00},{"min_qty":72,"cost":3.78},{"min_qty":90,"cost":3.65},{"min_qty":144,"cost":2.64},{"min_qty":180,"cost":2.50},{"min_qty":288,"cost":2.12},{"min_qty":360,"cost":2.00},{"min_qty":576,"cost":1.62},{"min_qty":2500,"cost":1.43}]');

-- ============================================================================
-- Transfer Express — Gang Sheets — Non-Vector artwork
-- ============================================================================

INSERT INTO vendor_price_tables (vendor, name, decoration_type, category, artwork_type, colors, sheet_size, tiers) VALUES
  ('Transfer Express', 'Gang Sheet — Non-Vector, 1 Color', 'heat applied', 'gang_sheet', 'non_vector', 1, 'standard',
   '[{"min_qty":6,"cost":13.89},{"min_qty":12,"cost":7.50},{"min_qty":18,"cost":6.67},{"min_qty":24,"cost":4.71},{"min_qty":36,"cost":4.11},{"min_qty":48,"cost":3.75},{"min_qty":72,"cost":2.83},{"min_qty":90,"cost":2.73},{"min_qty":144,"cost":1.98},{"min_qty":180,"cost":1.88},{"min_qty":288,"cost":1.59},{"min_qty":360,"cost":1.50},{"min_qty":576,"cost":1.21},{"min_qty":2500,"cost":1.07}]'),

  ('Transfer Express', 'Gang Sheet — Non-Vector, 2 Colors', 'heat applied', 'gang_sheet', 'non_vector', 2, 'standard',
   '[{"min_qty":6,"cost":16.20},{"min_qty":12,"cost":8.75},{"min_qty":18,"cost":7.78},{"min_qty":24,"cost":5.49},{"min_qty":36,"cost":4.79},{"min_qty":48,"cost":4.38},{"min_qty":72,"cost":3.30},{"min_qty":90,"cost":3.19},{"min_qty":144,"cost":2.31},{"min_qty":180,"cost":2.19},{"min_qty":288,"cost":1.85},{"min_qty":360,"cost":1.75},{"min_qty":576,"cost":1.42},{"min_qty":2500,"cost":1.25}]'),

  ('Transfer Express', 'Gang Sheet — Non-Vector, 3 Colors', 'heat applied', 'gang_sheet', 'non_vector', 3, 'standard',
   '[{"min_qty":6,"cost":18.52},{"min_qty":12,"cost":10.00},{"min_qty":18,"cost":8.89},{"min_qty":24,"cost":6.27},{"min_qty":36,"cost":5.48},{"min_qty":48,"cost":5.00},{"min_qty":72,"cost":3.78},{"min_qty":90,"cost":3.65},{"min_qty":144,"cost":2.64},{"min_qty":180,"cost":2.50},{"min_qty":288,"cost":2.12},{"min_qty":360,"cost":2.00},{"min_qty":576,"cost":1.62},{"min_qty":2500,"cost":1.43}]'),

  ('Transfer Express', 'Gang Sheet — Non-Vector, 4 Colors', 'heat applied', 'gang_sheet', 'non_vector', 4, 'standard',
   '[{"min_qty":6,"cost":20.83},{"min_qty":12,"cost":11.25},{"min_qty":18,"cost":10.00},{"min_qty":24,"cost":7.06},{"min_qty":36,"cost":6.16},{"min_qty":48,"cost":5.63},{"min_qty":72,"cost":4.25},{"min_qty":90,"cost":4.10},{"min_qty":144,"cost":2.97},{"min_qty":180,"cost":2.81},{"min_qty":288,"cost":2.38},{"min_qty":360,"cost":2.25},{"min_qty":576,"cost":1.82},{"min_qty":2500,"cost":1.61}]');

-- ============================================================================
-- Transfer Express — UltraColor MAX
-- ============================================================================

INSERT INTO vendor_price_tables (vendor, name, decoration_type, category, sheet_size, tiers) VALUES
  ('Transfer Express', 'UltraColor MAX — Small (12×22)', 'heat applied', 'ultracolor_max', 'small',
   '[{"min_qty":1,"cost":14.25},{"min_qty":10,"cost":13.25},{"min_qty":25,"cost":12.50},{"min_qty":50,"cost":12.00},{"min_qty":100,"cost":11.25},{"min_qty":150,"cost":10.50},{"min_qty":300,"cost":9.50},{"min_qty":500,"cost":8.50}]'),

  ('Transfer Express', 'UltraColor MAX — Large (24×22)', 'heat applied', 'ultracolor_max', 'large',
   '[{"min_qty":1,"cost":28.00},{"min_qty":10,"cost":26.00},{"min_qty":25,"cost":24.50},{"min_qty":50,"cost":23.25},{"min_qty":100,"cost":21.88},{"min_qty":150,"cost":20.50},{"min_qty":300,"cost":18.50},{"min_qty":500,"cost":16.00}]');

-- ============================================================================
-- iDex — Embroidery (2026 price list)
-- ============================================================================

INSERT INTO vendor_price_tables (vendor, name, decoration_type, category, tiers, notes) VALUES
  ('iDex', 'Embroidery 0-4,999 stitches', 'embroidery', '0-4999_stitches',
   '[{"min_qty":1,"cost":6.61},{"min_qty":6,"cost":5.61},{"min_qty":12,"cost":3.97},{"min_qty":24,"cost":3.62},{"min_qty":72,"cost":3.12},{"min_qty":144,"cost":2.87},{"min_qty":601,"cost":2.67},{"min_qty":1201,"cost":2.51}]',
   'Base embroidery tier'),

  ('iDex', 'Embroidery 5,000-7,499 stitches', 'embroidery', '5000-7499_stitches',
   '[{"min_qty":1,"cost":6.86},{"min_qty":6,"cost":5.86},{"min_qty":12,"cost":4.22},{"min_qty":24,"cost":3.87},{"min_qty":72,"cost":3.37},{"min_qty":144,"cost":3.12},{"min_qty":601,"cost":2.92},{"min_qty":1201,"cost":2.76}]',
   NULL),

  ('iDex', 'Embroidery 7,500-9,999 stitches', 'embroidery', '7500-9999_stitches',
   '[{"min_qty":1,"cost":7.11},{"min_qty":6,"cost":6.11},{"min_qty":12,"cost":4.47},{"min_qty":24,"cost":4.12},{"min_qty":72,"cost":3.62},{"min_qty":144,"cost":3.37},{"min_qty":601,"cost":3.17},{"min_qty":1201,"cost":3.01}]',
   NULL),

  ('iDex', 'Embroidery 10,000-12,500 stitches', 'embroidery', '10000-12500_stitches',
   '[{"min_qty":1,"cost":7.36},{"min_qty":6,"cost":6.36},{"min_qty":12,"cost":4.72},{"min_qty":24,"cost":4.37},{"min_qty":72,"cost":3.87},{"min_qty":144,"cost":3.62},{"min_qty":601,"cost":3.42},{"min_qty":1201,"cost":3.26}]',
   NULL),

  ('iDex', 'Embroidery 12,501-14,999 stitches', 'embroidery', '12501-14999_stitches',
   '[{"min_qty":1,"cost":7.61},{"min_qty":6,"cost":6.61},{"min_qty":12,"cost":4.97},{"min_qty":24,"cost":4.62},{"min_qty":72,"cost":4.12},{"min_qty":144,"cost":3.87},{"min_qty":601,"cost":3.67},{"min_qty":1201,"cost":3.51}]',
   NULL);

-- ============================================================================
-- iDex — Screen Printing (2026)
-- ============================================================================

INSERT INTO vendor_price_tables (vendor, name, decoration_type, category, colors, tiers, notes) VALUES
  ('iDex', 'Screen Print 1 color', 'screen print', 'screen_print', 1,
   '[{"min_qty":72,"cost":1.26},{"min_qty":144,"cost":1.23},{"min_qty":288,"cost":1.18},{"min_qty":577,"cost":1.03},{"min_qty":1000,"cost":0.88},{"min_qty":2500,"cost":0.76},{"min_qty":5000,"cost":0.71}]',
   'Min 72 pcs. Screen charge $20/color.'),

  ('iDex', 'Screen Print 2 colors', 'screen print', 'screen_print', 2,
   '[{"min_qty":72,"cost":1.48},{"min_qty":144,"cost":1.33},{"min_qty":288,"cost":1.23},{"min_qty":577,"cost":1.08},{"min_qty":1000,"cost":0.93},{"min_qty":2500,"cost":0.81},{"min_qty":5000,"cost":0.76}]',
   NULL),

  ('iDex', 'Screen Print 3 colors', 'screen print', 'screen_print', 3,
   '[{"min_qty":72,"cost":1.63},{"min_qty":144,"cost":1.43},{"min_qty":288,"cost":1.28},{"min_qty":577,"cost":1.13},{"min_qty":1000,"cost":0.98},{"min_qty":2500,"cost":0.86},{"min_qty":5000,"cost":0.81}]',
   NULL),

  ('iDex', 'Screen Print 4 colors', 'screen print', 'screen_print', 4,
   '[{"min_qty":72,"cost":1.83},{"min_qty":144,"cost":1.53},{"min_qty":288,"cost":1.33},{"min_qty":577,"cost":1.23},{"min_qty":1000,"cost":1.13},{"min_qty":2500,"cost":1.01},{"min_qty":5000,"cost":0.96}]',
   NULL),

  ('iDex', 'Screen Print 5 colors', 'screen print', 'screen_print', 5,
   '[{"min_qty":72,"cost":2.08},{"min_qty":144,"cost":1.63},{"min_qty":288,"cost":1.43},{"min_qty":577,"cost":1.23},{"min_qty":1000,"cost":1.18},{"min_qty":2500,"cost":1.06},{"min_qty":5000,"cost":1.01}]',
   NULL),

  ('iDex', 'Screen Print 6 colors', 'screen print', 'screen_print', 6,
   '[{"min_qty":72,"cost":2.33},{"min_qty":144,"cost":1.73},{"min_qty":288,"cost":1.53},{"min_qty":577,"cost":1.38},{"min_qty":1000,"cost":1.23},{"min_qty":2500,"cost":1.11},{"min_qty":5000,"cost":1.06}]',
   NULL),

  ('iDex', 'Screen Print 7 colors', 'screen print', 'screen_print', 7,
   '[{"min_qty":72,"cost":2.48},{"min_qty":144,"cost":1.83},{"min_qty":288,"cost":1.63},{"min_qty":577,"cost":1.43},{"min_qty":1000,"cost":1.28},{"min_qty":2500,"cost":1.16},{"min_qty":5000,"cost":1.11}]',
   NULL),

  ('iDex', 'Screen Print 8 colors', 'screen print', 'screen_print', 8,
   '[{"min_qty":72,"cost":2.63},{"min_qty":144,"cost":1.93},{"min_qty":288,"cost":1.73},{"min_qty":577,"cost":1.48},{"min_qty":1000,"cost":1.33},{"min_qty":2500,"cost":1.21},{"min_qty":5000,"cost":1.16}]',
   NULL);

-- ============================================================================
-- iDex — DTF Printing (2026)
-- ============================================================================

INSERT INTO vendor_price_tables (vendor, name, decoration_type, category, sheet_size, tiers, notes) VALUES
  ('iDex', 'DTF Small (4.5×4.5)', 'dtf', 'dtf', 'small',
   '[{"min_qty":6,"cost":5.40},{"min_qty":12,"cost":4.90},{"min_qty":24,"cost":4.15},{"min_qty":48,"cost":3.90},{"min_qty":96,"cost":3.40},{"min_qty":144,"cost":2.90}]',
   '$15 setup per order'),

  ('iDex', 'DTF Large (11×11)', 'dtf', 'dtf', 'large',
   '[{"min_qty":6,"cost":6.65},{"min_qty":12,"cost":6.15},{"min_qty":24,"cost":5.40},{"min_qty":48,"cost":5.15},{"min_qty":96,"cost":4.90},{"min_qty":144,"cost":4.65}]',
   '$15 setup per order');

-- NOTE: Decoration surcharges are in seed.sql (they reference product_categories which are seeded there)
