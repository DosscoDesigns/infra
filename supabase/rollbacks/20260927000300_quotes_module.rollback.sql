-- ROLLBACK for 20260927000300_quotes_module.sql. Restores prod's pre-quote definitions of
-- inventory_reserved_recompute and v_decoration_transfer_stock, captured from prod with
-- pg_get_functiondef / pg_get_viewdef immediately before applying (2026-09-26), and removes
-- the quote objects. DESTROYS any quote data — only safe before quotes are in use.
BEGIN;
DROP TRIGGER IF EXISTS trg_orders_quote_number ON orders;
DROP FUNCTION IF EXISTS trg_orders_quote_number_fn();
DROP TABLE IF EXISTS quote_versions, order_mockups, order_shipments;
ALTER TABLE orders
  DROP COLUMN IF EXISTS job_name, DROP COLUMN IF EXISTS quote_number, DROP COLUMN IF EXISTS quote_version,
  DROP COLUMN IF EXISTS quote_published_at, DROP COLUMN IF EXISTS approved_at, DROP COLUMN IF EXISTS approved_by,
  DROP COLUMN IF EXISTS approved_name, DROP COLUMN IF EXISTS invoice_memo, DROP COLUMN IF EXISTS bill_email,
  DROP COLUMN IF EXISTS shipping_rate, DROP COLUMN IF EXISTS shipping_quoted;
DROP SEQUENCE IF EXISTS quote_number_seq;
-- pre-quote prod definition:
CREATE OR REPLACE FUNCTION public.inventory_reserved_recompute(p_variant_id uuid)
 RETURNS integer
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_want   int;
  v_inv_id uuid;
BEGIN
  IF p_variant_id IS NULL THEN
    RETURN NULL;
  END IF;

  -- The one true answer: open, undecorated, non-defect demand for this variant.
  SELECT COALESCE(sum(oi.qty), 0)
    INTO v_want
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
   WHERE oi.variant_id = p_variant_id
     AND NOT COALESCE(oi.decorated, false)
     AND NOT COALESCE(oi.defect, false)
     AND o.status NOT IN ('Completed', 'Delivered', 'Cancelled');

  SELECT id INTO v_inv_id
    FROM inventory
   WHERE variant_id = p_variant_id
     AND inventory_type = 'blank'
     AND org_id IS NULL
   LIMIT 1
   FOR UPDATE;

  IF v_inv_id IS NULL THEN
    -- Only materialise a stock row when something actually needs reserving.
    -- (The old adjust() created one on any non-zero delta, littering the
    -- inventory table with empty rows.)
    IF v_want > 0 THEN
      INSERT INTO inventory (
        variant_id, org_id, inventory_type, purpose, is_decorated,
        qty_on_hand, qty_on_order, reserved_qty, last_counted
      ) VALUES (
        p_variant_id, NULL, 'blank', 'stock', false,
        0, 0, v_want, current_date
      );
    END IF;
    RETURN v_want;
  END IF;

  UPDATE inventory
     SET reserved_qty = v_want,
         updated_at   = now()
   WHERE id = v_inv_id
     AND COALESCE(reserved_qty, 0) IS DISTINCT FROM v_want;   -- no-op stays a no-op

  RETURN v_want;
END;
$function$

;
CREATE OR REPLACE VIEW public.v_decoration_transfer_stock WITH (security_invoker = true) AS
 SELECT d.id AS decoration_id,
    i.id AS inventory_id,
    i.id IS NOT NULL AS tracked,
    COALESCE(i.qty_on_hand, 0) AS qty_on_hand,
    COALESCE(i.qty_on_order, 0) AS qty_on_order,
    COALESCE(dem.committed_qty, 0) AS committed_qty,
    COALESCE(i.qty_on_hand, 0) - COALESCE(dem.committed_qty, 0) AS available_qty,
    COALESCE(i.reorder_point, 0) AS reorder_point,
    i.box_id,
    b.box_number,
    b.label AS box_label,
    b.parent_box_id,
    i.last_counted
   FROM decorations d
     LEFT JOIN inventory i ON i.decoration_id = d.id AND i.inventory_type = 'transfer'::text
     LEFT JOIN boxes b ON b.id = i.box_id
     LEFT JOIN LATERAL ( SELECT sum(oi.qty * COALESCE(dsi.qty_per_garment, 1))::integer AS committed_qty
           FROM order_items oi
             JOIN orders o ON o.id = oi.order_id
             JOIN decoration_set_items dsi ON dsi.decoration_set_id = oi.decoration_set_id
          WHERE dsi.decoration_id = d.id AND NOT COALESCE(oi.decorated, false) AND NOT COALESCE(oi.defect, false) AND (o.status <> ALL (ARRAY['Completed'::text, 'Delivered'::text, 'Cancelled'::text]))) dem ON true;
COMMIT;
