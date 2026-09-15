#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "Python virtual environment not found:"
    echo "$PYTHON"
    exit 1
fi

# Load the database password once for the complete hourly cycle.
# Existing aggregate wrappers inherit it, and the species scripts use
# the same environment directly.
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

# Keep the existing aggregate activity path first so species-model
# failures cannot prevent the established activity forecast from running.
echo "Scoring completed activity predictions..."
"$ROOT/ml/score_predictions.sh"

echo
echo "Creating next activity prediction..."
"$ROOT/ml/predict_next_hour.sh"

# Species predictions use the same completed-hour T -> T+2 timing.
# Start with the two species that have enough signal and history for
# useful live evaluation. Sparse species remain retrospective for now.
echo
echo "Scoring completed species predictions..."
"$PYTHON" ml/src/score_species_predictions.py

for species in "House Finch" "Black Phoebe"; do
    echo
    echo "Creating species prediction: $species"
    "$PYTHON" ml/src/predict_species_live.py --species "$species"
done
