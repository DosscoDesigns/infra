-- 20260927000300_quotes_module.sql
-- Quote module schema (DosscoDesigns/dd #116), authored by dd-admin; recorded and applied by
-- JARVIS-dd, which owns infra/. Source: dd origin/handoff/dd-admin:docs/_handoff/quotes-schema-brief.sql @ 424c75b.
--
-- ONE CHANGE from the source, made by JARVIS-dd: the CREATE OR REPLACE VIEW for
-- v_decoration_transfer_stock now carries WITH (security_invoker = true). Without it, replacing
-- the view silently RESETS that option (tested 2026-09-26 on a prod-faithful local copy), which
-- would undo part of 20260927000100_close_anon_exposure.sql and put the view back to running as
-- its owner, bypassing RLS.
--
-- Jason's decisions encoded here: the system sends the quote email on publish; approval is a
-- customer link click or Jason marking it approved; an unapproved Quote does NOT reserve stock
-- ('Quote' joins the terminal statuses in inventory_reserved_recompute + the view).
-- BRIEF FOR `dd` (migration owner) — quote module, DosscoDesigns/dd #116
-- Proposed by dd-admin 2026-09-26. NOT applied anywhere. Purely additive:
-- no existing column, function, trigger or view changes.
--
-- Design: a quote is an ORDER STATE (#116 R2) — orders.status = 'Quote'.
-- On approval it becomes 'Processing' and flows into batches like any order
-- (batches only pick Paid/Processing, so an unapproved quote never lands in one).
-- Publishing snapshots an immutable version (R12); mockups attach to the order.

-- 1. Order-level quote fields ------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS quote_number_seq START 1001;

ALTER TABLE orders
  ADD COLUMN IF NOT EXISTS job_name           text,          -- R1, "[FOR APPROVAL] - <job_name>"
  ADD COLUMN IF NOT EXISTS quote_number       integer UNIQUE, -- Q-1001…, own series (QBO owns invoice numbers)
  ADD COLUMN IF NOT EXISTS quote_version      integer NOT NULL DEFAULT 0, -- latest published version, 0 = never published
  ADD COLUMN IF NOT EXISTS quote_published_at timestamptz,
  ADD COLUMN IF NOT EXISTS approved_at        timestamptz,   -- R7
  ADD COLUMN IF NOT EXISTS approved_by        text CHECK (approved_by IN ('customer', 'admin')),
  ADD COLUMN IF NOT EXISTS approved_name      text,          -- who clicked / who Jason recorded
  ADD COLUMN IF NOT EXISTS invoice_memo       text,          -- QBO CustomerMemo (garment + decoration spec)
  ADD COLUMN IF NOT EXISTS bill_email         text,          -- QBO BillEmail; falls back to customers.email
  ADD COLUMN IF NOT EXISTS shipping_rate      numeric(10,2), -- raw Shippo rate at quote time (logged, not charged)
  ADD COLUMN IF NOT EXISTS shipping_quoted    numeric(10,2); -- what the customer is charged = rate + 15% buffer (Jason 09-26)
-- Actual label cost lives per carton on order_shipments (section 4); a bulk job can ship in several boxes.

-- Number a quote the first time it enters 'Quote' — never renumber.
CREATE OR REPLACE FUNCTION trg_orders_quote_number_fn()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status = 'Quote' AND NEW.quote_number IS NULL THEN
    NEW.quote_number := nextval('quote_number_seq');
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_orders_quote_number ON orders;
CREATE TRIGGER trg_orders_quote_number
BEFORE INSERT OR UPDATE OF status ON orders
FOR EACH ROW EXECUTE FUNCTION trg_orders_quote_number_fn();

-- 2. Published versions (R12) -----------------------------------------------
CREATE TABLE IF NOT EXISTS quote_versions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id         uuid NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  version          integer NOT NULL,
  snapshot         jsonb NOT NULL,          -- rendered lines + totals + mockups exactly as sent
  total            numeric(10,2) NOT NULL,
  published_at     timestamptz NOT NULL DEFAULT now(),
  emailed_to       text,
  emailed_at       timestamptz,
  email_suppressed boolean NOT NULL DEFAULT false,  -- published without sending (Ocala pilot)
  superseded_at    timestamptz,
  UNIQUE (order_id, version)
);
CREATE INDEX IF NOT EXISTS quote_versions_order_id_idx ON quote_versions(order_id);

-- 3. Mockups attached to a quote ---------------------------------------------
-- Files go in the existing public `decorations` storage bucket under quotes/.
CREATE TABLE IF NOT EXISTS order_mockups (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id          uuid NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  url               text NOT NULL,
  caption           text,
  decoration_set_id uuid REFERENCES decoration_sets(id) ON DELETE SET NULL, -- when copied from a set's mockup
  sort              integer NOT NULL DEFAULT 0,
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS order_mockups_order_id_idx ON order_mockups(order_id);

-- 4. Shipments (R14/R16) — one row per purchased label / carton ------------------
-- The customer is charged shipping_quoted only. Each label's real cost + PDF is
-- booked in QBO as an Expense attached to the customer (Jason 09-26), so
-- quoted-vs-actual is visible per job and the 15% buffer can be tuned.
CREATE TABLE IF NOT EXISTS order_shipments (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id        uuid NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  carrier         text,
  service         text,
  tracking_number text,
  label_url       text,              -- Shippo label PDF
  label_cost      numeric(10,2),     -- actual purchased cost
  weight_lb       numeric(8,2),
  shippo_transaction_id text,
  qbo_expense_id  text,              -- QBO Purchase Id, CustomerRef = the job's customer
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS order_shipments_order_id_idx ON order_shipments(order_id);

-- 5. RLS — mirrors prod `orders` / `order_items` / `inventory_movements` exactly
-- (read off pg_policies 2026-09-26): RLS on, one policy, service_role only.
-- No `authenticated`/`anon` grants — do not copy Supabase's doc-example policies.
ALTER TABLE quote_versions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_mockups   ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_shipments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role full access" ON quote_versions;
CREATE POLICY "Service role full access" ON quote_versions
  FOR ALL USING (auth.role() = 'service_role');
DROP POLICY IF EXISTS "Service role full access" ON order_mockups;
CREATE POLICY "Service role full access" ON order_mockups
  FOR ALL USING (auth.role() = 'service_role');
DROP POLICY IF EXISTS "Service role full access" ON order_shipments;
CREATE POLICY "Service role full access" ON order_shipments
  FOR ALL USING (auth.role() = 'service_role');

-- 6. An unapproved quote holds NO stock (Jason 2026-09-26: "no").
-- 'Quote' joins the terminal statuses in both demand calculations, so neither blanks
-- (reserved_qty) nor transfers (committed) are held until approval. The existing
-- trg_orders_status_reserved_qty recomputes on Quote→Processing, so demand appears the
-- moment a quote is approved. Both bodies below are the LIVE prod definitions read
-- 2026-09-26 via pg_get_functiondef/pg_get_viewdef with only 'Quote' added. Diff = that token.
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
     AND o.status NOT IN ('Completed', 'Delivered', 'Cancelled', 'Quote');

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
$function$;

CREATE OR REPLACE VIEW v_decoration_transfer_stock WITH (security_invoker = true) AS
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
          WHERE dsi.decoration_id = d.id AND NOT COALESCE(oi.decorated, false) AND NOT COALESCE(oi.defect, false) AND (o.status <> ALL (ARRAY['Completed'::text, 'Delivered'::text, 'Cancelled'::text, 'Quote'::text]))) dem ON true;

-- Recompute any variant currently held by a quote (none in prod today; idempotent).
SELECT inventory_reserved_recompute(oi.variant_id)
  FROM order_items oi JOIN orders o ON o.id = oi.order_id
 WHERE o.status = 'Quote' AND oi.variant_id IS NOT NULL
 GROUP BY oi.variant_id;
