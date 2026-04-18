#!/usr/bin/env bash
# Restore local Supabase DB from a CSV dump directory
# Usage: ./scripts/restore-local.sh <dump-dir>
#
# Truncates all tables then restores from CSV files in dependency order.

set -euo pipefail

DUMP_DIR="${1:-}"

if [ -z "$DUMP_DIR" ]; then
  echo "Usage: $0 <dump-dir>"
  echo ""
  echo "Available dumps:"
  ls -1d supabase/seed-data/20*/ 2>/dev/null || echo "  (none found)"
  exit 1
fi

if [ ! -f "$DUMP_DIR/_tables.txt" ]; then
  echo "Error: Not a valid dump directory (missing _tables.txt): ${DUMP_DIR}"
  exit 1
fi

DB_HOST=localhost
DB_PORT=55322
DB_USER=postgres
DB_NAME=postgres
export PGPASSWORD=postgres

PSQL="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -q"

echo "Restoring from: ${DUMP_DIR}"
echo ""

# Disable FK checks
$PSQL -c "SET session_replication_role = 'replica';"

# Read table list
mapfile -t TABLES < "$DUMP_DIR/_tables.txt"

# Truncate all (reverse order)
for (( i=${#TABLES[@]}-1; i>=0; i-- )); do
  $PSQL -c "TRUNCATE TABLE ${TABLES[$i]} CASCADE;" 2>/dev/null || true
done

# Restore each table
for table in "${TABLES[@]}"; do
  CSV_FILE="${DUMP_DIR}/${table}.csv"
  if [ -f "$CSV_FILE" ]; then
    LINES=$(( $(wc -l < "$CSV_FILE") - 1 ))  # subtract header
    $PSQL -c "COPY ${table} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')" < "$CSV_FILE" 2>&1 | grep -v "^$" || true
    printf "  %-25s %6s rows\n" "$table" "$LINES"
  fi
done

# Re-enable FK checks
$PSQL -c "SET session_replication_role = 'origin';"

echo ""
echo "Restore complete."
