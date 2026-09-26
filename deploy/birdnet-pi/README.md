# BirdNET Pi deployment

This directory is the reproducible deployment path for the monitoring components that run beside an existing BirdNET-Pi installation.

BirdNET itself is not installed or managed by this repository.

## What the bootstrap installs

The Pi bootstrap configures:

- detection synchronization to PostgreSQL
- current-weather collection
- hourly weather forecasts
- Grafana Alloy -> local Loki
- systemd services and timers
- required Python packages
- the weather log directory

It does not embed live IP addresses, station coordinates, or credentials in Git.

## Prerequisites

Before running the bootstrap:

1. install and verify BirdNET-Pi itself
2. clone this repository as the Linux user that owns the BirdNET installation
3. install Grafana Alloy using the supported package for the Pi OS
4. create the local runtime configuration

Create the runtime file:

```bash
sudo install -d -m 0755 /etc/birdnet-monitoring
sudo install -m 0600 config/runtime.example.env /etc/birdnet-monitoring/runtime.env
sudoedit /etc/birdnet-monitoring/runtime.env
```

Replace every example value with the real local values. Never commit this file.

Required runtime settings include:

- station ID
- timezone
- latitude / longitude
- PostgreSQL host, database, user, password
- Loki base URL

The detection source defaults to:

```text
~/BirdNET-Pi/scripts/birds.db
```

Set `BIRDNET_SQLITE_DB` only when the BirdNET installation uses a different location.

## Bootstrap

From the repository root:

```bash
make pi-bootstrap
```

or directly:

```bash
sudo bash deploy/birdnet-pi/bootstrap.sh
```

The script derives the repository path and normal runtime user rather than requiring the checkout to live at one exact home-directory path.

If sudo cannot identify the intended BirdNET user, supply it explicitly:

```bash
sudo BIRDNET_RUNTIME_USER=<user> bash deploy/birdnet-pi/bootstrap.sh
```

## Verify

Run:

```bash
make pi-verify
```

The verification checks:

- BirdNET SQLite readability
- Python collector dependencies
- PostgreSQL connectivity
- local Loki readiness
- weather service
- Alloy
- detection-sync timer
- forecast timer
- live Alloy config versus Git
- recent BirdNET and weather log delivery to Loki

Fresh stations may initially warn about missing recent log entries until BirdNET/weather have produced data.

## Separation of responsibilities

The Pi should remain able to perform its primary BirdNET detection function if PostgreSQL, Loki, Grafana, or the infrastructure VM is unavailable.

Monitoring failures must not become BirdNET runtime dependencies.
