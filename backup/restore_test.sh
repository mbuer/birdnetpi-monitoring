#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/birdnet-postgres"
TEST_DB="birdnet_restore_test"

latest="$(
  find "$BACKUP_DIR" -maxdepth 1 -type f -name 'birdnet-*.dump' -printf '%T@ %p\n' 2>/dev/null     | sort -nr     | head -1     | cut -d' ' -f2-
)"

[[ -n "$latest" ]] || {
  echo "ERROR: no BirdNET backup found in $BACKUP_DIR" >&2
  exit 1
}

cleanup() {
  docker exec birdnet-postgres dropdb -U birdnet --if-exists "$TEST_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Testing restore from: $latest"

docker exec birdnet-postgres dropdb -U birdnet --if-exists "$TEST_DB"
docker exec birdnet-postgres createdb -U birdnet -O birdnet "$TEST_DB"

cat "$latest" | docker exec -i birdnet-postgres   pg_restore -U birdnet -d "$TEST_DB" --no-owner --exit-on-error

docker exec -i birdnet-postgres psql -U birdnet -d "$TEST_DB" -v ON_ERROR_STOP=1 <<'SQL'
SELECT
  to_regclass('public.detections') AS detections,
  to_regclass('public.weather_observations') AS weather_observations,
  to_regclass('public.weather_forecasts') AS weather_forecasts,
  to_regclass('public.station_health_hourly') AS station_health_hourly,
  to_regclass('public.bird_activity_predictions') AS bird_activity_predictions,
  to_regclass('public.bird_species_predictions') AS bird_species_predictions,
  to_regclass('public.bird_activity_hourly') AS bird_activity_hourly,
  to_regclass('public.bird_species_hourly') AS bird_species_hourly;

SELECT count(*) AS restored_detections FROM detections;
SQL

cleanup
trap - EXIT

echo "Restore test passed."
