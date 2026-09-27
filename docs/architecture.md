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
