-- 20261013000000_org_checkout_fields.sql
-- dd#120: per-org custom checkout fields (school clients: teacher + student name).
-- Design signed off by JARVIS-dd 2026-10-13 (Jason, Hub dd D7: "build 120 ASAP").
--
--   * org_checkout_fields: admin-editable config, one row per field per org. No client role
--     can touch it: the admin app reaches it through the worker's /db/rest (service_role,
--     admin-gated) and the storefront through GET /store/checkout-fields?org_code= (worker,
--     service_role, returns ONLY the active fields of the one store being viewed).
--   * orders.custom_fields: the values, on the ORDER (Jason 2026-09-25), {field_key: value}.
--   * store_create_pending_order validates p_order.custom_fields against the org's ACTIVE
--     config: required fields enforced HERE (not only in the dialog), unknown/inactive keys
--     dropped, values trimmed, 200-char cap. An org with no config stores '{}' — exactly as
--     before. store_finalize_order_paid only updates status + payment, so the values carry
--     through untouched (no change needed there).
--   * The migration seeds NO config rows. RPK + SJCA rows ship in the SJCA launch seed
--     (DosscoDesigns/dd scripts/sjca-launch/), run AFTER the app deploy: a required field
--     added before the new checkout is live would 400 every RPK order on the old build.
--
-- Also revokes EXECUTE on the three store_* RPCs from anon/authenticated. They were
-- executable with the public anon key (store_create_pending_order takes unit_price from the
-- caller). Only the worker calls them, as service_role (routes/store.js,
-- lib/pruneAbandonedOrders.js), which keeps its grant.
--
-- Rollback: supabase/rollbacks/20261013000000_org_checkout_fields.rollback.sql

BEGIN;

CREATE TABLE public.org_checkout_fields (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES public.orgs(id) ON DELETE CASCADE,
  field_key   text NOT NULL CHECK (field_key ~ '^[a-z][a-z0-9_]{0,39}$'),
  label       text NOT NULL CHECK (length(btrim(label)) BETWEEN 1 AND 80),
  field_type  text NOT NULL DEFAULT 'text' CHECK (field_type IN ('text')),
  required    boolean NOT NULL DEFAULT false,
  sort_order  integer NOT NULL DEFAULT 0,
  active      boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, field_key)
);
CREATE INDEX org_checkout_fields_org_idx ON public.org_checkout_fields (org_id, sort_order);
CREATE TRIGGER trg_org_checkout_fields_updated_at BEFORE UPDATE ON public.org_checkout_fields
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- RLS on with no policies = no client access. service_role bypasses RLS.
ALTER TABLE public.org_checkout_fields ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.org_checkout_fields FROM anon, authenticated;

ALTER TABLE public.orders
  ADD COLUMN custom_fields jsonb NOT NULL DEFAULT '{}'::jsonb
  CONSTRAINT orders_custom_fields_object CHECK (jsonb_typeof(custom_fields) = 'object');

CREATE OR REPLACE FUNCTION public.store_create_pending_order(p_order jsonb, p_items jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_order_id uuid;
  v_seq      integer;
  v_item     jsonb;
  v_count    int := 0;
  v_org_id   uuid := (p_order->>'org_id')::uuid;
  v_in       jsonb := COALESCE(p_order->'custom_fields', '{}'::jsonb);
  v_fields   jsonb := '{}'::jsonb;
  v_field    record;
  v_val      text;
BEGIN
  IF jsonb_typeof(v_in) <> 'object' THEN
    RAISE EXCEPTION 'checkout_field_invalid: custom_fields must be an object';
  END IF;
  FOR v_field IN
    SELECT field_key, label, required FROM org_checkout_fields
     WHERE org_id = v_org_id AND active ORDER BY sort_order, field_key
  LOOP
    v_val := btrim(COALESCE(v_in->>v_field.field_key, ''));
    IF length(v_val) > 200 THEN
      RAISE EXCEPTION 'checkout_field_too_long: %', v_field.label;
    END IF;
    IF v_field.required AND v_val = '' THEN
      RAISE EXCEPTION 'checkout_field_required: %', v_field.label;
    END IF;
    IF v_val <> '' THEN
      v_fields := v_fields || jsonb_build_object(v_field.field_key, v_val);
    END IF;
  END LOOP;

  INSERT INTO orders (
    customer_id, org_id, event_id,
    status, payment_method, delivery_method,
    coupon_code, discount_type, discount_value, notes, custom_fields
  ) VALUES (
    (p_order->>'customer_id')::uuid,
    v_org_id,
    NULLIF(p_order->>'event_id', '')::uuid,
    'Pending',
    p_order->>'payment_method',
    p_order->>'delivery_method',
    p_order->>'coupon_code',
    p_order->>'discount_type',
    COALESCE((p_order->>'discount_value')::numeric, 0),
    p_order->>'notes',
    v_fields
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

REVOKE EXECUTE ON FUNCTION public.store_create_pending_order(jsonb, jsonb) FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.store_finalize_order_paid(uuid, jsonb) FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.store_prune_abandoned_orders(integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.store_create_pending_order(jsonb, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.store_finalize_order_paid(uuid, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.store_prune_abandoned_orders(integer) TO service_role;

COMMIT;
