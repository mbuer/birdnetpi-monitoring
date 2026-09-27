# BirdNET-Pi Monitoring

A Home Lab platform for turning a BirdNET-Pi station into a trustworthy long-term dataset for observability, analysis, machine learning, and downstream AI-assisted interpretation.

BirdNET remains responsible for the microphone, audio analysis, and native detections. This repository builds around it without making the station dependent on the rest of the lab.

The guiding idea is:

> Preserve the source data first. Add observability and analysis around it. Only add prediction or AI when the evidence is good enough to justify it.

## What exists today

The project currently provides:

- read-only synchronization of BirdNET detections into PostgreSQL
- current weather observations and historical forecast snapshots from Open-Meteo
- local operational logging through Grafana Alloy and Loki
- Grafana dashboards for station activity, historical analysis, and ML predictions
- hourly station-health evidence so quiet hours can be distinguished from missing data
- live aggregate bird-activity forecasting
- live per-species presence forecasting
- validated PostgreSQL backups
- reproducible Pi and infrastructure deployment/verification workflows
- a constrained downstream data boundary for AI Nexus / Birdynator

## Architecture at a glance

```text
BirdNET Pi
  |
  +-- BirdNET analysis
  |     `-- native birds.db
  |
  +-- detection sync ---------> PostgreSQL on ubuntu-infra
  +-- weather collectors -----> PostgreSQL on ubuntu-infra
  `-- Grafana Alloy ---------> Loki on ubuntu-infra

ubuntu-infra
  |
  +-- PostgreSQL
  |     +-- detections / weather / forecasts
  |     +-- station-health evidence
  |     +-- analytical views
  |     `-- stored ML predictions
  |
  +-- Loki
  +-- Prometheus
  +-- Grafana OSS
  `-- station-health + ML jobs
          |
          `-- read-only evidence
                 |
                 v
          AI Nexus / Birdynator
```

The important ownership rule is that **BirdNET and ubuntu-infra remain authoritative for the BirdNET data pipeline**. AI Nexus consumes evidence; it does not own collection, health monitoring, or model training.

The broader ML/health evidence interface to Birdynator is still deliberately narrow and partly deferred while the analytical contract matures.

For the detailed architecture, failure behavior, security boundaries, and AI Nexus relationship, read [docs/architecture.md](docs/architecture.md).

## Data model

The project deliberately separates three kinds of information.

| Layer | Role |
|---|---|
| BirdNET SQLite | Authoritative completed detections at the edge |
| PostgreSQL | Durable structured history, analytical views, predictions, station health |
| Loki | Shorter-lived operational logs and service evidence |

PostgreSQL currently stores:

- `detections`
- `weather_observations`
- `weather_forecasts`
- `station_health_hourly`
- `bird_activity_predictions`
- `bird_species_predictions`

Derived views:

- `bird_activity_hourly`
- `bird_species_hourly`

A deliberate bridge exists between observability and analysis: hourly BirdNET coverage is derived from Loki and persisted into PostgreSQL because it matters later when deciding whether a zero-detection hour is genuinely quiet or simply lacks reliable station evidence.

## Machine learning

ML is an experimental layer on top of preserved historical evidence, not the reason the data exists.

### Aggregate activity

Live aggregate models:

- Random Forest — established reference
- XGBoost — challenger
- HistGradientBoosting — challenger accumulating forward evidence

Timing contract:

```text
station health at :20
ML cycle at :30
completed hour T -> target hour T+2
```

The current live feature set uses time/daylight context and recent activity lags. Weather is available analytically but is not currently a live model feature.

### Species presence

Reference forecasts are currently issued for:

- House Finch
- Black Phoebe
- American Crow
- Black-crowned Night-Heron
- Lesser Goldfinch

Random Forest and XGBoost are the reference model families. Separate challengers currently exist for Black Phoebe and American Crow.

Stored forecasts are treated as historical evidence: the project distinguishes real forward predictions from retrospective model reruns.

See [docs/ml.md](docs/ml.md) for methodology and [ml/README.md](ml/README.md) for operations.

## Health-aware zeros

A quiet hour and a broken station must not look identical to a model.

`station_health_hourly` stores analysis coverage and one of:

- `healthy`
- `incomplete`
- `unknown`

Current ML logic keeps positive observations usable, but in the health-evidence era it only treats a zero as a trustworthy biological zero when the station was healthy. Missing evidence stays unknown.

That rule is one of the most important data-quality protections in the project.

## Grafana and observability

The active observability path is local-only:## Remaining scope

The infrastructure is intentionally close to feature-complete. The goal is no longer to harden or automate every possible detail.

Before freezing the infrastructure, finish only these essentials:

1. replicate PostgreSQL backups off-host and perform one real restore drill
2. make the narrow PostgreSQL access policy reproducible, including required roles/grants and host access rules
3. remove clearly obsolete Cloud-era and Pi-local migration artifacts after confirming they are unused

After that, prefer feature and analysis work over infrastructure refinement. Reopen infrastructure work only for a concrete security exposure, recovery problem, observed failure, or requirement from a real feature.

Known technical debt such as DST ambiguity, the weather-backed aggregate view, broader Loki hardening, and fully automated base-host provisioning remains documented but is not active scope by default.

See [docs/architecture.md](docs/architecture.md) and [docs/decisions.md](docs/decisions.md) for context.


