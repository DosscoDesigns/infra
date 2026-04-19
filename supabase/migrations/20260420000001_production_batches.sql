-- Production Batches: extend order_item_batches for batch management + decoration tracking

-- Add metadata columns to order_item_batches
ALTER TABLE order_item_batches ADD COLUMN IF NOT EXISTS decoration_set_id UUID REFERENCES decoration_sets(id);
ALTER TABLE order_item_batches ADD COLUMN IF NOT EXISTS decoration_method TEXT;
ALTER TABLE order_item_batches ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES orgs(id);
ALTER TABLE order_item_batches ADD COLUMN IF NOT EXISTS event_id UUID REFERENCES events(id);
ALTER TABLE order_item_batches ADD COLUMN IF NOT EXISTS total_items INTEGER DEFAULT 0;
ALTER TABLE order_item_batches ADD COLUMN IF NOT EXISTS decorated_count INTEGER DEFAULT 0;
ALTER TABLE order_item_batches ADD COLUMN IF NOT EXISTS defect_count INTEGER DEFAULT 0;
ALTER TABLE order_item_batches ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE order_item_batches ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE order_item_batches ADD COLUMN IF NOT EXISTS notes TEXT;

-- Change default status from 'decorating' to 'pending'
ALTER TABLE order_item_batches ALTER COLUMN status SET DEFAULT 'pending';

-- Add defect notes to order_items
ALTER TABLE order_items ADD COLUMN IF NOT EXISTS defect_notes TEXT;

-- Indexes for batch queries
CREATE INDEX IF NOT EXISTS idx_batches_status ON order_item_batches(status);
CREATE INDEX IF NOT EXISTS idx_batches_decoration_set ON order_item_batches(decoration_set_id);
CREATE INDEX IF NOT EXISTS idx_order_items_decorated ON order_items(decorated) WHERE NOT decorated;
CREATE INDEX IF NOT EXISTS idx_order_items_order_batch ON order_items(order_id, batch_id);

-- Recreate v_orders view to include batch info (DROP required — column set changed)
DROP VIEW IF EXISTS v_orders;
CREATE VIEW v_orders AS
SELECT
  o.*,
  c.first_name, c.last_name, c.business_name, c.phone AS customer_phone,
  org.org_code, org.name AS org_name,
  e.event_code, e.name AS event_name,
  count(oi.id) AS item_count,
  sum(oi.qty) AS total_qty,
  count(oi.id) FILTER (WHERE oi.decorated) AS decorated_count,
  count(oi.id) FILTER (WHERE oi.bagged) AS bagged_count,
  count(oi.id) FILTER (WHERE oi.batch_id IS NOT NULL) AS batched_count
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.id
LEFT JOIN orgs org ON o.org_id = org.id
LEFT JOIN events e ON o.event_id = e.id
LEFT JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id, c.id, org.id, e.id;
