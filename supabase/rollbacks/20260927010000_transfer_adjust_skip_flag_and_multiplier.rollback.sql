-- ROLLBACK: restores prod's definition as captured immediately before applying (2026-09-27).
CREATE OR REPLACE FUNCTION public.inventory_transfer_adjust(p_decoration_set_id uuid, p_delta integer, p_reason text DEFAULT NULL::text, p_source_id uuid DEFAULT NULL::uuid)
 RETURNS integer
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_rows int := 0;
BEGIN
  IF p_decoration_set_id IS NULL OR p_delta = 0 THEN
    RETURN 0;
  END IF;

  PERFORM inventory_ctx_set(p_reason, p_source_id);

  -- Transfers are NOT clamped at 0: a negative on-hand is a deliberate, honest
  -- signal that you decorated more than you printed and need a reprint.
  UPDATE inventory i
     SET qty_on_hand = COALESCE(i.qty_on_hand, 0) + p_delta,
         updated_at  = now()
   WHERE i.inventory_type = 'transfer'
     AND i.decoration_id IN (
       SELECT dsi.decoration_id
         FROM decoration_set_items dsi
         JOIN decorations d ON d.id = dsi.decoration_id
        WHERE dsi.decoration_set_id = p_decoration_set_id
          AND d.method = 'heat-transfer'
     );

  GET DIAGNOSTICS v_rows = ROW_COUNT;
  PERFORM inventory_ctx_clear();
  RETURN v_rows;
END;
$function$

;
