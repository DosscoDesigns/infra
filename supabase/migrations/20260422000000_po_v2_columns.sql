-- PO v2: decoration type scoping, org/event tracking, shipping costs
-- Enables POs scoped by decoration type and optionally by org/event

-- Decoration type for PO scoping (heat applied vs embroidery vs leather patch)
ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS decoration_type TEXT;

-- Org/event tracking — organizational metadata + embroidery contractor scoping
ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES orgs(id);
ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS event_id UUID REFERENCES events(id);

-- Shipping/handling costs (entered after receiving invoice)
ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS shipping_cost DECIMAL(10,2) DEFAULT 0;
ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS handling_cost DECIMAL(10,2) DEFAULT 0;

-- Indexes for filtered queries
CREATE INDEX IF NOT EXISTS idx_po_decoration_type ON purchase_orders(decoration_type);
CREATE INDEX IF NOT EXISTS idx_po_org ON purchase_orders(org_id);
CREATE INDEX IF NOT EXISTS idx_po_event ON purchase_orders(event_id);
