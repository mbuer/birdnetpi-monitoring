# AGENTS.md

Guidance for automated coding agents and future development sessions working in this repository.

Use this file as an architectural and operational guardrail. For implementation details, follow the component READMEs and current code.

## New session / new chat startup

Before making meaningful changes in a fresh session:

1. read `docs/executive-summary.md`
2. read `docs/architecture.md`
3. read `docs/decisions.md`
4. read the relevant subsystem README or methodology document
5. inspect current code/runtime evidence before assuming a documented deployment state

For architectural, database, ML-methodology, security, networking, or other cross-cutting changes, treat newer entries in `docs/decisions.md` as current context unless they are deliberately superseded.

---

# Project Purpose

This repository contains the monitoring, structured data collection, observability integration, machine-learning experiments, and Home Lab deployment surrounding a BirdNET-Pi station.

BirdNET itself is not part of this repository. Do not attempt to replace or absorb BirdNET's core application into this project.

---

# Current Architecture

## BirdNET Pi

The Raspberry Pi is the edge device. It owns:

- microphone and audio capture
- BirdNET analysis
- BirdNET native SQLite database
- detection synchronization
- weather observation collection
- weather forecast collection
- Grafana Alloy
- local operational logs

BirdNET's native database is `~/BirdNET-Pi/scripts/birds.db`.

Treat it as authoritative source data for completed detections. Monitoring code may read from it; do not modify it merely to simplify this project.

## ubuntu-infra

The infrastructure VM owns centralized services and ML execution:

- PostgreSQL
- Loki
- Prometheus
- Grafana OSS
- Python ML experiments
- automated aggregate activity prediction/scoring
- automated species prediction/scoring for the currently configured live species
- hourly persistence of BirdNET analysis-coverage evidence from Loki

Grafana deployment itself is maintained in the separate `homelab-grafana` repository.

## AI Nexus / Birdynator

AI Nexus is a separate secure agent platform maintained in the \`ai-nexus\` repository.

For BirdNET work, treat AI Nexus as a downstream consumer:

- BirdNET/ubuntu-infra remain authoritative for detections, weather, station health, and ML evidence
- Birdynator may consume BirdNET evidence through a constrained read-only datasource boundary
- Birdynator does not collect station health and must not duplicate the upstream collector
- Birdynator does not write into BirdNET source data
- Birdynator analysis history belongs to AI Nexus, not this repository
- a richer ML/health evidence interface is deferred until upstream analytical outputs are stable

Do not move BirdNET collection or ML ownership into AI Nexus merely to simplify an agent workflow. Cross-repository interfaces should remain narrow and explicit.


---

# Data Roles

## BirdNET SQLite

Authoritative BirdNET detection source.

## PostgreSQL

Durable structured historical and analytical data.

Core tables:

- `detections`
- `weather_observations`
- `weather_forecasts`
- `bird_activity_predictions`
- `bird_species_predictions`
- `station_health_hourly`

Analytical views:

- `bird_activity_hourly`
- `bird_species_hourly`

## Loki

Operational logs and observability.

## Grafana

Visualization across operational and analytical data.

Do not treat Loki as the permanent structured historical database, and do not turn PostgreSQL into a replacement for operational logging.

The exception is compact derived provenance that has long-term analytical value. `station_health_hourly` persists hourly analysis coverage from Loki so future ML can distinguish a healthy biological zero from incomplete or unavailable station evidence. Missing telemetry must remain `unknown`, not be converted into a false outage or false zero.

---

# PostgreSQL

Production BirdNET PostgreSQL runs on `ubuntu-infra`.

Deployment: `deploy/ubuntu-infra/postgres/`  
Container: `birdnet-postgres`  
Database: `birdnet`  
Application role: `birdnet`  
Read-only Grafana role: `grafana_reader`

Applications use:

- `BIRDNET_DB_HOST`
- `BIRDNET_DB_NAME`
- `BIRDNET_DB_USER`
- `BIRDNET_DB_PASSWORD`

Do not hard-code production passwords.

Database schema and analytical objects are documented in `database/README.md`.

---

# Machine Learning

The project has two live ML tracks.

## Aggregate activity prediction

Current live model labels:

- `random_forest_v2_completed` — established reference
- `xgboost_v2_completed` — live comparison model
- `hist_gradient_boosting_v1_completed` — live experimental challenger

Timing convention: **completed hour T → target hour T+2**

The coordinated hourly automation is driven by:

- `ml/src/timing.py`
- `ml/hourly_prediction_cycle.sh`
- `systemd/birdnet-ml-prediction.service`
- `systemd/birdnet-ml-prediction.timer`

## Species prediction

Species prediction code, storage, scoring, dashboarding, and hourly execution are implemented.

Relevant files include:

- `database/views/bird_species_hourly.sql`
- `database/species_predictions.sql`
- `ml/src/compare_species_models.py`
- `ml/src/predict_species_live.py`
- `ml/src/predict_species_challengers.py`
- `ml/src/score_species_predictions.py`
- `ml/species_challengers.json`
- `grafana/Bird Home - Species Prediction.json`

The existing hourly cycle currently performs:

```text
score aggregate
predict aggregate Random Forest + XGBoost + HistGradientBoosting
score species predictions
predict configured reference species
predict configured species challengers
```

Reference species are configured in `ml/live_species.txt`. Per-species challenger strategies live in `ml/species_challengers.json`. Challenger rows use distinct model labels and must not overwrite reference forecasts.

Do not add separate species timers unless there is a clear operational reason. Keep coordinated hourly work in the existing cycle where practical.

## ML rules

- Preserve temporal order.
- Do not use random train/test shuffling for time-series claims.
- Prevent target leakage.
- Compare against simple baselines.
- Store live forecasts before outcomes occur.
- Treat retrospective results and live forward validation as different evidence.
- Do not promote a more complex model for trivial metric improvements.
- Preserve older experiment code/results as historical methodology unless deliberately superseded and documented.
- Run the timing/leakage regression tests after changing `ml/src/timing.py` or related live feature construction.

Current regression test command:

```bash
.venv/bin/python -m unittest discover -s ml/tests -v
```

The suite covers timing/leakage behavior plus aggregate and species scoring guards.

Stable methodology: `docs/ml.md`  
Curated experiment results: `docs/experiments/`  
Operational ML instructions: `ml/README.md`

---

# Time Semantics

The current deployment uses `America/Los_Angeles`.

Several analytical objects store local wall-clock hours as `timestamp without time zone`.

Grafana time-series queries should convert prediction targets with:

```sql
predicted_hour AT TIME ZONE 'America/Los_Angeles'
```

Known limitation: local wall-clock timestamps cannot uniquely represent both occurrences of the repeated autumn DST hour. Do not silently treat these values as UTC.

---

# Weather

The repository weather collectors explicitly request:

- Fahrenheit temperature
- mph wind speed
- inches for precipitation

The database columns `precipitation_in` assume inch values. Historical rows collected before the explicit `precipitation_unit=inch` fix may have different unit provenance and should not be silently converted without verification.

The checked-in Pi deployment path was runtime-verified against the live host on 2026-09-26. For future changes, use the canonical bootstrap/verification workflow and validate the resulting runtime rather than maintaining undocumented one-off copies.

---

# Grafana

Current dashboard exports include:

- `grafana/Bird Home - Burbank Cloud.json`
- `grafana/Bird Home - Burbank Local.json`
- `grafana/bird-home-prediction-lab.json`
- `grafana/Bird Home - Species Prediction.json`

The PostgreSQL datasource currently uses UID `afy5j1yt18b9cb`.

Do not assume a dashboard can be copied to another Grafana instance without checking datasource UIDs, datasource names, plugins, and query compatibility.

Grafana deployment itself belongs in `homelab-grafana`.

---

# Loki and Alloy

Local Loki is deployed on `ubuntu-infra`.

The active Pi Alloy architecture writes operational logs only to local Loki on `ubuntu-infra`. Grafana Cloud Loki was retired after the local path was runtime-verified.

Use the canonical Pi bootstrap/verification workflow for Alloy changes. Validate configuration before restart and verify end-to-end Loki delivery afterward; a running Alloy service alone is not sufficient evidence.

---

# Public repository hygiene

This repository should remain safe to share publicly.

Do not commit:

- exact private IP addresses or private subnets from the live environment
- exact station latitude/longitude
- public WAN addresses or dynamic-DNS names
- environment-specific hostnames that reveal live topology where symbolic names suffice
- credentials, tokens, private keys, or passwords
- screenshots containing sensitive infrastructure details

Use symbolic names such as:

```text
BIRDNET_HOST
INFRA_HOST
LOKI_URL
POSTGRES_HOST
```

Safe examples belong in `config/runtime.example.env`. Real environment values belong in ignored local configuration.

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

Examples must contain placeholders only.

---

# Runtime State

Keep runtime state outside Git:

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

When an installed systemd unit changes, update the corresponding file under `systemd/`.

Do not fix only `/etc/systemd/system/...` and leave the repository stale.

Before adding a new timer, check whether the work belongs in an existing coordinated cycle.

---

# Server Deployment

Prefer Docker Compose for server-side stateful services where practical.

Deployment configuration should be reproducible, understandable, version-controlled, secret-free, and explicit about persistent storage and health checks.

Prefer pinned container versions over floating `latest` tags when a tested version is known.

Deployment and rebuild guidance lives in `deploy/ubuntu-infra/README.md`.

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

Current centralized backup script: `backup/backup_infra_postgres.sh`  
Runtime destination: `/var/backups/birdnet-postgres`  
Retention: 14 days

Systemd units:

- `birdnet-postgres-backup.service`
- `birdnet-postgres-backup.timer`

At least one backup should eventually exist outside the same VM/storage as PostgreSQL. Do not treat archive listing as equivalent to a tested restore.

---

# Reliability Principle

BirdNET's primary function is bird detection.

Monitoring infrastructure should not prevent the station from performing that job. If PostgreSQL, Loki, Grafana, or the Home Lab infrastructure is unavailable, BirdNET should continue collecting its own native source data whenever possible.

Prefer recoverable asynchronous data flows over fragile tight coupling.

---

# Documentation Rules

The repository already has a sensible structure. Do not reorganize directories merely to make documentation feel cleaner.

Use the existing documentation roles:

- root `README.md` — concise project overview and navigation
- `docs/architecture.md` — detailed current architecture, ownership, trust boundaries, and AI Nexus relationship
- `AGENTS.md` — architectural and development guardrails
- `docs/decisions.md` — architectural and development decisions
- `docs/ml.md` — stable ML methodology
- `docs/experiments/` — dated experiment findings
- `ml/README.md` — ML operation and execution
- `database/README.md` — database contract and setup
- `grafana/README.md` — dashboard requirements and behavior
- `deploy/ubuntu-infra/README.md` — deployment and recovery runbook
- `ml/reports/` — raw or legacy historical experiment material

When architecture changes, update relevant documentation in the same change.

Do not describe completed work as future work or planned work as deployed.

---

# Commit Provenance

When ChatGPT makes a repository change directly through the GitHub connector, prefix the commit message with:

`Sol:`

Example:

`Sol: Add aggregate scoring regression tests`

This convention is only for changes written directly by ChatGPT. User-created local commits keep normal commit messages. The prefix is informational and does not imply different review or trust requirements.

---

# Reproducible deployment

Treat these as the canonical deployment/verification entry points:

```bash
make pi-bootstrap
make pi-verify
make infra-bootstrap
make infra-verify
make repo-check
```

Do not replace these workflows with undocumented one-off installation steps. When deployment behavior changes, update the bootstrap, verification, relevant documentation, and decision log together.

Run `make repo-check` after changes that touch configuration, networking, deployment docs, or examples.

# Editing Style

Favor small understandable components, explicit configuration, simple deployment commands, validation after changes, reversible migrations, and preserved historical experiment context.

Avoid hidden runtime assumptions, duplicated configuration without reason, credentials in source, unnecessary frameworks, needless directory reshuffling, replacing working components without a rollback path, or silently changing model methodology while retaining the same model label.

This is a Home Lab project, but it should remain maintainable, reproducible, and honest about the limits of its data and experiments.
