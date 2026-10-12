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

Infrastructure status: **frozen by default**. The planned recovery, access-control, and legacy-cleanup work is complete; reopen infrastructure only for a concrete operational, security, recovery, or feature need.

## Architecture at a glance

```text
BirdNET Pi: native detections + weather collectors -> PostgreSQL on ubuntu-infra
            Grafana Alloy                       -> Loki on ubuntu-infra

ubuntu-infra: station-health evidence + hourly ML -> stored predictions
             PostgreSQL + Loki                  -> Grafana dashboards
             read-only PostgreSQL evidence      -> AI Nexus / Birdynator
```

BirdNET's native SQLite database remains authoritative for detections. PostgreSQL stores durable analytical history; Loki stores operational logs. Birdynator interprets upstream evidence without owning collection or writing into BirdNET source data. Shared Grafana deployment belongs to `homelab-grafana`; the agent runtime belongs to `ai-nexus`.

## Operating the system

Start with the runbook for the host you are changing. Keep real addresses, station coordinates, and credentials in ignored local configuration, using [the runtime example](config/runtime.example.env) as a template.

| Task | Runbook | Commands |
|---|---|---|
| Deploy or verify Pi integration | [BirdNET Pi](deploy/birdnet-pi/README.md) | `make pi-bootstrap`, `make pi-verify` |
| Deploy or verify centralized services | [ubuntu-infra](deploy/ubuntu-infra/README.md) | `make infra-bootstrap`, `make infra-verify` |
| Check repository hygiene | [Agent guidance](AGENTS.md) | `make repo-check` |
| Back up or test database recovery | [Backup and recovery](docs/backup-recovery.md) | `make backup`, `make restore-test` |
| Run ML regression tests | [ML operations](ml/README.md) | `make test` |

Host verification requires the corresponding deployed services. A repository check alone does not establish live health. Recovery combines validated logical PostgreSQL dumps with the off-host Proxmox backup chain.

## Understanding the evidence

Live forecasts are experimental and use completed hour T to predict T+2. Station-health evidence distinguishes healthy quiet hours from incomplete or unknown observations. Stored forecasts and later scores support forward validation; they are not proof of ecological forecasting accuracy.

See [ML methodology](docs/ml.md) for timing, health gates, and limitations, and [experiment findings](docs/experiments/) for dated results.

## Read next

- [Executive summary](docs/executive-summary.md): current state and reading order
- [Architecture](docs/architecture.md): ownership, data flow, and failure boundaries
- [Database](database/README.md) and [station health](health/README.md): data contracts
- [Grafana dashboards](grafana/README.md): imports, datasources, and interpretation
- [Decision log](docs/decisions.md): historical context and current decisions
- [Agent guidance](AGENTS.md): invariants and required checks for changes

