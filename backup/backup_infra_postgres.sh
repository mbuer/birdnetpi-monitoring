#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/birdnet-postgres"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
FINAL_FILE="$BACKUP_DIR/birdnet-$STAMP.dump"
TEMP_FILE="$FINAL_FILE.tmp"

mkdir -p "$BACKUP_DIR"

cleanup() {
  rm -f "$TEMP_FILE"
}
trap cleanup EXIT

docker exec birdnet-postgres   pg_dump     -U birdnet     -d birdnet     -Fc   > "$TEMP_FILE"

if [[ ! -s "$TEMP_FILE" ]]; then
  echo "Backup failed: dump is empty." >&2
  exit 1
fi

# Validate that PostgreSQL can read the archive before publishing it as
# the completed backup. pg_restore runs inside the PostgreSQL container
# so the host does not need PostgreSQL client packages installed.
docker exec -i birdnet-postgres   pg_restore -l   < "$TEMP_FILE"   > /dev/null

mv "$TEMP_FILE" "$FINAL_FILE"
trap - EXIT

find "$BACKUP_DIR"   -type f   -name 'birdnet-*.dump'   -mtime +14   -delete

echo "Backup created and validated: $FINAL_FILE"
