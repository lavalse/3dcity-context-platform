#!/bin/bash
# Import PLATEAU 避難施設 (shelter) GeoJSON into the 3DCityDB PostgreSQL container.
#
# Usage:
#   ./data/import/import-shelters.sh [path-to-geojson]
#
# If no argument is given, the script downloads the GeoJSON from the PLATEAU CDN.
# To use a local file:
#   ./data/import/import-shelters.sh data/shelters/13106_tokyo23ku-taito-ku_pref_2023_shelter.geojson

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_CONTAINER=3dcity-backend
SOURCE="${1:-https://assets.cms.plateau.reearth.io/assets/c9/6d984f-6d29-4ecb-9442-ec8baaff4566/13106_tokyo23ku-taito-ku_pref_2023_shelter.geojson}"

echo "=== Shelter facility import ==="
echo "Source: $SOURCE"
echo ""

echo "[1/3] Copying import script into backend container..."
docker cp "$SCRIPT_DIR/import_shelters_direct.py" "$BACKEND_CONTAINER:/tmp/import_shelters_direct.py"

if [ -f "$SOURCE" ]; then
  docker cp "$SOURCE" "$BACKEND_CONTAINER:/tmp/shelter_input.geojson"
  ARG="/tmp/shelter_input.geojson"
else
  ARG="$SOURCE"
fi

echo "[2/3] Running import..."
docker exec "$BACKEND_CONTAINER" python /tmp/import_shelters_direct.py "$ARG"

echo "[3/3] Restarting Martin tile server to discover new table..."
docker compose restart martin

echo ""
echo "Done! Verify with:"
echo "  curl http://localhost:3000/api/shelters | python3 -m json.tool | head -30"
