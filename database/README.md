# BirdNET PostgreSQL Database

PostgreSQL is the durable structured datastore for the BirdNET monitoring project.

It stores historical bird detections, actual weather observations, and historical weather forecast snapshots.

PostgreSQL complements Loki:

    Loki        -> operational logs and observability
    PostgreSQL  -> structured historical data and analysis

The database is intended to accumulate months and eventually years of station history.

---

# Current Deployment

The primary PostgreSQL instance runs on:

    ubuntu-infra

Current Home Lab address:

    192.168.1.137

Docker container:

    birdnet-postgres

Database:

    birdnet

Application role:

    birdnet

TCP port:

    5432

Deployment configuration:

    deploy/ubuntu-infra/postgres/

Schema:

    database/schema.sql

The BirdNET Pi currently connects from:

    192.168.1.136

---

# Tables

## detections

Stores BirdNET detections imported from BirdNET's native SQLite database.

Source:

    ~/BirdNET-Pi/scripts/birds.db

Importer:

    collector/import_detections.py

Important fields include:

- detection timestamp
- station ID
- common species name
- scientific species name
- confidence
- latitude
- longitude
- cutoff
- week
- sensitivity
- overlap
- source filename
- source SQLite row ID

The BirdNET SQLite database remains the authoritative source for completed detections.

PostgreSQL provides the durable analytical copy.

---

## weather_observations

Stores actual weather conditions collected from Open-Meteo.

Important fields include:

- observation timestamp
- station ID
- temperature
- dew point
- relative humidity
- atmospheric pressure
- precipitation
- cloud cover
- wind speed
- wind gusts
- wind direction
- weather code
- day/night state
- sunrise
- sunset

The uniqueness rule prevents duplicate storage when Open-Meteo returns the same current observation more than once.

---

## weather_forecasts

Stores snapshots of future weather forecasts.

Collector:

    weather/forecast.py

The important timestamps are:

    forecast_created_at
    forecast_for

`forecast_created_at` is when the snapshot was collected.

`forecast_for` is the future hour being predicted.

The same `forecast_for` time can therefore appear in multiple snapshots.

This is intentional and allows analysis of how a forecast changed as the target time approached.

Potential uses include:

- forecast accuracy analysis
- identifying useful forecast horizons
- comparing predicted and actual weather
- future bird-activity prediction using information available at prediction time

---

# Detection Synchronization

The detection path is:

    BirdNET birds.db
          │
          ▼
    birdnet-db-sync.timer
          │
          ▼
    birdnet-db-sync.service
          │
          ▼
    import_detections.py
          │
          ▼
    PostgreSQL detections

The timer runs approximately once per minute.

---

## Incremental state

The importer stores its last processed source row ID in:

    ~/.local/state/birdnet-db-sync/last_rowid

Normal runs only inspect rows newer than that value.

The state advances only after the PostgreSQL transaction succeeds.

This allows failed imports to be retried safely.

---

## Source database rebuild handling

If BirdNET recreates its SQLite database, source row IDs may restart at lower values.

The importer detects:

    SQLite MAX(rowid) < stored last_rowid

and restarts synchronization from row zero.

Existing PostgreSQL uniqueness constraints prevent normal historical records from being inserted twice.

---

# Connection Configuration

The collectors use environment-based PostgreSQL configuration.

Supported variables:

    BIRDNET_DB_HOST
    BIRDNET_DB_NAME
    BIRDNET_DB_USER
    BIRDNET_DB_PASSWORD

The current Pi loads these values through systemd from:

    /home/birduser/.config/birdnet-monitoring/db.env

Example structure:

    BIRDNET_DB_HOST=database-host
    BIRDNET_DB_NAME=birdnet
    BIRDNET_DB_USER=birdnet
    BIRDNET_DB_PASSWORD=...

The real password must never be committed to Git.

---

# Initializing a New Database

The Home Lab deployment normally initializes the schema automatically through the PostgreSQL container.

The schema file is:

    database/schema.sql

For a manual database, create the role and database first and then apply:

    psql \
      -h DATABASE_HOST \
      -U birdnet \
      -d birdnet \
      -f database/schema.sql

Verify:

    psql \
      -h DATABASE_HOST \
      -U birdnet \
      -d birdnet \
      -c '\dt'

Expected tables:

    detections
    weather_observations
    weather_forecasts

---

# Current Migration

The original structured database ran locally on the BirdNET Pi.

It was migrated to `ubuntu-infra` using:

    pg_dump -Fc

and restored into the centralized PostgreSQL instance.

The source dump was validated with:

    pg_restore -l

Migration baseline row counts were:

    detections              7886
    weather_observations    1573
    weather_forecasts      17712

Destination row counts matched exactly.

After migration, live detection and weather ingestion were confirmed by observing the destination row counts increase.

These values are historical migration checkpoints and are expected to become outdated as new records arrive.

---

# Network Security

The PostgreSQL Docker service currently publishes:

    5432/tcp

PostgreSQL host authentication is restricted to the BirdNET Pi:

    192.168.1.136/32

Authentication uses:

    scram-sha-256

Do not replace this with a broad:

    host all all all ...

rule without a specific reason.

If the Pi receives a new address, update the database access rule deliberately rather than broadly opening the service.

---

# Backups

The centralized database is backed up using:

    backup/backup_infra_postgres.sh

Runtime destination:

    /var/backups/birdnet-postgres

Backup format:

    PostgreSQL custom archive

Example:

    birdnet-2026-09-13_15-22-15.dump

The backup can be inspected with:

    pg_restore -l backup.dump

---

## Schedule

systemd units:

    birdnet-postgres-backup.service
    birdnet-postgres-backup.timer

Current schedule:

    03:15 America/Los_Angeles

The timer is persistent.

Retention:

    14 days

Old matching dumps are automatically removed.

---

# Restore Procedure

Do not test restore procedures directly against the live production database.

A safe general workflow is:

1. identify the desired dump
2. validate it with `pg_restore -l`
3. create a temporary test database
4. restore into the temporary database
5. verify tables and row counts
6. only then plan any production restore

Example inspection:

    pg_restore -l \
      /var/backups/birdnet-postgres/birdnet-YYYY-MM-DD_HH-MM-SS.dump

The project should periodically perform a real test restore into a temporary database.

A backup that has never been restored is not fully proven.

---

# Backup Scope

The PostgreSQL custom-format dump protects the logical database contents.

It does not back up:

- BirdNET audio
- BirdNET's native `birds.db`
- Docker images
- Grafana dashboards outside Git
- Loki data
- the VM itself
- operating system configuration not represented in Git

Those concerns should be handled separately.

---

# Disaster Recovery

The current dumps live on the same infrastructure VM as PostgreSQL.

This is useful but not sufficient for complete disaster recovery.

A future improvement should copy backups to physically separate storage such as:

- an external backup drive
- NAS
- another server
- remote storage

At least one backup copy should eventually survive the loss of `ubuntu-infra`.

---

# Grafana Access

Grafana does not yet require direct PostgreSQL access for the current BirdNET dashboard migration.

The planned historical dashboard phase should use a dedicated read-only PostgreSQL role rather than the `birdnet` ingestion role.

Target model:

    birdnet
        -> collector write role

    grafana_birdnet
        -> read-only visualization role

That work should happen when PostgreSQL is connected to Grafana.

---

# Monitoring

Useful future PostgreSQL monitoring includes:

- database availability
- database size
- row growth
- backup success
- age of newest backup
- connection count
- failed connections
- table growth
- query performance if needed

Prometheus already exists on `ubuntu-infra`, so PostgreSQL metrics can later be integrated into the existing monitoring stack.

---

# Data Ownership

The project intentionally distinguishes source and derived data.

## Authoritative source

Bird detections:

    BirdNET birds.db

## Durable analytical copy

    PostgreSQL detections

## External environmental source

    Open-Meteo

## Historical environmental copy

    PostgreSQL weather_observations
    PostgreSQL weather_forecasts

This distinction matters during recovery and troubleshooting.

PostgreSQL is important, but BirdNET's own source database should not be modified merely to make the monitoring stack easier.

---

# Security Rules

Never commit:

- PostgreSQL passwords
- `.env` files
- `db.env`
- database dumps
- private SSH keys
- Grafana tokens
- Grafana Cloud credentials

The repository should contain enough configuration to rebuild the database service without containing production credentials or live data.

---

# Future Database Work

Planned improvements include:

- read-only Grafana role
- Grafana PostgreSQL datasource
- historical activity dashboards
- database health metrics
- backup age monitoring
- off-host backup replication
- periodic restore testing
- eventual removal of the old Pi PostgreSQL installation
- analysis views or materialized views if useful
- long-term bird/weather correlation work
- forecast accuracy analysis
- prediction datasets

Avoid premature database complexity.

Add indexes, derived tables, or materialized views when actual query patterns justify them.
