#!/usr/bin/env bash
# Legacy Pi-local PostgreSQL backup path retained for migration/recovery
# reference. The current centralized backup is backup_infra_postgres.sh.
set -euo pipefail

BACKUP_DIR="/home/birduser/backups/postgresql"
DATABASE="birdnet"
DATABASE_USER="birdnet"
RETENTION_DAYS=14

timestamp="$(date '+%Y-%m-%d_%H-%M-%S')"
backup_file="${BACKUP_DIR}/${DATABASE}_${timestamp}.dump"

mkdir -p "${BACKUP_DIR}"

pg_dump \
    --host=localhost \
    --username="${DATABASE_USER}" \
    --format=custom \
    --file="${backup_file}" \
    "${DATABASE}"

find "${BACKUP_DIR}" \
    -type f \
    -name "${DATABASE}_*.dump" \
    -mtime +"${RETENTION_DAYS}" \
    -delete

echo "PostgreSQL backup created: ${backup_file}"
