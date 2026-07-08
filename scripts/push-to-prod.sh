#!/usr/bin/env bash
# Push local DB data to production Supabase via supabase db query
# Usage: ./scripts/push-to-prod.sh <dump-dir>
#
# Requires SUPABASE_ACCESS_TOKEN and project linked via supabase link

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

PSQL_LOCAL="psql -h localhost -p 55322 -U postgres -d postgres -tAq"
export PGPASSWORD=postgres

echo "Pushing data to production Supabase..."
echo "Source: ${DUMP_DIR}"
echo ""

# Read table list
mapfile -t TABLES < "$DUMP_DIR/_tables.txt"

# Disable FK checks
supabase db query "SET session_replication_role = 'replica';" --linked 2>/dev/null

# Truncate all tables in reverse order
echo "Truncating prod tables..."
TRUNCATE_SQL=""
for (( i=${#TABLES[@]}-1; i>=0; i-- )); do
  TRUNCATE_SQL+="TRUNCATE TABLE ${TABLES[$i]} CASCADE; "
done
supabase db query "$TRUNCATE_SQL" --linked 2>/dev/null

# For each table, generate INSERT statements from CSV and push
for table in "${TABLES[@]}"; do
  CSV_FILE="${DUMP_DIR}/${table}.csv"
  if [ ! -f "$CSV_FILE" ]; then
    continue
  fi

  LINES=$(( $(wc -l < "$CSV_FILE") - 1 ))
  if [ "$LINES" -le 0 ]; then
    continue
  fi

  printf "  %-25s %6s rows ... " "$table" "$LINES"

  # Get column names from CSV header
  HEADER=$(head -1 "$CSV_FILE")

  # Use COPY via local psql to generate INSERT statements, then push
  # Create a temp table approach: generate SQL from the CSV
  # For large tables, batch in chunks

  # Generate INSERT SQL from CSV using Python (handles quoting, NULLs, etc.)
  python3 -c "
import csv, sys, io

table = '${table}'
with open('${CSV_FILE}', 'r') as f:
    reader = csv.DictReader(f)
    cols = reader.fieldnames
    col_list = ', '.join(cols)

    batch = []
    batch_size = 100
    batch_num = 0

    for row in reader:
        values = []
        for col in cols:
            v = row[col]
            if v == '' or v is None:
                values.append('NULL')
            elif v.lower() in ('true', 'false'):
                values.append(v.lower())
            else:
                # Escape single quotes
                v = v.replace(\"'\", \"''\")
                values.append(f\"'{v}'\")
        batch.append(f'({', '.join(values)})')

        if len(batch) >= batch_size:
            print(f'INSERT INTO {table} ({col_list}) VALUES')
            print(',\n'.join(batch) + ';')
            batch = []
            batch_num += 1

    if batch:
        print(f'INSERT INTO {table} ({col_list}) VALUES')
        print(',\n'.join(batch) + ';')
" > /tmp/dd_push_${table}.sql 2>&1

  # Push via supabase db query (split large files)
  FILESIZE=$(wc -c < "/tmp/dd_push_${table}.sql" | tr -d ' ')

  if [ "$FILESIZE" -gt 0 ]; then
    # supabase db query has a size limit, so split if needed
    if [ "$FILESIZE" -gt 500000 ]; then
      # Split into chunks and push each
      split -l 500 "/tmp/dd_push_${table}.sql" "/tmp/dd_chunk_${table}_"
      for chunk in /tmp/dd_chunk_${table}_*; do
        supabase db query "$(cat "$chunk")" --linked 2>/dev/null
      done
      rm -f /tmp/dd_chunk_${table}_*
    else
      supabase db query "$(cat /tmp/dd_push_${table}.sql)" --linked 2>/dev/null
    fi
    echo "done"
  else
    echo "skip (empty)"
  fi

  rm -f "/tmp/dd_push_${table}.sql"
done

# Re-enable FK checks
supabase db query "SET session_replication_role = 'origin';" --linked 2>/dev/null

# Re-run Spring 2026 price rules (they depend on orgs/events being present)
echo ""
echo "Re-running Spring 2026 price rules migration..."
supabase db query "$(cat supabase/migrations/20260416000003_rcc_spring_2026_gear_sale.sql)" --linked 2>/dev/null

echo ""
echo "Verifying row counts..."
for table in "${TABLES[@]}"; do
  CSV_FILE="${DUMP_DIR}/${table}.csv"
  if [ ! -f "$CSV_FILE" ]; then continue; fi
  LOCAL=$(( $(wc -l < "$CSV_FILE") - 1 ))
  PROD=$(supabase db query "SELECT count(*) FROM ${table}" --linked 2>/dev/null | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['rows'][0]['count'])" 2>/dev/null || echo "?")
  MATCH=$([ "$LOCAL" = "$PROD" ] && echo "✓" || echo "✗")
  printf "  %s %-25s local=%-6s prod=%-6s\n" "$MATCH" "$table" "$LOCAL" "$PROD"
done

echo ""
echo "Done."
