# BirdNET Grafana Dashboards

This directory contains the BirdNET-specific dashboard exports.

Grafana deployment, plugin installation, and shared datasource provisioning belong to the separate `homelab-grafana` repository.

The dashboards intentionally separate operational monitoring from analytical and ML views:

```text
Loki + Infinity/Open-Meteo -> Bird Home - Burbank
PostgreSQL                -> Prediction Lab
PostgreSQL                -> Species Prediction
```

---

## Dashboard Files

| File | Purpose | Export format |
|---|---|---|
| `Bird Home - Burbank Cloud.json` | Original Grafana Cloud operational reference | `dashboard.grafana.app/v2` resource |
| `Bird Home - Burbank Local.json` | Active local Grafana OSS operational dashboard | `dashboard.grafana.app/v2` resource |
| `bird-home-prediction-lab.json` | Aggregate activity forecasts, outcomes, and error metrics | Classic dashboard JSON |
| `Bird Home - Species Prediction.json` | Per-species forecast probabilities, decisions, and scored results | Classic dashboard JSON |

The two Bird Home operational exports retain the same internal dashboard identity. Their filenames alone do not make them separate Grafana dashboards. Check the import preview before loading both into the same Grafana instance.

JSON validity does not by itself prove Grafana import compatibility.

---

# Operational Bird Home Dashboard

The local operational dashboard uses:

- Loki for BirdNET logs and recent detections
- Infinity for Open-Meteo weather data
- Grafana OSS for visualization

The Cloud export remains as a reference during the local observability migration.

The Local export references `Loki` and `Infinity`. The Cloud export uses the original Grafana Cloud datasource references.

Infinity supplies direct Open-Meteo requests. Relative `/forecast?...` requests require the datasource base URL:

```text
https://api.open-meteo.com/v1
```

The current Home Lab local Loki endpoint is:

```text
http://192.168.1.137:3100
```

The reported live Pi configuration currently dual-writes operational logs to Grafana Cloud Loki and local Loki. The committed Alloy sample may not fully represent that live configuration, so do not replace the installed Alloy configuration blindly.

Useful Loki Explore checks include:

```logql
{unit="birdnet_analysis.service"}
```

```logql
{job="weather"} | json
```

Operational log counts are not expected to exactly match PostgreSQL analytical counts. The two paths represent different data products.

---

# PostgreSQL Datasource

The analytical dashboards use the PostgreSQL database:

```text
birdnet
```

Current datasource:

```text
BirdNET PostgreSQL
UID: afy5j1yt18b9cb
```

The datasource UID is embedded in dashboard JSON. When importing into another Grafana instance, verify or remap datasource references.

Grafana should use the read-only role:

```text
grafana_reader
```

See [database documentation](../database/README.md) for object installation and grants.

---

# Prediction Lab

File:

`bird-home-prediction-lab.json`

This dashboard visualizes aggregate BirdNET activity forecasts produced by the live v2 prediction pipeline.

Required PostgreSQL objects:

- `bird_activity_hourly`
- `bird_activity_predictions`

The live aggregate model is:

```text
random_forest_v2_completed
```

The dashboard compares:

- Random Forest forecast
- observed activity
- persistence baseline
- absolute prediction error
- MAE
- model edge over persistence
- model win rate
- recent prediction records

The aggregate pipeline uses the completed-hour T → T+2 timing convention documented in [ML methodology](../docs/ml.md).

Pending forecasts are expected before the target hour has completed and the scoring grace period has elapsed.

A missing or stale forecast should not automatically be interpreted as zero predicted activity.

---

## Prediction Lab Query Scope

Current panels intentionally use different scopes.

| Panel/group | Query scope |
|---|---|
| Next Hour Forecast | Latest stored v2 forecast |
| Latest Completed Activity | Latest sufficiently completed activity hour |
| Live MAE / Model Edge / Scored Forecasts | All scored v2 rows |
| Forecast vs Reality / Prediction Error / Daily MAE | Selected Grafana time range |
| Model Win Rate / ML MAE / Persistence MAE / Best Forecast | All scored v2 rows |
| Recent Predictions | Most recent prediction records |

“Daily MAE” is grouped by local calendar day. It is not a rolling moving average.

Zero observed activity is valid, but the current data pipeline cannot always distinguish a genuinely quiet hour from an ingestion or station outage.

---

# Species Prediction Dashboard

File:

`Bird Home - Species Prediction.json`

This dashboard visualizes stored live predictions for individual bird species.

Required PostgreSQL objects:

- `bird_species_hourly`
- `bird_species_predictions`

The dashboard uses a Grafana variable:

```text
$species
```

The variable is populated from species already present in `bird_species_predictions`.

Current live model labels are:

```text
random_forest_species_v1
xgboost_species_v1
```

The dashboard currently includes:

- latest XGBoost forecast probability
- latest Random Forest forecast probability
- forecast target time
- XGBoost present/absent decision
- probability history for both models
- live model accuracy for scored predictions
- prediction history with actual outcome and correctness

The present/absent decision currently uses the stored prediction threshold, which is initially `0.5`.

This threshold is not assumed to be optimal for all species. Sparse species can have useful probability ranking while still performing poorly at a fixed 0.5 classification threshold. See [species experiment results](../docs/experiments/2026-09-14-species-models.md).

---

## Why Live Model Accuracy May Show No Data

A newly imported Species Prediction dashboard can legitimately show no data in the Live Model Accuracy panel.

A prediction is not scoreable until:

1. the target hour has completed
2. the scoring grace period has elapsed
3. the target outcome is available in `bird_species_hourly`
4. the scoring script has updated the prediction row

Until then:

```text
actual_present = NULL
correct = NULL
```

This is expected behavior rather than a dashboard error.

The current species prediction Python scripts are committed, but repository-managed systemd automation for that species cycle is not yet complete. The dashboard therefore reflects whatever live species predictions have actually been written to PostgreSQL.

---

# Time Handling

Prediction target hours are currently stored as Los Angeles wall-clock timestamps without timezone.

For Grafana time-series queries, convert them to an instant using:

```sql
predicted_hour AT TIME ZONE 'America/Los_Angeles'
```

This handles normal timezone conversion for display.

It does not recover ambiguity already introduced by the repeated autumn DST hour.

The operational and analytical dashboards may also use the viewer's browser timezone for display, so clearly distinguish display timezone from the local timestamp semantics stored in PostgreSQL.

---

# Validating Dashboard JSON

From the repository root:

```bash
python3 -m json.tool grafana/bird-home-prediction-lab.json > /dev/null
python3 -m json.tool "grafana/Bird Home - Species Prediction.json" > /dev/null
```

For the operational exports, use an import method compatible with their Grafana resource format.

After importing any dashboard, verify:

- datasource mapping
- variable queries
- panel SQL or LogQL
- expected recent data
- timestamps
- pending versus scored predictions

A successful import validates configuration, not model correctness.

---

# Dashboard Ownership

This repository owns BirdNET-specific dashboard definitions.

The separate `homelab-grafana` repository owns shared Grafana infrastructure such as:

- Grafana container deployment
- datasource provisioning
- plugin installation
- shared infrastructure configuration

Keep that separation unless the architecture is deliberately changed.

---

# Current Limitations

Important limitations across the analytical dashboards include:

- local wall-clock prediction timestamps have DST ambiguity
- scoring uses an ingestion grace period rather than a formal completeness signal
- late detections can change historical reality after a prediction has already been scored
- aggregate activity depends on weather-backed hourly coverage
- species prediction thresholds are still experimental
- species live automation is not yet fully represented in committed systemd units

These dashboards should therefore be treated as experimental analytical tools rather than authoritative ecological forecasting systems.

For model methodology and limitations, see [docs/ml.md](../docs/ml.md).
