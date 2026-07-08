-- Purchase Order enhancements: linking columns + indexes
-- Links order_items to PO lines and adds supplier confirmation tracking

-- Link order_items to PO lines (which PO covers this item's blanks)
ALTER TABLE order_items ADD COLUMN po_line_item_id UUID REFERENCES po_line_items(id);
CREATE INDEX idx_order_items_po_line ON order_items(po_line_item_id);

-- SanMar/vendor confirmation number (manual entry for now)
ALTER TABLE purchase_orders ADD COLUMN supplier_confirmation TEXT;

-- Indexes for PO queries
CREATE INDEX idx_po_line_items_po ON po_line_items(po_id);
CREATE INDEX idx_po_line_items_variant ON po_line_items(variant_id);
