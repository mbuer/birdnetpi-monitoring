# ubuntu-infra BirdNET Deployment

This directory contains the server-side BirdNET deployment for the Home Lab infrastructure VM.

The goal is to keep the BirdNET Raspberry Pi focused on sensing and collection while moving durable storage and observability services to a more capable centralized host.

---

# Hosts

## BirdNET Pi

Current address:

```text
192.168.1.136
```

Responsibilities:

- microphone and audio
- BirdNET analysis
- BirdNET native `birds.db`
- detection synchronization
- weather collection
- weather forecast collection
- Grafana Alloy
- local logs

---

## ubuntu-infra

Current address:

```text
192.168.1.137
```

Responsibilities:

- PostgreSQL
- Loki
- Prometheus
- Grafana OSS
- Python ML experiments and hourly prediction/scoring

Grafana is deployed through the separate:

```text
homelab-grafana
```

repository.

---

# Current Architecture

```text
BirdNET Pi
|
|-- birds.db
|    `-- import_detections.py ------> PostgreSQL
|-- weather.py --------------------> PostgreSQL
|-- forecast.py ------------------> PostgreSQL
|
`-- Grafana Alloy
    |--> Grafana Cloud Loki
    `--> Local Loki ---------------> Grafana OSS

ubuntu-infra
|-- PostgreSQL
|-- Loki
|-- Prometheus
`-- Grafana OSS
```

PostgreSQL is the structured historical datastore.

Loki is the operational log datastore.

Grafana Alloy currently dual-writes operational logs to Grafana Cloud Loki and the local Loki instance during validation.

Grafana OSS uses Loki for the Bird Home operational dashboard. PostgreSQL is available separately for structured historical analysis and the Prediction Lab.

---

# Deployment Layout

```text
deploy/ubuntu-infra/
|
|-- README.md
|-- postgres/
|   |-- compose.yaml
|   |-- .env.example
|   `-- .env          # runtime only, ignored
|
`-- loki/
    |-- compose.yaml
    `-- loki-config.yaml
```

PostgreSQL and Loki are both deployed on `ubuntu-infra`.

---

# PostgreSQL

Status:

    DEPLOYED

Container:

    birdnet-postgres

Image:

    postgres:17.2

Database:

    birdnet

Application role:

    birdnet

Published port:

    5432

Persistent storage:

    Docker named volume

Schema initialization:

    database/schema.sql

Only the base schema is mounted. The hourly view, prediction table, and Grafana grants require separate application; see [database setup](../../database/README.md#initializing-a-new-database). Initialization does not rerun on an existing volume.

The schema is mounted into:

    /docker-entrypoint-initdb.d/

during initial database creation.

---

# PostgreSQL Migration

The previous PostgreSQL dataset ran on the BirdNET Pi.

Migration workflow:

1. create custom-format dump on Pi
2. validate dump with `pg_restore -l`
3. record source row counts
4. copy dump to `ubuntu-infra`
5. restore historical data
6. compare destination counts
7. reconfigure clients
8. confirm live row growth

Migration checkpoint:

    detections              7886
    weather_observations    1573
    weather_forecasts      17712

All counts matched after restore.

Live detection and weather ingestion were subsequently confirmed.

---

# BirdNET Client Configuration

The Pi uses:

    /home/birduser/.config/birdnet-monitoring/db.env

Variables:

    BIRDNET_DB_HOST
    BIRDNET_DB_NAME
    BIRDNET_DB_USER
    BIRDNET_DB_PASSWORD

The installed systemd services load this file.

The environment file is runtime state and must not be committed.

---

# PostgreSQL Access Control

The database accepts remote application connections from:

    192.168.1.136/32

using:

    scram-sha-256

The Pi has been verified to connect successfully after the restriction was applied.

That rule covers the Pi only. Grafana also connects through its Docker network, and ML jobs default to the host's loopback address. Preserve the actual live authentication rules; they are not captured in this Compose file.

If addressing changes later, update the relevant client rules deliberately.

Do not simply reopen PostgreSQL to the entire network.

---

# PostgreSQL Backups

Backup script:

    backup/backup_infra_postgres.sh

Runtime destination:

    /var/backups/birdnet-postgres

systemd service:

    birdnet-postgres-backup.service

systemd timer:

    birdnet-postgres-backup.timer

Schedule:

    03:15 America/Los_Angeles

Retention:

    14 days

The backup job produces PostgreSQL custom-format archives.

Example validation:

    pg_restore -l \
      /var/backups/birdnet-postgres/birdnet-YYYY-MM-DD_HH-MM-SS.dump

---

# Useful PostgreSQL Commands

## Container status

    docker ps --filter name=birdnet-postgres

## Logs

    docker logs birdnet-postgres --tail 50

## Database tables

    docker exec birdnet-postgres \
      psql -U birdnet -d birdnet -c '\dt'

## Current row counts

    docker exec birdnet-postgres \
      psql -U birdnet -d birdnet -c "
    SELECT
      (SELECT count(*) FROM detections) AS detections,
      (SELECT count(*) FROM weather_observations) AS weather_observations,
      (SELECT count(*) FROM weather_forecasts) AS weather_forecasts;
    "

## Backup timer

    systemctl status birdnet-postgres-backup.timer --no-pager

## Existing backups

    ls -lh /var/backups/birdnet-postgres

---

# Loki

Status:

```text
DEPLOYED
```

Container:

```text
birdnet-loki
```

Image:

```text
grafana/loki:3.5.5
```

Published port:

```text
3100
```

Retention:

```text
30 days
```

Persistent storage:

```text
Docker named volume
```

Repository configuration:

```text
deploy/ubuntu-infra/loki/
```

Grafana Alloy on the BirdNET Pi currently sends operational logs to both Grafana Cloud Loki and local Loki on `ubuntu-infra`.

The local path has been verified for:

- BirdNET journal ingestion
- parsed detection logs
- weather JSONL ingestion
- persistence across container restart
- Grafana OSS queries

The reported live dual-write period is intentional. However, the committed `alloy/config.alloy` still forwards only to Cloud and contains literal credential placeholders. Do not use it to replace the working installed configuration until reconciled.

Historical Grafana Cloud Loki data is not being migrated into local Loki.

Loki is currently exposed directly on port `3100` within the Home Lab. Network and authentication hardening remain future work.

---

# Grafana Integration

Grafana itself is not deployed from this repository.

Local Grafana lives in the separate:

```text
homelab-grafana
```

repository.

The BirdNET repository owns:

- BirdNET dashboard exports
- BirdNET-specific datasource expectations
- BirdNET data architecture

The Grafana repository owns:

- Grafana container deployment
- global datasource configuration
- plugin installation
- local dashboard operation

The BirdNET dashboard exports are:

```text
grafana/Bird Home - Burbank Cloud.json
grafana/Bird Home - Burbank Local.json
grafana/bird-home-prediction-lab.json
```

`Bird Home - Burbank Cloud.json` is the original Grafana Cloud reference export.

`Bird Home - Burbank Local.json` is the active Grafana OSS version.

The local Grafana instance currently uses:

- Loki for BirdNET operational logs and recent detection activity
- Infinity for Open-Meteo current and forecast data
- Prometheus for infrastructure metrics
- PostgreSQL for structured history and Prediction Lab

The Bird Home dashboard remains primarily Loki-based. PostgreSQL is not intended to replace Loki in this operational dashboard.

---

# PostgreSQL + Grafana Integration

A dedicated read-only Grafana role is already configured for PostgreSQL.

Grafana can query the `birdnet` database without reusing the BirdNET ingestion role.

PostgreSQL is reserved for structured historical and analytical work such as:

- long-term activity analysis
- bird and weather correlations
- forecast-versus-observation analysis
- seasonal patterns
- stored predictions and experimental accuracy comparisons

---
# Prometheus Integration

Prometheus already runs on `ubuntu-infra`.

Future BirdNET infrastructure monitoring can include:

- PostgreSQL exporter
- Loki metrics
- Alloy health
- backup success
- backup age
- Pi availability
- database growth
- ingestion freshness

These are future observability improvements and are not required for the current BirdNET data path.

---

# Rebuild Order

A practical rebuild sequence for a replacement infrastructure VM is:

1. install and verify `ubuntu-infra`
2. clone the Home Lab repositories
3. restore local secrets and environment files
4. deploy PostgreSQL
5. restore the latest validated PostgreSQL dump
6. verify BirdNET collectors can reach PostgreSQL
7. deploy Loki
8. deploy/provision Grafana through `homelab-grafana`
9. verify Alloy log delivery
10. verify Grafana datasources and dashboards
11. apply/verify the hourly view, prediction table, and Grafana grants; recreate the ML virtual environment
12. install the completed-hour v2 fix, inspect pending/scored rows, and restore the ML service/timer deliberately
13. verify backups and timers

BirdNET itself should remain functional throughout an infrastructure rebuild because its native SQLite database stays on the Pi.

---

# Recovery Philosophy

The deployment should be reproducible from:

    Git
      +
    secrets
      +
    database backup

Git contains configuration.

Secrets remain outside Git.

Persistent data is protected separately.

A replacement `ubuntu-infra` VM should eventually be rebuildable without reconstructing the architecture from memory.

---

# Migration Status

## Completed

- PostgreSQL Compose deployment
- PostgreSQL schema initialization
- historical database migration
- Pi client environment configuration
- remote detection ingestion
- remote weather ingestion
- remote forecast configuration
- PostgreSQL network restriction
- centralized database backup script
- daily backup systemd service
- daily backup systemd timer
- local Loki deployment
- local Loki storage and health verification
- BirdNET journal ingestion into local Loki
- weather JSONL ingestion into local Loki
- local Grafana Loki datasource
- Infinity datasource and Open-Meteo support
- Bird Home local dashboard adaptation and verification
- read-only Grafana PostgreSQL role
- Grafana PostgreSQL datasource

## Transitional

Grafana Alloy currently writes operational logs to both Grafana Cloud Loki and local Loki.

This dual-write period is intentional. Grafana Cloud remains available as a reference while the local stack is observed over time.

Retire the Grafana Cloud Loki output only after local operation has been proven stable.

## Later

- PostgreSQL metrics
- Loki metrics
- off-host PostgreSQL backups
- restore testing
- removal of Pi-local PostgreSQL
- historical analysis
- reliable completed-hour prediction and scoring

---

# Operational Principle

Do not remove a working previous component simply because the replacement has started working.

For major migrations:

1. deploy the replacement
2. verify the replacement
3. observe it
4. retain rollback options
5. retire the old component only when confidence is high

This approach was used for the PostgreSQL migration and should also be used for Loki and Grafana.

# ML Prediction Cycle

The checked-in service runs as `infra` in `/opt/birdnetpi-monitoring`, using the root `.venv` through shell wrappers. It requires Docker. The wrappers obtain the database password from the local container if no password environment variable is present; the service currently has no `EnvironmentFile`.

`OnCalendar=*-*-* *:10:00` runs at minute 10 each hour using the host timezone. `Persistent=true` triggers catch-up activation after downtime, not reconstruction of all missed forecasts. Docker service startup ordering does not establish database readiness.

**Before enabling this on a replacement host:** install the completed-hour v2 code described in [the ML README](../../ml/README.md). It uses completed inputs with a ten-minute grace period, rejects stale/gapped recent input, and scores v2 only after the target ends plus ten minutes. Legacy scores remain untouched. A successful timer run still does not establish full ingestion completeness.

After installing the accompanying fix and verifying schema, permissions, virtual environment and script paths, install the units:

```bash
cd /opt/birdnetpi-monitoring
sudo install -m 0644 systemd/birdnet-ml-prediction.service systemd/birdnet-ml-prediction.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now birdnet-ml-prediction.timer
systemctl list-timers birdnet-ml-prediction.timer --all
journalctl -u birdnet-ml-prediction.service -n 50 --no-pager
```

For the current deployment, inspect without creating new predictions:

```bash
systemctl cat birdnet-ml-prediction.service birdnet-ml-prediction.timer
systemctl status birdnet-ml-prediction.timer --no-pager
docker exec birdnet-postgres psql -U birdnet -d birdnet -c "SELECT prediction_created_at, predicted_hour, model, actual_activity, scored_at FROM bird_activity_predictions ORDER BY predicted_hour DESC LIMIT 10;"
```

A manual `./ml/hourly_prediction_cycle.sh` writes scores and predictions. It is not a read-only health check.

## Recovery details

Database dumps include prediction records and the regular view, but not global roles or runtime secrets. Recreate roles before restoring ownership/grants. Keep predictions as historical evidence; do not regenerate old forecasts and call them live results.

Before resuming collectors after database restoration, reconcile the Pi importer checkpoint with the restored data. A checkpoint newer than the backup can skip detections lost in the restore. Preserve then deliberately reset the checkpoint for replay if needed; uniqueness constraints deduplicate retained SQLite records.

The central backup script writes directly to its final filename and does not validate archives or publish atomically. A failed dump can leave a partial file. Archive listing alone is not a full restore test.

## Dashboard checks

See [Grafana README](../../grafana/README.md) for export formats, datasource mapping and Prediction Lab metric scopes. Its PostgreSQL UID is `afy5j1yt18b9cb`; the view and prediction table need SELECT grants for `grafana_reader`.

The ML service needs bounded execution, database readiness/retry handling, explicit runtime configuration, and freshness/failure monitoring in a follow-up code change.
