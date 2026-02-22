#!/usr/bin/env bash
# Create a compressed PostgreSQL dump of the 3DCityDB database.
# Use this to create a snapshot for sharing with team members.
#
# Usage:
#   ./scripts/db-dump.sh [output-filename]
#
# Example:
#   ./scripts/db-dump.sh taito-ku-bldg-imported.dump

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT="${1:-${REPO_ROOT}/taito-ku_3dcitydb_${TIMESTAMP}.dump}"

source "${REPO_ROOT}/.env" 2>/dev/null || source "${REPO_ROOT}/.env.example"

echo "==> Creating DB dump: ${OUTPUT}"
docker exec 3dcitydb-pg pg_dump \
  -U "${POSTGRES_USER:-citydb}" \
  -d "${POSTGRES_DB:-citydb}" \
  -Fc \
  -Z 9 \
  > "${OUTPUT}"

SIZE=$(du -sh "${OUTPUT}" | cut -f1)
echo "==> Done. File size: ${SIZE}"
echo "==> Share this file with team members and document its location."
