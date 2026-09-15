# AGENTS.md

Guidance for automated coding agents and future development sessions working in this repository.

Use this file as a concise architectural and operational guardrail. For implementation details, follow the component READMEs and current code.

---

# Project Purpose

This repository contains the monitoring, structured data collection, observability integration, machine-learning experiments, and Home Lab deployment surrounding a BirdNET-Pi station.

BirdNET itself is not part of this repository.

Do not attempt to replace or absorb BirdNET's core application into this project.

---

# Current Architecture

## BirdNET Pi

The Raspberry Pi is the edge device.

It owns:

- microphone and audio capture
- BirdNET analysis
- BirdNET native SQLite database
- detection synchronization
- weather observation collection
- weather forecast collection
- Grafana Alloy
- local operational logs

BirdNET's native database is:

`~/BirdNET-Pi/scripts/birds.db`

Treat this as authoritative source data for completed detections.

Monitoring code may read from it. Do not modify it merely to simplify this project.

## ubuntu-infra

The infrastructure VM owns centralized services and ML execution.

Current services include:

- PostgreSQL
- Loki
- Prometheus
- Grafana OSS
- Python ML experiments
- automated aggregate activity prediction and scoring

Grafana deployment itself is maintained in the separate:

`homelab-grafana`

repository.

Do not move Grafana deployment into this repository unless the architecture is explicitly changed.

---

# Data Roles

Keep responsibilities separate.

## BirdNET SQLite

Authoritative BirdNET detection source.

## PostgreSQL

Durable structured historical and analytical data.

Core tables include:

- `detections`
- `weather_observations`
- `weather_forecasts`
- `bird_activity_predictions`
- `bird_species_predictions`

Analytical views include:

- `bird_activity_hourly`
- `bird_species_hourly`

## Loki

Operational logs and observability.

## Grafana

Visualization across operational and analytical data.

Do not treat Loki as the permanent structured historical database.

Do not turn PostgreSQL into a replacement for operational logging.

---

# PostgreSQL

Production BirdNET PostgreSQL runs on `ubuntu-infra`.

Deployment:

`deploy/ubuntu-infra/postgres/`

Container:

`birdnet-postgres`

Database:

`birdnet`

Application role:

`birdnet`

Read-only Grafana role:

`grafana_reader`

Applications use:

- `BIRDNET_DB_HOST`
- `BIRDNET_DB_NAME`
- `BIRDNET_DB_USER`
- `BIRDNET_DB_PASSWORD`

Do not hard-code production passwords.

Avoid hard-coding deployment-specific addresses when environment configuration is reasonable.

Database schema and analytical objects are documented in:

`database/README.md`

---

# Machine Learning

The project currently has two ML tracks.

## Aggregate activity prediction

Current live model:

`random_forest_v2_completed`

Timing convention:

**completed hour T → target hour T+2**

The current hourly automation scores previous eligible forecasts first, then generates a new activity forecast.

Relevant files include:

- `ml/src/timing.py`
- `ml/src/predict_next_hour.py`
- `ml/src/score_predictions.py`
- `ml/hourly_prediction_cycle.sh`
- `systemd/birdnet-ml-prediction.service`
- `systemd/birdnet-ml-prediction.timer`

## Species prediction

Species prediction code and storage are implemented.

Relevant files include:

- `database/views/bird_species_hourly.sql`
- `database/species_predictions.sql`
- `ml/src/compare_species_models.py`
- `ml/src/predict_species_live.py`
- `ml/src/score_species_predictions.py`
- `grafana/Bird Home - Species Prediction.json`

Species prediction is not yet represented by its own committed systemd automation.

Prefer integrating species work into the existing hourly ML cycle rather than creating unnecessary parallel timers unless there is a clear operational reason.

Do not claim species automation is deployed until the committed runtime path actually invokes it.

## ML rules

- Preserve temporal order.
- Do not use random train/test shuffling for time-series claims.
- Prevent target leakage.
- Compare against simple baselines.
- Store live forecasts before their outcomes occur.
- Treat retrospective results and live forward validation as different evidence.
- Do not promote a more complex model for trivial metric improvements.
- Preserve older experiment code/results as historical methodology unless deliberately superseded and documented.

Stable methodology belongs in:

`docs/ml.md`

Curated experiment results belong in:

`docs/experiments/`

Operational ML instructions belong in:

`ml/README.md`

---

# Time Semantics

The current deployment uses:

`America/Los_Angeles`

Several analytical objects store local wall-clock hours as `timestamp without time zone`.

Grafana time-series queries should convert prediction targets with:

`predicted_hour AT TIME ZONE 'America/Los_Angeles'`

Known limitation:

local wall-clock timestamps cannot uniquely represent both occurrences of the repeated autumn DST hour.

Do not silently treat these values as UTC.

---

# Grafana

This repository owns BirdNET dashboard exports and BirdNET-specific datasource expectations.

Current dashboard exports include:

- `grafana/Bird Home - Burbank Cloud.json`
- `grafana/Bird Home - Burbank Local.json`
- `grafana/bird-home-prediction-lab.json`
- `grafana/Bird Home - Species Prediction.json`

The PostgreSQL datasource currently uses UID:

`afy5j1yt18b9cb`

Do not assume a dashboard can be copied to another Grafana instance without checking datasource UIDs, datasource names, plugins, and query compatibility.

Grafana deployment itself belongs in `homelab-grafana`.

See:

`grafana/README.md`

---

# Loki and Alloy

Local Loki is deployed on `ubuntu-infra`.

The reported live Pi Alloy configuration dual-writes operational logs to local Loki and Grafana Cloud Loki during validation.

The repository sample may not exactly match the installed live Alloy configuration.

Do not overwrite a known-working installed Alloy configuration merely because a repository sample differs. Reconcile first.

Historical Grafana Cloud Loki data does not need to be migrated unless a concrete need appears.

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

Commit examples such as `.env.example` when useful.

Examples must contain placeholders only.

---

# Runtime State

Keep runtime state outside Git.

Examples:

- PostgreSQL Docker volumes
- Loki storage
- Alloy state
- logs
- database dumps
- synchronization checkpoints
- generated caches
- virtual environments
- generated experiment output

Git should contain enough configuration and documentation to recreate services, not their live state.

---

# Systemd

When an installed systemd unit changes, update the corresponding file under:

`systemd/`

Do not fix only `/etc/systemd/system/...` and leave the repository stale.

Before adding a new timer, check whether the work belongs in an existing coordinated cycle.

---

# Server Deployment

Prefer Docker Compose for server-side stateful services where practical.

Deployment configuration should be:

- reproducible
- understandable
- version controlled
- secret-free
- explicit about persistent storage
- explicit about health checks

Prefer pinned container versions over floating `latest` tags when a tested version is known.

Deployment and rebuild guidance lives in:

`deploy/ubuntu-infra/README.md`

---

# Database Changes

Protect historical data.

Before destructive or migration-related database work:

1. create a PostgreSQL dump
2. validate it with `pg_restore -l`
3. record useful row counts
4. perform the change
5. verify resulting objects and row counts
6. verify live ingestion afterward

Do not delete populated volumes to force initialization scripts to rerun.

Remember that `CREATE TABLE IF NOT EXISTS` is not a migration mechanism for incompatible existing schemas.

---

# Backups

Current centralized backup script:

`backup/backup_infra_postgres.sh`

Runtime destination:

`/var/backups/birdnet-postgres`

Current retention:

14 days

Systemd units:

- `birdnet-postgres-backup.service`
- `birdnet-postgres-backup.timer`

At least one backup should eventually exist outside the same VM/storage as PostgreSQL.

Do not treat archive listing as equivalent to a tested restore.

---

# Reliability Principle

BirdNET's primary function is bird detection.

Monitoring infrastructure should not prevent the station from performing that job.

If PostgreSQL, Loki, Grafana, or the Home Lab infrastructure is unavailable, BirdNET should continue collecting its own native source data whenever possible.

Prefer recoverable asynchronous data flows over fragile tight coupling.

---

# Documentation Rules

The repository already has a sensible structure. Do not reorganize directories merely to make documentation feel cleaner.

Use the existing documentation roles:

- root `README.md` — concise project overview and navigation
- `AGENTS.md` — architectural and development guardrails
- `docs/ml.md` — stable ML methodology
- `docs/experiments/` — dated experiment findings
- `ml/README.md` — ML operation and execution
- `database/README.md` — database contract and setup
- `grafana/README.md` — dashboard requirements and behavior
- `deploy/ubuntu-infra/README.md` — deployment and recovery runbook
- `ml/reports/` — raw or legacy historical experiment material

When architecture changes, update the relevant documentation in the same change.

Prefer correcting existing documentation over appending contradictory sections.

Do not describe completed work as future work.

Do not describe planned work as deployed.

---

# Editing Style

Favor:

- small understandable components
- explicit configuration
- comments where behavior is non-obvious
- simple deployment commands
- validation after changes
- reversible migrations
- preserving historical experiment context

Avoid:

- hidden runtime assumptions
- duplicated configuration without reason
- credentials in source
- unnecessary frameworks
- needless directory reshuffling
- replacing working components without a rollback path
- silently changing model methodology while retaining the same model label

This is a Home Lab project, but it should remain maintainable, reproducible, and honest about the limits of its data and experiments.
