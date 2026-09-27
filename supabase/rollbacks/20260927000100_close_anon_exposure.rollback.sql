-- ROLLBACK for 20260927000100_close_anon_exposure.sql. Restores the prior (insecure) state.
-- Only for an emergency where the fix broke something; never auto-applied.
BEGIN;
ALTER VIEW public.v_orders                    RESET (security_invoker);
ALTER VIEW public.order_messaging_state       RESET (security_invoker);
ALTER VIEW public.v_decoration_transfer_stock RESET (security_invoker);
ALTER VIEW public.v_products                  RESET (security_invoker);
GRANT ALL ON public.v_orders, public.order_messaging_state, public.v_decoration_transfer_stock TO anon, authenticated;
DROP POLICY IF EXISTS "Public read vendors"             ON public.vendors;
DROP POLICY IF EXISTS "Public read vendor_product_refs" ON public.vendor_product_refs;
DROP POLICY IF EXISTS "Public read vendor_variant_refs" ON public.vendor_variant_refs;
DROP POLICY IF EXISTS "Public read category_mappings"   ON public.category_mappings;
CREATE POLICY "Service role full access" ON public.vendors             FOR ALL USING (true);
CREATE POLICY "Service role full access" ON public.vendor_product_refs FOR ALL USING (true);
CREATE POLICY "Service role full access" ON public.vendor_variant_refs FOR ALL USING (true);
CREATE POLICY "Service role full access" ON public.category_mappings   FOR ALL USING (true);
GRANT INSERT, UPDATE, DELETE, TRUNCATE
  ON public.vendors, public.vendor_product_refs, public.vendor_variant_refs, public.category_mappings
  TO anon, authenticated;
GRANT TRUNCATE ON ALL TABLES IN SCHEMA public TO anon, authenticated;
COMMIT;
