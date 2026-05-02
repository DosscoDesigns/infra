-- PO invoice total: actual charged amount for reconciliation against estimated PO total
ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS invoice_total DECIMAL(10,2);
