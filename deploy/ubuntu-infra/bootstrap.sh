#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo ./deploy/ubuntu-infra/bootstrap.sh" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INFRA_USER="${BIRDNET_INFRA_USER:-${SUDO_USER:-}}"
POSTGRES_DIR="$ROOT/deploy/ubuntu-infra/postgres"
LOKI_DIR="$ROOT/deploy/ubuntu-infra/loki"

if [[ -z "$INFRA_USER" || "$INFRA_USER" == "root" ]]; then
  echo "Set BIRDNET_INFRA_USER to the normal infrastructure service user." >&2
  exit 1
fi

if ! getent passwd "$INFRA_USER" >/dev/null; then
  echo "Infra user does not exist: $INFRA_USER" >&2
  exit 1
fi

if [[ ! -f "$POSTGRES_DIR/.env" ]]; then
  echo "Missing $POSTGRES_DIR/.env" >&2
  echo "Copy .env.example to .env and set POSTGRES_PASSWORD first." >&2
  exit 1
fi

if grep -Eq '^POSTGRES_PASSWORD=(change-me|CHANGE_ME)?$' "$POSTGRES_DIR/.env"; then
  echo "POSTGRES_PASSWORD is still an example value." >&2
  exit 1
fi

command -v docker >/dev/null || {
  echo "Docker is required before running this bootstrap." >&2
  exit 1
}

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 plugin is required before running this bootstrap." >&2
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip curl ca-certificates make

echo "Starting PostgreSQL and Loki..."
docker compose --env-file "$POSTGRES_DIR/.env" -f "$POSTGRES_DIR/compose.yaml" up -d
docker compose -f "$LOKI_DIR/compose.yaml" up -d

echo "Waiting for PostgreSQL..."
for _ in {1..30}; do
  if docker exec birdnet-postgres pg_isready -U birdnet -d birdnet >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
docker exec birdnet-postgres pg_isready -U birdnet -d birdnet >/dev/null

echo "Applying database objects..."
for sql in   database/schema.sql   database/predictions.sql   database/species_predictions.sql   database/views/bird_activity_hourly.sql   database/views/bird_species_hourly.sql
do
  docker exec -i birdnet-postgres     psql -v ON_ERROR_STOP=1 -U birdnet -d birdnet     < "$ROOT/$sql"
done

echo "Configuring PostgreSQL access policy..."
bash "$POSTGRES_DIR/configure_access.sh"

echo "Preparing ML/health Python environment..."
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  sudo -u "$INFRA_USER" python3 -m venv "$ROOT/.venv"
fi
sudo -u "$INFRA_USER" "$ROOT/.venv/bin/python" -m pip install -r "$ROOT/ml/requirements.txt"

install -d -o "$INFRA_USER" -g "$INFRA_USER" -m 0750 /var/backups/birdnet-postgres

render_unit() {
  local src="$1"
  local dst="$2"
  sed     -e "s#User=infra#User=$INFRA_USER#g"     -e "s#/opt/birdnetpi-monitoring#$ROOT#g"     "$src" > "$dst"
  chmod 0644 "$dst"
}

echo "Installing infra systemd units..."
render_unit "$ROOT/systemd/birdnet-station-health.service" /etc/systemd/system/birdnet-station-health.service
render_unit "$ROOT/systemd/birdnet-ml-prediction.service" /etc/systemd/system/birdnet-ml-prediction.service
render_unit "$ROOT/systemd/birdnet-postgres-backup.service" /etc/systemd/system/birdnet-postgres-backup.service

install -m 0644 "$ROOT/systemd/birdnet-station-health.timer" /etc/systemd/system/birdnet-station-health.timer
install -m 0644 "$ROOT/systemd/birdnet-ml-prediction.timer" /etc/systemd/system/birdnet-ml-prediction.timer
install -m 0644 "$ROOT/systemd/birdnet-postgres-backup.timer" /etc/systemd/system/birdnet-postgres-backup.timer

systemctl daemon-reload
systemctl enable --now birdnet-station-health.timer
systemctl enable --now birdnet-ml-prediction.timer
systemctl enable --now birdnet-postgres-backup.timer

echo
echo "ubuntu-infra bootstrap complete."
echo "Grafana provisioning remains owned by the separate homelab-grafana repository."
echo "Run: sudo $ROOT/deploy/ubuntu-infra/verify.sh"
