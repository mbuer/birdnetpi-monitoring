#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo ./deploy/ubuntu-infra/verify.sh" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

require_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Prerequisite missing: $name" >&2
    exit 2
  fi
}

require_command docker
require_command curl
require_command systemctl

if ! docker compose version >/dev/null 2>&1; then
  echo "Prerequisite missing: Docker Compose v2 plugin" >&2
  exit 2
fi

failures=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

for container in birdnet-postgres birdnet-loki; do
  if docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null | grep -qx true; then
    pass "$container running"
  else
    fail "$container not running"
  fi
done

if docker exec birdnet-postgres pg_isready -U birdnet -d birdnet >/dev/null 2>&1; then
  pass "PostgreSQL ready"
else
  fail "PostgreSQL not ready"
fi

if curl -fsS http://127.0.0.1:3100/ready >/dev/null; then
  pass "Loki ready"
else
  fail "Loki not ready"
fi

db_objects="$(docker exec birdnet-postgres psql -At -U birdnet -d birdnet -c "
SELECT count(*) FROM information_schema.tables
WHERE table_schema='public'
AND table_name IN (
  'detections','weather_observations','weather_forecasts',
  'station_health_hourly','bird_activity_predictions','bird_species_predictions'
);
")"
[[ "$db_objects" == "6" ]] && pass "Core PostgreSQL tables present" || fail "Core PostgreSQL tables incomplete"

db_views="$(docker exec birdnet-postgres psql -At -U birdnet -d birdnet -c "
SELECT count(*) FROM information_schema.views
WHERE table_schema='public'
AND table_name IN ('bird_activity_hourly','bird_species_hourly');
")"
[[ "$db_views" == "2" ]] && pass "Analytical views present" || fail "Analytical views incomplete"

for unit in birdnet-station-health.timer birdnet-ml-prediction.timer birdnet-postgres-backup.timer; do
  systemctl is-active --quiet "$unit" && pass "$unit active" || fail "$unit not active"
  systemctl is-enabled --quiet "$unit" && pass "$unit enabled" || fail "$unit not enabled"
done

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  pass "ML virtual environment present"
else
  fail "ML virtual environment missing"
fi

if "$ROOT/.venv/bin/python" -m unittest discover -s "$ROOT/ml/tests" -v >/dev/null 2>&1; then
  pass "ML regression tests"
else
  fail "ML regression tests"
fi

echo
if (( failures > 0 )); then
  echo "Verification failed: $failures check(s)."
  exit 1
fi
echo "ubuntu-infra verification passed."
