# ubuntu-infra BirdNET Deployment

This directory documents the BirdNET services that run on the Home Lab infrastructure VM.

The architecture keeps the Raspberry Pi focused on sensing and collection while durable storage, observability, dashboards, and ML workloads run centrally.

---

# Hosts

## BirdNET Pi

Current address: `192.168.1.136`

Responsibilities:

- microphone and audio capture
- BirdNET analysis
- BirdNET native `birds.db`
- detection synchronization
- weather observation collection
- weather forecast collection
- Grafana Alloy
- local logs

The Pi remains the authoritative source for completed BirdNET detections.

## ubuntu-infra

Current address: `192.168.1.137`

Responsibilities:

- PostgreSQL
- Loki
- Prometheus
- Grafana OSS host
- Python ML experiments
- live aggregate activity prediction/scoring
- live reference species prediction/scoring plus configured challenger forecasts

Grafana deployment itself is maintained in the separate `homelab-grafana` repository.

---

# Architecture

```text
BirdNET Pi
|
|-- birds.db
|    `-- import_detections.py ------> PostgreSQL
|-- weather.py --------------------> PostgreSQL
|-- forecast.py ------------------> PostgreSQL
|
`-- Grafana Alloy
    |--> Grafana Cloud Loki
    `--> Local Loki ---------------> Grafana OSS

ubuntu-infra
|-- PostgreSQL
|    |-- detections
|    |-- weather observations
|    |-- weather forecasts
|    |-- activity predictions
|    `-- species predictions
|-- Loki
|-- Prometheus
|-- Grafana OSS
`-- BirdNET ML hourly cycle
```

PostgreSQL is the structured historical datastore. Loki is the operational log datastore.

Grafana Alloy is intended to dual-write operational logs to Grafana Cloud Loki and local Loki while the local stack is being validated.

---

# Deployment Layout

```text
deploy/ubuntu-infra/
|
|-- README.md
|-- postgres/
|   |-- compose.yaml
|   |-- .env.example
|   `-- .env          # runtime only, ignored
|
`-- loki/
    |-- compose.yaml
    `-- loki-config.yaml
```

Shared database, ML, Grafana, backup, and systemd assets live elsewhere in the repository.

---

# PostgreSQL

Status: **DEPLOYED**

Container: `birdnet-postgres`  
Image: `postgres:17.2`  
Database: `birdnet`  
Application role: `birdnet`  
Published port: `5432`

Persistent storage uses a Docker named volume.

The Compose deployment bootstraps the base schema from `database/schema.sql` only when PostgreSQL initializes a new data volume.

Additional analytical objects must be applied separately:

```text
database/views/bird_activity_hourly.sql
database/views/bird_species_hourly.sql
database/predictions.sql
database/species_predictions.sql
```

See [database/README.md](../../database/README.md) for application order, grants, timestamp semantics, and rebuild details.

---

# BirdNET Client Configuration

The Pi uses:

```text
/home/birduser/.config/birdnet-monitoring/db.env
```

Variables:

```text
BIRDNET_DB_HOST
BIRDNET_DB_NAME
BIRDNET_DB_USER
BIRDNET_DB_PASSWORD
```

The installed systemd services load this file. It contains runtime secrets and must never be committed.

---

# PostgreSQL Access Control

The live deployment is intentionally scoped rather than open to the LAN.

Known required clients include:

- BirdNET Pi ingestion from `192.168.1.136/32`
- Grafana through its Docker network
- local ML jobs through the infrastructure host/container path

The read-only Grafana role is `grafana_reader` and requires SELECT access to both analytical views and both prediction tables.

Authentication rules are host-specific runtime configuration. During rebuild, compare the live `pg_hba.conf` and Docker network ranges before recreating them; do not replace them with broad `0.0.0.0/0` rules for convenience.

---

# PostgreSQL Backups

Backup script: `backup/backup_infra_postgres.sh`  
Runtime destination: `/var/backups/birdnet-postgres`  
Schedule: `03:15 America/Los_Angeles`  
Retention: `14 days`

Systemd units:

```text
birdnet-postgres-backup.service
birdnet-postgres-backup.timer
```

The older `backup/backup_postgres.sh` and `birdnet-db-backup.*` units are retained only as Pi-local migration/recovery history. They are not the current centralized backup path.

Validate an archive with:

```bash
pg_restore -l /var/backups/birdnet-postgres/birdnet-YYYY-MM-DD_HH-MM-SS.dump
```

These backups currently live on the same infrastructure VM as PostgreSQL. Off-host replication remains an important disaster-recovery improvement.

---

# Useful PostgreSQL Checks

```bash
docker ps --filter name=birdnet-postgres
docker logs birdnet-postgres --tail 50
docker exec birdnet-postgres psql -U birdnet -d birdnet -c '\dt'
docker exec birdnet-postgres psql -U birdnet -d birdnet -c '\dv'
```

Recent aggregate predictions:

```bash
docker exec birdnet-postgres psql -U birdnet -d birdnet -c "
SELECT prediction_created_at, predicted_hour, model,
       actual_activity, scored_at
FROM bird_activity_predictions
ORDER BY predicted_hour DESC
LIMIT 10;
"
```

Recent species predictions:

```bash
docker exec birdnet-postgres psql -U birdnet -d birdnet -c "
SELECT prediction_created_at, species, predicted_hour,
       model, probability, actual_present, scored_at
FROM bird_species_predictions
ORDER BY predicted_hour DESC, species
LIMIT 20;
"
```

---

# Loki

Status: **DEPLOYED**

Container: `birdnet-loki`  
Image: `grafana/loki:3.5.5`  
Published port: `3100`  
Retention: `30 days`

The local path has been verified for BirdNET journal ingestion, parsed detection logs, weather JSONL ingestion, persistence across container restart, and Grafana OSS queries.

The repository `alloy/config.alloy` now reflects the intended local + Cloud dual-write architecture. Before deploying it to the Pi, compare it with the currently installed `/etc/alloy/config.alloy` and preserve any working runtime-only credentials or differences.

Historical Grafana Cloud Loki data is not being migrated into local Loki.

Loki is still exposed directly on port `3100` inside the Home Lab. Network hardening remains future work.

---

# Grafana Integration

Grafana itself is deployed from the separate `homelab-grafana` repository.

Current BirdNET dashboard exports:

```text
grafana/Bird Home - Burbank Cloud.json
grafana/Bird Home - Burbank Local.json
grafana/bird-home-prediction-lab.json
grafana/Bird Home - Species Prediction.json
```

The local Grafana instance uses:

- Loki for BirdNET operational logs and recent detections
- Infinity for Open-Meteo current/forecast data
- Prometheus for infrastructure metrics
- PostgreSQL for historical analysis and ML prediction dashboards

See [grafana/README.md](../../grafana/README.md) for datasource mapping, dashboard prerequisites, and time handling.

---

# ML Environment

Repository path:

```text
/opt/birdnetpi-monitoring
```

Virtual environment:

```text
/opt/birdnetpi-monitoring/.venv
```

Install dependencies with:

```bash
cd /opt/birdnetpi-monitoring
python3 -m venv .venv
.venv/bin/python -m pip install -r ml/requirements.txt
```

Methodology: `docs/ml.md`  
Operations: `ml/README.md`  
Curated experiments: `docs/experiments/`

---

# Hourly ML Prediction Cycle

The committed timer/service coordinates aggregate and species prediction.

Model timing convention:

```text
completed hour T -> target hour T+2
```

The timer runs at minute 10 to provide a ten-minute ingestion grace period.

Execution path:

```text
birdnet-ml-prediction.timer
    -> birdnet-ml-prediction.service
    -> ml/hourly_prediction_cycle.sh
        -> score aggregate predictions
        -> create aggregate Random Forest + XGBoost predictions
        -> score species predictions
        -> predict configured reference species
        -> predict configured species challengers
```

Aggregate model labels:

- `random_forest_v2_completed`
- `xgboost_v2_completed`

Species reference labels:

- `random_forest_species_v1`
- `xgboost_species_v1`

Current challenger labels:

- `xgboost_tuned_species_v1`
- `xgboost_bootstrap_species_v1`

The aggregate steps run first deliberately, so a later species-side failure does not prevent the main activity forecast from being created.

`Persistent=true` causes a catch-up activation after downtime, but it does not reconstruct every forecast missed while the host was offline.

Install/refresh the units with:

```bash
cd /opt/birdnetpi-monitoring
sudo install -m 0644 \
  systemd/birdnet-ml-prediction.service \
  systemd/birdnet-ml-prediction.timer \
  /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now birdnet-ml-prediction.timer
```

Verify:

```bash
systemctl status birdnet-ml-prediction.timer --no-pager
systemctl list-timers birdnet-ml-prediction.timer --all
journalctl -u birdnet-ml-prediction.service -n 50 --no-pager
```

A manual run writes scores/predictions; it is not a read-only health check:

```bash
./ml/hourly_prediction_cycle.sh
```

Regression tests:

```bash
.venv/bin/python -m unittest discover -s ml/tests -v
```

---

# Weather Deployment Note

The checked-in weather collectors now explicitly request precipitation in inches before writing `precipitation_in`.

Before deploying those repo changes to the Pi, compare the live files and services:

```bash
grep -n "precipitation_unit" /home/birduser/weather/weather.py
grep -n "precipitation_unit" /home/birduser/birdnetPi-monitoring/weather/forecast.py
systemctl cat weather.service
systemctl cat birdnet-forecast.service
```

Historical precipitation rows created before explicit unit selection may require a provenance audit before quantitative use.

---

# Rebuild Order

A practical replacement-host sequence is:

1. install and verify `ubuntu-infra`
2. clone the Home Lab repositories
3. restore runtime secrets and environment files
4. deploy PostgreSQL
5. restore the latest validated PostgreSQL dump
6. recreate required database roles and scoped authentication rules
7. apply/verify analytical views, prediction tables, and Grafana grants
8. verify BirdNET Pi collectors can reach PostgreSQL
9. deploy Loki
10. deploy/provision Grafana through `homelab-grafana`
11. verify Alloy log delivery
12. verify Grafana datasources and dashboards
13. recreate the BirdNET ML virtual environment
14. restore and verify the ML timer/service
15. run the ML regression tests
16. verify aggregate and species prediction/scoring records
17. verify PostgreSQL backups and timers

BirdNET itself should continue operating during an infrastructure rebuild because its native SQLite source database remains on the Pi.

---

# Recovery Notes

Database dumps contain database objects and data, but PostgreSQL cluster-wide roles and runtime secrets must be recreated separately.

Prediction records are historical evidence. Do not regenerate historical predictions and present them as forecasts that were actually issued before the target occurred.

Before resuming detection synchronization after a restore, reconcile the Pi importer checkpoint with the restored PostgreSQL state. A checkpoint newer than the backup can otherwise skip detections lost in the restore.

---

# Current Status

Completed:

- centralized PostgreSQL and historical migration
- remote detection/weather/forecast ingestion
- PostgreSQL backups
- local Loki and Grafana integration
- Alloy local + Cloud dual-write architecture in repo
- aggregate hourly prediction/scoring
- species reference and challenger prediction/scoring in the hourly cycle
- aggregate and species prediction dashboards
- timing/leakage regression tests

Still intentionally open:

- compare repo weather/Alloy files with the actual installed Pi files before deployment
- off-host PostgreSQL backups
- periodic real restore testing
- stronger ingestion-freshness monitoring
- forward-validation of species challengers and additional species when data supports them
- removal of obsolete Pi-local PostgreSQL components when no longer needed

---

# Recovery Philosophy

The deployment should be reproducible from:

```text
Git
+
secrets
+
database backup
```

For major migrations: deploy, verify, observe, retain rollback options, then retire the old component only after confidence is high.
