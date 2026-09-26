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

## Start here

For a compact human-oriented overview and recommended reading order, see [Executive summary](docs/executive-summary.md).

For automated coding sessions and architectural guardrails, read [AGENTS.md](AGENTS.md) and [Decision log](docs/decisions.md) before cross-cutting changes.

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
     └──> local Loki                   ├──> historical analysis
             │                         ├──> ML training
             │                         └──> stored predictions
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

The live Home Lab addresses are intentionally excluded from Git. Documentation uses symbolic host roles such as `BIRDNET_HOST` and `INFRA_HOST`; real values belong in ignored local runtime configuration.

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
- `station_health_hourly`

Derived analytical views include:

- `bird_activity_hourly`
- `bird_species_hourly`

PostgreSQL is the foundation for historical analysis and machine learning. It also stores compact hourly station-health evidence derived from Loki so future ML can distinguish healthy zero-detection hours from incomplete or unavailable station evidence.

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

The collector explicitly requests imperial precipitation units before writing `precipitation_in`. Historical rows collected before that fix may require a provenance audit before precipitation is used quantitatively.

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

The aggregate pipeline predicts the project's hourly activity index.

The live aggregate models are:

```text
random_forest_v2_completed
xgboost_v2_completed
hist_gradient_boosting_v1_completed
```

Both use the same completed historical input and timing convention:

```text
completed hour T -> target hour T+2
```

At 14:30, for example, the most recent completed input hour is 13:00–14:00 and the next full target hour is 15:00–16:00. The :30 schedule allows station-health collection at :20 to persist provenance first.

Random Forest remains the established live reference model. XGBoost remains a live challenger, and HistGradientBoosting is now added as a third experimental challenger so all three can accumulate true matched forward-validation evidence. Each model is stored as a separate row in `bird_activity_predictions` under its own model label.

## Species presence

The species pipeline predicts the probability that a particular species will be detected during a future hourly period.

The live hourly cycle scores stored species predictions and creates reference Random Forest + XGBoost forecasts for House Finch, Black Phoebe, American Crow, Black-crowned Night-Heron, and Lesser Goldfinch. It also issues separate challenger forecasts for Black Phoebe (tuned XGBoost) and American Crow (class-balanced bootstrap XGBoost ensemble), so the alternatives can accumulate matched forward-validation history without replacing the reference models.

The coordinated cycle is:

```text
birdnet-ml-prediction.timer
    -> birdnet-ml-prediction.service
    -> ml/hourly_prediction_cycle.sh
        -> score aggregate predictions
        -> predict aggregate activity with Random Forest + XGBoost + HistGradientBoosting
        -> score species predictions
        -> predict configured reference species
        -> predict configured species challengers
```

Keeping the existing aggregate work first means a species-side failure does not prevent the primary activity forecasts from being created during that run.

## Validation philosophy

Time-series prediction must be evaluated chronologically.

The current methodology emphasizes:

- no random train/test shuffling for v2 experiments
- walk-forward validation
- training only on labels that would already have been observable
- strong persistence/prevalence baselines
- stored live forecasts for true forward validation
- regression tests around completed-hour timing, gaps, lags, and DST ambiguity

See:

- [ML methodology](docs/ml.md)
- [ML operations](ml/README.md)
- [activity experiment](docs/experiments/2026-09-14-activity-models.md)
- [species experiment](docs/experiments/2026-09-14-species-models.md)
- [species challenger comparison](docs/experiments/2026-09-18-species-challengers.md)
- [American Crow bootstrap experiment](docs/experiments/2026-09-18-american-crow-bootstrap-ensemble.md)
- [live forward-validation checkpoint](docs/experiments/2026-09-26-live-forward-validation.md)

Historical experiment material under `ml/reports/` is retained as project history and should not be confused with the current v2 methodology.

---

# Grafana

Grafana provides both operational and analytical views.

Current dashboard exports:

| Dashboard | Purpose |
|---|---|
| `Bird Home - Burbank Cloud.json` | Original Grafana Cloud operational reference |
| `Bird Home - Burbank Local.json` | Local Grafana OSS operational dashboard |
| `bird-home-prediction-lab.json` | Aggregate Random Forest + XGBoost forecasts and scoring |
| `Bird Home - Species Prediction.json` | Species probability and classification forecasts |

The operational dashboard primarily uses Loki and Infinity/Open-Meteo.

The prediction dashboards use PostgreSQL.

See [grafana/README.md](grafana/README.md) for datasource, import, time-zone, and scoring details.

---

# Backups and Recovery

The centralized PostgreSQL instance is backed up daily using custom-format PostgreSQL archives.

Current schedule: `03:15 America/Los_Angeles`  
Current retention: `14 days`  
Runtime backup location: `/var/backups/birdnet-postgres`

The repository intentionally keeps backup logic in Git but not the dumps themselves.

The main remaining backup improvement is an off-host copy that survives loss of `ubuntu-infra` itself.

See [database/README.md](database/README.md) and the [ubuntu-infra deployment runbook](deploy/ubuntu-infra/README.md) for recovery details.

---

# Current Project State

The core data path is operational.

| Area | Status |
|---|---|
| BirdNET detection synchronization | Deployed |
| Weather observations | Deployed; repo now explicitly requests precipitation in inches |
| Historical weather forecasts | Deployed; repo now explicitly requests precipitation in inches |
| Central PostgreSQL | Deployed |
| PostgreSQL backups | Deployed |
| Local Loki | Deployed |
| Grafana OSS integration | Deployed |
| Alloy → local Loki only | Deployed and verified |
| Aggregate activity ML | Live hourly Random Forest + XGBoost + HistGradientBoosting prediction/scoring |
| Species ML experiments | Working |
| Species live prediction/scoring | Reference + challenger forecasts integrated into the hourly ML cycle |
| Station-health persistence | Deployed and verified; hourly Loki-derived coverage persisted in PostgreSQL |
| ML timing/leakage/scoring regression tests | Automated unittest suite under `ml/tests/` |
| Off-host database backup | Planned |

Grafana Cloud Loki output was retired on 2026-09-26 after the local-only Alloy path was validated for fresh BirdNET and weather log delivery.

---

# Repository Structure

| Path | Purpose |
|---|---|
| `collector/` | Read-only BirdNET SQLite synchronization |
| `weather/` | Weather observation and forecast collectors |
| [`health/`](health/README.md) | Durable hourly BirdNET analysis-coverage evidence from Loki |
| [`database/`](database/README.md) | Schema, analytical views, prediction tables, database operations |
| `alloy/` | Grafana Alloy configuration/reference material |
| [`deploy/ubuntu-infra/`](deploy/ubuntu-infra/README.md) | Central PostgreSQL/Loki deployment and rebuild guidance |
| `backup/` | PostgreSQL backup scripts |
| [`grafana/`](grafana/README.md) | BirdNET dashboard exports and datasource assumptions |
| [`ml/`](ml/README.md) | ML scripts and operational prediction workflow |
| [`docs/ml.md`](docs/ml.md) | Stable ML methodology |
| `docs/experiments/` | Dated, reproducible experiment conclusions |
| `systemd/` | Collector, backup, weather, forecast, and ML service/timer definitions |
| [`AGENTS.md`](AGENTS.md) | Guardrails and current architecture for future coding/AI work |

The repository structure is intentionally simple. Prefer updating the documentation and existing components over repeatedly reorganizing directories.

---

# Documentation Map

| Document | Role |
|---|---|
| [`database/README.md`](database/README.md) | Database schema, synchronization, grants, backup, restore, species/activity data contracts |
| [`grafana/README.md`](grafana/README.md) | Dashboard exports, PostgreSQL requirements, datasource and time handling |
| [`ml/README.md`](ml/README.md) | How to run experiments and live prediction/scoring code |
| [`docs/decisions.md`](docs/decisions.md) | Architectural and development decisions that should survive across work sessions |
| [`docs/ml.md`](docs/ml.md) | Stable ML methodology and validation rules |
| [`docs/experiments/`](docs/experiments/) | Dated model comparisons and conclusions |
| [`deploy/ubuntu-infra/README.md`](deploy/ubuntu-infra/README.md) | Deployment, rebuild, recovery, and operational checks |
| [`AGENTS.md`](AGENTS.md) | Project guardrails for future development sessions |

---

# Design Principles

- **Keep BirdNET independent.** Monitoring must not become a prerequisite for bird detection.
- **Protect source data.** Read from BirdNET's native SQLite database; do not modify it merely to simplify monitoring.
- **Separate observability from analytical history.** Loki is for operational logs; PostgreSQL is for durable structured analysis.
- **Prefer honest models over impressive models.** Timing semantics, baselines, leakage prevention, and stored live forecasts matter more than headline metrics.
- **Keep history reproducible.** Preserve raw detections, timestamps, weather observations, forecast snapshots, predictions, and scored outcomes.
- **Keep infrastructure understandable.** Prefer small components, explicit configuration, clear ownership, and recoverable migrations.

---

# Security and Runtime State

Git should contain enough information to understand and rebuild the system, but not live secrets or state.

Do not commit PostgreSQL/Grafana credentials, `.env` or `db.env`, database dumps, private SSH keys, live logs, Docker volumes, or Alloy state.

---

# Near-Term Direction

The highest-value next steps are:

1. continue collecting matched live forward-validation history for the current aggregate models
2. continue accumulating genuine matched forward-validation history for `HistGradientBoostingRegressor`; do not promote it before enough scored evidence exists
3. compare aggregate models only on matched scored target hours and characterize performance by day/night and activity level before changing the aggregate champion
4. accumulate live reference Random Forest + XGBoost forward-validation history for Black-crowned Night-Heron and Lesser Goldfinch; do not add species-specific challengers yet
5. accumulate matched forward-validation for Black Phoebe and American Crow challengers before promoting them
6. evaluate species-specific thresholds and add daylight/sunrise features where justified
7. use the now-validated `station_health_hourly` evidence carefully in future ML methodology changes; do not treat incomplete or unknown hours as biological zeros
8. create an off-host PostgreSQL backup copy and periodically test restores
9. continue observing local Loki/Grafana health and retention after the Cloud Loki retirement
10. keep the checked-in Pi weather/Alloy configuration aligned with the verified installed Pi files

Longer term, the growing dataset can support stronger seasonal analysis, weather-aware models, richer species forecasts, and better automated monitoring.

The project should become more capable as the data justifies it, while staying understandable enough to rebuild from Git, secrets, and backups.
