#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"

REPORT_DIR="$ROOT/ml/reports/runs"
TIMESTAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
REPORT="$REPORT_DIR/run_$TIMESTAMP.txt"

if [[ ! -x "$PYTHON" ]]; then
    echo "Python virtual environment not found:"
    echo "$PYTHON"
    exit 1
fi

if [[ -z "${BIRDNET_DB_PASSWORD:-}" ]]; then
    BIRDNET_DB_PASSWORD="$(
        docker inspect birdnet-postgres \
            --format '{{range .Config.Env}}{{println .}}{{end}}' \
        | sed -n 's/^POSTGRES_PASSWORD=//p'
    )"

    export BIRDNET_DB_PASSWORD
fi

if [[ -z "$BIRDNET_DB_PASSWORD" ]]; then
    echo "Could not load PostgreSQL password."
    exit 1
fi

mkdir -p "$REPORT_DIR"

cd "$ROOT"

{
    echo "BirdNET ML experiment run"
    echo "========================="
    echo
    echo "Timestamp: $(date --iso-8601=seconds)"
    echo "Git commit: $(git rev-parse HEAD)"
    echo

    echo "Dataset"
    echo "-------"

    "$PYTHON" - <<'PY'
import sys

sys.path.insert(0, "ml/src")

from data import load_hourly_data

df = load_hourly_data()

print(f"Rows:       {len(df)}")
print(f"First hour: {df['hour_local'].min()}")
print(f"Last hour:  {df['hour_local'].max()}")
PY

    echo
    echo
    echo "Model comparison"
    echo "----------------"
    "$PYTHON" ml/src/compare_models.py

    echo
    echo
    echo "Rolling validation"
    echo "------------------"
    "$PYTHON" ml/src/rolling_validation.py

    echo
    echo
    echo "Feature importance"
    echo "------------------"
    "$PYTHON" ml/src/feature_importance.py

    echo
    echo
    echo "Feature ablation"
    echo "----------------"
    "$PYTHON" ml/src/ablation.py

} 2>&1 | tee "$REPORT"

echo
echo "Saved report:"
echo "$REPORT"
