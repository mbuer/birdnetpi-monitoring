# ubuntu-infra BirdNET Deployment

This directory documents the BirdNET services that run on the Home Lab infrastructure VM.

The architecture keeps the Raspberry Pi focused on sensing and collection while durable storage, observability, dashboards, and ML workloads run centrally.

---

# Hosts

## BirdNET Pi

Current address:

```text
192.168.1.136
```

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

Current address:

```text
192.168.1.137
```

Responsibilities:

- PostgreSQL
- Loki
- Prometheus
- Grafana OSS host
- Python ML experiments
- live aggregate activity prediction and scoring
- species-model experiments and manual live species prediction/scoring

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
`-- BirdNET ML
```

PostgreSQL is the structured historical datastore.

Loki is the operational log datastore.

Grafana Alloy currently dual-writes operational logs to Grafana Cloud Loki and local Loki while the local stack is being validated.

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

The repository also contains shared database, ML, Grafana, backup, and systemd assets outside this directory.

---

# PostgreSQL

Status:

```text
DEPLOYED
```

Container:

```text
birdnet-postgres
```

Image:

```text
postgres:17.2
```

Database:

```text
birdnet
```

Application role:

```text
birdnet
```

Published port:

```text
5432
```

Persistent storage uses a Docker named volume.

The Compose deployment bootstraps the base schema from:

```text
database/schema.sql
```

Additional analytical objects must be applied separately:

```text
database/views/bird_activity_hourly.sql
database/predictions.sql
database/views/bird_species_hourly.sql
database/species_predictions.sql
```

See [database documentation](../../database/README.md) for the current application order, grants, timestamp semantics, and rebuild details.

Initialization scripts only run automatically on a new PostgreSQL data volume.

---

# PostgreSQL Migration

The original structured PostgreSQL dataset ran on the BirdNET Pi and was migrated to `ubuntu-infra`.

The migration workflow was:

1. create a custom-format dump on the Pi
2. validate it with `pg_restore -l`
3. record source row counts
4. copy the dump to `ubuntu-infra`
5. restore historical data
6. compare destination counts
7. reconfigure clients
8. confirm live row growth

Historical migration checkpoint:

```text
detections              7886
weather_observations    1573
weather_forecasts      17712
```

Those counts matched after restore and are historical checkpoints only.

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

The installed systemd services load this file.

The environment file contains runtime secrets and must never be committed.

---

# PostgreSQL Access Control

The live system permits BirdNET ingestion from:

```text
192.168.1.136/32
```

using SCRAM authentication.

Grafana connects from its Docker network and local ML jobs connect from the infrastructure host.

The live authentication rules are not fully represented by the committed Compose file, so rebuilds must preserve deliberately scoped client rules rather than opening PostgreSQL broadly to the LAN.

The read-only Grafana role is:

```text
grafana_reader
```

It requires SELECT access to the analytical views and prediction tables documented in `database/README.md`.

---

# PostgreSQL Backups

Backup script:

```text
backup/backup_infra_postgres.sh
```

Runtime destination:

```text
/var/backups/birdnet-postgres
```

systemd units:

```text
birdnet-postgres-backup.service
birdnet-postgres-backup.timer
```

Schedule:

```text
03:15 America/Los_Angeles
```

Retention:

```text
14 days
```

The job creates PostgreSQL custom-format archives.

Example validation:

```bash
pg_restore -l /var/backups/birdnet-postgres/birdnet-YYYY-MM-DD_HH-MM-SS.dump
```

These backups currently live on the same infrastructure VM as PostgreSQL. Off-host replication remains an important disaster-recovery improvement.

---

# Useful PostgreSQL Checks

Container status:

```bash
docker ps --filter name=birdnet-postgres
```

Recent logs:

```bash
docker logs birdnet-postgres --tail 50
```

Tables:

```bash
docker exec birdnet-postgres \
  psql -U birdnet -d birdnet -c '\dt'
```

Views:

```bash
docker exec birdnet-postgres \
  psql -U birdnet -d birdnet -c '\dv'
```

Prediction records:

```bash
docker exec birdnet-postgres \
  psql -U birdnet -d birdnet -c "
  SELECT prediction_created_at, predicted_hour, model,
         actual_activity, scored_at
  FROM bird_activity_predictions
  ORDER BY predicted_hour DESC
  LIMIT 10;
  "
```

Species prediction records:

```bash
docker exec birdnet-postgres \
  psql -U birdnet -d birdnet -c "
  SELECT prediction_created_at, species, predicted_hour,
         model, probability, actual_present, scored_at
  FROM bird_species_predictions
  ORDER BY predicted_hour DESC, species
  LIMIT 20;
  "
```

---

# Loki

Status:

```text
DEPLOYED
```

Container:

```text
birdnet-loki
```

Image:

```text
grafana/loki:3.5.5
```

Published port:

```text
3100
```

Retention:

```text
30 days
```

Persistent storage uses a Docker named volume.

Repository configuration:

```text
deploy/ubuntu-infra/loki/
```

The local path has been verified for:

- BirdNET journal ingestion
- parsed detection logs
- weather JSONL ingestion
- persistence across container restart
- Grafana OSS queries

The reported live Pi Alloy configuration currently dual-writes to local and Cloud Loki.

The committed `alloy/config.alloy` does not fully represent that live state, so do not replace the working installed configuration without reconciling it first.

Historical Grafana Cloud Loki data is not being migrated into local Loki.

Loki is still exposed directly on port `3100` inside the Home Lab. Network hardening remains future work.

---

# Grafana Integration

Grafana itself is deployed from the separate:

```text
homelab-grafana
```

repository.

This BirdNET repository owns the BirdNET-specific dashboard exports and datasource expectations.

Current dashboard exports:

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

The operational Bird Home dashboard remains primarily Loki-based.

PostgreSQL is not intended to replace Loki for operational log exploration.

See [Grafana documentation](../../grafana/README.md) for datasource mapping, dashboard prerequisites, and time handling.

---

# ML Environment

The checked-in ML code runs from:

```text
/opt/birdnetpi-monitoring
```

using the repository-level virtual environment:

```text
/opt/birdnetpi-monitoring/.venv
```

Install dependencies with:

```bash
cd /opt/birdnetpi-monitoring
python3 -m venv .venv
.venv/bin/python -m pip install -r ml/requirements.txt
```

Current methodology is documented in:

```text
docs/ml.md
```

Operational ML instructions are documented in:

```text
ml/README.md
```

Curated experiment results live in:

```text
docs/experiments/
```

---

# Aggregate Activity Prediction

The aggregate live pipeline is deployed and uses the corrected completed-hour convention.

Current model label:

```text
random_forest_v2_completed
```

Timing convention:

```text
completed hour T -> target hour T+2
```

The pipeline waits until minute 10 so the previous hour has a ten-minute ingestion grace period.

systemd units:

```text
birdnet-ml-prediction.service
birdnet-ml-prediction.timer
```

Execution path:

```text
birdnet-ml-prediction.timer
    -> birdnet-ml-prediction.service
    -> ml/hourly_prediction_cycle.sh
        -> ml/score_predictions.sh
        -> ml/predict_next_hour.sh
    -> PostgreSQL bird_activity_predictions
```

The cycle scores eligible previous forecasts first and then creates the next forecast.

The timer runs at minute 10 each hour in the host timezone.

`Persistent=true` causes a catch-up activation after downtime, but it does not reconstruct every forecast that was missed while the host was offline.

Install the committed units with:

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

Running this manually writes scores and predictions:

```bash
./ml/hourly_prediction_cycle.sh
```

It is not a read-only health check.

---

# Species Prediction

Species-level prediction code and database objects are now part of the repository.

Relevant files:

```text
ml/src/compare_species_models.py
ml/src/predict_species_live.py
ml/src/score_species_predictions.py
database/views/bird_species_hourly.sql
database/species_predictions.sql
grafana/Bird Home - Species Prediction.json
```

The live species scripts write model labels:

```text
random_forest_species_v1
xgboost_species_v1
```

The first live species focus is House Finch and Black Phoebe.

American Crow remains useful for probability experiments, but its lower prevalence makes the default 0.5 threshold less useful.

Important operational status:

**Species prediction is not yet wired into a committed systemd timer/service.**

The code, database table, and dashboard exist, but reproducible hourly automation still needs to be integrated into the central ML cycle or another deliberate scheduler.

Until that integration is committed and tested, do not describe species prediction as fully automated.

---

# Rebuild Order

A practical replacement-host sequence is:

1. install and verify `ubuntu-infra`
2. clone the Home Lab repositories
3. restore runtime secrets and environment files
4. deploy PostgreSQL
5. restore the latest validated PostgreSQL dump
6. recreate required database roles and authentication rules
7. apply/verify analytical views, prediction tables, and Grafana grants
8. verify BirdNET Pi collectors can reach PostgreSQL
9. deploy Loki
10. deploy/provision Grafana through `homelab-grafana`
11. verify Alloy log delivery
12. verify Grafana datasources and dashboards
13. recreate the BirdNET ML virtual environment
14. restore and verify the aggregate ML timer/service
15. verify prediction and scoring records
16. verify PostgreSQL backups and timers
17. verify species DB objects/dashboard; restore species automation only after it exists in Git

BirdNET itself should continue operating during an infrastructure rebuild because its native SQLite source database remains on the Pi.

---

# Recovery Notes

Database dumps contain database objects and data, but PostgreSQL cluster-wide roles and runtime secrets must be recreated separately.

Prediction records are historical evidence. Do not regenerate historical predictions and present them as forecasts that were actually issued before the target occurred.

Before resuming detection synchronization after a restore, reconcile the Pi importer checkpoint with the restored PostgreSQL state. A checkpoint newer than the backup can otherwise skip detections that were lost in the restore.

The current backup workflow should eventually be improved with off-host copies and periodic real restore tests.

---

# Migration Status

## Completed

- centralized PostgreSQL deployment
- historical PostgreSQL migration
- remote Pi detection ingestion
- remote weather ingestion
- weather forecast storage
- scoped PostgreSQL client access
- PostgreSQL backup script and timer
- local Loki deployment
- BirdNET journal ingestion into local Loki
- weather JSONL ingestion into local Loki
- local Grafana Loki datasource
- Infinity/Open-Meteo integration
- local Bird Home dashboard
- read-only Grafana PostgreSQL role
- PostgreSQL Grafana datasource
- aggregate activity analytical view
- aggregate prediction table
- completed-hour aggregate live prediction/scoring
- aggregate Prediction Lab dashboard
- species hourly analytical view
- species prediction table
- species model experiments
- species live prediction/scoring code
- Species Prediction dashboard

## Transitional

Grafana Alloy currently writes operational logs to both Grafana Cloud Loki and local Loki.

This dual-write period is intentional while the local stack is observed.

## Not Yet Automated

- recurring species prediction/scoring through committed systemd or central ML-cycle integration

## Later

- PostgreSQL metrics
- Loki metrics
- stronger ingestion-freshness monitoring
- off-host PostgreSQL backups
- periodic restore testing
- removal of obsolete Pi-local PostgreSQL components
- broader historical/seasonal analysis
- additional species and threshold tuning
- model uncertainty estimates

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

Git contains configuration and code.

Secrets remain outside Git.

Persistent data is backed up separately.

For major migrations:

1. deploy the replacement
2. verify the replacement
3. observe it
4. retain rollback options
5. retire the old component only after confidence is high

The goal is that a replacement `ubuntu-infra` host can eventually be rebuilt without reconstructing the architecture from memory.
