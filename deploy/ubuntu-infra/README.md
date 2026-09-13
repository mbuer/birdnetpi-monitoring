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

Grafana OSS uses Loki for the Bird Home operational dashboard. PostgreSQL is available separately for structured historical analysis and future prediction work.

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

If addressing changes later, update this rule deliberately.

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

The dual-write period is intentional. Grafana Cloud remains available as a reference while the local stack is observed over time.

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
```

`Bird Home - Burbank Cloud.json` is the original Grafana Cloud reference export.

`Bird Home - Burbank Local.json` is the active Grafana OSS version.

The local Grafana instance currently uses:

- Loki for BirdNET operational logs and recent detection activity
- Infinity for Open-Meteo current and forecast data
- Prometheus for infrastructure metrics
- PostgreSQL for structured historical data and future analysis

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
- future prediction work

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
11. verify backups and timers

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
- prediction work

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
