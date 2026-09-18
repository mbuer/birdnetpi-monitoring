# BirdNET PostgreSQL Database

PostgreSQL is the durable structured datastore for the BirdNET monitoring project.

It stores:

- BirdNET detections
- weather observations
- historical weather forecast snapshots
- aggregate activity predictions
- species-presence predictions

PostgreSQL complements Loki:

```text
Loki        -> operational logs and observability
PostgreSQL  -> structured historical data and analysis
```

BirdNET's native SQLite database remains the authoritative source for completed detections. PostgreSQL is the durable analytical copy used by dashboards, experiments, and prediction scoring.

---

# Current Deployment

Primary PostgreSQL host:

```text
ubuntu-infra
192.168.1.137
```

Container:

```text
birdnet-postgres
```

Database:

```text
birdnet
```

Application role:

```text
birdnet
```

Read-only Grafana role:

```text
grafana_reader
```

Published port:

```text
5432
```

Deployment configuration:

```text
deploy/ubuntu-infra/postgres/
```

The BirdNET Pi currently connects from:

```text
192.168.1.136
```

These addresses describe the current Home Lab deployment and are not intended as universal defaults.

---

# Database Objects

The database layer is split between the base schema, derived views, and prediction tables.

```text
database/
├── schema.sql
├── predictions.sql
├── species_predictions.sql
└── views/
    ├── bird_activity_hourly.sql
    └── bird_species_hourly.sql
```

## Base tables

`database/schema.sql` defines the durable source tables.

### `detections`

Stores BirdNET detections imported from BirdNET's native SQLite database.

Source:

```text
~/BirdNET-Pi/scripts/birds.db
```

Importer:

```text
collector/import_detections.py
```

Important fields include:

- detection timestamp
- station ID
- common species name
- scientific species name
- confidence
- latitude / longitude
- BirdNET cutoff and sensitivity values
- overlap
- source filename
- source SQLite row ID

### `weather_observations`

Stores actual weather conditions collected from Open-Meteo.

Important fields include temperature, humidity, pressure, precipitation, cloud cover, wind, weather code, day/night state, sunrise, and sunset.

### `weather_forecasts`

Stores historical snapshots of future Open-Meteo forecasts.

The two important timestamps are:

```text
forecast_created_at
forecast_for
```

Multiple snapshots for the same future hour are retained intentionally. This allows later comparison of how the forecast changed as the target approached.

---

# Detection Synchronization

The detection path is:

```text
BirdNET birds.db
      |
      v
birdnet-db-sync.timer
      |
      v
birdnet-db-sync.service
      |
      v
collector/import_detections.py
      |
      v
PostgreSQL detections
```

The timer runs approximately once per minute.

## Incremental state

The importer stores its last processed SQLite row ID in:

```text
~/.local/state/birdnet-db-sync/last_rowid
```

The checkpoint advances only after a successful PostgreSQL transaction, allowing failed writes to be retried.

If BirdNET recreates its SQLite database and source row IDs restart, the importer can detect a source `MAX(rowid)` below the saved checkpoint and rescan. PostgreSQL uniqueness constraints protect against normal duplicate replay.

---

# Connection Configuration

Collectors use:

```text
BIRDNET_DB_HOST
BIRDNET_DB_NAME
BIRDNET_DB_USER
BIRDNET_DB_PASSWORD
```

The BirdNET Pi currently loads these through systemd from:

```text
/home/birduser/.config/birdnet-monitoring/db.env
```

Real credentials must remain outside Git.

ML jobs use the same database variable names. Current wrappers can obtain the local PostgreSQL password from the `birdnet-postgres` container when `BIRDNET_DB_PASSWORD` is not already supplied.

---

# Installing Database Objects

The PostgreSQL Compose deployment mounts only:

```text
database/schema.sql
```

and PostgreSQL initialization scripts run only when a new data volume is created.

The analytical views and prediction tables therefore need to be applied separately.

For an existing deployment, first create and inspect a backup. Then run from the repository root on `ubuntu-infra`:

```bash
docker exec -i birdnet-postgres \
  psql -v ON_ERROR_STOP=1 -U birdnet -d birdnet \
  < database/views/bird_activity_hourly.sql

docker exec -i birdnet-postgres \
  psql -v ON_ERROR_STOP=1 -U birdnet -d birdnet \
  < database/views/bird_species_hourly.sql

docker exec -i birdnet-postgres \
  psql -v ON_ERROR_STOP=1 -U birdnet -d birdnet \
  < database/predictions.sql

docker exec -i birdnet-postgres \
  psql -v ON_ERROR_STOP=1 -U birdnet -d birdnet \
  < database/species_predictions.sql
```

Then ensure Grafana has read-only access to the analytical objects:

```bash
docker exec birdnet-postgres \
  psql -v ON_ERROR_STOP=1 -U birdnet -d birdnet -c "
GRANT USAGE ON SCHEMA public TO grafana_reader;
GRANT SELECT ON
  public.bird_activity_hourly,
  public.bird_species_hourly,
  public.bird_activity_predictions,
  public.bird_species_predictions
TO grafana_reader;
"
```

Verify:

```bash
docker exec birdnet-postgres psql -U birdnet -d birdnet -c '\dt'
docker exec birdnet-postgres psql -U birdnet -d birdnet -c '\dv'
```

A fresh manually created database also needs `database/schema.sql` first.

Do not delete a populated PostgreSQL volume merely to rerun initialization.

`CREATE TABLE IF NOT EXISTS` is not a migration mechanism for an already incompatible table definition.

---

# Aggregate Activity View

`database/views/bird_activity_hourly.sql` defines `bird_activity_hourly`.

Per local hour:

```text
capped_detections = sum(min(detections per species, 10))
activity_index = species_count + capped_detections
```

The view combines detection activity with hourly weather data.

Important limitations:

- weather hours define the output timeline
- bird hours without weather can disappear
- weather hours without detections become zero-activity hours
- stations are currently combined
- no additional confidence filter is applied in the view
- a zero-activity hour cannot by itself distinguish quiet conditions from ingestion or station failure

`hour_local` is stored as Los Angeles wall time without timezone. Repeated autumn DST hours therefore cannot always be represented uniquely.

The current aggregate ML pipeline handles additional freshness and gap checks in Python. See [ML methodology](../docs/ml.md).

---

# Species Hourly View

`database/views/bird_species_hourly.sql` defines `bird_species_hourly`.

Its purpose is different from the aggregate activity view: it creates a continuous species-presence dataset independent of weather availability.

For each station, the view:

1. finds the first and latest detection hour
2. generates a continuous hourly timeline between them
3. builds the list of species observed by that station
4. creates one row for every station/species/hour combination
5. left-joins the actual detections
6. explicitly represents absence with zero detections

Columns include:

| Field | Meaning |
|---|---|
| `station_id` | BirdNET station identifier |
| `hour_local` | Los Angeles local wall-clock hour |
| `species` | Common species name |
| `species_latin` | Scientific name |
| `detection_count` | Number of detections in that hour |
| `present` | `1` when at least one detection exists, otherwise `0` |
| `avg_confidence` | Average confidence for detections in the hour |
| `max_confidence` | Maximum confidence for detections in the hour |

This makes zero-detection hours explicit and provides the canonical dataset for the current species classifiers.

The timeline currently ends at the latest detection hour for each station. Live prediction code can extend its working frame through the latest completed hour when necessary.

As with the aggregate view, `hour_local` is a local timestamp without timezone and retains the DST overlap limitation.

---

# Aggregate Prediction Table

`database/predictions.sql` defines `bird_activity_predictions`.

Important fields:

| Field | Meaning |
|---|---|
| `prediction_created_at` | Actual insertion time with timezone |
| `predicted_hour` | Target Los Angeles wall-clock hour |
| `model` | Model identifier |
| `predicted_activity` | Model output |
| `current_activity` | Saved persistence baseline |
| `training_rows` | Rows used to train that fit |
| `actual_activity` | Target activity after scoring |
| `absolute_error` | Absolute model error after scoring |
| `scored_at` | Scoring time |

Current live aggregate model identifiers:

```text
random_forest_v2_completed
xgboost_v2_completed
```

Random Forest remains the established reference while both models accumulate matched live scoring history.

The unique key is:

```text
(predicted_hour, model)
```

This preserves the first stored forecast for a target/model pair.

The current scorer waits until the target hour has completed plus the ingestion grace period before filling the outcome fields. Legacy prediction rows remain stored separately.

---

# Species Prediction Table

`database/species_predictions.sql` defines `bird_species_predictions`.

Important fields:

| Field | Meaning |
|---|---|
| `prediction_created_at` | Actual insertion time with timezone |
| `station_id` | Station being predicted |
| `species` | Species being predicted |
| `predicted_hour` | Target Los Angeles wall-clock hour |
| `model` | Species model identifier |
| `probability` | Predicted probability of presence |
| `threshold` | Classification threshold, currently normally `0.5` |
| `predicted_present` | Binary forecast derived from the threshold |
| `current_present` | Presence state in the latest completed input hour |
| `training_rows` | Rows used to train that fit |
| `actual_present` | Observed target state after scoring |
| `correct` | Whether the binary prediction matched the outcome |
| `scored_at` | Scoring time |

The unique key is:

```text
(station_id, species, predicted_hour, model)
```

Current species reference model identifiers are:

```text
random_forest_species_v1
xgboost_species_v1
```

Current live challenger identifiers are:

```text
xgboost_tuned_species_v1
xgboost_bootstrap_species_v1
```

The challenger rows are stored in the same table under separate model labels. Species models store both probabilities and thresholded present/absent decisions; the threshold is stored per row and should not be assumed to be universally optimal.

See [ML methodology](../docs/ml.md) and the [species experiment record](../docs/experiments/2026-09-14-species-models.md).

---

# Time Handling

The current analytical prediction hours use Los Angeles local wall time without timezone.

For Grafana time-series queries, convert them to an instant with:

```sql
predicted_hour AT TIME ZONE 'America/Los_Angeles'
```

This handles normal display conversion but cannot recover two distinct autumn DST hours after they have already been represented by the same local timestamp.

A future multi-station architecture should move toward explicit UTC instants plus station timezone metadata.

---

# Historical Migration

The original structured PostgreSQL database ran locally on the BirdNET Pi and was migrated to `ubuntu-infra` with a custom-format `pg_dump`.

Historical migration checkpoint:

```text
detections              7886
weather_observations    1573
weather_forecasts      17712
```

Destination counts matched at migration time, and live ingestion was confirmed afterward.

These numbers are historical checkpoints, not current totals.

---

# Network Security

PostgreSQL publishes `5432/tcp`.

The system currently needs access for more than the BirdNET Pi alone:

- BirdNET ingestion from the Pi
- ML jobs on `ubuntu-infra`
- Grafana through its Docker network

Use narrow SCRAM-authenticated client rules rather than reopening PostgreSQL broadly to the LAN.

The committed Compose file does not fully reproduce the live `pg_hba.conf` rules, so the active authentication configuration must be preserved and documented during rebuilds.

The `birdnet` role is the current application/bootstrap role and should not automatically be treated as a least-privilege account.

---

# Grafana Access

Grafana uses the read-only role:

```text
grafana_reader
```

The PostgreSQL datasource currently uses UID:

```text
afy5j1yt18b9cb
```

Grafana analytical dashboards currently depend on:

```text
bird_activity_hourly
bird_activity_predictions
bird_species_hourly
bird_species_predictions
```

See [Grafana documentation](../grafana/README.md).

Role creation, credentials, connection rules, and grants are cluster/runtime configuration and must remain recoverable separately from database contents.

---

# Backups

Central backup script:

```text
backup/backup_infra_postgres.sh
```

Runtime destination:

```text
/var/backups/birdnet-postgres
```

Format:

```text
PostgreSQL custom archive
```

systemd units:

```text
birdnet-postgres-backup.service
birdnet-postgres-backup.timer
```

Current schedule:

```text
03:15 America/Los_Angeles
```

Current retention:

```text
14 days
```

The logical database dump includes prediction tables and regular views. It does not include cluster-wide roles, runtime secrets, BirdNET audio, the native BirdNET SQLite database, Loki data, Grafana state, or the VM itself.

Current dumps remain on the same infrastructure VM as PostgreSQL, so off-host backup replication remains important future work.

---

# Restore Guidance

Do not test restoration directly against the live database.

A safe workflow is:

1. identify a backup
2. inspect it with `pg_restore -l`
3. create a temporary database
4. restore the dump there
5. verify objects and row counts
6. verify analytical views
7. verify prediction tables
8. only then plan a production restore if needed

A backup that has never been restored is not fully proven.

When restoring an older database snapshot, also reconcile the BirdNET Pi importer checkpoint. A checkpoint newer than the restored database could otherwise skip detections still present in BirdNET's source SQLite database.

---

# Data Ownership

The project intentionally distinguishes source and derived data.

```text
BirdNET birds.db
    -> authoritative detection source

PostgreSQL detections
    -> durable analytical copy

Open-Meteo
    -> external environmental source

PostgreSQL weather_observations / weather_forecasts
    -> historical environmental copy

PostgreSQL views
    -> reproducible derived datasets

PostgreSQL prediction tables
    -> historical record of forecasts issued before outcomes were known
```

The raw historical data is more valuable long term than any particular trained model. Derived views and models can be recreated; lost source observations generally cannot.

---

# Security Rules

Never commit:

- PostgreSQL passwords
- `.env` files
- `db.env`
- database dumps
- SSH private keys
- Grafana credentials or tokens
- Grafana Cloud credentials

The repository should contain enough code and schema to understand and rebuild the service without containing production secrets or live database contents.

---

# Future Database Work

Priorities include:

- make role creation and grants fully reproducible
- preserve and document narrow live PostgreSQL access rules
- add database and backup-health monitoring
- replicate backups off `ubuntu-infra`
- periodically test real restores
- eventually retire the old Pi PostgreSQL instance
- improve station-health / ingestion-completeness evidence
- move analytical timestamps toward UTC plus explicit station timezone metadata
- add materialized views or indexes only when real query patterns justify them

Avoid premature database complexity.
