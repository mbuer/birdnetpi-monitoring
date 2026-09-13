# ubuntu-infra BirdNET Deployment

This directory contains the server-side BirdNET deployment for the Home Lab infrastructure VM.

The goal is to keep the BirdNET Raspberry Pi focused on sensing and collection while moving durable storage and observability services to a more capable centralized host.

---

# Hosts

## BirdNET Pi

Current address:

    192.168.1.136

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

    192.168.1.137

Responsibilities:

Current:

- PostgreSQL

Next:

- Loki

Related services already hosted on the VM:

- Prometheus
- Grafana

Grafana is deployed through the separate:

    homelab-grafana

repository.

---

# Target Architecture

    BirdNET Pi
    │
    ├── birds.db
    │      │
    │      ▼
    │   import_detections.py
    │      │
    │      └────────────► PostgreSQL
    │
    ├── weather.py ─────► PostgreSQL
    │
    ├── forecast.py ────► PostgreSQL
    │
    └── Grafana Alloy
           │
           ▼
          Loki
           │
           ▼
        Grafana

                ubuntu-infra

PostgreSQL is the structured historical datastore.

Loki is the operational log datastore.

Grafana visualizes both.

---

# Deployment Layout

    deploy/ubuntu-infra/
    │
    ├── README.md
    ├── postgres/
    │   ├── compose.yaml
    │   ├── .env.example
    │   └── .env          # runtime only, ignored
    │
    └── loki/
        └── ...

The `loki` deployment is the next migration phase.

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

# Loki Migration

Status:

    NEXT

The current Alloy configuration still represents the previous Grafana Cloud logging architecture.

The target is:

    BirdNET Pi Alloy
           │
           ▼
    Loki on ubuntu-infra
           │
           ▼
    local Grafana

Planned migration:

1. create local Loki configuration
2. deploy Loki on `ubuntu-infra`
3. verify `/ready`
4. verify persistent storage
5. confirm Loki survives container restart
6. update Pi Alloy destination
7. verify BirdNET journal ingestion
8. verify weather JSONL ingestion
9. add Loki datasource to local Grafana
10. migrate/adapt the BirdNET dashboard
11. observe the new path for several days
12. retire Grafana Cloud only after confidence is established

Historical Grafana Cloud Loki data does not necessarily need to be migrated.

The old Cloud deployment can remain available temporarily for historical reference while the local Loki database begins at cutover.

---

# Grafana Migration

Grafana itself is not deployed from this repository.

Local Grafana lives in the Home Lab Grafana project.

The BirdNET repository owns:

- BirdNET dashboard export
- BirdNET-specific datasource expectations
- BirdNET data architecture

The Grafana repository owns:

- Grafana container deployment
- Grafana provisioning
- global datasource provisioning
- local dashboard loading

The existing dashboard export is:

    grafana/Bird Home - Burbank.json

Before copying it directly into local provisioning, inspect:

- datasource UIDs
- Loki datasource references
- Infinity datasource/plugin requirements
- Grafana Cloud assumptions
- direct Open-Meteo calls

The objective is to adapt the existing dashboard rather than recreate it manually.

---

# Planned PostgreSQL + Grafana Integration

After local Loki/Grafana migration is stable:

1. create a read-only PostgreSQL role
2. add PostgreSQL datasource to Grafana
3. add historical panels
4. build bird/weather correlation views
5. add forecast-versus-observation analysis

The ingestion role should not be reused as the Grafana query role.

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

This is useful, but it should follow the successful Loki/Grafana migration rather than block it.

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

## Next

- Loki deployment
- Alloy local Loki cutover
- local Grafana Loki datasource
- BirdNET dashboard migration

## Later

- Grafana PostgreSQL datasource
- read-only Grafana database role
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
