# BirdNET PostgreSQL Database

PostgreSQL is the durable structured datastore for the BirdNET monitoring project.

It stores historical bird detections, actual weather observations, historical weather forecast snapshots, and stored ML predictions.

PostgreSQL complements Loki:

    Loki        -> operational logs and observability
    PostgreSQL  -> structured historical data and analysis

The database is intended to accumulate months and eventually years of station history.

---

# Current Deployment

The primary PostgreSQL instance runs on:

    ubuntu-infra

Current Home Lab address:

    192.168.1.137

Docker container:

    birdnet-postgres

Database:

    birdnet

Application role:

    birdnet

TCP port:

    5432

Deployment configuration:

    deploy/ubuntu-infra/postgres/

Schema:

    database/schema.sql

The BirdNET Pi currently connects from:

    192.168.1.136

---

# Tables

## detections

Stores BirdNET detections imported from BirdNET's native SQLite database.

Source:

    ~/BirdNET-Pi/scripts/birds.db

Importer:

    collector/import_detections.py

Important fields include:

- detection timestamp
- station ID
- common species name
- scientific species name
- confidence
- latitude
- longitude
- cutoff
- week
- sensitivity
- overlap
- source filename
- source SQLite row ID

The BirdNET SQLite database remains the authoritative source for completed detections.

PostgreSQL provides the durable analytical copy.

---

## weather_observations

Stores actual weather conditions collected from Open-Meteo.

Important fields include:

- observation timestamp
- station ID
- temperature
- dew point
- relative humidity
- atmospheric pressure
- precipitation
- cloud cover
- wind speed
- wind gusts
- wind direction
- weather code
- day/night state
- sunrise
- sunset

The uniqueness rule prevents duplicate storage when Open-Meteo returns the same current observation more than once.

---

## weather_forecasts

Stores snapshots of future weather forecasts.

Collector:

    weather/forecast.py

The important timestamps are:

    forecast_created_at
    forecast_for

`forecast_created_at` is when the snapshot was collected.

`forecast_for` is the future hour being predicted.

The same `forecast_for` time can therefore appear in multiple snapshots.

This is intentional and allows analysis of how a forecast changed as the target time approached.

Potential uses include:

- forecast accuracy analysis
- identifying useful forecast horizons
- comparing predicted and actual weather
- future bird-activity prediction using information available at prediction time

---

# Detection Synchronization

The detection path is:

    BirdNET birds.db
          │
          ▼
    birdnet-db-sync.timer
          │
          ▼
    birdnet-db-sync.service
          │
          ▼
    import_detections.py
          │
          ▼
    PostgreSQL detections

The timer runs approximately once per minute.

---

## Incremental state

The importer stores its last processed source row ID in:

    ~/.local/state/birdnet-db-sync/last_rowid

Normal runs only inspect rows newer than that value.

The state advances only after the PostgreSQL transaction succeeds.

This allows failed imports to be retried safely.

---

## Source database rebuild handling

If BirdNET recreates its SQLite database, source row IDs may restart at lower values.

The importer detects:

    SQLite MAX(rowid) < stored last_rowid

and restarts synchronization from row zero.

Existing PostgreSQL uniqueness constraints prevent normal historical records from being inserted twice.

---

# Connection Configuration

The collectors use environment-based PostgreSQL configuration.

Supported variables:

    BIRDNET_DB_HOST
    BIRDNET_DB_NAME
    BIRDNET_DB_USER
    BIRDNET_DB_PASSWORD

The current Pi loads these values through systemd from:

    /home/birduser/.config/birdnet-monitoring/db.env

Example structure:

    BIRDNET_DB_HOST=database-host
    BIRDNET_DB_NAME=birdnet
    BIRDNET_DB_USER=birdnet
    BIRDNET_DB_PASSWORD=...

The real password must never be committed to Git.

---

# Initializing a New Database

The Compose file mounts only `database/schema.sql`, and initialization scripts apply only to a fresh data volume. It does not automatically install tonight's view or prediction table.

For an existing deployment, first take and inspect a backup and record row counts. Run from the repository root on `ubuntu-infra`. The view file ends with a grant to `grafana_reader`, so that role must already exist (create its login and password privately if rebuilding).

```bash
docker exec -i birdnet-postgres psql -v ON_ERROR_STOP=1 -U birdnet -d birdnet < database/views/bird_activity_hourly.sql
docker exec -i birdnet-postgres psql -v ON_ERROR_STOP=1 -U birdnet -d birdnet < database/predictions.sql
docker exec birdnet-postgres psql -v ON_ERROR_STOP=1 -U birdnet -d birdnet -c "GRANT USAGE ON SCHEMA public TO grafana_reader; GRANT SELECT ON public.bird_activity_hourly, public.bird_activity_predictions TO grafana_reader;"
docker exec birdnet-postgres psql -U birdnet -d birdnet -c '\dt'
docker exec birdnet-postgres psql -U birdnet -d birdnet -c '\dv'
```

A fresh manual database also needs the base schema first. Do not delete a populated volume to trigger initialization. `CREATE TABLE IF NOT EXISTS` does not migrate an existing incompatible table.

## Hourly activity view

`views/bird_activity_hourly.sql` defines a regular view, not a stored table or materialized view. Per local hour:

```text
capped_detections = sum(min(detections per species, 10))
activity_index = species_count + capped_detections
```

It groups by common species name, combines all stations, and applies no additional confidence filter. Weather hours define the output: missing detections become zero, while hours without weather disappear. This cannot distinguish a quiet station from an ingestion outage.

`hour_local` is a timestamp without timezone representing Los Angeles wall time. The current hour is included as soon as observations arrive. Repeated autumn DST hours collapse into one bucket. These are known limitations, not a complete hourly quality contract.

## Prediction table

`predictions.sql` defines `bird_activity_predictions`:

| Field | Meaning |
|---|---|
| `prediction_created_at` | Actual insertion time, with timezone |
| `predicted_hour` | Target hour as Los Angeles wall time, without timezone |
| `model` | Corrected live model: `random_forest_v2_completed`; legacy rows retained |
| `predicted_activity` | Nonnegative model output |
| `current_activity` | Saved persistence baseline |
| `training_rows` | Rows used for that fit |
| `actual_activity`, `absolute_error`, `scored_at` | Nullable until scored |

The unique key is `(predicted_hour, model)`; repeat prediction attempts preserve the original record. The corrected scorer updates only v2 rows with null actuals, requires creation before the target began, and waits until the target ends plus ten minutes. It leaves all legacy predictions and scores unchanged. It does not revise late actuals. See [ML limitations](../ml/README.md#known-validation-limitations).

For Grafana time-series queries, convert `predicted_hour AT TIME ZONE 'America/Los_Angeles'` into an instant. This cannot recover distinctions already lost at a DST overlap.

---

# Current Migration

The original structured database ran locally on the BirdNET Pi.

It was migrated to `ubuntu-infra` using:

    pg_dump -Fc

and restored into the centralized PostgreSQL instance.

The source dump was validated with:

    pg_restore -l

Migration baseline row counts were:

    detections              7886
    weather_observations    1573
    weather_forecasts      17712

Destination row counts matched exactly.

After migration, live detection and weather ingestion were confirmed by observing the destination row counts increase.

These values are historical migration checkpoints and are expected to become outdated as new records arrive.

---

# Network Security

PostgreSQL publishes `5432/tcp`. The earlier Pi rule, `192.168.1.136/32`, covers ingestion only. The current system also has local ML connections and Grafana connections from its Docker network.

The previous session confirmed Grafana access, but the committed Compose file does not capture the live authentication rules. Preserve and document the actual narrow client rules and SCRAM authentication during rebuilds.

The Compose bootstrap user is `birdnet`; do not assume it is a least-privilege ingestion role. Audit its privileges separately from `grafana_reader`.

---

# Backups

The centralized database is backed up using:

    backup/backup_infra_postgres.sh

Runtime destination:

    /var/backups/birdnet-postgres

Backup format:

    PostgreSQL custom archive

Example:

    birdnet-2026-09-13_15-22-15.dump

The backup can be inspected with:

    pg_restore -l backup.dump

---

## Schedule

systemd units:

    birdnet-postgres-backup.service
    birdnet-postgres-backup.timer

Current schedule:

    03:15 America/Los_Angeles

The timer is persistent.

Retention:

    14 days

Old matching dumps are automatically removed.

---

# Restore Procedure

Do not test restore procedures directly against the live production database.

A safe general workflow is:

1. identify the desired dump
2. validate it with `pg_restore -l`
3. create a temporary test database
4. restore into the temporary database
5. verify tables and row counts
6. only then plan any production restore

Example inspection:

    pg_restore -l \
      /var/backups/birdnet-postgres/birdnet-YYYY-MM-DD_HH-MM-SS.dump

The project should periodically perform a real test restore into a temporary database.

A backup that has never been restored is not fully proven.

---

# Backup Scope

The PostgreSQL custom-format dump protects the logical database contents.

It does not back up:

- BirdNET audio
- BirdNET's native `birds.db`
- Docker images
- Grafana dashboards outside Git
- Loki data
- the VM itself
- operating system configuration not represented in Git

Those concerns should be handled separately.

---

# Disaster Recovery

The current dumps live on the same infrastructure VM as PostgreSQL.

This is useful but not sufficient for complete disaster recovery.

A future improvement should copy backups to physically separate storage such as:

- an external backup drive
- NAS
- another server
- remote storage

At least one backup copy should eventually survive the loss of `ubuntu-infra`.

---

# Grafana Access

The existing read-only role is `grafana_reader`. The previous session confirmed SELECT grants on `bird_activity_hourly` and `bird_activity_predictions`. The view SQL includes its grant; the prediction-table SQL does not, so deployment must apply that grant explicitly.

The Prediction Lab uses datasource `BirdNET PostgreSQL`, UID `afy5j1yt18b9cb`. The Cloud/Local operational dashboards continue using Loki and Infinity. See [Grafana documentation](../grafana/README.md).

Role creation, credentials, connection rules, and grants must be recoverable separately from database data. A database-only dump does not recreate cluster-wide roles.

---

# Monitoring

Useful future PostgreSQL monitoring includes:

- database availability
- database size
- row growth
- backup success
- age of newest backup
- connection count
- failed connections
- table growth
- query performance if needed

Prometheus already exists on `ubuntu-infra`, so PostgreSQL metrics can later be integrated into the existing monitoring stack.

---

# Data Ownership

The project intentionally distinguishes source and derived data.

## Authoritative source

Bird detections:

    BirdNET birds.db

## Durable analytical copy

    PostgreSQL detections

## External environmental source

    Open-Meteo

## Historical environmental copy

    PostgreSQL weather_observations
    PostgreSQL weather_forecasts

This distinction matters during recovery and troubleshooting.

PostgreSQL is important, but BirdNET's own source database should not be modified merely to make the monitoring stack easier.

---

# Security Rules

Never commit:

- PostgreSQL passwords
- `.env` files
- `db.env`
- database dumps
- private SSH keys
- Grafana tokens
- Grafana Cloud credentials

The repository should contain enough configuration to rebuild the database service without containing production credentials or live data.

---

# Future Database Work

Planned improvements include:

- make the existing Grafana role and grants reproducible
- historical activity dashboards
- database health metrics
- backup age monitoring
- off-host backup replication
- periodic restore testing
- eventual removal of the old Pi PostgreSQL installation
- analysis views or materialized views if useful
- long-term bird/weather correlation work
- forecast accuracy analysis
- completed-hour, gap-aware, station-specific prediction datasets

Avoid premature database complexity.

Add indexes, derived tables, or materialized views when actual query patterns justify them.
