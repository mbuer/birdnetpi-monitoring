# Architecture

This document describes how the BirdNET monitoring project fits together today, where its trust boundaries are, and how it connects to the wider Home Lab.

It is intentionally more detailed than the root README and less procedural than the deployment runbooks.

## System goals

The system is designed around four priorities:

1. keep BirdNET independent and reliable at the edge
2. preserve detections and environmental context durably
3. separate operational observability from analytical history
4. expose trustworthy analytical evidence to downstream tools without giving them ownership of collection

The most important boundary is simple:

> BirdNET must continue detecting birds even if PostgreSQL, Loki, Grafana, ML, or AI Nexus is unavailable.

## High-level architecture

```text
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
```

Grafana deployment is maintained in the separate `homelab-grafana` repository. AI Nexus is maintained in the separate `ai-nexus` repository.

This repository owns the BirdNET-side collection, structured data model, observability integration, station-health evidence, ML workflow, BirdNET-specific dashboards, and the contract that downstream consumers can rely on.

## Component ownership

### BirdNET Pi: authoritative edge source

The Raspberry Pi owns:

- microphone and audio capture
- BirdNET analysis
- native BirdNET SQLite database
- detection synchronization
- current-weather collection
- weather forecast collection
- Grafana Alloy
- local operational logs

BirdNET's native SQLite database remains the authoritative source for completed detections. Monitoring code reads it but does not modify it merely to simplify downstream processing.

### ubuntu-infra: durable data and analysis

The infrastructure VM owns:

- PostgreSQL
- Loki
- Prometheus
- Grafana OSS host
- station-health persistence
- aggregate activity ML
- species-presence ML
- prediction scoring
- PostgreSQL logical backups

The current hourly sequencing is:

```text
:20  station-health collection
:30  ML scoring + prediction
```

That ordering matters because the ML pipeline uses station-health provenance when deciding whether a zero-detection observation is trustworthy.

### Grafana: visualization, not ownership

Grafana combines multiple data products:

- Loki for operational logs and recent BirdNET events
- PostgreSQL for historical analysis and prediction results
- Prometheus for infrastructure metrics
- Infinity/Open-Meteo for selected live weather panels

Grafana does not become the source of truth for any of those datasets.

### AI Nexus / Birdynator: downstream analytical consumer

AI Nexus is deliberately outside the BirdNET collection path.

Birdynator can consume BirdNET data through a constrained read-only datasource boundary, but:

- BirdNET/ubuntu-infra remain authoritative
- Birdynator does not collect station health
- Birdynator does not own the detection importer, weather collectors, or ML jobs
- Birdynator does not write back into BirdNET source data
- raw BirdNET rows are not copied into long-term agent memory merely for convenience
- Birdynator analysis runs are stored on the AI Nexus side, separate from BirdNET source history

The current AI integration should therefore be understood as:

```text
BirdNET / ubuntu-infra
        │
        │ authoritative evidence
        v
constrained read-only boundary
        │
        v
AI Nexus / Birdynator
        │
        └─ interpretation / analysis
```

A broader ML-to-Birdynator evidence interface is intentionally deferred until the ML outputs and provenance contract are stable enough to expose cleanly. Future downstream evidence may include health state such as `healthy`, `incomplete`, or `unknown` so an AI analysis does not mistake missing station evidence for biological absence.

That future interface should remain narrow and read-only rather than coupling Birdynator directly to internal training code or collector implementation details.

## Data roles

### BirdNET SQLite

Role: authoritative edge source for completed detections.

The importer is incremental and read-only. PostgreSQL uniqueness rules provide replay protection.

### PostgreSQL

Role: durable structured analytical history.

Core tables:

- `detections`
- `weather_observations`
- `weather_forecasts`
- `station_health_hourly`
- `bird_activity_predictions`
- `bird_species_predictions`

Derived views:

- `bird_activity_hourly`
- `bird_species_hourly`

PostgreSQL answers questions such as:

- what was detected historically?
- what weather was observed or forecast?
- what prediction was actually issued before an outcome?
- was a zero-detection hour backed by healthy station evidence?

### Loki

Role: operational observability.

Loki answers questions such as:

- is BirdNET analysis still producing log evidence?
- is the weather collector writing?
- what did the service do recently?

Loki retention is intentionally shorter than the analytical history in PostgreSQL.

Compact health provenance is the deliberate bridge between those roles: recent operational evidence is summarized into `station_health_hourly` because that information has long-term analytical value.

### Prediction tables

Predictions are historical evidence, not disposable cache.

A stored prediction records what the model actually forecast before the target outcome was known. Retrospective model reruns must not be presented as if they were genuine forward forecasts.

## ML architecture

There are two prediction tracks.

### Aggregate activity

Live models:

- `random_forest_v2_completed` — established reference
- `xgboost_v2_completed` — challenger
- `hist_gradient_boosting_v1_completed` — challenger accumulating forward evidence

Timing:

```text
completed hour T -> target hour T+2
```

Current feature families include:

- hour of day
- sunrise-relative time
- day/night state
- current activity
- 1h / 2h / 3h / 24h activity lags

Weather is present in the aggregate analytical view but is not currently used as a live model feature.

### Species presence

The live reference set currently includes:

- House Finch
- Black Phoebe
- American Crow
- Black-crowned Night-Heron
- Lesser Goldfinch

Reference models are Random Forest and XGBoost. Separate challenger strategies currently exist for Black Phoebe and American Crow.

Species prediction remains experimental. Probability quality, classification thresholds, sparse positives, and forward-validation history matter more than simply increasing the number of species.

## Health-aware data quality

A zero detection is only biologically meaningful if the station was actually in a state where it could have detected something.

The station-health collector derives hourly analysis coverage from BirdNET journal evidence in Loki and persists:

- analysis segment count
- expected segment count
- coverage percentage
- `healthy`, `incomplete`, or `unknown`

Current ML behavior is provenance-aware:

- positive activity/presence remains usable even when health is incomplete or unknown
- a zero in the explicit health era is only treated as a biological zero when health is `healthy`
- missing health evidence is `unknown`, not a fabricated outage and not a biological zero
- older pre-health historical data remains usable under the legacy methodology

This is intentionally narrower than weighting every row by coverage. It fixes the known false-zero problem without adding model complexity that has not yet earned its keep.

## Security and trust boundaries

Environment-specific values stay outside Git.

Do not commit:

- live private IP addresses or subnets
- exact station coordinates
- credentials, tokens, or private keys
- database dumps
- runtime `.env` files
- public WAN/DDNS details

Git contains the configuration shape and recovery logic. The live environment supplies secrets and topology.

The primary trust boundaries are:

```text
BirdNET source
    -> read-only monitoring access

Pi collectors
    -> authenticated PostgreSQL write path
    -> local Loki write path

Grafana
    -> read-only analytical/observability access

AI Nexus
    -> constrained read-only BirdNET evidence
```

AI Nexus must not become an alternate write path into BirdNET source data.

## Failure behavior

The architecture prefers asynchronous failure over tight coupling.

If PostgreSQL is down:

- BirdNET should continue detecting into its native SQLite database
- detection sync can catch up later

If Loki is down:

- BirdNET should continue detecting
- PostgreSQL history can continue independently where collectors still have DB access
- station-health evidence may become `unknown`

If Grafana is down:

- collection and analysis should continue

If ML fails:

- source history and observability remain intact

If AI Nexus is down:

- BirdNET monitoring and prediction continue normally

That separation is a core design property, not an accident.

## Reproducibility model

The monitoring stack is intended to be recoverable from:

```text
Git
+ local runtime configuration / secrets
+ PostgreSQL backup when historical state is required
```

Canonical acceptance tests:

```bash
make repo-check
make pi-verify
make infra-verify
```

The Pi and infra verification workflows were runtime-validated against the live hosts on 2026-09-26.

See:

- [BirdNET Pi deployment](../deploy/birdnet-pi/README.md)
- [ubuntu-infra deployment](../deploy/ubuntu-infra/README.md)
- [Database and recovery](../database/README.md)

## Known architectural debt

Current known debt includes:

- analytical SQL still encodes Los Angeles wall-clock semantics
- some prediction timestamps are `timestamp without time zone`, creating DST ambiguity
- the aggregate activity view is weather-backed
- PostgreSQL roles and `pg_hba.conf` policy are not yet fully reproduced by committed automation
- PostgreSQL backups are not yet replicated off-host
- Loki is directly reachable inside the Home Lab
- historical precipitation before the explicit inches fix has uncertain unit provenance
- some legacy Pi-local PostgreSQL backup artifacts remain in the repository for migration history
- the future ML/health evidence boundary to Birdynator is not yet a stable public interface

These are documented limitations, not reasons to hide the current system behind extra abstraction.

## Architectural rule of thumb

When deciding where new functionality belongs:

- sensing and native detections belong on BirdNET
- durable structured evidence belongs in PostgreSQL
- operational events belong in Loki
- visualization belongs in Grafana
- prediction methodology belongs in the ML layer
- interpretation and agent workflows belong in AI Nexus
- cross-system interfaces should be narrow, explicit, and preferably read-only```text
BirdNET / ubuntu-infra
        |
        | authoritative evidence
        v
constrained read-only boundary
        |
        v
AI Nexus / Birdynator
        |
        `-- interpretation / analysis
```Architecture

This document describes how the BirdNET monitoring project fits together today, where its trust boundaries are, and how it connects to the wider Home Lab.

It is intentionally more detailed than the root README and less procedural than the deployment runbooks.

## System goals

The system is designed around four priorities:

1. keep BirdNET independent and reliable at the edge
2. preserve detections and environmental context durably
3. separate operational observability from analytical history
4. expose trustworthy analytical evidence to downstream tools without giving them ownership of collection

The most important boundary is simple:

> BirdNET must continue detecting birds even if PostgreSQL, Loki, Grafana, ML, or AI Nexus is unavailable.

## High-level architecture

```text
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
```

Grafana deployment is maintained in the separate `homelab-grafana` repository. AI Nexus is maintained in the separate `ai-nexus` repository.

This repository owns the BirdNET-side collection, structured data model, observability integration, station-health evidence, ML workflow, BirdNET-specific dashboards, and the contract that downstream consumers can rely on.

## Component ownership

### BirdNET Pi: authoritative edge source

The Raspberry Pi owns:

- microphone and audio capture
- BirdNET analysis
- native BirdNET SQLite database
- detection synchronization
- current-weather collection
- weather forecast collection
- Grafana Alloy
- local operational logs

BirdNET's native SQLite database remains the authoritative source for completed detections. Monitoring code reads it but does not modify it merely to simplify downstream processing.

### ubuntu-infra: durable data and analysis

The infrastructure VM owns:

- PostgreSQL
- Loki
- Prometheus
- Grafana OSS host
- station-health persistence
- aggregate activity ML
- species-presence ML
- prediction scoring
- PostgreSQL logical backups

The current hourly sequencing is:

```text
:20  station-health collection
:30  ML scoring + prediction
```

That ordering matters because the ML pipeline uses station-health provenance when deciding whether a zero-detection observation is trustworthy.

### Grafana: visualization, not ownership

Grafana combines multiple data products:

- Loki for operational logs and recent BirdNET events
- PostgreSQL for historical analysis and prediction results
- Prometheus for infrastructure metrics
- Infinity/Open-Meteo for selected live weather panels

Grafana does not become the source of truth for any of those datasets.

### AI Nexus / Birdynator: downstream analytical consumer

AI Nexus is deliberately outside the BirdNET collection path.

Birdynator can consume BirdNET data through a constrained read-only datasource boundary, but:

- BirdNET/ubuntu-infra remain authoritative
- Birdynator does not collect station health
- Birdynator does not own the detection importer, weather collectors, or ML jobs
- Birdynator does not write back into BirdNET source data
- raw BirdNET rows are not copied into long-term agent memory merely for convenience
- Birdynator analysis runs are stored on the AI Nexus side, separate from BirdNET source history

The current AI integration should therefore be understood as:

```text
BirdNET / ubuntu-infra
        │
        │ authoritative evidence
        v
constrained read-only boundary
        │
        v
AI Nexus / Birdynator
        │
        └─ interpretation / analysis
```

A broader ML-to-Birdynator evidence interface is intentionally deferred until the ML outputs and provenance contract are stable enough to expose cleanly. Future downstream evidence may include health state such as `healthy`, `incomplete`, or `unknown` so an AI analysis does not mistake missing station evidence for biological absence.

That future interface should remain narrow and read-only rather than coupling Birdynator directly to internal training code or collector implementation details.

## Data roles

### BirdNET SQLite

Role: authoritative edge source for completed detections.

The importer is incremental and read-only. PostgreSQL uniqueness rules provide replay protection.

### PostgreSQL

Role: durable structured analytical history.

Core tables:

- `detections`
- `weather_observations`
- `weather_forecasts`
- `station_health_hourly`
- `bird_activity_predictions`
- `bird_species_predictions`

Derived views:

- `bird_activity_hourly`
- `bird_species_hourly`

PostgreSQL answers questions such as:

- what was detected historically?
- what weather was observed or forecast?
- what prediction was actually issued before an outcome?
- was a zero-detection hour backed by healthy station evidence?

### Loki

Role: operational observability.

Loki answers questions such as:

- is BirdNET analysis still producing log evidence?
- is the weather collector writing?
- what did the service do recently?

Loki retention is intentionally shorter than the analytical history in PostgreSQL.

Compact health provenance is the deliberate bridge between those roles: recent operational evidence is summarized into `station_health_hourly` because that information has long-term analytical value.

### Prediction tables

Predictions are historical evidence, not disposable cache.

A stored prediction records what the model actually forecast before the target outcome was known. Retrospective model reruns must not be presented as if they were genuine forward forecasts.

## ML architecture

There are two prediction tracks.

### Aggregate activity

Live models:

- `random_forest_v2_completed` — established reference
- `xgboost_v2_completed` — challenger
- `hist_gradient_boosting_v1_completed` — challenger accumulating forward evidence

Timing:

```text
completed hour T -> target hour T+2
```

Current feature families include:

- hour of day
- sunrise-relative time
- day/night state
- current activity
- 1h / 2h / 3h / 24h activity lags

Weather is present in the aggregate analytical view but is not currently used as a live model feature.

### Species presence

The live reference set currently includes:

- House Finch
- Black Phoebe
- American Crow
- Black-crowned Night-Heron
- Lesser Goldfinch

Reference models are Random Forest and XGBoost. Separate challenger strategies currently exist for Black Phoebe and American Crow.

Species prediction remains experimental. Probability quality, classification thresholds, sparse positives, and forward-validation history matter more than simply increasing the number of species.

## Health-aware data quality

A zero detection is only biologically meaningful if the station was actually in a state where it could have detected something.

The station-health collector derives hourly analysis coverage from BirdNET journal evidence in Loki and persists:

- analysis segment count
- expected segment count
- coverage percentage
- `healthy`, `incomplete`, or `unknown`

Current ML behavior is provenance-aware:

- positive activity/presence remains usable even when health is incomplete or unknown
- a zero in the explicit health era is only treated as a biological zero when health is `healthy`
- missing health evidence is `unknown`, not a fabricated outage and not a biological zero
- older pre-health historical data remains usable under the legacy methodology

This is intentionally narrower than weighting every row by coverage. It fixes the known false-zero problem without adding model complexity that has not yet earned its keep.

## Security and trust boundaries

Environment-specific values stay outside Git.

Do not commit:

- live private IP addresses or subnets
- exact station coordinates
- credentials, tokens, or private keys
- database dumps
- runtime `.env` files
- public WAN/DDNS details

Git contains the configuration shape and recovery logic. The live environment supplies secrets and topology.

The primary trust boundaries are:

```text
BirdNET source
    -> read-only monitoring access

Pi collectors
    -> authenticated PostgreSQL write path
    -> local Loki write path

Grafana
    -> read-only analytical/observability access

AI Nexus
    -> constrained read-only BirdNET evidence
```

AI Nexus must not become an alternate write path into BirdNET source data.

## Failure behavior

The architecture prefers asynchronous failure over tight coupling.

If PostgreSQL is down:

- BirdNET should continue detecting into its native SQLite database
- detection sync can catch up later

If Loki is down:

- BirdNET should continue detecting
- PostgreSQL history can continue independently where collectors still have DB access
- station-health evidence may become `unknown`

If Grafana is down:

- collection and analysis should continue

If ML fails:

- source history and observability remain intact

If AI Nexus is down:

- BirdNET monitoring and prediction continue normally

That separation is a core design property, not an accident.

## Reproducibility model

The monitoring stack is intended to be recoverable from:

```text
Git
+ local runtime configuration / secrets
+ PostgreSQL backup when historical state is required
```

Canonical acceptance tests:

```bash
make repo-check
make pi-verify
make infra-verify
```

The Pi and infra verification workflows were runtime-validated against the live hosts on 2026-09-26.

See:

- [BirdNET Pi deployment](../deploy/birdnet-pi/README.md)
- [ubuntu-infra deployment](../deploy/ubuntu-infra/README.md)
- [Database and recovery](../database/README.md)

## Known architectural debt

Current known debt includes:

- analytical SQL still encodes Los Angeles wall-clock semantics
- some prediction timestamps are `timestamp without time zone`, creating DST ambiguity
- the aggregate activity view is weather-backed
- PostgreSQL roles and `pg_hba.conf` policy are not yet fully reproduced by committed automation
- PostgreSQL backups are not yet replicated off-host
- Loki is directly reachable inside the Home Lab
- historical precipitation before the explicit inches fix has uncertain unit provenance
- some legacy Pi-local PostgreSQL backup artifacts remain in the repository for migration history
- the future ML/health evidence boundary to Birdynator is not yet a stable public interface

These are documented limitations, not reasons to hide the current system behind extra abstraction.

## Architectural rule of thumb

When deciding where new functionality belongs:

- sensing and native detections belong on BirdNET
- durable structured evidence belongs in PostgreSQL
- operational events belong in Loki
- visualization belongs in Grafana
- prediction methodology belongs in the ML layer
- interpretation and agent workflows belong in AI Nexus
- cross-system interfaces should be narrow, explicit, and preferably read-only
