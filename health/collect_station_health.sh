#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "Python virtual environment not found: $PYTHON" >&2
    exit 1
fi

if [[ -z "${BIRDNET_DB_PASSWORD:-}" ]]; then
    BIRDNET_DB_PASSWORD=$(
        docker inspect birdnet-postgres             --format '{{range .Config.Env}}{{println .}}{{end}}'         | sed -n 's/^POSTGRES_PASSWORD=//p'
    )
    export BIRDNET_DB_PASSWORD
fi

if [[ -z "${BIRDNET_DB_PASSWORD:-}" ]]; then
    echo "Could not load PostgreSQL password." >&2
    exit 1
fi

export BIRDNET_DB_HOST="${BIRDNET_DB_HOST:-127.0.0.1}"
export BIRDNET_DB_NAME="${BIRDNET_DB_NAME:-birdnet}"
export BIRDNET_DB_USER="${BIRDNET_DB_USER:-birdnet}"
export BIRDNET_LOKI_URL="${BIRDNET_LOKI_URL:-http://localhost:3100}"

exec "$PYTHON" "$ROOT/health/collect_station_health.py" "$@"
