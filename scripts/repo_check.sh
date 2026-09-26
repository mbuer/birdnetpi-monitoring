#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0

if git grep -nE '\b192\.168\.[0-9]{1,3}\.[0-9]{1,3}\b|\b10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\b|\b172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3}\b' -- .   ':!docs/experiments/**' ':!ml/reports/**'
then
  echo
  echo "FAIL: live/private RFC1918 addressing found in tracked files." >&2
  fail=1
else
  echo "PASS: no tracked live/private RFC1918 addresses."
fi

if git grep -nE '^(LATITUDE|LONGITUDE)[[:space:]]*=[[:space:]]*-?[0-9]' -- '*.py' >/dev/null; then
  git grep -nE '^(LATITUDE|LONGITUDE)[[:space:]]*=[[:space:]]*-?[0-9]' -- '*.py'
  echo "FAIL: hard-coded station coordinates found." >&2
  fail=1
else
  echo "PASS: no hard-coded Python station coordinates."
fi

if git grep -nE 'GRAFANA_CLOUD_PASSWORD|logs-prod-[0-9]+\.grafana\.net|loki\.write\.cloud' -- . ':!scripts/repo_check.sh' >/dev/null; then
  git grep -nE 'GRAFANA_CLOUD_PASSWORD|logs-prod-[0-9]+\.grafana\.net|loki\.write\.cloud' -- . ':!scripts/repo_check.sh'
  echo "FAIL: active Grafana Cloud configuration marker found." >&2
  fail=1
else
  echo "PASS: no active Grafana Cloud configuration markers."
fi

exit "$fail"
