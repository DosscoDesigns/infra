-- 20260927010000_transfer_adjust_skip_flag_and_multiplier.sql
-- DosscoDesigns/dd #124 (+ a regression found alongside). Authored by the dd-admin nightly
-- (brief: dd origin/handoff/dd-admin:docs/_handoff/brief-124-transfer-adjust.sql); reviewed,
-- tested and applied by JARVIS-dd, which owns migrations.
--
-- (A) #124: a heat-transfer set with no mapped heat-transfer design updated 0 rows and wrote
--     NOTHING, so un-deducted transfers were invisible. Now it writes a flagged
--     inventory_movements row (reason 'transfer_skipped:<reason>', delta 0).
-- (B) regression: 20260824's 4-arg version (the one the app calls) dropped 20260809's
--     qty_per_garment multiplier, so a two-transfer design deducted 1. Restored.
--
-- Both bugs REPRODUCED on the prior prod definition before this was applied (2026-09-27,
-- prod-faithful local copy): qty 2 -> -1; unmapped set -> 0 ledger rows.
-- Tested after: unmapped -> 0 + 1 flagged row; embroidery -> silent; mapped -> -1 logged;
-- qty 2 -> -2; undo nets 0; delta 0 -> early exit; ctx cleared. Return contract unchanged.
--
-- NOT changed, deliberately: inventory_transfer_adjust_decorations. It serves the editable
-- defect flow, where the user names the exact designs wasted with no set context, so a set's
-- qty_per_garment does not apply. (It takes ids not counts — an app-side question, flagged.)
-- The 2-arg overload the brief suggested dropping does NOT exist on prod.
-- Rollback: supabase/rollbacks/20260927010000_transfer_adjust_skip_flag_and_multiplier.rollback.sql
CREATE OR REPLACE FUNCTION public.inventory_transfer_adjust(
  p_decoration_set_id uuid, p_delta integer,
  p_reason text DEFAULT NULL::text, p_source_id uuid DEFAULT NULL::uuid)
RETURNS integer
LANGUAGE plpgsql
AS $function$
DECLARE
  v_rows int := 0;
  v_type text;
BEGIN
  IF p_decoration_set_id IS NULL OR p_delta = 0 THEN
    RETURN 0;
  END IF;

  PERFORM inventory_ctx_set(p_reason, p_source_id);

  -- (B) honour qty_per_garment again (restores 20260809's intent on the 4-arg form).
  -- Transfers are NOT clamped at 0: negative on-hand is the honest reprint signal.
  UPDATE inventory i
     SET qty_on_hand = COALESCE(i.qty_on_hand, 0) + p_delta * s.qty_per_garment,
         updated_at  = now()
    FROM (
      SELECT dsi.decoration_id, MAX(dsi.qty_per_garment) AS qty_per_garment
        FROM decoration_set_items dsi
        JOIN decorations d ON d.id = dsi.decoration_id
       WHERE dsi.decoration_set_id = p_decoration_set_id
         AND d.method = 'heat-transfer'
       GROUP BY dsi.decoration_id
    ) s
   WHERE i.inventory_type = 'transfer'
     AND i.decoration_id = s.decoration_id;

  GET DIAGNOSTICS v_rows = ROW_COUNT;

  -- (A) a heat-transfer set that touched nothing is a misconfiguration, not a no-op:
  -- leave a flagged ledger row so skips are countable instead of invisible.
  -- delta 0 / before=after=0: nothing moved; the row IS the signal.
  IF v_rows = 0 THEN
    SELECT decoration_type INTO v_type FROM decoration_sets WHERE id = p_decoration_set_id;
    IF v_type = 'heat-transfer' THEN
      INSERT INTO inventory_movements
        (inventory_type, field, delta, qty_before, qty_after, reason, source_id)
      VALUES
        ('transfer', 'qty_on_hand', 0, 0, 0,
         'transfer_skipped:' || COALESCE(p_reason, 'unspecified'), p_source_id);
    END IF;
  END IF;

  PERFORM inventory_ctx_clear();
  RETURN v_rows;
END;
$function$;
