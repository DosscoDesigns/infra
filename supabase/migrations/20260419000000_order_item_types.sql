-- Support on-hand and custom line items in orders
-- item_type: 'product' (default), 'on_hand', 'custom'
ALTER TABLE order_items ADD COLUMN IF NOT EXISTS item_type TEXT DEFAULT 'product';
ALTER TABLE order_items ADD COLUMN IF NOT EXISTS description TEXT;
