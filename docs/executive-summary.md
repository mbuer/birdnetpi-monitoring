# Executive Summary

BirdNET-Pi Monitoring is the Home Lab data, observability, and machine-learning platform around an independent BirdNET-Pi station.

The project preserves BirdNET detections, enriches them with weather and station-health provenance, stores durable history in PostgreSQL, observes runtime behavior through local Loki/Grafana, issues live aggregate/species forecasts, and exposes BirdNET evidence downstream to AI Nexus without giving the agent platform ownership of collection.

## Current architecture

\`\`\`text
BirdNET Pi
├─ BirdNET analysis + native SQLite
├─ detection sync ───────────────┐
├─ weather + forecast ───────────┤
└─ Alloy -> local Loki ───────┐  │
                              │  │
ubuntu-infra                  │  │
├─ Loki <─────────────────────┘  │
├─ PostgreSQL <──────────────────┘
├─ station-health persistence
├─ hourly ML prediction/scoring
├─ Prometheus
└─ Grafana OSS
        │
        │ constrained read-only evidence
        v
AI Nexus / Birdynator
└─ separate downstream analysis
\`\`\`

BirdNET remains authoritative for native detections. PostgreSQL is the durable analytical store. Loki is the operational log store. AI Nexus is a downstream consumer, not part of the collection path.

See [Architecture](architecture.md) for the detailed boundaries and failure model.

## Data-quality contract

The system explicitly distinguishes a healthy quiet hour from missing evidence.

\`station_health_hourly\` stores Loki-derived BirdNET analysis coverage as:

- \`healthy\`
- \`incomplete\`
- \`unknown\`

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

\`\`\`text
station health at :20
ML at :30
completed hour T -> target T+2
\`\`\`

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

\`\`\`bash
make repo-check
make pi-bootstrap
make pi-verify
make infra-bootstrap
make infra-verify
\`\`\`

The Pi and infra verification suites both passed against the live hosts on 2026-09-26.

Recovery model:

\`\`\`text
Git
+ local configuration / secrets
+ PostgreSQL backup when historical state is required
\`\`\`

Grafana infrastructure remains in \`homelab-grafana\`. AI Nexus remains in \`ai-nexus\`.

## Highest-value remaining work

- replicate PostgreSQL backups off-host
- perform a real restore drill
- make PostgreSQL roles/access policy more reproducible
- continue matched forward-validation for aggregate and species challengers
- reduce remaining local-wall-clock/DST debt
- harden Loki network exposure
- define the future Birdynator ML/health evidence interface only after the upstream evidence is stable

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

1. \`AGENTS.md\`
2. this executive summary
3. \`docs/architecture.md\`
4. \`docs/decisions.md\`
5. the relevant subsystem document

Prefer the repository's current architecture over remembered chat history when the two disagree.```text
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
```Executive Summary

BirdNET-Pi Monitoring is the Home Lab data, observability, and machine-learning platform around an independent BirdNET-Pi station.

The project preserves BirdNET detections, enriches them with weather and station-health provenance, stores durable history in PostgreSQL, observes runtime behavior through local Loki/Grafana, issues live aggregate/species forecasts, and exposes BirdNET evidence downstream to AI Nexus without giving the agent platform ownership of collection.

## Current architecture

\`\`\`text
BirdNET Pi
├─ BirdNET analysis + native SQLite
├─ detection sync ───────────────┐
├─ weather + forecast ───────────┤
└─ Alloy -> local Loki ───────┐  │
                              │  │
ubuntu-infra                  │  │
├─ Loki <─────────────────────┘  │
├─ PostgreSQL <──────────────────┘
├─ station-health persistence
├─ hourly ML prediction/scoring
├─ Prometheus
└─ Grafana OSS
        │
        │ constrained read-only evidence
        v
AI Nexus / Birdynator
└─ separate downstream analysis
\`\`\`

BirdNET remains authoritative for native detections. PostgreSQL is the durable analytical store. Loki is the operational log store. AI Nexus is a downstream consumer, not part of the collection path.

See [Architecture](architecture.md) for the detailed boundaries and failure model.

## Data-quality contract

The system explicitly distinguishes a healthy quiet hour from missing evidence.

\`station_health_hourly\` stores Loki-derived BirdNET analysis coverage as:

- \`healthy\`
- \`incomplete\`
- \`unknown\`

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

\`\`\`text
station health at :20
ML at :30
completed hour T -> target T+2
\`\`\`

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

\`\`\`bash
make repo-check
make pi-bootstrap
make pi-verify
make infra-bootstrap
make infra-verify
\`\`\`

The Pi and infra verification suites both passed against the live hosts on 2026-09-26.

Recovery model:

\`\`\`text
Git
+ local configuration / secrets
+ PostgreSQL backup when historical state is required
\`\`\`

Grafana infrastructure remains in \`homelab-grafana\`. AI Nexus remains in \`ai-nexus\`.

## Highest-value remaining work

- replicate PostgreSQL backups off-host
- perform a real restore drill
- make PostgreSQL roles/access policy more reproducible
- continue matched forward-validation for aggregate and species challengers
- reduce remaining local-wall-clock/DST debt
- harden Loki network exposure
- define the future Birdynator ML/health evidence interface only after the upstream evidence is stable

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

1. \`AGENTS.md\`
2. this executive summary
3. \`docs/architecture.md\`
4. \`docs/decisions.md\`
5. the relevant subsystem document

Prefer the repository's current architecture over remembered chat history when the two disagree.
