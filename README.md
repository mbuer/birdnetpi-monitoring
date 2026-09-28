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

