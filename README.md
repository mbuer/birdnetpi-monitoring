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

\`\`\`text
BirdNET Pi
├─ microphone -> BirdNET analysis -> native birds.db
├─ detection sync ───────────────────────────────┐
├─ weather + forecast collectors ────────────────┤
└─ Grafana Alloy -> local Loki ───────────────┐  │
                                               │  │
ubuntu-infra                                   │  │
├─ Loki <──────────────────────────────────────┘  │
├─ PostgreSQL <───────────────────────────────────┘
│  ├─ detections / weather / forecasts
│  ├─ station-health evidence
│  ├─ analytical views
│  └─ stored ML predictions + scores
├─ hourly station-health + ML jobs
├─ Prometheus
└─ Grafana OSS

             constrained read-only evidence
BirdNET / ubuntu-infra ──────────────────────────> AI Nexus / Birdynator
                                                   └─ separate analysis runs
\`\`\`

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

- \`detections\`
- \`weather_observations\`
- \`weather_forecasts\`
- \`station_health_hourly\`
- \`bird_activity_predictions\`
- \`bird_species_predictions\`

Derived views:

- \`bird_activity_hourly\`
- \`bird_species_hourly\`

A deliberate bridge exists between observability and analysis: hourly BirdNET coverage is derived from Loki and persisted into PostgreSQL because it matters later when deciding whether a zero-detection hour is genuinely quiet or simply lacks reliable station evidence.

## Machine learning

ML is an experimental layer on top of preserved historical evidence, not the reason the data exists.

### Aggregate activity

Live aggregate models:

- Random Forest — established reference
- XGBoost — challenger
- HistGradientBoosting — challenger accumulating forward evidence

Timing contract:

\`\`\`text
station health at :20
ML cycle at :30
completed hour T -> target hour T+2
\`\`\`

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

\`station_health_hourly\` stores analysis coverage and one of:

- \`healthy\`
- \`incomplete\`
- \`unknown\`

Current ML logic keeps positive observations usable, but in the health-evidence era it only treats a zero as a trustworthy biological zero when the station was healthy. Missing evidence stays unknown.

That rule is one of the most important data-quality protections in the project.

## Grafana and observability

The active observability path is local-only:

\`\`\`text
BirdNET Pi -> Grafana Alloy -> Loki on ubuntu-infra -> Grafana OSS
\`\`\`

Grafana Cloud Loki was retired after the local path was runtime-verified.

BirdNET-specific dashboards live in this repository. Shared Grafana deployment, datasource provisioning, and plugins belong to the separate \`homelab-grafana\` repository.

Current dashboard exports include:

- local Bird Home operational dashboard
- historical Cloud dashboard export retained as reference
- aggregate Prediction Lab
- Species Prediction dashboard

See [grafana/README.md](grafana/README.md).

## AI Nexus / Birdynator

AI Nexus is a separate secure agent platform in the Home Lab.

Its Birdynator workflow is downstream of this repository:

\`\`\`text
authoritative BirdNET evidence
        -> constrained read-only datasource boundary
        -> Birdynator analysis
        -> AI Nexus analysis history
\`\`\`

Birdynator does not collect station health and does not become a second owner of BirdNET data. The BirdNET stack remains responsible for provenance, structured history, and ML evidence.

A richer ML-to-Birdynator interface is deferred until the evidence exposed across that boundary is stable enough to be useful without leaking internal implementation details.

## Rebuild and verify

A new session should not reconstruct this system from chat history.

Canonical workflows:

\`\`\`bash
# repository hygiene
make repo-check

# existing BirdNET-Pi host
make pi-bootstrap
make pi-verify

# ubuntu-infra
make infra-bootstrap
make infra-verify
\`\`\`

The Pi and infra verification workflows were exercised successfully against the live hosts on 2026-09-26.

Rebuild contract:

\`\`\`text
Git
+ local runtime configuration / secrets
+ PostgreSQL backup when historical state is required
= reproducible monitoring environment
\`\`\`

BirdNET-Pi itself is installed independently and is not managed by this repository.

See:

- [BirdNET Pi deployment](deploy/birdnet-pi/README.md)
- [ubuntu-infra deployment](deploy/ubuntu-infra/README.md)
- [database backup and recovery](database/README.md)

## Current state

| Area | State |
|---|---|
| Detection sync | Deployed and verified |
| Weather observations | Deployed and verified |
| Weather forecast snapshots | Deployed and verified |
| PostgreSQL | Deployed |
| PostgreSQL logical backups | Deployed |
| Local Loki | Deployed |
| Alloy -> local Loki | Deployed and end-to-end verified |
| Grafana OSS integration | Deployed |
| Station-health persistence | Deployed and used by ML zero-gating |
| Aggregate ML | Live RF + XGBoost + HGB forecasting/scoring |
| Species ML | Live reference + selected challenger forecasting/scoring |
| ML regression tests | Automated and passing during latest infra verification |
| AI Nexus BirdNET consumption | Constrained downstream read-only consumer |
| Rich ML/health -> Birdynator interface | Deferred |
| Off-host PostgreSQL backup | Planned |
| Real restore drill | Still recommended |

## Known limitations

The main technical debt is explicit rather than hidden:

- analytical SQL still uses station-local wall-clock semantics in places
- prediction timestamps retain a DST-overlap ambiguity
- the aggregate analytical view is weather-backed
- PostgreSQL role/\`pg_hba.conf\` recreation is not yet fully automated
- historical precipitation before the explicit inches fix has uncertain unit provenance
- backups still need off-host replication
- Loki network exposure inside the Home Lab can be hardened further

See [docs/architecture.md](docs/architecture.md) and [docs/decisions.md](docs/decisions.md) for context.

## Repository map

| Path | Purpose |
|---|---|
| \`collector/\` | BirdNET SQLite -> PostgreSQL synchronization |
| \`weather/\` | Weather observation and forecast collectors |
| \`health/\` | Hourly station-health provenance |
| \`database/\` | Schema, analytical views, prediction storage, recovery |
| \`alloy/\` | Local-only Alloy configuration |
| \`grafana/\` | BirdNET-specific dashboard exports |
| \`ml/\` | Prediction, scoring, experiments, tests |
| \`backup/\` | PostgreSQL backup scripts |
| \`systemd/\` | Runtime service/timer definitions |
| \`deploy/birdnet-pi/\` | Pi bootstrap and acceptance checks |
| \`deploy/ubuntu-infra/\` | Central infrastructure bootstrap and recovery |
| \`docs/architecture.md\` | Detailed current architecture and boundaries |
| \`docs/ml.md\` | Stable ML methodology |
| \`docs/decisions.md\` | Durable architectural decisions |
| \`docs/experiments/\` | Dated experiment evidence |
| \`AGENTS.md\` | Guardrails for future coding/AI sessions |

## Suggested reading order

For a human reading the project end-to-end:

1. this README
2. [Architecture](docs/architecture.md)
3. [Executive summary](docs/executive-summary.md)
4. [Decision log](docs/decisions.md)
5. [Database](database/README.md)
6. [ML methodology](docs/ml.md)
7. [ML operations](ml/README.md)
8. [Grafana](grafana/README.md)
9. the Pi and infra deployment runbooks

For a new ChatGPT/coding session:

1. \`AGENTS.md\`
2. \`docs/executive-summary.md\`
3. \`docs/architecture.md\`
4. \`docs/decisions.md\`
5. the relevant subsystem document

## Design principles

- Keep BirdNET independent.
- Protect source data.
- Prefer recoverable asynchronous data flows.
- Separate logs from analytical history.
- Preserve predictions as forward evidence.
- Treat missing provenance as unknown rather than inventing certainty.
- Keep AI downstream and read-only where possible.
- Keep Git safe to share: no live IPs, coordinates, credentials, or private topology.
- Prefer small understandable components over hidden automation.
- Make deployed state reproducible enough that a fresh session can rebuild it without relying on conversation memory.```text
BirdNET Pi
  |
  +-- BirdNET analysis
  |     \`-- native birds.db
  |
  +-- detection sync ---------> PostgreSQL on ubuntu-infra
  +-- weather collectors -----> PostgreSQL on ubuntu-infra
  \`-- Grafana Alloy ---------> Loki on ubuntu-infra

ubuntu-infra
  |
  +-- PostgreSQL
  |     +-- detections / weather / forecasts
  |     +-- station-health evidence
  |     +-- analytical views
  |     \`-- stored ML predictions
  |
  +-- Loki
  +-- Prometheus
  +-- Grafana OSS
  \`-- station-health + ML jobs
          |
          \`-- read-only evidence
                 |
                 v
          AI Nexus / Birdynator
```BirdNET-Pi Monitoring

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

\`\`\`text
BirdNET Pi
├─ microphone -> BirdNET analysis -> native birds.db
├─ detection sync ───────────────────────────────┐
├─ weather + forecast collectors ────────────────┤
└─ Grafana Alloy -> local Loki ───────────────┐  │
                                               │  │
ubuntu-infra                                   │  │
├─ Loki <──────────────────────────────────────┘  │
├─ PostgreSQL <───────────────────────────────────┘
│  ├─ detections / weather / forecasts
│  ├─ station-health evidence
│  ├─ analytical views
│  └─ stored ML predictions + scores
├─ hourly station-health + ML jobs
├─ Prometheus
└─ Grafana OSS

             constrained read-only evidence
BirdNET / ubuntu-infra ──────────────────────────> AI Nexus / Birdynator
                                                   └─ separate analysis runs
\`\`\`

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

- \`detections\`
- \`weather_observations\`
- \`weather_forecasts\`
- \`station_health_hourly\`
- \`bird_activity_predictions\`
- \`bird_species_predictions\`

Derived views:

- \`bird_activity_hourly\`
- \`bird_species_hourly\`

A deliberate bridge exists between observability and analysis: hourly BirdNET coverage is derived from Loki and persisted into PostgreSQL because it matters later when deciding whether a zero-detection hour is genuinely quiet or simply lacks reliable station evidence.

## Machine learning

ML is an experimental layer on top of preserved historical evidence, not the reason the data exists.

### Aggregate activity

Live aggregate models:

- Random Forest — established reference
- XGBoost — challenger
- HistGradientBoosting — challenger accumulating forward evidence

Timing contract:

\`\`\`text
station health at :20
ML cycle at :30
completed hour T -> target hour T+2
\`\`\`

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

\`station_health_hourly\` stores analysis coverage and one of:

- \`healthy\`
- \`incomplete\`
- \`unknown\`

Current ML logic keeps positive observations usable, but in the health-evidence era it only treats a zero as a trustworthy biological zero when the station was healthy. Missing evidence stays unknown.

That rule is one of the most important data-quality protections in the project.

## Grafana and observability

The active observability path is local-only:

\`\`\`text
BirdNET Pi -> Grafana Alloy -> Loki on ubuntu-infra -> Grafana OSS
\`\`\`

Grafana Cloud Loki was retired after the local path was runtime-verified.

BirdNET-specific dashboards live in this repository. Shared Grafana deployment, datasource provisioning, and plugins belong to the separate \`homelab-grafana\` repository.

Current dashboard exports include:

- local Bird Home operational dashboard
- historical Cloud dashboard export retained as reference
- aggregate Prediction Lab
- Species Prediction dashboard

See [grafana/README.md](grafana/README.md).

## AI Nexus / Birdynator

AI Nexus is a separate secure agent platform in the Home Lab.

Its Birdynator workflow is downstream of this repository:

\`\`\`text
authoritative BirdNET evidence
        -> constrained read-only datasource boundary
        -> Birdynator analysis
        -> AI Nexus analysis history
\`\`\`

Birdynator does not collect station health and does not become a second owner of BirdNET data. The BirdNET stack remains responsible for provenance, structured history, and ML evidence.

A richer ML-to-Birdynator interface is deferred until the evidence exposed across that boundary is stable enough to be useful without leaking internal implementation details.

## Rebuild and verify

A new session should not reconstruct this system from chat history.

Canonical workflows:

\`\`\`bash
# repository hygiene
make repo-check

# existing BirdNET-Pi host
make pi-bootstrap
make pi-verify

# ubuntu-infra
make infra-bootstrap
make infra-verify
\`\`\`

The Pi and infra verification workflows were exercised successfully against the live hosts on 2026-09-26.

Rebuild contract:

\`\`\`text
Git
+ local runtime configuration / secrets
+ PostgreSQL backup when historical state is required
= reproducible monitoring environment
\`\`\`

BirdNET-Pi itself is installed independently and is not managed by this repository.

See:

- [BirdNET Pi deployment](deploy/birdnet-pi/README.md)
- [ubuntu-infra deployment](deploy/ubuntu-infra/README.md)
- [database backup and recovery](database/README.md)

## Current state

| Area | State |
|---|---|
| Detection sync | Deployed and verified |
| Weather observations | Deployed and verified |
| Weather forecast snapshots | Deployed and verified |
| PostgreSQL | Deployed |
| PostgreSQL logical backups | Deployed |
| Local Loki | Deployed |
| Alloy -> local Loki | Deployed and end-to-end verified |
| Grafana OSS integration | Deployed |
| Station-health persistence | Deployed and used by ML zero-gating |
| Aggregate ML | Live RF + XGBoost + HGB forecasting/scoring |
| Species ML | Live reference + selected challenger forecasting/scoring |
| ML regression tests | Automated and passing during latest infra verification |
| AI Nexus BirdNET consumption | Constrained downstream read-only consumer |
| Rich ML/health -> Birdynator interface | Deferred |
| Off-host PostgreSQL backup | Planned |
| Real restore drill | Still recommended |

## Known limitations

The main technical debt is explicit rather than hidden:

- analytical SQL still uses station-local wall-clock semantics in places
- prediction timestamps retain a DST-overlap ambiguity
- the aggregate analytical view is weather-backed
- PostgreSQL role/\`pg_hba.conf\` recreation is not yet fully automated
- historical precipitation before the explicit inches fix has uncertain unit provenance
- backups still need off-host replication
- Loki network exposure inside the Home Lab can be hardened further

See [docs/architecture.md](docs/architecture.md) and [docs/decisions.md](docs/decisions.md) for context.

## Repository map

| Path | Purpose |
|---|---|
| \`collector/\` | BirdNET SQLite -> PostgreSQL synchronization |
| \`weather/\` | Weather observation and forecast collectors |
| \`health/\` | Hourly station-health provenance |
| \`database/\` | Schema, analytical views, prediction storage, recovery |
| \`alloy/\` | Local-only Alloy configuration |
| \`grafana/\` | BirdNET-specific dashboard exports |
| \`ml/\` | Prediction, scoring, experiments, tests |
| \`backup/\` | PostgreSQL backup scripts |
| \`systemd/\` | Runtime service/timer definitions |
| \`deploy/birdnet-pi/\` | Pi bootstrap and acceptance checks |
| \`deploy/ubuntu-infra/\` | Central infrastructure bootstrap and recovery |
| \`docs/architecture.md\` | Detailed current architecture and boundaries |
| \`docs/ml.md\` | Stable ML methodology |
| \`docs/decisions.md\` | Durable architectural decisions |
| \`docs/experiments/\` | Dated experiment evidence |
| \`AGENTS.md\` | Guardrails for future coding/AI sessions |

## Suggested reading order

For a human reading the project end-to-end:

1. this README
2. [Architecture](docs/architecture.md)
3. [Executive summary](docs/executive-summary.md)
4. [Decision log](docs/decisions.md)
5. [Database](database/README.md)
6. [ML methodology](docs/ml.md)
7. [ML operations](ml/README.md)
8. [Grafana](grafana/README.md)
9. the Pi and infra deployment runbooks

For a new ChatGPT/coding session:

1. \`AGENTS.md\`
2. \`docs/executive-summary.md\`
3. \`docs/architecture.md\`
4. \`docs/decisions.md\`
5. the relevant subsystem document

## Design principles

- Keep BirdNET independent.
- Protect source data.
- Prefer recoverable asynchronous data flows.
- Separate logs from analytical history.
- Preserve predictions as forward evidence.
- Treat missing provenance as unknown rather than inventing certainty.
- Keep AI downstream and read-only where possible.
- Keep Git safe to share: no live IPs, coordinates, credentials, or private topology.
- Prefer small understandable components over hidden automation.
- Make deployed state reproducible enough that a fresh session can rebuild it without relying on conversation memory.
