#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/birdnet-postgres"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
FILE="$BACKUP_DIR/birdnet-$STAMP.dump"

mkdir -p "$BACKUP_DIR"

docker exec birdnet-postgres \
  pg_dump \
    -U birdnet \
    -d birdnet \
    -Fc \
  > "$FILE"

find "$BACKUP_DIR" \
  -type f \
  -name 'birdnet-*.dump' \
  -mtime +14 \
  -delete

echo "Backup created: $FILE"
