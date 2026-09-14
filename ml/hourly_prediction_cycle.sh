#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"

echo "Scoring completed predictions..."
"$ROOT/ml/score_predictions.sh"

echo
echo "Creating next-hour prediction..."
"$ROOT/ml/predict_next_hour.sh"
