# BirdNET-Pi Monitoring

A reproducible monitoring and long-term data platform built around a BirdNET-Pi station.

BirdNET itself remains responsible for listening to the microphone and identifying birds. This repository surrounds that station with the infrastructure needed to collect, preserve, visualize, and analyze the resulting data and experiment with next-hour activity forecasts.

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

The longer-term goal is to create a durable dataset that connects bird activity with environmental conditions and supports historical analysis and experimental prediction.

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
    bird_activity_predictions

Derived view: `bird_activity_hourly`.

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
|-- hourly ML prediction and scoring (systemd + Python)
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
- Loki
- Prometheus
- Grafana OSS
- hourly ML prediction, scoring, and experiment runs

Grafana itself is managed through the separate:

    homelab-grafana

repository.

This separation keeps the BirdNET repository focused on BirdNET-specific data collection and infrastructure rather than owning the entire Home Lab monitoring stack.

---

# Bird Detection Data Path

BirdNET owns `~/BirdNET-Pi/scripts/birds.db`. The read-only importer runs approximately once per minute through `birdnet-db-sync.timer`, preserving detections in PostgreSQL.

Its checkpoint, `~/.local/state/birdnet-db-sync/last_rowid`, advances after a successful transaction. Failed writes can be retried; uniqueness constraints prevent normal duplicate records. A source maximum row ID below the checkpoint triggers a rescan. This detects some source rebuilds, not every possible replacement.

See [database documentation](database/README.md) for schema, synchronization, and recovery details.

---

# Weather Observations

`weather/weather.py` collects Open-Meteo observations approximately every 15 minutes, using station timezone `America/Los_Angeles`. It stores temperature, humidity, wind, precipitation, pressure, cloud cover, day/night and sunrise/sunset fields in `weather_observations`, and writes weather JSONL to `/var/log/weather/weather.log`.

This gives weather two complementary paths: structured history in PostgreSQL and operational events in Alloy/Loki. The database stores Open-Meteo observation time; logs also retain retrieval time. Missed collection intervals are not automatically backfilled.

See [database documentation](database/README.md) for the data model. The [weather setup note](docs/weather-setup.md) needs its interpreter/dependency instructions reconciled with the installed service.

---

# Weather Forecast History

`weather/forecast.py`, scheduled by `birdnet-forecast.timer`, requests 48 hours of weather forecasts and stores hourly snapshots in `weather_forecasts`.

Each record distinguishes `forecast_created_at` from `forecast_for`. Multiple snapshots for the same future hour preserve changing forecasts. Collection is hourly with up to five minutes of randomized delay; same-hour retries preserve the first stored snapshot.

This supports forecast-versus-observation analysis and future weather-aware bird models. The current live bird model does not use weather forecasts. Exact forecast availability needs additional provenance because creation time is rounded to the hour.

Both weather collectors need a precipitation-unit audit before their `precipitation_in` fields are used in analysis: neither explicitly requests precipitation units.

---

# PostgreSQL

PostgreSQL runs on `ubuntu-infra` in container `birdnet-postgres`, database `birdnet`. The Pi retains its old local instance temporarily as migration fallback.

The base schema is `database/schema.sql`. Tonight's additions are `database/views/bird_activity_hourly.sql` and `database/predictions.sql`; these require separate installation and grants because Compose mounts only the base schema.

Collectors read `BIRDNET_DB_HOST`, `BIRDNET_DB_NAME`, `BIRDNET_DB_USER`, and `BIRDNET_DB_PASSWORD`. Pi services load `/home/birduser/.config/birdnet-monitoring/db.env`. Keep real credentials outside Git. ML wrappers use the same variable names but have a different local-container password fallback; see [ML setup](ml/README.md).

---

# PostgreSQL Migration

Historical data was migrated from the Pi to `ubuntu-infra`, and live ingestion was confirmed. Historical row-count checkpoints are retained in the [database README](database/README.md); they are not current totals.

---

# PostgreSQL Network Access

PostgreSQL publishes port `5432`. Access must account for the Pi, local ML jobs, and Grafana's Docker connection path. The earlier Pi-only restriction is not a complete description of today's clients. Live authentication rules are not reproduced by the committed Compose file.

Grafana uses the read-only `grafana_reader` role. See the [database README](database/README.md) for ML object grants.

---

# PostgreSQL Backups

The central backup runs daily at **03:15 America/Los_Angeles**, writes custom-format dumps to `/var/backups/birdnet-postgres`, and removes matching files with `find -mtime +14`.

A full database dump includes the prediction table and hourly view. It does not include cluster-wide roles, secrets, BirdNET SQLite/audio, Loki data, or Grafana state. Dumps remain on the same VM; off-host copies and isolated restore tests remain open work.

See the [deployment runbook](deploy/ubuntu-infra/README.md) for operations and recovery.

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

The local Loki path was reported live and verified in Grafana OSS. However, the committed `alloy/config.alloy` still sends only to Cloud and uses literal credential placeholders. Preserve the installed dual-write configuration until the repository sample is reconciled.

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

The operational BirdNET dashboard exists in two repository variants:

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
- PostgreSQL for structured history and the separate Prediction Lab dashboard

The Bird Home dashboard itself remains primarily Loki-based. PostgreSQL is not intended to replace Loki in this operational dashboard.

The local dashboard has been verified against the local Loki datasource and the required Infinity plugin is installed.

The additional `grafana/bird-home-prediction-lab.json` visualizes stored forecasts, persistence, actual activity, and errors. It uses PostgreSQL datasource UID `afy5j1yt18b9cb`. See [Grafana documentation](grafana/README.md) for import details and metric limitations.

---

# Why Grafana and PostgreSQL Both Matter

The operational view uses Loki for current logs, recent detections, weather logging and troubleshooting. The analytical view uses PostgreSQL for durable statistics, weather history, stored predictions and error comparisons.

Keep this distinction visible as dashboards evolve. Operational filters and raw log counts need not match the SQL activity index.

---

# Repository Structure

| Path | Responsibility |
|---|---|
| `collector/` | Read-only BirdNET SQLite import |
| `weather/` | Observations and forecast snapshots |
| [database/](database/README.md) | Base schema, hourly view, prediction table |
| `alloy/` | Log collection sample; currently behind the reported live dual-write setup |
| [deploy/ubuntu-infra/](deploy/ubuntu-infra/README.md) | PostgreSQL/Loki deployment and operations |
| `backup/` | Central backup and legacy Pi-local backup |
| [grafana/](grafana/README.md) | Cloud/Local operational exports and Prediction Lab |
| [ml/](ml/README.md) | Experiments, live prediction, scoring, curated results |
| `systemd/` | Pi collector units and infrastructure backup/ML units |
| `docs/` | Pi setup notes and recorded package versions |
| `AGENTS.md` | Development guidance; migration status needs reconciliation |

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
- hourly activity view and ML experiment scripts
- Random Forest prediction storage and hourly scoring/prediction cycle
- PostgreSQL Prediction Lab dashboard and read-only access

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
- improve and validate the experimental bird activity forecasts

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

The project began as a way to visualize BirdNET detections. It is becoming a small environmental data platform built around BirdNET, weather, historical forecasts, PostgreSQL, and machine learning.

The immediate goal is a reproducible local Home Lab deployment and trustworthy prediction evaluation.

## Machine Learning

The repository includes chronological and expanding-window experiments plus an hourly prediction/scoring cycle. Historical reports favored Random Forest over persistence on average. The corrected live `random_forest_v2_completed` job refits on each invocation, stores its forecast and persistence value, and preserves the first forecast per target hour/model.

**Completed-hour update:** install the accompanying ML fix before using this documentation. At 14:10, v2 uses the completed 13:00–14:00 bucket to forecast 15:00–16:00 and waits until 16:10 to score. It rejects stale/gapped recent inputs and keeps legacy records separate. Historical experiment results use the older horizon and are not directly comparable. The ten-minute grace period does not establish ingestion completeness; scores remain experimental.

See [ML methodology and operations](ml/README.md) and [historical experiment results](ml/reports/experiments.md).
