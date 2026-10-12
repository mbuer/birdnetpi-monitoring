#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo ./deploy/ubuntu-infra/verify.sh" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POSTGRES_DIR="$ROOT/deploy/ubuntu-infra/postgres"
ENV_FILE="$POSTGRES_DIR/.env"

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

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Prerequisite missing: $ENV_FILE" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

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

reader_roles="$(docker exec birdnet-postgres psql -At -U birdnet -d birdnet -c "
SELECT count(*)
FROM pg_roles
WHERE rolname IN ('grafana_reader','birdynator_reader')
  AND rolcanlogin
  AND NOT rolsuper
  AND NOT rolcreatedb
  AND NOT rolcreaterole;
")"
[[ "$reader_roles" == "2" ]] && pass "Read-only PostgreSQL roles constrained" || fail "Read-only PostgreSQL roles incorrect"

grafana_grants="$(docker exec birdnet-postgres psql -At -U birdnet -d birdnet -c "
SELECT count(*)
FROM information_schema.role_table_grants
WHERE grantee='grafana_reader' AND privilege_type='SELECT';
")"
[[ "$grafana_grants" == "8" ]] && pass "Grafana PostgreSQL grants" || fail "Grafana PostgreSQL grants incorrect"

birdynator_grants="$(docker exec birdnet-postgres psql -At -U birdnet -d birdnet -c "
SELECT count(*)
FROM information_schema.role_table_grants
WHERE grantee='birdynator_reader' AND privilege_type='SELECT';
")"
[[ "$birdynator_grants" == "4" ]] && pass "Birdynator PostgreSQL grants" || fail "Birdynator PostgreSQL grants incorrect"

schema_usage="$(docker exec birdnet-postgres psql -At -U birdnet -d birdnet -c "
SELECT
  has_schema_privilege('grafana_reader','public','USAGE')
  AND has_schema_privilege('birdynator_reader','public','USAGE');
")"
[[ "$schema_usage" == "t" ]] && pass "Reader schema usage" || fail "Reader schema usage missing"

hba_errors="$(docker exec birdnet-postgres psql -At -U birdnet -d birdnet -c "
SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL;
")"
[[ "$hba_errors" == "0" ]] && pass "PostgreSQL HBA parses cleanly" || fail "PostgreSQL HBA has parse errors"

postgres_gateway="$(
  docker inspect birdnet-postgres     --format '{{range .NetworkSettings.Networks}}{{println .Gateway}}{{end}}'     | awk 'NF {print; exit}'
)"
postgres_gateway_cidr="${postgres_gateway}/32"

hba_text="$(docker exec birdnet-postgres cat /var/lib/postgresql/data/pg_hba.conf)"
check_hba_rule() {
  local database="$1"
  local user="$2"
  local cidr="$3"
  if grep -Eq "^host[[:space:]]+$database[[:space:]]+$user[[:space:]]+$cidr[[:space:]]+scram-sha-256[[:space:]]*$" <<<"$hba_text"; then
    pass "HBA $user from $cidr"
  else
    fail "HBA missing $user from $cidr"
  fi
}

check_hba_rule birdnet birdnet "$BIRDNET_CLIENT_CIDR"
check_hba_rule birdnet grafana_reader "$GRAFANA_CLIENT_CIDR"
check_hba_rule birdnet grafana_reader "$postgres_gateway_cidr"
check_hba_rule birdnet birdnet "$postgres_gateway_cidr"
check_hba_rule birdnet birdynator_reader "$BIRDYNATOR_CLIENT_CIDR"

if grep -Eq '^host[[:space:]]+all[[:space:]]+all[[:space:]]+[^[:space:]]+[[:space:]]+scram-sha-256' <<<"$hba_text"; then
  fail "Broad remote HBA rule present"
else
  pass "No broad remote HBA rule"
fi

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
