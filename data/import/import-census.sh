#!/bin/bash
# Import e-stat 小地域 census boundary GML into the 3DCityDB PostgreSQL container.
#
# Usage:
#   ./data/import/import-census.sh <path-to-gml>
#
# Example:
#   ./data/import/import-census.sh data/census/r2ka13106.gml
#
# Download the GML from e-stat.go.jp:
#   https://www.e-stat.go.jp/gis/statmap-search?page=1&type=2&aggregateUnitForBoundary=A&toukeiCode=00200521&toukeiYear=2020&serveyId=A002005212020&coordsys=1&format=GML&datum=2011
#   → 東京都 → 台東区 (code 13106) → ダウンロード → GML を解凍して r2ka13106.gml を取得

set -e
GML_FILE="${1:?Usage: $0 <path-to-gml>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_CONTAINER=3dcity-backend

if [ ! -f "$GML_FILE" ]; then
  echo "Error: GML file not found: $GML_FILE"
  exit 1
fi

echo "=== Census boundary import ==="
echo "GML: $GML_FILE"
echo ""

echo "[1/3] Copying files into backend container..."
docker cp "$GML_FILE" "$BACKEND_CONTAINER:/tmp/census_input.gml"
docker cp "$SCRIPT_DIR/import_census_direct.py" "$BACKEND_CONTAINER:/tmp/import_census_direct.py"

echo "[2/3] Running import..."
docker exec "$BACKEND_CONTAINER" python /tmp/import_census_direct.py /tmp/census_input.gml

echo "[3/3] Restarting Martin tile server to discover new table..."
docker compose restart martin

echo ""
echo "Done! Verify with:"
echo "  curl http://localhost:3000/api/areas | python3 -m json.tool | head -20"
