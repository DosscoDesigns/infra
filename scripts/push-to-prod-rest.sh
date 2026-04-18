#!/usr/bin/env bash
# Push local DB data to production Supabase via REST API (PostgREST)
# Much faster than supabase db query for large tables
# Usage: ./scripts/push-to-prod-rest.sh <dump-dir>

set -euo pipefail

DUMP_DIR="${1:-}"

if [ -z "$DUMP_DIR" ]; then
  echo "Usage: $0 <dump-dir>"
  ls -1d supabase/seed-data/20*/ 2>/dev/null
  exit 1
fi

[ ! -f "$DUMP_DIR/_tables.txt" ] && echo "Error: invalid dump dir" && exit 1

# Get service role key from Supabase API
SUPABASE_ACCESS_TOKEN="${SUPABASE_ACCESS_TOKEN:-}"
[ -z "$SUPABASE_ACCESS_TOKEN" ] && echo "Error: SUPABASE_ACCESS_TOKEN not set" && exit 1

PROJECT_REF="bbrpsznwntrhvnobhxkp"
API_URL="https://${PROJECT_REF}.supabase.co/rest/v1"

SERVICE_KEY=$(curl -s -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  "https://api.supabase.com/v1/projects/${PROJECT_REF}/api-keys" | \
  python3 -c "import sys,json; [print(k['api_key']) for k in json.loads(sys.stdin.read()) if k['name']=='service_role']")

if [ -z "$SERVICE_KEY" ]; then
  echo "Error: Could not get service_role key"
  exit 1
fi

echo "Pushing to prod via REST API..."
echo "Source: ${DUMP_DIR}"
echo ""

mapfile -t TABLES < "$DUMP_DIR/_tables.txt"

# Truncate via supabase db query (REST API can't truncate)
echo "Truncating prod tables..."
TRUNCATE_SQL="SET session_replication_role = 'replica'; "
for (( i=${#TABLES[@]}-1; i>=0; i-- )); do
  TRUNCATE_SQL+="TRUNCATE TABLE ${TABLES[$i]} CASCADE; "
done
supabase db query "$TRUNCATE_SQL" --linked >/dev/null 2>&1

# Push each table via REST API bulk insert
for table in "${TABLES[@]}"; do
  CSV_FILE="${DUMP_DIR}/${table}.csv"
  [ ! -f "$CSV_FILE" ] && continue

  LINES=$(( $(wc -l < "$CSV_FILE") - 1 ))
  [ "$LINES" -le 0 ] && continue

  printf "  %-25s %6s rows ... " "$table" "$LINES"

  # Convert CSV to JSON array using Python, then POST in batches
  python3 -c "
import csv, json, sys

batch_size = 500
table = '${table}'

with open('${CSV_FILE}', 'r') as f:
    reader = csv.DictReader(f)
    batch = []
    batch_num = 0

    for row in reader:
        # Convert empty strings to None (null)
        clean = {}
        for k, v in row.items():
            if v == '':
                clean[k] = None
            elif v == 't':
                clean[k] = True
            elif v == 'f':
                clean[k] = False
            else:
                # Try numeric conversion
                try:
                    if '.' in v:
                        clean[k] = float(v)
                    else:
                        clean[k] = int(v)
                except (ValueError, TypeError):
                    clean[k] = v
        batch.append(clean)

        if len(batch) >= batch_size:
            json.dump(batch, open(f'/tmp/dd_batch_{table}_{batch_num}.json', 'w'))
            batch_num += 1
            batch = []

    if batch:
        json.dump(batch, open(f'/tmp/dd_batch_{table}_{batch_num}.json', 'w'))
        batch_num += 1

    # Write batch count
    print(batch_num)
" > /tmp/dd_batch_count_${table}.txt 2>&1

  BATCH_COUNT=$(cat /tmp/dd_batch_count_${table}.txt)

  ERRORS=0
  for (( b=0; b<BATCH_COUNT; b++ )); do
    BATCH_FILE="/tmp/dd_batch_${table}_${b}.json"
    HTTP_CODE=$(curl -s -o /tmp/dd_rest_response.txt -w "%{http_code}" \
      "${API_URL}/${table}" \
      -H "apikey: $SERVICE_KEY" \
      -H "Authorization: Bearer $SERVICE_KEY" \
      -H "Content-Type: application/json" \
      -H "Prefer: resolution=ignore-duplicates" \
      -X POST \
      -d @"$BATCH_FILE")

    if [ "$HTTP_CODE" != "201" ]; then
      ERRORS=$((ERRORS + 1))
      echo ""
      echo "    ERROR (HTTP $HTTP_CODE): $(cat /tmp/dd_rest_response.txt | head -c 200)"
    fi
    rm -f "$BATCH_FILE"
  done

  rm -f /tmp/dd_batch_count_${table}.txt

  if [ "$ERRORS" -eq 0 ]; then
    echo "done"
  else
    echo "($ERRORS batch errors)"
  fi
done

# Re-enable FK checks
supabase db query "SET session_replication_role = 'origin';" --linked >/dev/null 2>&1

# Re-run Spring 2026 price rules
echo ""
echo "Applying Spring 2026 price rules..."
supabase db query "$(cat supabase/migrations/20260416000003_rcc_spring_2026_gear_sale.sql)" --linked >/dev/null 2>&1

# Run seed.sql for surcharges
echo "Applying seed.sql (surcharges, config)..."
supabase db query "$(cat supabase/seed.sql)" --linked >/dev/null 2>&1

# Verify
echo ""
echo "Verifying row counts..."
MISMATCH=0
for table in "${TABLES[@]}"; do
  CSV_FILE="${DUMP_DIR}/${table}.csv"
  [ ! -f "$CSV_FILE" ] && continue
  LOCAL=$(( $(wc -l < "$CSV_FILE") - 1 ))
  [ "$LOCAL" -le 0 ] && continue

  PROD=$(curl -s "${API_URL}/${table}?select=count" \
    -H "apikey: $SERVICE_KEY" \
    -H "Authorization: Bearer $SERVICE_KEY" \
    -H "Prefer: count=exact" \
    -H "Range-Unit: items" \
    -H "Range: 0-0" \
    -o /dev/null -w "" \
    -D - 2>/dev/null | grep -i content-range | grep -oP '/\K[0-9]+' || echo "?")

  # Fallback: query count
  if [ "$PROD" = "?" ]; then
    PROD=$(curl -s "${API_URL}/${table}?select=id" \
      -H "apikey: $SERVICE_KEY" \
      -H "Authorization: Bearer $SERVICE_KEY" \
      -H "Prefer: count=exact" \
      -H "Range: 0-0" \
      -D /tmp/dd_headers.txt -o /dev/null 2>/dev/null
    PROD=$(grep -i content-range /tmp/dd_headers.txt 2>/dev/null | sed 's/.*\///' | tr -d '\r' || echo "?"))
  fi

  MATCH=$([ "$LOCAL" = "$PROD" ] && echo "✓" || echo "✗")
  [ "$MATCH" = "✗" ] && MISMATCH=$((MISMATCH + 1))
  printf "  %s %-25s local=%-6s prod=%-6s\n" "$MATCH" "$table" "$LOCAL" "$PROD"
done

echo ""
if [ "$MISMATCH" -eq 0 ]; then
  echo "All tables match."
else
  echo "$MISMATCH table(s) have mismatches."
fi
