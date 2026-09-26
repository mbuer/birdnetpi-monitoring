# Executive Summary

## What this project is

BirdNET-Pi Monitoring is the Home Lab data, observability, and machine-learning platform around a BirdNET-Pi station.

BirdNET itself remains independent and authoritative for audio capture and native detections. This repository preserves and enriches that data without making BirdNET depend on the monitoring stack.

The design separates:

- BirdNET source data on the Pi
- durable analytical history in PostgreSQL
- operational observability in local Loki/Grafana
- experimental aggregate and species prediction
- durable station-health provenance used to avoid false biological zeroes

Environment-specific addresses, credentials, and station coordinates intentionally live outside Git.

## Current deployed architecture

```text
BirdNET Pi
├── BirdNET analysis + native SQLite
├── detection sync
├── weather observations
├── weather forecasts
└── Grafana Alloy
        |
        v
     local Loki

ubuntu-infra
├── PostgreSQL
├── Loki
├── Grafana OSS
├── station-health persistence
└── hourly ML prediction/scoring
```

Grafana Cloud Loki has been retired. Local Loki is the active operational log destination.

## Current ML state

Aggregate live models:

- Random Forest — established reference
- XGBoost — challenger
- HistGradientBoosting — experimental challenger accumulating genuine forward evidence

Live species reference forecasts:

- House Finch
- Black Phoebe
- American Crow
- Black-crowned Night-Heron
- Lesser Goldfinch

Species challengers currently exist for Black Phoebe and American Crow.

The timing contract is:

```text
station health at :20
ML cycle at :30
completed hour T -> forecast target T+2
```

Health-aware gating preserves older pre-health history while preventing explicit unreliable zero observations from being treated as biological zeroes.

## Configuration and security boundary

Git must not contain:

- live private IP addresses or subnets
- exact station coordinates
- credentials or tokens
- environment-specific runtime secrets

Safe examples belong in:

```text
config/runtime.example.env
```

Real values belong in an ignored local runtime file.

The repository should remain understandable and rebuildable without publishing the live Home Lab topology.

## Recovery

PostgreSQL receives validated custom-format logical backups. Proxmox snapshots/backups are complementary rollback and recovery mechanisms, not substitutes for database backup.

The highest-value remaining recovery improvement is an off-host copy of the PostgreSQL backups.

## Recommended human reading order

1. [README](../README.md) — project overview and current status
2. [Executive summary](executive-summary.md) — this document
3. [Decision log](decisions.md) — durable architectural choices and why they were made
4. [ubuntu-infra deployment and recovery](../deploy/ubuntu-infra/README.md) — rebuild and operations
5. [Database](../database/README.md) — data contracts, schema, backup, and restore
6. [Grafana](../grafana/README.md) — operational and ML dashboards
7. [ML methodology](ml.md) — stable modeling and validation rules
8. [ML operations](../ml/README.md) — live prediction/scoring workflow
9. [Experiments](experiments/) — dated model findings and historical evidence
10. [Alloy setup](alloy-setup.md) and [Weather setup](weather-setup.md) — Pi-side collectors and observability

## For a new ChatGPT session

A new session should read, in this order:

1. `AGENTS.md`
2. `docs/executive-summary.md`
3. `docs/decisions.md`
4. the subsystem document relevant to the requested work

Do not reconstruct architecture from old chat history when the repository already records the current decision.
