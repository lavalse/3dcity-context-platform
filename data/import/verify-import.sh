#!/usr/bin/env bash
# verify-import.sh — check that all expected feature types are present in 3DCityDB
# Usage: ./data/import/verify-import.sh
# Exit 0 = all PASS; Exit 1 = one or more FAIL

set -euo pipefail

CONTAINER="3dcitydb-pg"
DB_USER="citydb"
DB_NAME="citydb"

# Minimum expected counts (conservative, ~5% below actual for Taito-ku 2024)
declare -A EXPECTED_MIN=(
  ["Building"]=70000
  ["LandUse"]=180000
  ["Road"]=20000
  ["WaterBody"]=8000
  ["Bridge"]=50
  ["CityFurniture"]=7000
  ["SolitaryVegetationObject"]=10000
  ["ReliefFeature"]=15
)

PASS=0
FAIL=0

echo "=== 3DCityDB Import Verification ==="
echo ""

for classname in "${!EXPECTED_MIN[@]}"; do
  min=${EXPECTED_MIN[$classname]}
  count=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT COUNT(*) FROM citydb.cityobject co
     JOIN citydb.objectclass oc ON oc.id = co.objectclass_id
     WHERE oc.classname = '${classname}';" 2>/dev/null | tr -d ' ')

  if [ -z "$count" ] || ! [[ "$count" =~ ^[0-9]+$ ]]; then
    echo "FAIL  ${classname}: could not query DB (is ${CONTAINER} running?)"
    FAIL=$((FAIL + 1))
    continue
  fi

  if [ "$count" -ge "$min" ]; then
    echo "PASS  ${classname}: ${count} (min ${min})"
    PASS=$((PASS + 1))
  else
    echo "FAIL  ${classname}: ${count} (expected >= ${min}) — run: ./data/import/run-import.sh udx/<type>"
    FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "=== Results: ${PASS} PASS, ${FAIL} FAIL ==="

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "Missing feature types. Check docs/setup.md Step 4 for the full import list."
  exit 1
fi

exit 0
