# ubuntu-infra BirdNET Deployment

This directory documents the BirdNET services that run on the Home Lab infrastructure VM.

The architecture keeps the Raspberry Pi focused on sensing and collection while durable storage, observability, dashboards, and ML workloads run centrally.

---

## Canonical bootstrap

For a fresh infrastructure VM, first install Docker with the Compose v2 plugin and clone this repository. The bootstrap installs `make` and the remaining OS-level helper packages used by the documented operator commands.

Create the PostgreSQL runtime configuration file:

```bash
cd deploy/ubuntu-infra/postgres
cp .env.example .env
chmod 600 .env
# edit .env:
# - set POSTGRES_PASSWORD
# - set reader passwords for fresh role creation
# - set the BirdNET, Grafana, and Birdynator client CIDRs
```

The real values remain local and ignored. Use `/32` for exact host clients such as the BirdNET Pi and AI Nexus.

Then from the repository root:

```bash
make infra-bootstrap
make infra-verify
```

The bootstrap starts PostgreSQL and Loki, applies the complete committed database object set, recreates the PostgreSQL reader roles/grants and narrow HBA policy from local configuration, creates the ML Python environment, prepares the backup directory, and installs/enables the station-health, ML, and PostgreSQL-backup timers.

Grafana provisioning remains in the separate `homelab-grafana` repository.

The verification script checks its prerequisites first. If Docker, Docker Compose v2, `curl`, or `systemctl` is unavailable, it stops immediately with a prerequisite error rather than reporting misleading downstream service failures.

---

# Hosts

## BirdNET Pi

Role: `BIRDNET_HOST` (live address intentionally local-only)

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

Role: `INFRA_HOST` (live address intentionally local-only)

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

PostgreSQL is the structured historical datastore. Loki is the operational log datastore. AI Nexus is a downstream analytical consumer and is not part of the collection path.

Grafana Alloy writes operational logs only to local Loki. The former Grafana Cloud output is retired.

See [the architecture document](../../docs/architecture.md) for ownership, trust boundaries, failure behavior, and the AI Nexus relationship.

---

# Deployment Layout

```text
deploy/ubuntu-infra/
|
|-- README.md
|-- postgres/
|   |-- compose.yaml
|   |-- configure_access.sh
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

The Pi-side services use the shared runtime file:

```text
/etc/birdnet-monitoring/runtime.env
```

Start from `config/runtime.example.env` and set real values only on the host.

Relevant variables include:

```text
BIRDNET_DB_HOST
BIRDNET_DB_NAME
BIRDNET_DB_USER
BIRDNET_DB_PASSWORD
BIRDNET_STATION_ID
BIRDNET_TIMEZONE
BIRDNET_LATITUDE
BIRDNET_LONGITUDE
BIRDNET_LOKI_URL
```

The runtime file contains environment-specific values and credentials and must never be committed.

---

# PostgreSQL Access Control

The live deployment is intentionally scoped rather than open to the LAN.

Known required clients include:

- BirdNET Pi ingestion from the exact `BIRDNET_HOST` address only
- Grafana through its Docker network
- local ML jobs through the infrastructure host/container path

The read-only roles are `grafana_reader` and `birdynator_reader`. Their object grants are defined in `database/access.sql`.

`deploy/ubuntu-infra/postgres/configure_access.sh` applies the committed role/grant contract and renders `pg_hba.conf` from local CIDR values in the ignored PostgreSQL `.env`. It derives the PostgreSQL Docker gateway automatically for local ML/health access.

The intended HBA policy is narrow:

- BirdNET Pi -> database `birdnet`, role `birdnet`, configured exact client CIDR
- Grafana -> database `birdnet`, role `grafana_reader`, configured Grafana Docker CIDR
- local ML/health -> database `birdnet`, role `birdnet`, derived PostgreSQL bridge gateway
- Birdynator -> database `birdnet`, role `birdynator_reader`, configured exact client CIDR

Do not replace these rules with broad LAN-wide access for convenience.

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

Validate an archive with:

```bash
pg_restore -l /var/backups/birdnet-postgres/birdnet-YYYY-MM-DD_HH-MM-SS.dump
```

The daily dumps are local staging and short-term recovery copies.

For off-host recovery, use the Proxmox backup-hook pattern documented in [Backup and recovery](../../docs/backup-recovery.md). Proxmox triggers a fresh validated logical dump through the QEMU Guest Agent immediately before capturing the VM to external backup storage. The hook aborts the VM backup if the logical dump fails.

Operator commands:

```bash
make backup
make restore-test
```

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

The repository `alloy/config.alloy` is the local-only reference configuration. It obtains the Loki base URL from `BIRDNET_LOKI_URL`; keep the real endpoint in local runtime configuration and validate before replacing an installed config.

Historical Grafana Cloud Loki data is not being migrated into local Loki.

Loki is still exposed directly on port `3100` inside the Home Lab. This is a documented limitation; further network hardening is outside the frozen infrastructure scope unless a concrete need arises.

---

# Grafana Integration

Grafana itself is deployed from the separate `homelab-grafana` repository.

Current BirdNET dashboard exports:

```text
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

The station-health timer runs at minute 20 and the ML timer runs at minute 30. This ordering gives provenance collection time to complete before the newest completed hour is used by the ML cycle.

Execution path:

```text
birdnet-ml-prediction.timer
    -> birdnet-ml-prediction.service
    -> ml/hourly_prediction_cycle.sh
        -> score aggregate predictions
        -> create aggregate Random Forest + XGBoost + HistGradientBoosting predictions
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

Database dumps contain database objects and data, but not cluster-wide roles or runtime secrets. `infra-bootstrap` recreates the committed reader-role/grant contract and HBA policy from the local ignored `.env`; the secrets themselves must still be restored separately.

Prediction records are historical evidence. Do not regenerate historical predictions and present them as forecasts that were actually issued before the target occurred.

Before resuming detection synchronization after a restore, reconcile the Pi importer checkpoint with the restored PostgreSQL state. A checkpoint newer than the backup can otherwise skip detections lost in the restore.

---

# Current Status

Completed and runtime-verified:

- centralized PostgreSQL and historical migration
- remote detection/weather/forecast ingestion
- PostgreSQL backups plus tested logical restore and off-host Proxmox capture
- reproducible narrow PostgreSQL roles, grants, and HBA policy
- local Loki and Grafana integration
- Alloy local-only architecture
- aggregate hourly prediction/scoring
- species reference and challenger prediction/scoring in the hourly cycle
- aggregate and species prediction dashboards
- timing/leakage regression tests
- constrained Grafana and Birdynator read-only database paths

The infrastructure is frozen by default. Future work should focus on analysis and features unless a concrete operational, security, or recovery need appears.

Still intentionally open as feature/analysis work:

- stronger ingestion-freshness monitoring if it becomes useful
- forward-validation of species challengers and additional species when data supports them

---

The Pi-local PostgreSQL instance and its legacy backup timer were retired after the active Pi pipeline was verified against centralized PostgreSQL on `ubuntu-infra`. The Pi no longer runs a local PostgreSQL server.

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

---

# Station Health Evidence

`ubuntu-infra` also persists compact hourly BirdNET analysis-coverage evidence from local Loki into PostgreSQL.

Repository components:

```text
health/collect_station_health.py
health/collect_station_health.sh
systemd/birdnet-station-health.service
systemd/birdnet-station-health.timer
```

The BirdNET Pi itself is not modified.

## Apply the schema

After pulling the repository and taking a fresh database backup:

```bash
cd /opt/birdnetpi-monitoring

docker exec -i birdnet-postgres \
  psql -v ON_ERROR_STOP=1 -U birdnet -d birdnet \
  < database/schema.sql
```

Verify:

```bash
docker exec birdnet-postgres psql -U birdnet -d birdnet -c "\\d station_health_hourly"
```

## Install the systemd units

```bash
sudo cp systemd/birdnet-station-health.service /etc/systemd/system/
sudo cp systemd/birdnet-station-health.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now birdnet-station-health.timer
```

The timer runs hourly at minute 20 and rechecks the latest six completed hours. This repeated lookback allows delayed Loki telemetry to repair earlier `unknown` or incomplete rows through upsert.

Inspect:

```bash
systemctl status birdnet-station-health.timer --no-pager
systemctl list-timers birdnet-station-health.timer --no-pager
journalctl -u birdnet-station-health.service -n 50 --no-pager
```

## Initial verified backfill

The data-quality audit established continuous local Loki evidence for 312 consecutive completed hours from 2026-09-13 11:00 through 2026-09-26 11:00 America/Los_Angeles (end exclusive), with 312/312 hourly samples and 239–240 analyzed 15-second segments per hour.

Backfill that evidence only after the table exists:

```bash
bash health/collect_station_health.sh \
  --start 2026-09-13T11:00:00-07:00 \
  --end   2026-09-26T11:00:00-07:00
```

Do not infer health for older hours whose Loki evidence is no longer retained.

Runtime validation completed on 2026-09-26. The scheduled timer fired successfully at 19:20 UTC, rechecked the latest six completed hours, and persisted 240/240 healthy coverage with fresh collection timestamps. ML behavior remains unchanged until a separate methodology change deliberately consumes this evidence.

