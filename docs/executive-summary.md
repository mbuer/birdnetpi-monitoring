# Executive Summary

BirdNET-Pi Monitoring is the Home Lab data, observability, and machine-learning platform around an independent BirdNET-Pi station.

The project preserves BirdNET detections, enriches them with weather and station-health provenance, stores durable history in PostgreSQL, observes runtime behavior through local Loki/Grafana, issues live aggregate/species forecasts, and exposes BirdNET evidence downstream to AI Nexus without giving the agent platform ownership of collection.

## Current architecture

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

BirdNET remains authoritative for native detections. PostgreSQL is the durable analytical store. Loki is the operational log store. AI Nexus is a downstream consumer, not part of the collection path.

See [Architecture](architecture.md) for the detailed boundaries and failure model.

## Data-quality contract

The system explicitly distinguishes a healthy quiet hour from missing evidence.

`station_health_hourly` stores Loki-derived BirdNET analysis coverage as:

- `healthy`
- `incomplete`
- `unknown`

Current ML uses this provenance when handling zero observations. Positive detections remain useful, while explicit zeroes in the health era are only treated as biological zeroes when station health is healthy.

## Current ML state

Aggregate live models:

- Random Forest — established reference
- XGBoost — challenger
- HistGradientBoosting — challenger accumulating forward evidence

Reference species:

- House Finch
- Black Phoebe
- American Crow
- Black-crowned Night-Heron
- Lesser Goldfinch

Selected species challengers currently exist for Black Phoebe and American Crow.

Timing:

```text
station health at :20
ML at :30
completed hour T -> target T+2
```

Stored forecasts are preserved as genuine forward evidence rather than overwritten by retrospective reruns.

## AI Nexus boundary

Birdynator consumes BirdNET evidence through a constrained read-only boundary.

It does not:

- collect detections or weather
- collect station health
- own the PostgreSQL/Loki data path
- write into BirdNET source data

AI Nexus stores its own analysis runs separately.

A richer ML/health evidence interface is intentionally deferred until the analytical contract is stable enough to expose cleanly.

## Reproducibility

Environment-specific addresses, coordinates, and credentials stay outside Git.

Canonical workflows:

```bash
make repo-check
make pi-bootstrap
make pi-verify
make infra-bootstrap
make infra-verify
```

The Pi and infra verification suites both passed against the live hosts on 2026-09-26.

Recovery model:

```text
Git
+ local configuration / secrets
+ PostgreSQL backup when historical state is required
```

Grafana infrastructure remains in `homelab-grafana`. AI Nexus remains in `ai-nexus`.

## Simplified remaining scope

Infrastructure work is deliberately limited to three remaining essentials:

1. off-host PostgreSQL backup plus one real restore drill
2. reproducible narrow PostgreSQL roles/grants and host access policy
3. cleanup of clearly obsolete Cloud-era and Pi-local migration artifacts

After those are complete, treat the infrastructure as frozen unless a concrete failure, security exposure, recovery problem, or feature requirement justifies reopening it.

Do not pursue hardening for its own sake. Docker/Alloy auto-installation, large verification frameworks, timestamp redesign, aggregate-view redesign, and broader network hardening are not active priorities.

The preferred next phase is Birdynator analysis, useful reports, anomaly detection, and patient forward-validation of the existing ML models.

## Recommended human reading order

1. [README](../README.md)
2. [Architecture](architecture.md)
3. [Decision log](decisions.md)
4. [Database](../database/README.md)
5. [ML methodology](ml.md)
6. [ML operations](../ml/README.md)
7. [Grafana](../grafana/README.md)
8. [BirdNET Pi deployment](../deploy/birdnet-pi/README.md)
9. [ubuntu-infra deployment](../deploy/ubuntu-infra/README.md)
10. dated material in [experiments](experiments/) when you want model history

## For a new ChatGPT session

Read:

1. `AGENTS.md`
2. this executive summary
3. `docs/architecture.md`
4. `docs/decisions.md`
5. the relevant subsystem document

Prefer the repository's current architecture over remembered chat history when the two disagree.
