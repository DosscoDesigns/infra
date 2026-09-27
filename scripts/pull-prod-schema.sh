#!/usr/bin/env bash
# pull-prod-schema.sh — rebuild the LOCAL DD database from PRODUCTION.
#
# Why this exists: prod is the only schema source of truth. Migrations have been
# split across two repos since 2026-08-01 (infra/supabase/migrations stops at
# 07-27; later ones live in dd/supabase/migrations) and prod is applied directly,
# so replaying migration history does NOT reproduce prod. This copies prod's
# `public` schema exactly (tables, functions, triggers, RLS, policies, grants).
#
# Data: catalog/config tables only. `boxes` (physical storage bins — number, label, location;
# FKs only to orgs/events/itself, no PII) IS copied: inventory.box_id references it, and without
# it any test that updates an inventory row twice in one transaction fails its FK re-check.
# Deliberately NOT copied —
#   customer PII:      customers, orders, order_items, payments, messages
#   order-linked rows: order_item_batches, inventory_movements
#   secrets:           integration_tokens (live QBO tokens), app_config
#
# DESTRUCTIVE TO LOCAL ONLY: drops and recreates local `public`. A backup of the
# old local `public` is written to ../TEMP first. Never points at prod for writes:
# prod is only ever the source of a pg_dump (read-only).
#
# Usage:  direnv exec ~/dev/dd infra/scripts/pull-prod-schema.sh
# Needs:  local stack running (supabase start), op signed in (dd.prod.supabase).
set -euo pipefail

REF=bbrpsznwntrhvnobhxkp
PROD="host=aws-1-us-east-1.pooler.supabase.com port=5432 user=postgres.${REF} dbname=postgres sslmode=require"
# In-container addresses (the host sees this DB on 55322). Two roles on purpose:
#  OWNER — restores the schema so every object is owned by `postgres`, exactly as on prod.
#          Ownership decides what SECURITY DEFINER functions run as and who bypasses RLS,
#          so restoring as a superuser would make local behave differently from prod.
#  ADMIN — superuser, needed only to drop/recreate the schema and to load data with
#          triggers off (session_replication_role requires superuser).
OWNER="postgresql://postgres:postgres@127.0.0.1:5432/postgres"
ADMIN="postgresql://supabase_admin:postgres@127.0.0.1:5432/postgres"
LOCAL="$ADMIN"
C=supabase_db_dd                      # use the container's pg_dump: it matches prod's PG 17
OUT="${DD_TEMP:-$HOME/dev/dd/TEMP}/prod-pull-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

KEEP=(boxes category_mappings coupons decoration_set_items decoration_sets decoration_surcharges
      decorations events inventory message_templates org_products orgs po_line_items
      price_rule_products price_rules pricing_config product_categories products
      purchase_orders suppliers tax_config variants vendor_price_tables
      vendor_product_refs vendor_variant_refs vendors)

docker exec "$C" true || { echo "local stack not running: cd infra && supabase start"; exit 1; }
PGPASSWORD="$(op read "op://DEV/dd.prod.supabase/password")"; export PGPASSWORD

echo "1/5 backing up current local public -> $OUT/local-before.sql"
docker exec "$C" pg_dump "$LOCAL" -n public --no-owner > "$OUT/local-before.sql"

echo "2/5 dumping PROD schema (read-only)"
docker exec -e PGPASSWORD "$C" pg_dump "$PROD" -n public --schema-only --no-owner > "$OUT/prod-schema.sql"
# PG17's pg_dump -n public emits its own CREATE SCHEMA; we create it above with prod's owner.
sed -i '' '/^CREATE SCHEMA public;$/d' "$OUT/prod-schema.sql"
# Default-privilege rules for OTHER roles (e.g. FOR ROLE supabase_admin) can only be set by a
# superuser, so they are split out and applied as ADMIN after the owner restore.
grep '^ALTER DEFAULT PRIVILEGES' "$OUT/prod-schema.sql" > "$OUT/prod-default-privs.sql" || true
sed -i '' '/^ALTER DEFAULT PRIVILEGES/d' "$OUT/prod-schema.sql"

echo "3/5 dumping PROD catalog data (${#KEEP[@]} tables, no PII, no secrets)"
T=(); for t in "${KEEP[@]}"; do T+=(-t "public.$t"); done
docker exec -e PGPASSWORD "$C" pg_dump "$PROD" --data-only --no-owner "${T[@]}" > "$OUT/prod-data.sql"
unset PGPASSWORD

echo "4/5 recreating local public from prod schema"
docker exec -i "$C" psql "$LOCAL" -v ON_ERROR_STOP=1 -q <<'SQL'
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
ALTER SCHEMA public OWNER TO pg_database_owner;   -- matches prod
GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON SCHEMA public TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES    TO postgres, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres, anon, authenticated, service_role;
SQL
docker exec -i "$C" psql "$OWNER" -v ON_ERROR_STOP=1 -q < "$OUT/prod-schema.sql"
docker exec -i "$C" psql "$ADMIN" -v ON_ERROR_STOP=1 -q < "$OUT/prod-default-privs.sql"

echo "5/5 loading catalog data (triggers off during load)"
{ echo "SET session_replication_role = replica;"; cat "$OUT/prod-data.sql"; echo "SET session_replication_role = origin;"; } \
  | docker exec -i "$C" psql "$LOCAL" -v ON_ERROR_STOP=1 -q

echo "done. artifacts in $OUT"
docker exec "$C" psql "$LOCAL" -Atc "select 'tables='||count(*) from pg_tables where schemaname='public'"
