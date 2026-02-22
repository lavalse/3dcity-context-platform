#!/usr/bin/env bash
# Run the 3DCityDB Importer/Exporter to load PLATEAU CityGML into the database.
# Prerequisites: Docker running, db container healthy, CityGML files in data/citygml/
#
# Usage:
#   ./data/import/run-import.sh [path-to-gml-file-or-directory]
#
# Example:
#   ./data/import/run-import.sh data/citygml/13106_taito-ku_city_2024_citygml_1_op/udx/bldg/

set -euo pipefail

INPUT_PATH="${1:-data/citygml}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Load environment variables
source "${REPO_ROOT}/.env" 2>/dev/null || source "${REPO_ROOT}/.env.example"

echo "==> Importing: ${INPUT_PATH}"
echo "==> Target DB: ${POSTGRES_HOST:-localhost}:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-citydb}"

docker run --rm \
  --network host \
  -v "${REPO_ROOT}/data/citygml:/data:ro" \
  3dcitydb/impexp:latest \
  import \
  -H "${POSTGRES_HOST:-localhost}" \
  -P "${POSTGRES_PORT:-5432}" \
  -d "${POSTGRES_DB:-citydb}" \
  -u "${POSTGRES_USER:-citydb}" \
  -p "${POSTGRES_PASSWORD:-citydb}" \
  "/data/${INPUT_PATH#data/citygml/}"

echo "==> Import complete."
