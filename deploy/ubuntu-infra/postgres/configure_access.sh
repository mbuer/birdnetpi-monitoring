#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
POSTGRES_DIR="$ROOT/deploy/ubuntu-infra/postgres"
ENV_FILE="$POSTGRES_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

required=(
  POSTGRES_PASSWORD
  BIRDNET_CLIENT_CIDR
  GRAFANA_CLIENT_CIDR
  BIRDYNATOR_CLIENT_CIDR
)

for name in "${required[@]}"; do
  value="${!name:-}"
  if [[ -z "$value" || "$value" == "change-me" || "$value" == "CHANGE_ME" ]]; then
    echo "Missing or example value for $name in $ENV_FILE" >&2
    exit 1
  fi
done

role_exists() {
  local role="$1"
  docker exec birdnet-postgres     psql -At -U birdnet -d birdnet -c     "SELECT 1 FROM pg_roles WHERE rolname='$role';"     | grep -qx 1
}

if ! role_exists grafana_reader; then
  if [[ -z "${GRAFANA_DB_PASSWORD:-}" || "${GRAFANA_DB_PASSWORD}" == "change-me" || "${GRAFANA_DB_PASSWORD}" == "CHANGE_ME" ]]; then
    echo "GRAFANA_DB_PASSWORD is required when creating grafana_reader." >&2
    exit 1
  fi
fi

if ! role_exists birdynator_reader; then
  if [[ -z "${BIRDYNATOR_DB_PASSWORD:-}" || "${BIRDYNATOR_DB_PASSWORD}" == "change-me" || "${BIRDYNATOR_DB_PASSWORD}" == "CHANGE_ME" ]]; then
    echo "BIRDYNATOR_DB_PASSWORD is required when creating birdynator_reader." >&2
    exit 1
  fi
fi

python3 - "$BIRDNET_CLIENT_CIDR" "$GRAFANA_CLIENT_CIDR" "$BIRDYNATOR_CLIENT_CIDR" <<'PY'
import ipaddress
import sys

for value in sys.argv[1:]:
    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError as exc:
        raise SystemExit(f"Invalid client CIDR {value!r}: {exc}")
PY

if ! docker inspect birdnet-postgres >/dev/null 2>&1; then
  echo "birdnet-postgres container is not available." >&2
  exit 1
fi

postgres_gateway="$(
  docker inspect birdnet-postgres     --format '{{range .NetworkSettings.Networks}}{{println .Gateway}}{{end}}'     | awk 'NF {print; exit}'
)"

if [[ -z "$postgres_gateway" ]]; then
  echo "Could not derive the PostgreSQL Docker gateway." >&2
  exit 1
fi

postgres_gateway_cidr="${postgres_gateway}/32"

echo "Applying PostgreSQL reader roles and grants..."
docker exec -i birdnet-postgres   psql -v ON_ERROR_STOP=1        -v grafana_password="${GRAFANA_DB_PASSWORD:-}"        -v birdynator_password="${BIRDYNATOR_DB_PASSWORD:-}"        -U birdnet -d birdnet   < "$ROOT/database/access.sql"

tmp_hba="$(mktemp)"
trap 'rm -f "$tmp_hba"' EXIT

cat > "$tmp_hba" <<EOF
# Managed by deploy/ubuntu-infra/postgres/configure_access.sh
# Environment-specific client CIDRs come from the ignored postgres/.env file.

# Local container administration.
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust

# Local replication support.
local   replication     all                                     trust
host    replication     all             127.0.0.1/32            trust
host    replication     all             ::1/128                 trust

# BirdNET Pi ingestion: exact configured client only.
host    birdnet         birdnet         $BIRDNET_CLIENT_CIDR     scram-sha-256

# Grafana: its Docker client network plus host-to-container gateway path.
host    birdnet         grafana_reader  $GRAFANA_CLIENT_CIDR     scram-sha-256
host    birdnet         grafana_reader  $postgres_gateway_cidr   scram-sha-256

# Local ML/health jobs reach the published PostgreSQL port through this gateway.
host    birdnet         birdnet         $postgres_gateway_cidr   scram-sha-256

# AI Nexus / Birdynator: exact configured client only.
host    birdnet         birdynator_reader $BIRDYNATOR_CLIENT_CIDR scram-sha-256
EOF

docker cp "$tmp_hba" birdnet-postgres:/tmp/pg_hba.conf.managed
docker exec birdnet-postgres sh -lc '
  install -o postgres -g postgres -m 0600     /tmp/pg_hba.conf.managed     /var/lib/postgresql/data/pg_hba.conf
  rm -f /tmp/pg_hba.conf.managed
'

hba_errors="$(
  docker exec birdnet-postgres     psql -At -U birdnet -d birdnet -c     "SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL;"
)"

if [[ "$hba_errors" != "0" ]]; then
  echo "PostgreSQL rejected the rendered pg_hba.conf:" >&2
  docker exec birdnet-postgres     psql -U birdnet -d birdnet -c     "SELECT line_number, type, database, user_name, address, auth_method, error
     FROM pg_hba_file_rules
     WHERE error IS NOT NULL
     ORDER BY line_number;" >&2
  exit 1
fi

docker exec birdnet-postgres   psql -v ON_ERROR_STOP=1 -U birdnet -d birdnet   -c "SELECT pg_reload_conf();" >/dev/null

echo "PostgreSQL access policy applied."
