-- ROLLBACK for 20261013000000_org_checkout_fields.sql. Restores the pre-#120
-- store_create_pending_order (captured with pg_get_functiondef on 2026-10-13) and its
-- previous EXECUTE grants, and drops the config table + orders.custom_fields.
-- DESTROYS any captured teacher/student values. Roll the app back first: the #120 worker
-- reads org_checkout_fields and would fail checkout without it.
BEGIN;
CREATE OR REPLACE FUNCTION public.store_create_pending_order(p_order jsonb, p_items jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_order_id uuid;
  v_seq      integer;
  v_item     jsonb;
  v_count    int := 0;
BEGIN
  INSERT INTO orders (
    customer_id, org_id, event_id,
    status, payment_method, delivery_method,
    coupon_code, discount_type, discount_value, notes
  ) VALUES (
    (p_order->>'customer_id')::uuid,
    (p_order->>'org_id')::uuid,
    NULLIF(p_order->>'event_id', '')::uuid,
    'Pending',
    p_order->>'payment_method',
    p_order->>'delivery_method',
    p_order->>'coupon_code',
    p_order->>'discount_type',
    COALESCE((p_order->>'discount_value')::numeric, 0),
    p_order->>'notes'
  )
  RETURNING id, seq INTO v_order_id, v_seq;

  FOR v_item IN SELECT * FROM jsonb_array_elements(p_items)
  LOOP
    INSERT INTO order_items (
      order_id, product_id, variant_id, decoration_set_id,
      qty, unit_price, matched_rule_id, org_cut
    ) VALUES (
      v_order_id,
      NULLIF(v_item->>'product_id', '')::uuid,
      NULLIF(v_item->>'variant_id', '')::uuid,
      NULLIF(v_item->>'decoration_set_id', '')::uuid,
      GREATEST(1, COALESCE((v_item->>'qty')::int, 1)),
      COALESCE((v_item->>'unit_price')::numeric, 0),
      NULLIF(v_item->>'matched_rule_id', '')::uuid,
      COALESCE((v_item->>'org_cut')::numeric, 0)
    );
    v_count := v_count + 1;
  END LOOP;

  IF v_count = 0 THEN
    RAISE EXCEPTION 'store_create_pending_order: no items supplied';
  END IF;

  RETURN jsonb_build_object('order_id', v_order_id, 'seq', v_seq, 'item_count', v_count);
END;
$function$;
GRANT EXECUTE ON FUNCTION public.store_create_pending_order(jsonb, jsonb) TO PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.store_finalize_order_paid(uuid, jsonb) TO PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.store_prune_abandoned_orders(integer) TO PUBLIC, anon, authenticated;
ALTER TABLE public.orders DROP COLUMN IF EXISTS custom_fields;
DROP TABLE IF EXISTS public.org_checkout_fields;
COMMIT;
