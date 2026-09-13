# ubuntu-infra Deployment

This directory contains the Home Lab server-side deployment for BirdNET monitoring.

The BirdNET Raspberry Pi remains responsible for:

- audio capture
- BirdNET detection
- the native `birds.db` SQLite database
- local collection jobs
- Alloy log shipping

`ubuntu-infra` provides the centralized services:

- PostgreSQL
- Loki
- Grafana

## Target architecture

    BirdNET Pi
        |
        +--> birds.db
        |      |
        |      +--> import_detections.py
        |                 |
        |                 v
        |             PostgreSQL
        |
        +--> weather.py ----------> PostgreSQL
        |
        +--> Grafana Alloy -------> Loki

    ubuntu-infra
        |
        +--> PostgreSQL
        +--> Loki
        +--> Grafana

Grafana itself is deployed separately through the `homelab-grafana` repository.

This repository contains the BirdNET-specific ingestion, database, and observability configuration.

## Migration order

1. deploy PostgreSQL on `ubuntu-infra`
2. migrate the existing PostgreSQL data
3. point BirdNET collectors at the new PostgreSQL instance
4. deploy Loki on `ubuntu-infra`
5. point Alloy at local Loki
6. provision the BirdNET Grafana dashboard locally
7. verify local operation
8. retire Grafana Cloud dependencies
