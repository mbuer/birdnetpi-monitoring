# AGENTS.md

Guidance for automated coding agents and future development sessions working in this repository.

---

# Project Purpose

This repository contains the monitoring, structured data collection, and Home Lab deployment surrounding a BirdNET-Pi station.

BirdNET itself is not part of this repository.

Do not attempt to replace or absorb BirdNET's core application into this project.

---

# Architecture

## BirdNET Pi

The Raspberry Pi is the edge device.

It owns:

- microphone/audio capture
- BirdNET analysis
- BirdNET native SQLite database
- detection synchronization
- weather collection
- weather forecast collection
- Grafana Alloy
- local operational logs

BirdNET's native database is:

    ~/BirdNET-Pi/scripts/birds.db

Treat this as authoritative source data.

Monitoring code should read from it, not modify it.

---

## ubuntu-infra

The infrastructure VM owns centralized services.

Current:

- PostgreSQL

Next:

- Loki

Related Home Lab services:

- Prometheus
- Grafana

Grafana itself is maintained in the separate:

    homelab-grafana

repository.

Do not move the Grafana deployment into this repository unless the architecture is explicitly changed.

---

# Data Roles

Keep these responsibilities separate.

## BirdNET SQLite

Authoritative BirdNET detection source.

## PostgreSQL

Durable structured historical and analytical data.

Current tables:

    detections
    weather_observations
    weather_forecasts

## Loki

Operational logs and observability.

## Grafana

Visualization layer across observability and historical data.

Do not treat Loki as the permanent structured historical database.

Do not turn PostgreSQL into a replacement for operational logging.

---

# PostgreSQL

Production BirdNET PostgreSQL runs on `ubuntu-infra`.

Current deployment:

    deploy/ubuntu-infra/postgres/

Container:

    birdnet-postgres

Database:

    birdnet

Application role:

    birdnet

Applications obtain database configuration from:

    BIRDNET_DB_HOST
    BIRDNET_DB_NAME
    BIRDNET_DB_USER
    BIRDNET_DB_PASSWORD

Do not hard-code production passwords into Python source.

Avoid hard-coding deployment-specific addresses when environment configuration is reasonable.

---

# Secrets

Never commit:

- PostgreSQL passwords
- Grafana passwords
- Grafana Cloud tokens
- `.env` files
- `db.env`
- database dumps
- SSH private keys
- API tokens

Commit examples such as:

    .env.example

when useful.

Examples must contain placeholders, not real secrets.

---

# Runtime State

Keep runtime state outside Git.

Examples:

- PostgreSQL Docker volumes
- Loki storage
- Alloy state
- logs
- database dumps
- synchronization state
- generated cache files

Git should contain enough configuration to recreate services, not their live state.

---

# Pi Service Management

Pi collectors and scheduled jobs are managed with systemd.

When installed systemd units change, update the corresponding files under:

    systemd/

Do not fix only `/etc/systemd/system/...` and leave the repository templates stale.

---

# Server Deployment

Prefer Docker Compose for server-side stateful services where practical.

Current example:

    deploy/ubuntu-infra/postgres/compose.yaml

Deployment configuration should be:

- reproducible
- understandable
- version controlled
- secret-free
- explicit about persistent storage
- explicit about health checks

Prefer pinned container versions over floating `latest` tags when a tested version is known.

---

# Database Changes

Protect historical data.

Before destructive or migration-related database work:

1. create a PostgreSQL dump
2. validate the dump with `pg_restore -l`
3. record useful row counts
4. perform the change
5. verify destination row counts
6. verify live ingestion afterward

Do not remove the old Pi PostgreSQL installation until centralized PostgreSQL has been proven stable for a reasonable period.

---

# Backups

Current centralized backup script:

    backup/backup_infra_postgres.sh

Runtime backups:

    /var/backups/birdnet-postgres

Current retention:

    14 days

Backup systemd units:

    birdnet-postgres-backup.service
    birdnet-postgres-backup.timer

A backup should eventually exist outside the same VM/storage as the database.

When changing backup logic, preserve restore compatibility and document the change.

---

# Current Migration State

Completed:

- PostgreSQL deployed on `ubuntu-infra`
- historical PostgreSQL data migrated
- detection collector configured for remote PostgreSQL
- weather collector configured for remote PostgreSQL
- forecast collector configured for remote PostgreSQL
- PostgreSQL access restricted to the BirdNET Pi
- daily centralized PostgreSQL backups configured

Next:

- deploy local Loki
- repoint Alloy from Grafana Cloud to local Loki
- verify log ingestion
- connect local Grafana to Loki
- migrate/adapt the BirdNET dashboard
- verify local observability
- retire Grafana Cloud dependencies

Later:

- read-only Grafana PostgreSQL role
- Grafana PostgreSQL datasource
- historical dashboards
- PostgreSQL monitoring
- Loki monitoring
- off-host backups
- restore testing
- remove Pi-local PostgreSQL
- historical analysis
- prediction/ML

---

# Loki Migration Rules

Do not immediately destroy the Grafana Cloud path.

For the Loki migration:

1. deploy local Loki
2. verify Loki health
3. verify persistent storage
4. update Alloy
5. confirm BirdNET logs
6. confirm weather logs
7. configure local Grafana
8. observe the local pipeline
9. only then retire the Cloud dependency

Historical Cloud Loki data does not automatically need to be migrated.

Starting a new local Loki history at cutover is acceptable unless a concrete need for historical log migration appears.

---

# Grafana Rules

The existing BirdNET dashboard is:

    grafana/Bird Home - Burbank.json

Do not assume it can simply be copied unchanged into local Grafana.

Inspect:

- datasource UIDs
- datasource names
- Loki references
- Infinity plugin usage
- direct Open-Meteo queries
- Grafana Cloud assumptions

Prefer adapting the existing dashboard over rebuilding it manually.

Grafana deployment itself belongs in:

    homelab-grafana

not this repository.

---

# Historical Analysis

PostgreSQL is the foundation for future analysis.

Potential future work:

- species activity by hour
- activity relative to sunrise/sunset
- seasonal activity
- weather correlations
- forecast accuracy
- species-specific weather behavior
- prediction datasets
- machine-learning experiments

Do not prematurely introduce complex ML infrastructure before the underlying historical dataset and queries justify it.

---

# Reliability Principle

BirdNET's primary function is bird detection.

Monitoring infrastructure should not prevent the station from performing that job.

If PostgreSQL, Loki, Grafana, or the Home Lab infrastructure is unavailable, BirdNET should continue collecting its own native source data whenever possible.

Prefer recoverable asynchronous data flows over fragile tight coupling.

---

# Documentation Rules

When architecture changes:

- update the root README
- update the relevant component README
- update deployment documentation
- update systemd templates if runtime units changed
- update this AGENTS.md if architectural ownership changed

Prefer correcting existing documentation over appending a contradictory new section.

Documentation should describe the system as it exists now while clearly labeling planned future work.

---

# Editing Style

Favor:

- small understandable components
- explicit configuration
- comments where behavior is non-obvious
- simple deployment commands
- validation after changes
- reversible migrations

Avoid:

- hidden runtime assumptions
- duplicated configuration without reason
- credentials in source
- unnecessary frameworks
- replacing working components without a rollback path

This is a Home Lab project, but it should still be maintainable and reproducible.
