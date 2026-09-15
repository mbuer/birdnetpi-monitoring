# BirdNET ML

Machine-learning code for BirdNET activity and species prediction.

This directory contains the executable ML workflows. Stable methodology lives in [docs/ml.md](../docs/ml.md), while dated experiment results live in [docs/experiments/](../docs/experiments/).

The current prediction convention is:

**completed hour T → target hour T+2**

At 14:10, for example, the latest completed input hour is 13:00–14:00 and the forecast target is 15:00–16:00.

---

## Current ML Workflows

There are two active ML tracks.

### Aggregate activity prediction

Predicts the project `activity_index` for a future hour.

Current live model:

`random_forest_v2_completed`

Current live automation:

```text
birdnet-ml-prediction.timer
    -> birdnet-ml-prediction.service
    -> ml/hourly_prediction_cycle.sh
        -> score_predictions.sh
        -> predict_next_hour.sh
```

Predictions are stored in:

`bird_activity_predictions`

and visualized in:

`grafana/bird-home-prediction-lab.json`

### Species presence prediction

Estimates the probability that an individual species will be detected during the target hour.

Current live-capable scripts:

- `src/predict_species_live.py`
- `src/score_species_predictions.py`

Current model labels:

- `random_forest_species_v1`
- `xgboost_species_v1`

Predictions are stored in:

`bird_species_predictions`

and visualized in:

`grafana/Bird Home - Species Prediction.json`

The species predictor and scorer are committed and working, but they are **not yet wired into a committed systemd schedule**. Until that automation is added, species prediction runs are manual.

---

## Environment

The current deployment runs ML on `ubuntu-infra` from:

```text
/opt/birdnetpi-monitoring
```

The repository uses a root-level virtual environment:

```bash
cd /opt/birdnetpi-monitoring
python3 -m venv .venv
.venv/bin/python -m pip install -r ml/requirements.txt
```

Current pinned dependencies are:

- pandas 3.0.5
- scikit-learn 1.9.1
- psycopg 3.3.5
- XGBoost 3.4.1

---

## Database Configuration

ML scripts use the standard database environment variables:

```text
BIRDNET_DB_HOST
BIRDNET_DB_NAME
BIRDNET_DB_USER
BIRDNET_DB_PASSWORD
```

Typical local values are:

```text
BIRDNET_DB_HOST=127.0.0.1
BIRDNET_DB_NAME=birdnet
BIRDNET_DB_USER=birdnet
```

Never commit or paste the database password into documentation or source files.

The existing activity shell wrappers can retrieve `POSTGRES_PASSWORD` from the local `birdnet-postgres` container when `BIRDNET_DB_PASSWORD` is not already set. This requires Docker access and couples the wrappers to the local container deployment.

---

# Aggregate Activity

## Dataset

Aggregate models use:

`database/views/bird_activity_hourly.sql`

The view includes:

- hourly activity
- species count
- capped detections
- day/night information
- sunrise-relative timing
- weather observations

The current live model uses time and recent activity features, not weather variables.

The activity index is:

```text
capped detections = sum(min(detections per species, 10))
activity index = species count + capped detections
```

The aggregate view is weather-backed, so missing weather hours can remove hours from the analytical timeline. See [database/README.md](../database/README.md) and [docs/ml.md](../docs/ml.md) for the data-quality implications.

## Current live feature set

The corrected v2 activity model uses:

- `hour_of_day`
- `hours_from_sunrise`
- `is_day`
- `activity_index`
- `activity_lag_1h`
- `activity_lag_2h`
- `activity_lag_3h`
- `activity_lag_24h`

`src/timing.py` owns the completed-hour timing convention, hourly reindexing and recent-gap handling used by the live v2 path.

## Live prediction

The activity cycle runs scoring first and prediction second:

```text
ml/hourly_prediction_cycle.sh
    -> ml/score_predictions.sh
    -> ml/predict_next_hour.sh
```

The Python entry points are:

```text
src/score_predictions.py
src/predict_next_hour.py
```

The current service timer runs at minute 10 each hour. The ten-minute delay is an ingestion grace period, not proof that every detection has arrived.

Duplicate target-hour/model attempts preserve the first stored forecast through the prediction table's uniqueness rule.

## Aggregate experiments

Current v2 comparison:

```bash
BIRDNET_DB_PASSWORD="..." \
  .venv/bin/python ml/src/compare_v2_xgboost.py
```

This compares:

- persistence
- Random Forest
- XGBoost

The current documented result keeps Random Forest as the live model because XGBoost's aggregate advantage was too small to justify a change.

See:

`docs/experiments/2026-09-14-activity-models.md`

---

# Species Prediction

## Dataset

Species models use:

`database/views/bird_species_hourly.sql`

This view creates a continuous station/species/hour timeline and explicitly represents zero-detection hours.

Unlike `bird_activity_hourly`, it is independent of weather availability.

## Species experiment

Run the generic classifier comparison with:

```bash
BIRDNET_DB_PASSWORD="..." \
  .venv/bin/python ml/src/compare_species_models.py --species "House Finch"
```

The same script can evaluate any species present in the dataset.

Current comparison models are:

- prevalence baseline
- persistence
- Random Forest
- XGBoost

See:

`docs/experiments/2026-09-14-species-models.md`

## Manual live prediction

Example:

```bash
cd /opt/birdnetpi-monitoring

BIRDNET_DB_PASSWORD="$(docker exec birdnet-postgres printenv POSTGRES_PASSWORD)" \
  .venv/bin/python ml/src/predict_species_live.py --species "House Finch"
```

Another species can be run by changing `--species`.

The current live species pipeline has been tested with House Finch and Black Phoebe.

## Manual species scoring

```bash
cd /opt/birdnetpi-monitoring

BIRDNET_DB_PASSWORD="$(docker exec birdnet-postgres printenv POSTGRES_PASSWORD)" \
  .venv/bin/python ml/src/score_species_predictions.py
```

Scoring waits until the target hour has ended plus the same ten-minute grace period.

A prediction remains pending if a valid target outcome is not yet available.

---

# Script Map

## Current v2 / live work

| Script | Purpose |
|---|---|
| `src/timing.py` | Completed-hour timing, hourly preparation and v2 guards |
| `src/predict_next_hour.py` | Live aggregate Random Forest prediction |
| `src/score_predictions.py` | Score eligible aggregate predictions |
| `src/compare_v2_xgboost.py` | Leakage-safe v2 Random Forest vs XGBoost comparison |
| `src/compare_species_models.py` | Generic species walk-forward model comparison |
| `src/predict_species_live.py` | Live species probability prediction |
| `src/score_species_predictions.py` | Score eligible species predictions |

## Historical experiment code

The repository also retains earlier scripts such as:

- `src/features.py`
- `src/evaluate.py`
- `src/train.py`
- `src/compare_models.py`
- `src/rolling_validation.py`
- `src/feature_importance.py`
- `src/ablation.py`

These are useful historical methodology, but several use the older row-based target convention and should not be treated as directly comparable with the corrected T → T+2 v2 results.

`ml/reports/experiments.md` is likewise a historical experiment log. Current curated results belong in `docs/experiments/`.

---

# Validation Rules

Current v2 experiments use chronological evaluation rather than random train/test shuffling.

For walk-forward validation, a training target is included only when that target would already have been observable at the simulated issue time.

This prevents future outcomes from leaking into training.

For species classification, accuracy alone is not sufficient because many species are sparse. Use precision, recall, F1, ROC-AUC and PR-AUC together with prevalence.

See [docs/ml.md](../docs/ml.md) for the full methodology.

---

# Data Quality Limits

Current prediction results should remain experimental.

Important limitations include:

- the ten-minute grace period does not prove ingestion completeness
- a quiet station and a failed station can both appear as zero detections
- the aggregate activity view depends on weather-backed hourly coverage
- local wall-clock timestamps have DST ambiguity
- late detections can arrive after a forecast has already been scored
- the historical dataset is still short and does not support strong seasonal conclusions

The raw dataset and stored live forecasts are more important long-term than any current model artifact.

---

# Grafana

Aggregate prediction dashboard:

`grafana/bird-home-prediction-lab.json`

Species prediction dashboard:

`grafana/Bird Home - Species Prediction.json`

Both use PostgreSQL through the read-only Grafana datasource.

Pending forecasts are normal until their target hour has completed and scoring has occurred.

See [grafana/README.md](../grafana/README.md) for dashboard details.

---

# Next Operational Work

The immediate ML infrastructure task is to automate species scoring and prediction without creating unnecessary scheduler complexity.

The preferred direction is to integrate species work into the existing hourly ML cycle rather than create multiple unrelated timers.

After that, priorities are:

- accumulate forward-validation history
- evaluate species probability thresholds
- add stronger ingestion/uptime completeness checks
- repeat model comparisons as the dataset grows
- add sunrise/daylight and later weather features where justified

Keep the implementation simple enough that every prediction path remains understandable and reproducible.
