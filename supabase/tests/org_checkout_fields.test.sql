-- dd#120 checks for 20261013000000_org_checkout_fields. Runs in one transaction, rolled back.
--   psql "$DB" -v ON_ERROR_STOP=1 -f supabase/tests/org_checkout_fields.test.sql
-- Needs: orgs RCC + SJCA, at least one product variant. Prints PASS lines; any failure aborts.
BEGIN;
CREATE TEMP TABLE t_ctx AS
SELECT (SELECT id FROM orgs WHERE org_code = 'RCC')  AS rcc,
       (SELECT id FROM orgs WHERE org_code = 'SJCA') AS sjca,
       (SELECT v.id FROM variants v JOIN products p ON p.id = v.product_id LIMIT 1) AS variant,
       (SELECT v.product_id FROM variants v JOIN products p ON p.id = v.product_id LIMIT 1) AS product;
INSERT INTO customers (customer_type, first_name, last_name, email)
VALUES ('Individual', 'Test', 'Checkout120', 'zz-120@example.test');
CREATE TEMP TABLE t_cust AS SELECT id FROM customers WHERE email = 'zz-120@example.test';

CREATE FUNCTION pg_temp.place(p_org uuid, p_fields jsonb) RETURNS jsonb LANGUAGE sql AS $$
  SELECT store_create_pending_order(
    jsonb_build_object('customer_id', (SELECT id FROM t_cust), 'org_id', p_org,
                       'payment_method', 'square-online', 'delivery_method', 'Event Delivery',
                       'discount_value', 0, 'notes', 't120') ||
    CASE WHEN p_fields IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('custom_fields', p_fields) END,
    jsonb_build_array(jsonb_build_object('product_id', (SELECT product FROM t_ctx),
                      'variant_id', (SELECT variant FROM t_ctx), 'qty', 1, 'unit_price', 13)))
$$;
-- Place, then read the row back in a NEW statement (a single SQL statement can't see its own insert).
CREATE FUNCTION pg_temp.placed_fields(p_org uuid, p_fields jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_id uuid; v jsonb;
BEGIN
  v_id := (pg_temp.place(p_org, p_fields)->>'order_id')::uuid;
  SELECT custom_fields INTO v FROM orders WHERE id = v_id;
  RETURN v;
END $$;
CREATE FUNCTION pg_temp.expect_error(p_sql text, p_like text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  EXECUTE p_sql;
  RAISE EXCEPTION 'FAIL: expected error like % from: %', p_like, p_sql;
EXCEPTION WHEN OTHERS THEN
  IF SQLERRM LIKE 'FAIL:%' THEN RAISE; END IF;
  IF SQLERRM NOT LIKE p_like THEN RAISE EXCEPTION 'FAIL: got "%" , wanted %', SQLERRM, p_like; END IF;
  RAISE NOTICE 'PASS: rejected with %', SQLERRM;
END $$;
CREATE FUNCTION pg_temp.ok(p bool, p_msg text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN IF p IS NOT TRUE THEN RAISE EXCEPTION 'FAIL: %', p_msg; END IF; RAISE NOTICE 'PASS: %', p_msg; END $$;

-- 1. RCC regression: no config -> '{}' stored, with or without custom_fields sent.
SELECT pg_temp.ok((SELECT count(*) FROM org_checkout_fields WHERE org_id = (SELECT rcc FROM t_ctx)) = 0, 'RCC has no checkout config');
SELECT pg_temp.ok(pg_temp.placed_fields((SELECT rcc FROM t_ctx), NULL) = '{}'::jsonb,
  'RCC order without custom_fields stores {} (as before)');
SELECT pg_temp.ok(pg_temp.placed_fields((SELECT rcc FROM t_ctx), '{"student_name":"x"}') = '{}'::jsonb,
  'RCC drops keys it has no config for');

-- 2. SJCA with teacher (required), student (required), allergy (optional), retired (inactive).
INSERT INTO org_checkout_fields (org_id, field_key, label, required, sort_order, active)
SELECT sjca, k, l, r, s, a FROM t_ctx, (VALUES
  ('teacher_name', 'Teacher name', true, 1, true),
  ('student_name', 'Student name', true, 2, true),
  ('allergy', 'Notes for the teacher', false, 3, true),
  ('homeroom', 'Homeroom', true, 4, false)) v(k, l, r, s, a);

SELECT pg_temp.expect_error($q$SELECT pg_temp.place((SELECT sjca FROM t_ctx), NULL)$q$, 'checkout_field_required: Teacher name');
SELECT pg_temp.expect_error($q$SELECT pg_temp.place((SELECT sjca FROM t_ctx), '{"teacher_name":"Ms. A","student_name":"   "}')$q$, 'checkout_field_required: Student name');
SELECT pg_temp.expect_error($q$SELECT pg_temp.place((SELECT sjca FROM t_ctx), jsonb_build_object('teacher_name', repeat('x', 201), 'student_name', 'S'))$q$, 'checkout_field_too_long: Teacher name');
SELECT pg_temp.expect_error($q$SELECT pg_temp.place((SELECT sjca FROM t_ctx), '["a"]')$q$, 'checkout_field_invalid:%');
SELECT pg_temp.ok(NOT EXISTS (SELECT 1 FROM orders WHERE customer_id = (SELECT id FROM t_cust) AND org_id = (SELECT sjca FROM t_ctx)),
  'rejected SJCA checkouts wrote no order');

SELECT pg_temp.ok(pg_temp.placed_fields((SELECT sjca FROM t_ctx),
    '{"teacher_name":"  Ms. Avery ","student_name":"Sam","allergy":"","homeroom":"4B","evil":"x"}')
  = '{"teacher_name":"Ms. Avery","student_name":"Sam"}'::jsonb,
  'SJCA stores trimmed required values; drops empty optional, inactive and unknown keys');

-- 3. Finalize carries the values through.
SELECT store_finalize_order_paid(id, '{"amount":13}') FROM orders WHERE customer_id = (SELECT id FROM t_cust) AND org_id = (SELECT sjca FROM t_ctx);
SELECT pg_temp.ok((SELECT status = 'Paid' AND custom_fields->>'student_name' = 'Sam' FROM orders
  WHERE customer_id = (SELECT id FROM t_cust) AND org_id = (SELECT sjca FROM t_ctx)), 'finalize keeps custom_fields');

-- 4. Config guards + grants.
SELECT pg_temp.expect_error($q$INSERT INTO org_checkout_fields (org_id, field_key, label) SELECT sjca, 'Bad Key', 'x' FROM t_ctx$q$, '%org_checkout_fields_field_key_check%');
SELECT pg_temp.expect_error($q$INSERT INTO org_checkout_fields (org_id, field_key, label) SELECT sjca, 'teacher_name', 'dup' FROM t_ctx$q$, '%duplicate key%');
SELECT pg_temp.ok(NOT has_table_privilege('anon', 'org_checkout_fields', 'SELECT') AND NOT has_table_privilege('authenticated', 'org_checkout_fields', 'SELECT'),
  'anon/authenticated cannot read org_checkout_fields');
SELECT pg_temp.ok(NOT has_function_privilege('anon', 'store_create_pending_order(jsonb,jsonb)', 'EXECUTE')
              AND NOT has_function_privilege('anon', 'store_finalize_order_paid(uuid,jsonb)', 'EXECUTE')
              AND NOT has_function_privilege('authenticated', 'store_prune_abandoned_orders(integer)', 'EXECUTE')
              AND has_function_privilege('service_role', 'store_create_pending_order(jsonb,jsonb)', 'EXECUTE'),
  'store_* RPCs: service_role only');
ROLLBACK;
