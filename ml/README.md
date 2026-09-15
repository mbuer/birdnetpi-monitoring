# BirdNET ML

Machine-learning code for BirdNET aggregate activity and species-presence prediction.

Stable methodology lives in [docs/ml.md](../docs/ml.md). Dated experiment results live in [docs/experiments/](../docs/experiments/). Historical/raw experiment notes remain under `ml/reports/`.

Current timing convention:

**completed hour T → target hour T+2**

At 14:10, for example, the latest completed input hour is 13:00–14:00 and the forecast target is 15:00–16:00.

---

## Current Live Workflow

The existing hourly timer coordinates both aggregate and species prediction:

```text
birdnet-ml-prediction.timer
    -> birdnet-ml-prediction.service
    -> ml/hourly_prediction_cycle.sh
        -> score aggregate predictions
        -> create aggregate prediction
        -> score species predictions
        -> predict House Finch
        -> predict Black Phoebe
```

The aggregate work intentionally runs first so a later species-side failure does not prevent the primary activity forecast from being issued.

Predictions are stored in PostgreSQL:

- aggregate: `bird_activity_predictions`
- species: `bird_species_predictions`

Dashboards:

- `grafana/bird-home-prediction-lab.json`
- `grafana/Bird Home - Species Prediction.json`

---

# Environment

Current deployment path on `ubuntu-infra`:

```text
/opt/birdnetpi-monitoring
```

Repository virtual environment:

```bash
cd /opt/birdnetpi-monitoring
python3 -m venv .venv
.venv/bin/python -m pip install -r ml/requirements.txt
```

Pinned dependencies currently include:

- pandas 3.0.5
- scikit-learn 1.9.1
- psycopg 3.3.5
- XGBoost 3.4.1

ML scripts use:

```text
BIRDNET_DB_HOST
BIRDNET_DB_NAME
BIRDNET_DB_USER
BIRDNET_DB_PASSWORD
```

Never commit the database password.

The aggregate shell wrappers can retrieve `POSTGRES_PASSWORD` from the local `birdnet-postgres` container when `BIRDNET_DB_PASSWORD` is not already set. The coordinated hourly cycle inherits that environment for species scripts as well.

---

# Aggregate Activity

## Dataset

Aggregate models use:

`database/views/bird_activity_hourly.sql`

The view includes hourly activity, species count, capped detections, day/night information, sunrise-relative timing, and weather observations.

The current live model does not use weather as a feature.

Activity index:

```text
capped detections = sum(min(detections per species, 10))
activity index = species count + capped detections
```

The aggregate view is weather-backed, so missing weather hours can remove hours from the analytical timeline.

## Live model

Model label:

`random_forest_v2_completed`

Features:

- `hour_of_day`
- `hours_from_sunrise`
- `is_day`
- `activity_index`
- `activity_lag_1h`
- `activity_lag_2h`
- `activity_lag_3h`
- `activity_lag_24h`

`src/timing.py` owns completed-hour timing, hourly preparation, and recent-gap handling.

The timer runs at minute 10 each hour. This is an ingestion grace period, not proof that every detection has arrived.

Duplicate target-hour/model attempts preserve the first stored forecast through the prediction table uniqueness rule.

## Aggregate experiments

Current v2 comparison script:

```bash
BIRDNET_DB_PASSWORD="..." \
  .venv/bin/python ml/src/compare_v2_xgboost.py
```

It compares persistence, Random Forest, and XGBoost.

The current documented result keeps Random Forest live because XGBoost's aggregate improvement was too small to justify a change.

See `docs/experiments/2026-09-14-activity-models.md`.

---

# Species Prediction

## Dataset

Species models use:

`database/views/bird_species_hourly.sql`

This view creates a continuous station/species/hour timeline and explicitly represents zero-detection hours. Unlike `bird_activity_hourly`, it is independent of weather availability.

## Models

Live model labels:

- `random_forest_species_v1`
- `xgboost_species_v1`

Current scheduled species:

- House Finch
- Black Phoebe

American Crow remains useful for experiments but is not in the live hourly cycle because its lower prevalence makes the default `0.5` threshold less useful.

## Species experiments

Run the generic classifier comparison with:

```bash
BIRDNET_DB_PASSWORD="..." \
  .venv/bin/python ml/src/compare_species_models.py --species "House Finch"
```

Current comparison models:

- prevalence baseline
- persistence
- Random Forest
- XGBoost

See `docs/experiments/2026-09-14-species-models.md`.

## Manual live prediction

Manual runs remain useful for testing:

```bash
cd /opt/birdnetpi-monitoring

BIRDNET_DB_PASSWORD="$(docker exec birdnet-postgres printenv POSTGRES_PASSWORD)" \
  .venv/bin/python ml/src/predict_species_live.py --species "House Finch"
```

Manual scoring:

```bash
BIRDNET_DB_PASSWORD="$(docker exec birdnet-postgres printenv POSTGRES_PASSWORD)" \
  .venv/bin/python ml/src/score_species_predictions.py
```

Scoring waits until the target hour has ended plus the ten-minute grace period.

---

# Regression Tests

Timing and leakage-sensitive behavior is covered by:

`ml/tests/test_timing.py`

Run:

```bash
cd /opt/birdnetpi-monitoring
.venv/bin/python -m unittest ml/tests/test_timing.py -v
```

The current suite verifies:

- completed-hour selection after the grace period
- behavior before the grace period
- UTC → Los Angeles time conversion
- duplicate local-hour rejection around DST overlap
- missing recent-hour rejection
- T → T+2 training targets
- 1h / 2h / 3h / 24h lag construction

Run these tests after changing `src/timing.py` or related live feature construction.

---

# Script Map

| Script | Purpose |
|---|---|
| `src/timing.py` | Completed-hour timing, hourly preparation, and v2 guards |
| `src/predict_next_hour.py` | Live aggregate Random Forest prediction |
| `src/score_predictions.py` | Score eligible aggregate predictions |
| `src/compare_v2_xgboost.py` | Leakage-safe aggregate RF vs XGBoost comparison |
| `src/compare_species_models.py` | Generic species walk-forward comparison |
| `src/predict_species_live.py` | Live species probability prediction |
| `src/score_species_predictions.py` | Score eligible species predictions |

Earlier scripts such as `features.py`, `evaluate.py`, `train.py`, `compare_models.py`, `rolling_validation.py`, `feature_importance.py`, and `ablation.py` are retained as historical methodology. Several use the older row-based target convention and should not be presented as directly comparable with current T → T+2 results.

`ml/reports/experiments.md` is explicitly historical. Current curated findings belong in `docs/experiments/`.

---

# Validation Rules

Current v2 experiments use chronological evaluation rather than random train/test shuffling.

A training target is included only when that target would already have been observable at the simulated issue time.

For species classification, accuracy alone is insufficient because many species are sparse. Use precision, recall, F1, ROC-AUC, and PR-AUC together with prevalence.

See [docs/ml.md](../docs/ml.md) for the full methodology.

---

# Data Quality Limits

Current prediction results remain experimental.

Important limitations include:

- the ten-minute grace period does not prove ingestion completeness
- a quiet station and a failed station can both appear as zero detections
- the aggregate activity view depends on weather-backed hourly coverage
- local wall-clock timestamps have DST ambiguity
- late detections can arrive after a forecast has been scored
- the historical dataset is still short and does not support strong seasonal conclusions

The raw dataset and stored live forecasts are more valuable long-term than any current model artifact.

---

# Next Work

Priorities now are:

- accumulate forward-validation history
- evaluate species probability thresholds
- add stronger ingestion/uptime completeness checks
- repeat model comparisons as the dataset grows
- add sunrise/daylight and later weather features where justified

Keep every prediction path understandable, leakage-safe, and reproducible.
