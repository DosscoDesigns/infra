-- 20260927000100_close_anon_exposure.sql
-- Security audit, 2026-09-26 (JARVIS-dd, at Jason's request). Closes exposures that were
-- reachable with the PUBLIC anon key — the one embedded in every storefront page.
--
-- Verified live on prod before this was written (count-only, no data pulled):
--   anon GET /orders  -> 0 rows   (table RLS works)
--   anon GET /v_orders -> 479 rows (view bypassed RLS) — first/last name, business, phone,
--                                   notes and PO numbers for every order.
--
-- Nothing in deployed code (origin/main) reads the three private views, writes the four
-- vendor/category tables, or writes storage with the anon key: the admin app uses the
-- service_role key and the worker runs server-side as service_role, both of which bypass
-- RLS. Every read path the code uses is preserved. Rollback:
-- supabase/rollbacks/20260927000100_close_anon_exposure.rollback.sql (outside migrations/, never auto-applied).
--
-- NOT fixed here, and the bigger issue: the admin browser bundle ships VITE_SUPABASE_SERVICE_ROLE
-- (dd PR #117). While that is live, anyone holding the bundle bypasses all of this.

BEGIN;

-- 1. VIEWS. Views run as their owner by default and so ignored the callers' RLS.
ALTER VIEW public.v_orders                    SET (security_invoker = true);
ALTER VIEW public.order_messaging_state       SET (security_invoker = true);
ALTER VIEW public.v_decoration_transfer_stock SET (security_invoker = true);
ALTER VIEW public.v_products                  SET (security_invoker = true);
-- Private views: no client role reads them at all (admin/worker are service_role).
REVOKE ALL ON public.v_orders, public.order_messaging_state, public.v_decoration_transfer_stock
  FROM anon, authenticated;

-- 2. Four policies NAMED "Service role full access" were FOR ALL USING (true) TO public, and
--    anon held INSERT/UPDATE/DELETE — so anyone could rewrite or empty the SanMar SKU mapping.
--    service_role bypasses RLS and never needed a policy. Reads are kept to avoid breaking any
--    client read path; writes are closed twice (policy AND grant).
DROP POLICY IF EXISTS "Service role full access" ON public.vendors;
DROP POLICY IF EXISTS "Service role full access" ON public.vendor_product_refs;
DROP POLICY IF EXISTS "Service role full access" ON public.vendor_variant_refs;
DROP POLICY IF EXISTS "Service role full access" ON public.category_mappings;
DROP POLICY IF EXISTS "Public read vendors" ON public.vendors;
CREATE POLICY "Public read vendors"             ON public.vendors             FOR SELECT USING (true);
DROP POLICY IF EXISTS "Public read vendor_product_refs" ON public.vendor_product_refs;
CREATE POLICY "Public read vendor_product_refs" ON public.vendor_product_refs FOR SELECT USING (true);
DROP POLICY IF EXISTS "Public read vendor_variant_refs" ON public.vendor_variant_refs;
CREATE POLICY "Public read vendor_variant_refs" ON public.vendor_variant_refs FOR SELECT USING (true);
DROP POLICY IF EXISTS "Public read category_mappings" ON public.category_mappings;
CREATE POLICY "Public read category_mappings"   ON public.category_mappings   FOR SELECT USING (true);
REVOKE INSERT, UPDATE, DELETE, TRUNCATE
  ON public.vendors, public.vendor_product_refs, public.vendor_variant_refs, public.category_mappings
  FROM anon, authenticated;

-- 3. TRUNCATE ignores RLS entirely. No client needs it anywhere.
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA public FROM anon, authenticated;

COMMIT;
