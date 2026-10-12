#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "Python virtual environment not found:"
    echo "$PYTHON"
    exit 1
fi

if [[ -z "${BIRDNET_DB_PASSWORD:-}" ]]; then
    BIRDNET_DB_PASSWORD=$(
        docker inspect birdnet-postgres \
            --format '{{range .Config.Env}}{{println .}}{{end}}' \
        | sed -n 's/^POSTGRES_PASSWORD=//p'
    )

    export BIRDNET_DB_PASSWORD
fi

if [[ -z "${BIRDNET_DB_PASSWORD:-}" ]]; then
    echo "Could not load PostgreSQL password."
    exit 1
fi

cd "$ROOT"

exec "$PYTHON" ml/src/score_predictions.py
