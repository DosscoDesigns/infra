#!/usr/bin/env bash
# Dump local Supabase DB data for backup/restore
# Usage: ./scripts/dump-local.sh [output-dir]
#
# Uses COPY CSV to avoid pg_dump version mismatch.
# Restore with: ./scripts/restore-local.sh <dump-dir>

set -euo pipefail

OUTPUT_DIR="${1:-supabase/seed-data}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DUMP_DIR="${OUTPUT_DIR}/${TIMESTAMP}"

DB_HOST=localhost
DB_PORT=55322
DB_USER=postgres
DB_NAME=postgres
export PGPASSWORD=postgres

PSQL="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -tAq"

# Tables in dependency order
TABLES=(
  orgs suppliers product_categories products variants customers events
  decorations decoration_sets decoration_set_items
  price_rules price_rule_products org_products
  orders order_item_batches order_items payments
  inventory pricing_config tax_config sync_state airtable_id_map
  vendor_price_tables decoration_surcharges
)

mkdir -p "$DUMP_DIR"

echo "Dumping local DB to ${DUMP_DIR}/"

for table in "${TABLES[@]}"; do
  COUNT=$($PSQL -c "SELECT count(*) FROM ${table}" 2>/dev/null || echo "0")

  if [ "$COUNT" -gt 0 ] 2>/dev/null; then
    $PSQL -c "COPY ${table} TO STDOUT WITH (FORMAT csv, HEADER true, NULL '')" > "${DUMP_DIR}/${table}.csv" 2>/dev/null
    printf "  %-25s %6s rows\n" "$table" "$COUNT"
  fi
done

# Save table list for restore order
printf '%s\n' "${TABLES[@]}" > "${DUMP_DIR}/_tables.txt"

echo ""
TOTAL=$(du -sh "$DUMP_DIR" | cut -f1)
echo "Done: ${DUMP_DIR}/ (${TOTAL})"
echo "Restore: ./scripts/restore-local.sh ${DUMP_DIR}"
