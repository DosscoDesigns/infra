-- Add discount fields to orders
ALTER TABLE orders
  ADD COLUMN discount_type TEXT DEFAULT NULL,  -- 'dollar' or 'percent'
  ADD COLUMN discount_value DECIMAL(10,2) DEFAULT 0;
