# BirdNET-Pi Monitoring

A Home Lab platform for collecting, preserving, visualizing, and analyzing BirdNET data over the long term.

BirdNET remains responsible for listening to the microphone and identifying birds. This repository builds the surrounding data and observability system: structured PostgreSQL history, weather observations and forecasts, Loki logging, Grafana dashboards, backups, and experimental machine-learning forecasts.

The long-term goal is simple:

> Build a trustworthy historical dataset around the BirdNET station, then use it to understand and predict bird activity without compromising the reliability of the station itself.

---

## What the Project Does

The system currently supports four related jobs:

1. **Preserve BirdNET detections** outside the Pi's native database for long-term analysis.
2. **Collect environmental context** from Open-Meteo, including observations and historical forecast snapshots.
3. **Observe the station operationally** through Alloy, Loki, and Grafana.
4. **Experiment with prediction**, both for aggregate bird activity and individual species presence.

This allows questions such as:

- What birds are being detected now?
- Is the station still operating normally?
- How does bird activity change with time of day, sunrise, weather, or season?
- How accurate were weather forecasts before an observation occurred?
- Can recent activity predict the next complete hour?
- How likely is a particular species to appear in a future hour?

The project is intentionally evolving from a dashboard into a small environmental data platform.

---

# Architecture

The design separates source data, structured history, and operational observability.

```text
BirdNET Raspberry Pi
│
├── microphone / BirdNET analysis
├── BirdNET birds.db
│
├── detection importer ────────────────┐
├── weather observation collector ────┤
├── weather forecast collector ───────┤
│                                      ▼
└── Grafana Alloy                 PostgreSQL
     │                                 │
     ├──> Grafana Cloud Loki           ├──> historical analysis
     │                                 ├──> ML training
     └──> local Loki                   └──> stored predictions
             │
             ▼
         Grafana OSS

ubuntu-infra
├── PostgreSQL
├── Loki
├── Prometheus
├── Grafana OSS
└── Python ML prediction / scoring
```

The current Home Lab deployment uses:

- BirdNET Pi: `192.168.1.136`
- `ubuntu-infra`: `192.168.1.137`

These addresses describe the current installation, not application defaults.

Grafana itself is deployed from a separate Home Lab repository, `homelab-grafana`. This repository owns the BirdNET-specific dashboards, datasource expectations, data models, collectors, and analysis code.

---

# Data Responsibilities

## BirdNET SQLite — authoritative detection source

BirdNET owns:

```text
~/BirdNET-Pi/scripts/birds.db
```

The monitoring stack treats this database as source data.

It is read and synchronized, not modified for monitoring purposes.

This separation is deliberate: a failure in PostgreSQL, Loki, Grafana, or the infrastructure VM should not prevent BirdNET from continuing its primary job.

## PostgreSQL — durable analytical history

PostgreSQL stores structured data intended to survive beyond operational log retention.

Primary data includes:

- `detections`
- `weather_observations`
- `weather_forecasts`
- `bird_activity_predictions`
- `bird_species_predictions`

Derived analytical views include:

- `bird_activity_hourly`
- `bird_species_hourly`

PostgreSQL is the foundation for historical analysis and machine learning.

## Loki — operational observability

Loki stores logs and operational events collected through Grafana Alloy.

It answers a different question from PostgreSQL:

```text
PostgreSQL -> What happened historically?
Loki       -> What is the system doing operationally?
```

The two stores are intentionally complementary.

---

# Data Collection

## Bird detections

`collector/import_detections.py` synchronizes completed BirdNET detections from the Pi's SQLite database into PostgreSQL.

The synchronization is incremental and tracks the last processed SQLite row ID. Database constraints protect against normal duplicate insertion during retries or source rescans.

The Pi remains the authoritative source for completed BirdNET detections.

## Weather observations

`weather/weather.py` collects Open-Meteo observations and stores them in PostgreSQL.

The history includes environmental fields such as temperature, humidity, pressure, precipitation, wind, cloud cover, day/night state, sunrise, and sunset.

Weather data also enters the operational logging path so collector behavior can be observed independently from the analytical database.

## Weather forecasts

`weather/forecast.py` stores snapshots of future Open-Meteo forecasts.

Each forecast preserves both:

- when the forecast snapshot was collected
- which future hour the forecast described

Keeping multiple historical snapshots for the same target hour makes later forecast-accuracy analysis possible and creates a future path for weather-aware bird prediction using information that was actually available at forecast time.

---

# Machine Learning

Machine learning is deliberately treated as an experimental layer on top of the historical data rather than as the purpose of the whole system.

The project currently works with two prediction problems.

## Aggregate bird activity

The aggregate model predicts the project's hourly activity index.

The live model is:

```text
random_forest_v2_completed
```

It uses completed historical input and follows the current timing convention:

```text
completed hour T -> target hour T+2
```

At 14:10, for example, the most recent completed input hour is 13:00–14:00 and the next full target hour is 15:00–16:00.

The hourly systemd cycle scores eligible previous predictions first and then creates a new forecast.

Random Forest currently remains the live aggregate model. XGBoost has been evaluated as a challenger, but its improvement on the current dataset was too small to justify replacing the simpler live choice.

## Species presence

The species pipeline predicts the probability that a particular species will be detected during a future hourly period.

The generic classifier supports multiple species and currently compares:

- prevalence baseline
- persistence
- Random Forest
- XGBoost

Initial experiments include:

- House Finch
- Black Phoebe
- American Crow

The results show that predictability differs substantially by species and prevalence. Probability output is especially important for sparse species, where a fixed `0.5` classification threshold can be misleading.

Live species prediction and scoring code exists and stores forecasts in PostgreSQL. Unlike the aggregate activity pipeline, species prediction is **not yet wired into the committed hourly systemd cycle**. That is an intentional next operational step rather than something to hide behind documentation.

## Validation philosophy

Time-series prediction must be evaluated chronologically.

The current methodology emphasizes:

- no random train/test shuffling for v2 experiments
- walk-forward validation
- training only on labels that would already have been observable
- strong persistence/prevalence baselines
- stored live forecasts for true forward validation

A retrospective model can look good while still benefiting from future information accidentally leaking into training. Avoiding that is more important than maximizing a headline metric.

See:

- [ML methodology](docs/ml.md)
- [ML operations](ml/README.md)
- [activity experiment](docs/experiments/2026-09-14-activity-models.md)
- [species experiment](docs/experiments/2026-09-14-species-models.md)

Historical experiment material under `ml/reports/` is retained as project history and should not be confused with the current v2 methodology.

---

# Grafana

Grafana provides both operational and analytical views.

Current dashboard exports:

| Dashboard | Purpose |
|---|---|
| `Bird Home - Burbank Cloud.json` | Original Grafana Cloud operational reference |
| `Bird Home - Burbank Local.json` | Local Grafana OSS operational dashboard |
| `bird-home-prediction-lab.json` | Aggregate activity forecasts and scoring |
| `Bird Home - Species Prediction.json` | Species probability and classification forecasts |

The operational dashboard primarily uses Loki and Infinity/Open-Meteo.

The prediction dashboards use PostgreSQL.

This distinction matters: raw detection logs, accepted SQLite detections, and derived SQL activity indexes are related but are not interchangeable datasets.

See [grafana/README.md](grafana/README.md) for datasource, import, time-zone, and scoring details.

---

# Backups and Recovery

The centralized PostgreSQL instance is backed up daily using custom-format PostgreSQL archives.

Current schedule:

```text
03:15 America/Los_Angeles
```

Current retention:

```text
14 days
```

Runtime backup location:

```text
/var/backups/birdnet-postgres
```

The repository intentionally keeps backup logic in Git but not the dumps themselves.

A database backup protects structured PostgreSQL data. It does not replace backups for:

- BirdNET audio
- the Pi's native `birds.db`
- Loki data
- VM configuration outside Git
- Grafana state outside exported configuration
- secrets

The main remaining backup improvement is an off-host copy that survives loss of `ubuntu-infra` itself.

See [database/README.md](database/README.md) and the [ubuntu-infra deployment runbook](deploy/ubuntu-infra/README.md) for recovery details.

---

# Current Project State

The core data path is operational.

| Area | Status |
|---|---|
| BirdNET detection synchronization | Deployed |
| Weather observations | Deployed |
| Historical weather forecasts | Deployed |
| Central PostgreSQL | Deployed |
| PostgreSQL backups | Deployed |
| Local Loki | Deployed |
| Grafana OSS integration | Deployed |
| Alloy local + Cloud dual-write | Transitional |
| Aggregate activity ML | Live hourly prediction/scoring |
| Species ML experiments | Working |
| Species live prediction code | Working manually |
| Species scheduled automation | Not yet integrated |
| Off-host database backup | Planned |

Grafana Cloud Loki remains temporarily available during the local observability transition. The working previous path should not be removed until the local replacement has been observed long enough to justify doing so.

---

# Repository Structure

| Path | Purpose |
|---|---|
| `collector/` | Read-only BirdNET SQLite synchronization |
| `weather/` | Weather observation and forecast collectors |
| [`database/`](database/README.md) | Schema, analytical views, prediction tables, database operations |
| `alloy/` | Grafana Alloy configuration/reference material |
| [`deploy/ubuntu-infra/`](deploy/ubuntu-infra/README.md) | Central PostgreSQL/Loki deployment and rebuild guidance |
| `backup/` | PostgreSQL backup scripts |
| [`grafana/`](grafana/README.md) | BirdNET dashboard exports and datasource assumptions |
| [`ml/`](ml/README.md) | ML scripts and operational prediction workflow |
| [`docs/ml.md`](docs/ml.md) | Stable ML methodology |
| `docs/experiments/` | Dated, reproducible experiment conclusions |
| `systemd/` | Collector, backup, weather, and activity-ML service/timer definitions |
| [`AGENTS.md`](AGENTS.md) | Guardrails and current architecture for future coding/AI work |

The repository structure is intentionally simple. Prefer updating the documentation and existing components over repeatedly reorganizing directories.

---

# Documentation Map

Use the root README as the project overview. More detailed responsibilities are intentionally split out:

| Document | Role |
|---|---|
| [`database/README.md`](database/README.md) | Database schema, synchronization, grants, backup, restore, species/activity data contracts |
| [`grafana/README.md`](grafana/README.md) | Dashboard exports, PostgreSQL requirements, datasource and time handling |
| [`ml/README.md`](ml/README.md) | How to run experiments and live prediction/scoring code |
| [`docs/ml.md`](docs/ml.md) | Stable ML methodology and validation rules |
| [`docs/experiments/`](docs/experiments/) | Dated model comparisons and conclusions |
| [`deploy/ubuntu-infra/README.md`](deploy/ubuntu-infra/README.md) | Deployment, rebuild, recovery, and operational checks |
| [`AGENTS.md`](AGENTS.md) | Project guardrails for future development sessions |

This separation is deliberate: detailed implementation notes should live next to the component they describe instead of making this README a full operations manual.

---

# Design Principles

## Keep BirdNET independent

Monitoring must not become a prerequisite for bird detection.

If the Home Lab infrastructure disappears temporarily, BirdNET should continue doing its core work and preserve its own source data whenever possible.

## Protect source data

Do not modify BirdNET's native SQLite database merely to simplify the monitoring stack.

Read from it and synchronize elsewhere.

## Separate observability from analytical history

Use Loki for operational logs and PostgreSQL for durable structured analysis.

Do not force either datastore to become the other.

## Prefer honest models over impressive models

A sophisticated model with leakage or weak validation is less useful than a simpler model with trustworthy evaluation.

Baselines, chronological validation, data cutoffs, timing semantics, and stored live forecasts matter.

## Keep history reproducible

Preserve raw detections, timestamps, confidence, station identity, weather observations, forecast snapshots, historical predictions, and scored outcomes.

Models can always be replaced later. Historical source data cannot.

## Keep infrastructure understandable

This is a Home Lab project, not a platform engineering exercise.

Prefer:

- small components
- explicit configuration
- pinned versions where useful
- clear ownership
- recoverable migrations
- documented assumptions

Avoid adding complexity merely because it is technically possible.

---

# Security and Runtime State

Git should contain enough information to understand and rebuild the system, but not live secrets or state.

Do not commit:

- PostgreSQL passwords
- Grafana credentials or tokens
- `.env` or `db.env`
- database dumps
- private SSH keys
- live logs
- Docker volumes
- Alloy state

Runtime credentials and persistent service data belong outside the repository.

---

# Near-Term Direction

The highest-value next steps are intentionally practical rather than architectural:

1. integrate species scoring/prediction into the existing hourly ML cycle instead of creating unnecessary parallel timers
2. continue collecting live forward-validation history
3. evaluate useful probability thresholds for sparse species
4. add daylight/sunrise features to species experiments
5. improve ingestion-health/completeness evidence so quiet periods can be distinguished from outages
6. create an off-host PostgreSQL backup copy and periodically test restores
7. finish validating local Loki/Grafana before retiring the Cloud Loki path

Longer term, the growing dataset can support stronger seasonal analysis, weather-aware models, richer species forecasts, and better automated monitoring.

The project should become more capable as the data justifies it, while staying understandable enough to rebuild from Git, secrets, and backups.
