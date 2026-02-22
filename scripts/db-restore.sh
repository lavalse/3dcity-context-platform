#!/usr/bin/env bash
# Restore a 3DCityDB database from a pg_dump file.
# Use this when onboarding to the project without running the full CityGML import.
#
# Prerequisites: DB container must be running (docker compose up -d db)
#
# Usage:
#   ./scripts/db-restore.sh <path-to-dump-file>
#
# Example:
#   ./scripts/db-restore.sh ~/Downloads/taito-ku_3dcitydb_20260222.dump

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DUMP_FILE="${1:-}"

if [[ -z "${DUMP_FILE}" ]]; then
  echo "Usage: $0 <path-to-dump-file>"
  exit 1
fi

if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "Error: file not found: ${DUMP_FILE}"
  exit 1
fi

source "${REPO_ROOT}/.env" 2>/dev/null || source "${REPO_ROOT}/.env.example"

echo "==> Restoring from: ${DUMP_FILE}"
echo "==> WARNING: This will DROP and recreate the citydb database."
read -r -p "Continue? [y/N] " CONFIRM
[[ "${CONFIRM}" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

# Drop and recreate the database
docker exec 3dcitydb-pg psql -U "${POSTGRES_USER:-citydb}" -d postgres \
  -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-citydb};" \
  -c "CREATE DATABASE ${POSTGRES_DB:-citydb} OWNER ${POSTGRES_USER:-citydb};"

# Restore
docker exec -i 3dcitydb-pg pg_restore \
  -U "${POSTGRES_USER:-citydb}" \
  -d "${POSTGRES_DB:-citydb}" \
  --no-owner \
  --role="${POSTGRES_USER:-citydb}" \
  < "${DUMP_FILE}"

echo "==> Restore complete."
docker exec 3dcitydb-pg psql -U "${POSTGRES_USER:-citydb}" -d "${POSTGRES_DB:-citydb}" -c "
SELECT oc.classname, COUNT(*) AS count
FROM citydb.cityobject co
JOIN citydb.objectclass oc ON oc.id = co.objectclass_id
GROUP BY oc.classname ORDER BY count DESC;"
