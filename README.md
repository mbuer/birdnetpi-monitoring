# BirdNET-Pi Monitoring

A reproducible monitoring and long-term data platform built around a BirdNET-Pi station.

BirdNET itself remains responsible for listening to the microphone and identifying birds. This repository surrounds that station with the infrastructure needed to collect, preserve, visualize, and eventually analyze the resulting data.

The project combines:

- BirdNET-Pi
- PostgreSQL
- Grafana Alloy
- Loki
- Grafana
- Open-Meteo
- Python
- Docker
- systemd

The main goal is not simply to build another BirdNET dashboard.

The longer-term goal is to create a durable dataset that connects bird activity with environmental conditions and can eventually support historical analysis and prediction.

---

## What This Project Answers

Today the system can help answer questions such as:

- What birds are being detected right now?
- Is the BirdNET station still running normally?
- What were the weather conditions during a detection?
- How does activity change over days, weeks, months, and seasons?
- How accurate were weather forecasts compared with what actually happened?
- Which conditions appear to increase or reduce activity?

Longer term, the same dataset can support questions such as:

- Which species are most likely to appear tomorrow morning?
- Does recent weather improve prediction beyond season and time of day?
- Does wind, precipitation, temperature, or cloud cover affect detection activity?
- Can forecast weather be used to predict likely bird activity before it occurs?

---

# Architecture

The system deliberately separates three different kinds of data.

## 1. BirdNET source data

BirdNET owns its native SQLite database:

    ~/BirdNET-Pi/scripts/birds.db

This remains the authoritative BirdNET source for completed detections.

The monitoring project does not modify this database.

---

## 2. Structured historical data

PostgreSQL stores durable, normalized records for analysis.

Current PostgreSQL tables:

    detections
    weather_observations
    weather_forecasts

PostgreSQL answers questions about what the system knows historically.

Think:

    What do we know?

---

## 3. Operational observability

Grafana Alloy collects logs and operational events.

Loki stores those events for Grafana.

This path answers questions about what the system is doing.

Think:

    What is happening?

Keeping PostgreSQL and Loki separate is intentional.

Loki is not the historical analytical database, and PostgreSQL is not intended to replace operational logging.

---

# Home Lab Architecture

The project has moved from a mostly Pi-local / Grafana Cloud design to a small centralized Home Lab architecture.

PostgreSQL and the local Loki / Grafana data path are now live on `ubuntu-infra`.

Current layout:

```text
BirdNET Raspberry Pi
|
|-- microphone / audio
|-- BirdNET analysis
|-- birds.db
|
|-- import_detections.py ----------> PostgreSQL
|-- weather.py --------------------> PostgreSQL
|-- forecast.py -------------------> PostgreSQL
|
`-- Grafana Alloy
    |--> Grafana Cloud Loki
    `--> Local Loki ---------------> Grafana OSS

ubuntu-infra (192.168.1.137)
|-- PostgreSQL
|-- Loki
|-- Prometheus
`-- Grafana OSS
```

Grafana Alloy currently sends operational logs to both Grafana Cloud Loki and local Loki. This dual-write period is intentional while the local path is validated.

The BirdNET Pi currently uses:

```text
192.168.1.136
```

The infrastructure VM currently uses:

```text
192.168.1.137
```

These addresses describe the current Home Lab deployment and should not be treated as universal configuration defaults.

---

# Responsibilities

## BirdNET Pi

The Raspberry Pi remains the edge device.

It owns:

- microphone capture
- BirdNET analysis
- BirdNET's native SQLite database
- detection synchronization
- weather collection
- weather forecast collection
- Grafana Alloy
- local operational logs

Keeping these responsibilities on the Pi means BirdNET can continue collecting data close to the source even as the centralized infrastructure evolves.

---

## ubuntu-infra

The Ubuntu infrastructure VM provides centralized services.

Current:

- PostgreSQL

Being migrated next:

- Loki

Related Home Lab services already running on the VM include:

- Prometheus
- Grafana

Grafana itself is managed through the separate:

    homelab-grafana

repository.

This separation keeps the BirdNET repository focused on BirdNET-specific data collection and infrastructure rather than owning the entire Home Lab monitoring stack.

---

# Bird Detection Data Path

BirdNET maintains:

    ~/BirdNET-Pi/scripts/birds.db

The synchronization path is:

    birds.db
       │
       ▼
    birdnet-db-sync.timer
       │
       ▼
    birdnet-db-sync.service
       │
       ▼
    collector/import_detections.py
       │
       ▼
    PostgreSQL
       │
       ▼
    detections

The synchronization runs approximately once per minute.

---

## Incremental synchronization

The importer does not repeatedly scan the full BirdNET history.

It stores the last processed SQLite row ID in:

    ~/.local/state/birdnet-db-sync/last_rowid

On subsequent runs, only newer source rows are processed.

This keeps the synchronization lightweight even as the historical dataset grows.

---

## Transaction safety

Synchronization state advances only after the PostgreSQL transaction succeeds.

Conceptually:

    read new BirdNET rows
            │
            ▼
    write PostgreSQL rows
            │
            ▼
       commit succeeds
            │
            ▼
      update last_rowid

If PostgreSQL is unavailable, the state does not advance and the next run can retry the same source records.

---

## SQLite rebuild protection

BirdNET may eventually recreate its SQLite database.

If the current SQLite maximum row ID becomes lower than the synchronization state, the importer assumes that the source database was rebuilt and starts scanning again from row zero.

PostgreSQL uniqueness constraints protect existing historical records from accidental duplication.

---

# Weather Observations

Current weather is collected from Open-Meteo by:

    weather/weather.py

The service currently collects approximately every 15 minutes.

Collected fields include:

- temperature
- dew point
- relative humidity
- mean sea-level pressure
- precipitation
- cloud cover
- wind speed
- wind gusts
- wind direction
- weather code
- day/night state
- sunrise
- sunset

The station timezone is:

    America/Los_Angeles

Weather observations are stored in:

    weather_observations

The collector also writes operational JSONL data to:

    /var/log/weather/weather.log

This gives the weather data two useful paths:

    structured history -> PostgreSQL
    operational events -> Alloy / Loki

---

# Weather Forecast History

Forecast collection is handled by:

    weather/forecast.py

and scheduled through:

    birdnet-forecast.timer
        │
        ▼
    birdnet-forecast.service
        │
        ▼
    weather/forecast.py
        │
        ▼
    PostgreSQL weather_forecasts

The collector stores snapshots of future weather forecasts.

Each record distinguishes between:

    forecast_created_at

and:

    forecast_for

This is important.

A prediction for tomorrow at 08:00 may appear in multiple forecast snapshots because the forecast changes as tomorrow approaches.

Those records are intentionally preserved.

This makes it possible to study:

- how forecasts change over time
- how forecasts compare with observations
- which forecast horizon is most useful
- bird activity predictions using only information that was actually available at prediction time

---

# PostgreSQL

PostgreSQL is now centralized on `ubuntu-infra`.

Deployment:

    deploy/ubuntu-infra/postgres/

Container:

    birdnet-postgres

Database:

    birdnet

Application role:

    birdnet

Schema:

    database/schema.sql

The Pi no longer relies on its local PostgreSQL instance for active ingestion.

The existing Pi PostgreSQL installation is being retained temporarily as a migration fallback.

---

## Portable database configuration

The Python collectors do not hard-code the production database host or password.

They read:

    BIRDNET_DB_HOST
    BIRDNET_DB_NAME
    BIRDNET_DB_USER
    BIRDNET_DB_PASSWORD

The current Pi loads these from:

    ~/.config/birdnet-monitoring/db.env

The real environment file is runtime configuration and must not be committed.

If the environment variables are not provided, the applications retain local defaults where appropriate.

---

# PostgreSQL Migration

Historical PostgreSQL data was migrated from the BirdNET Pi to `ubuntu-infra` using a PostgreSQL custom-format dump.

The migration was validated by comparing source and destination row counts.

Migration baseline:

    detections              7886
    weather_observations    1573
    weather_forecasts      17712

After the cutover, new detections and weather observations were confirmed to arrive in the centralized PostgreSQL instance.

The baseline numbers above are migration reference values, not expected current totals.

---

# PostgreSQL Network Access

The PostgreSQL container publishes TCP port:

    5432

Remote PostgreSQL authentication is currently restricted to the BirdNET Pi:

    192.168.1.136/32

The goal is to allow the edge collector to reach PostgreSQL without making the database generally available to the rest of the LAN.

Do not broaden PostgreSQL access without a reason.

---

# PostgreSQL Backups

The centralized database is backed up independently of Docker volumes and Git.

Backup script:

    backup/backup_infra_postgres.sh

Runtime backup location:

    /var/backups/birdnet-postgres

Backup format:

    PostgreSQL custom archive

The current systemd units are:

    birdnet-postgres-backup.service
    birdnet-postgres-backup.timer

The timer runs daily at:

    03:15 America/Los_Angeles

Current retention:

    14 days

The timer is persistent, allowing systemd to catch up after downtime.

Git contains the backup logic and service definitions.

Git does not contain database dumps.

---

## Backup limitations

These backups currently remain on `ubuntu-infra`.

They protect against:

- accidental data changes
- database corruption
- application mistakes
- failed migrations
- needing an earlier logical database state

They do not yet provide complete disaster recovery if the infrastructure VM or its underlying storage is lost.

A future improvement is to replicate backups to separate physical storage.

---

# Operational Logging and Loki

Grafana Alloy runs on the BirdNET Pi.

It currently collects:

- BirdNET systemd journal events
- parsed BirdNET detection logs
- weather JSONL logs

Operational logs are currently sent to both:

- Grafana Cloud Loki
- local Loki on `ubuntu-infra`

The local Loki path is live and has been verified in Grafana OSS.

Current flow:

```text
BirdNET Pi
    |
    v
Grafana Alloy
    |------------------> Grafana Cloud Loki
    |
    `------------------> Local Loki on ubuntu-infra
                              |
                              v
                         Grafana OSS
```

Local Loki currently uses a 30-day retention period.

The dual-write setup is intentional during validation. Grafana Cloud remains available as a reference while the local observability stack is proven stable.

Loki is currently exposed directly on port `3100` within the Home Lab. Network and authentication hardening remain future work.

---

# Grafana

The BirdNET dashboard now exists in two repository variants:

```text
grafana/Bird Home - Burbank Cloud.json
grafana/Bird Home - Burbank Local.json
```

`Bird Home - Burbank Cloud.json` is the original Grafana Cloud reference export.

`Bird Home - Burbank Local.json` is the active Grafana OSS version. It keeps the existing dashboard design while using the local Home Lab datasources.

Local Grafana is maintained separately in:

```text
homelab-grafana
```

The local Grafana instance currently uses:

- Loki for BirdNET operational logs and recent detection activity
- Infinity for Open-Meteo current and forecast data
- Prometheus for infrastructure metrics
- PostgreSQL as a separate structured-data source for future historical analysis and prediction work

The Bird Home dashboard itself remains primarily Loki-based. PostgreSQL is not intended to replace Loki in this operational dashboard.

The local dashboard has been verified against the local Loki datasource and the required Infinity plugin is installed.

The goal remains to preserve the useful existing dashboard rather than rebuild it from scratch.

---

# Why Grafana and PostgreSQL Both Matter

The dashboard ultimately has two complementary jobs.

## Operational view

From Loki:

- current BirdNET logs
- recent detections
- service activity
- weather logging
- troubleshooting information

## Historical view

From PostgreSQL:

- long time-range detection statistics
- species trends
- weather correlations
- forecast accuracy
- seasonal patterns
- future prediction inputs

This distinction should remain visible in future dashboard design.

---

# Repository Structure

```text
birdnetPi-monitoring/
|
|-- README.md
|-- AGENTS.md
|-- .gitignore
|
|-- alloy/
|   |-- config.alloy
|   `-- default-alloy
|
|-- backup/
|   |-- backup_postgres.sh
|   `-- backup_infra_postgres.sh
|
|-- collector/
|   `-- import_detections.py
|
|-- database/
|   |-- README.md
|   `-- schema.sql
|
|-- deploy/
|   `-- ubuntu-infra/
|       |-- README.md
|       |-- postgres/
|       `-- loki/
|
|-- docs/
|
|-- grafana/
|   |-- Bird Home - Burbank Cloud.json
|   `-- Bird Home - Burbank Local.json
|
|-- systemd/
|
`-- weather/
    |-- weather.py
    |-- forecast.py
    `-- requirements.txt
```

---

# Current Migration Status

## Completed

- BirdNET structured detection synchronization
- weather observation collection
- historical weather forecast collection
- PostgreSQL schema
- Pi-local PostgreSQL historical dataset
- centralized PostgreSQL deployment on `ubuntu-infra`
- historical database migration
- remote detection ingestion
- remote weather ingestion
- remote forecast configuration
- PostgreSQL access restriction
- daily centralized PostgreSQL backups
- systemd-based backup scheduling
- local Loki deployment on `ubuntu-infra`
- local Loki storage and health verification
- BirdNET journal ingestion into local Loki
- weather log ingestion into local Loki
- local Loki datasource in Grafana OSS
- Infinity datasource and Open-Meteo support
- local Bird Home dashboard adaptation and verification

## Transitional

Grafana Alloy currently writes operational logs to both Grafana Cloud Loki and local Loki.

This dual-write period is intentional. Grafana Cloud remains available as a reference while the local stack is observed over time.

The next migration decision is to retire the Grafana Cloud Loki output only after local operation has been proven stable.

---

# Future Work

## Grafana

- build long-term activity panels
- correlate detections with weather
- visualize forecast versus actual conditions
- create species-specific historical views
- monitor BirdNET infrastructure health
- add useful alerting where appropriate

## Database

- add database health monitoring
- review long-term retention requirements
- periodically test restore procedures
- remove the old Pi PostgreSQL installation after the migration has proven stable

## Backups

- replicate PostgreSQL dumps off `ubuntu-infra`
- keep at least one copy on physically separate storage
- document and periodically test a full restore

## Configuration

- gradually move deployment-specific constants out of source where useful
- retain safe defaults for simple development
- avoid turning the project into an unnecessarily complex configuration framework

## Analysis

Potential future analysis includes:

- activity by hour of day
- activity relative to sunrise and sunset
- weather correlations
- species seasonality
- forecast accuracy
- detection confidence behavior
- time-series models
- species-specific prediction
- bird activity forecasts

The goal is to build these features on top of the durable PostgreSQL dataset rather than reconstruct historical data from operational logs.

---

# Design Principles

A few decisions guide the project.

## Keep BirdNET independent

The monitoring stack should not interfere with BirdNET's core job.

If Grafana, Loki, PostgreSQL, or the Home Lab infrastructure is temporarily unavailable, BirdNET should still be able to detect birds and maintain its own source database.

## Keep authoritative source data intact

Do not modify `birds.db` as part of monitoring.

Read it and synchronize from it.

## Separate observability from history

Use:

    Loki -> operational logs

and:

    PostgreSQL -> structured historical data

Do not force one datastore to perform both roles.

## Keep infrastructure reproducible

Git should contain:

- source code
- schema
- Docker configuration
- systemd definitions
- provisioning configuration
- documentation

Git should not contain:

- passwords
- `.env` files
- database dumps
- Docker volumes
- runtime logs
- Alloy state
- SSH private keys

## Prefer understandable infrastructure

This is a Home Lab project.

The architecture should remain understandable enough that the entire system can be rebuilt and debugged without depending on hidden state.

---

# Project Direction

The project began as a way to visualize BirdNET detections.

It is becoming a small environmental data platform:

    BirdNET
       +
    Weather
       +
    Historical Forecasts
       │
       ▼
    PostgreSQL
       │
       ├── historical analysis
       ├── Grafana visualization
       └── prediction / ML

At the same time:

    BirdNET services
       +
    Weather logs
       │
       ▼
    Alloy
       │
       ▼
    Loki
       │
       ▼
    Grafana

These two paths are intentionally complementary.

The immediate goal is a completely local, reproducible Home Lab deployment.

The longer-term goal is to turn the accumulated history into something useful for understanding — and eventually predicting — bird activity.
