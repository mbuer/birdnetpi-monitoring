#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo ./deploy/birdnet-pi/bootstrap.sh" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME_ENV="/etc/birdnet-monitoring/runtime.env"
RUNTIME_USER="${BIRDNET_RUNTIME_USER:-${SUDO_USER:-}}"

if [[ -z "$RUNTIME_USER" || "$RUNTIME_USER" == "root" ]]; then
  echo "Set BIRDNET_RUNTIME_USER to the Linux user that owns the BirdNET installation." >&2
  exit 1
fi

if ! getent passwd "$RUNTIME_USER" >/dev/null; then
  echo "Runtime user does not exist: $RUNTIME_USER" >&2
  exit 1
fi

USER_HOME="$(getent passwd "$RUNTIME_USER" | cut -d: -f6)"

if [[ ! -f "$RUNTIME_ENV" ]]; then
  echo "Missing $RUNTIME_ENV" >&2
  echo "Create it from config/runtime.example.env and fill in real local values." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$RUNTIME_ENV"
set +a

required=(
  BIRDNET_DB_HOST BIRDNET_DB_NAME BIRDNET_DB_USER BIRDNET_DB_PASSWORD
  BIRDNET_STATION_ID BIRDNET_TIMEZONE BIRDNET_LATITUDE BIRDNET_LONGITUDE
  BIRDNET_LOKI_URL
)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" || "${!name}" == "CHANGE_ME" || "${!name}" == *"INFRA_HOST"* ]]; then
    echo "Runtime variable is not configured: $name" >&2
    exit 1
  fi
done

echo "Installing Pi-side Python dependencies..."
apt-get update
apt-get install -y python3 python3-requests python3-psycopg curl ca-certificates

if ! command -v alloy >/dev/null; then
  echo "Grafana Alloy is not installed." >&2
  echo "Install Alloy first, then rerun this bootstrap." >&2
  exit 1
fi

echo "Preparing weather runtime..."
install -d -o "$RUNTIME_USER" -g "$RUNTIME_USER" -m 0755 "$USER_HOME/weather"
install -d -o "$RUNTIME_USER" -g "$RUNTIME_USER" -m 0755 /var/log/weather
install -o "$RUNTIME_USER" -g "$RUNTIME_USER" -m 0644   "$ROOT/weather/weather.py" "$USER_HOME/weather/weather.py"

render_unit() {
  local src="$1"
  local dst="$2"
  sed     -e "s#User=birduser#User=$RUNTIME_USER#g"     -e "s#/home/birduser/birdnetPi-monitoring#$ROOT#g"     -e "s#/home/birduser/weather#$USER_HOME/weather#g"     "$src" > "$dst"
  chmod 0644 "$dst"
}

echo "Installing Pi-side systemd units..."
render_unit "$ROOT/systemd/birdnet-db-sync.service" /etc/systemd/system/birdnet-db-sync.service
render_unit "$ROOT/systemd/birdnet-forecast.service" /etc/systemd/system/birdnet-forecast.service
render_unit "$ROOT/systemd/weather.service" /etc/systemd/system/weather.service

install -m 0644 "$ROOT/systemd/birdnet-db-sync.timer" /etc/systemd/system/birdnet-db-sync.timer
install -m 0644 "$ROOT/systemd/birdnet-forecast.timer" /etc/systemd/system/birdnet-forecast.timer

echo "Installing Alloy configuration..."
install -d -m 0755 /etc/systemd/system/alloy.service.d
install -o root -g root -m 0644 "$ROOT/alloy/config.alloy" /etc/alloy/config.alloy
install -o root -g root -m 0644   "$ROOT/deploy/birdnet-pi/alloy.override.conf"   /etc/systemd/system/alloy.service.d/override.conf

echo "Validating Alloy configuration..."
/usr/bin/alloy validate /etc/alloy/config.alloy

systemctl daemon-reload
systemctl enable --now birdnet-db-sync.timer
systemctl enable --now birdnet-forecast.timer
systemctl enable --now weather.service
systemctl enable --now alloy.service

echo
echo "BirdNET Pi bootstrap complete."
echo "Run: sudo $ROOT/deploy/birdnet-pi/verify.sh"
