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
        -> create aggregate Random Forest + XGBoost predictions
        -> score species predictions
        -> predict House Finch
        -> predict Black Phoebe
```

The aggregate work intentionally runs first so a later species-side failure does not prevent the primary activity forecasts from being issued.

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

The current live models do not use weather as a feature.

Activity index:

```text
capped detections = sum(min(detections per species, 10))
activity index = species count + capped detections
```

The aggregate view is weather-backed, so missing weather hours can remove hours from the analytical timeline.

## Live models

Model labels:

- `random_forest_v2_completed`
- `xgboost_v2_completed`

Both models use the same feature frame, timing, target hour, and training rows so their live results are directly comparable.

Features:

- `hour_of_day`
- `hours_from_sunrise`
- `is_day`
- `activity_index`
- `activity_lag_1h`
- `activity_lag_2h`
- `activity_lag_3h`
- `activity_lag_24h`

Random Forest configuration:

```text
n_estimators = 300
min_samples_leaf = 3
random_state = 42
```

XGBoost configuration:

```text
n_estimators = 300
max_depth = 3
learning_rate = 0.03
subsample = 0.8
colsample_bytree = 0.8
objective = reg:squarederror
tree_method = hist
random_state = 42
```

`src/timing.py` owns completed-hour timing, hourly preparation, and recent-gap handling.

The timer runs at minute 10 each hour. This is an ingestion grace period, not proof that every detection has arrived.

Duplicate target-hour/model attempts preserve the first stored forecast through the prediction table uniqueness rule. Because uniqueness includes both `predicted_hour` and `model`, Random Forest and XGBoost can safely store independent forecasts for the same target hour.

## Aggregate experiments

Current v2 comparison script:

```bash
BIRDNET_DB_PASSWORD="..." \
  .venv/bin/python ml/src/compare_v2_xgboost.py
```

It compares persistence, Random Forest, and XGBoost.

The retrospective result showed only a very small XGBoost advantage, so Random Forest remains the established reference model. XGBoost is now also issued live so the project can compare both models using true forward-validation history rather than relying only on retrospective testing.

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

Current reference-model species are read from:

`ml/live_species.txt`

The current live baseline set is:

- House Finch
- Black Phoebe
- American Crow

This keeps the hourly runner generic: adding or removing a scheduled species no longer requires editing `hourly_prediction_cycle.sh`.

Before promoting another species, review the available signal with:

```bash
cd /opt/birdnetpi-monitoring

BIRDNET_DB_PASSWORD="$(docker exec birdnet-postgres printenv POSTGRES_PASSWORD)" \
  .venv/bin/python ml/src/species_candidates.py
```

The report ranks species by positive hourly buckets and shows prevalence, total detections, and whether each species is already in the live set. Use `--min-positive-hours` and `--limit` to narrow the report.

American Crow is now included in the live baseline set specifically so its existing Random Forest/XGBoost reference predictions can be compared against a bootstrap challenger on matched future hours. This is forward-validation, not a declaration that the baseline classifier is production-ready.

Per-species challenger configuration lives in:

`ml/species_challengers.json`

Current challenger plan:

- House Finch: no challenger; keep the current reference models
- Black Phoebe: tuned single XGBoost challenger, model label `xgboost_tuned_species_v1`
- American Crow: 15-member class-balanced bootstrap XGBoost probability ensemble, model label `xgboost_bootstrap_species_v1`
- Anna's Hummingbird: configured as experimental-only and not issued live

The challenger runner stores independent model rows in the existing `bird_species_predictions` table. Reference models remain unchanged, and the existing species scorer picks up challenger labels because they still end in `_species_v1`.

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

For sparse species where the fixed XGBoost configuration or 0.5 threshold is weak, run the leakage-safe randomized search:

```bash
BIRDNET_DB_PASSWORD="$(docker exec birdnet-postgres printenv POSTGRES_PASSWORD)" \
  .venv/bin/python ml/src/optimize_species_xgboost.py \
  --species "American Crow"
```

The optimizer:

- reserves the newest 20% of rows as an untouched chronological holdout
- searches XGBoost hyperparameters only on earlier chronological folds
- optimizes mean validation PR-AUC
- includes class-imbalance weighting through `scale_pos_weight`
- chooses a decision threshold from development predictions only
- compares the current XGBoost baseline and tuned challenger on the same final walk-forward holdout

The holdout must not be used to iterate on parameters after seeing its result. Treat any tuned model as a challenger until it also builds live forward-validation history.

To test the class-balanced bootstrap ensemble proposed for sparse species:

```bash
BIRDNET_DB_PASSWORD="$(docker exec birdnet-postgres printenv POSTGRES_PASSWORD)" \
  .venv/bin/python ml/src/bootstrap_species_ensemble.py \
  --species "American Crow"
```

The ensemble experiment:

- reuses the leakage-safe chronological development/holdout split
- finds XGBoost hyperparameters on development folds only
- builds multiple class-balanced bootstrap samples with replacement
- trains one XGBoost model per bootstrap sample
- averages member probabilities rather than majority-voting hard labels
- tunes the single-model and ensemble thresholds on development predictions only
- reports a chronological holdout comparison against the current XGBoost baseline

For a species whose holdout has already been inspected in an earlier experiment, treat that same window as diagnostic rather than untouched. The script does not modify live prediction, scheduled species, or stored forecasts.

See `docs/experiments/2026-09-14-species-models.md` and `docs/experiments/2026-09-18-american-crow-bootstrap-ensemble.md`.

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

Timing, leakage-sensitive behavior, and aggregate scoring coverage are tested under `ml/tests/`.

Run the full current suite with:

```bash
cd /opt/birdnetpi-monitoring
.venv/bin/python -m unittest discover -s ml/tests -v
```

The timing suite verifies:

- completed-hour selection after the grace period
- behavior before the grace period
- UTC → Los Angeles time conversion
- duplicate local-hour rejection around DST overlap
- missing recent-hour rejection
- T → T+2 training targets
- 1h / 2h / 3h / 24h lag construction

The aggregate scoring suite verifies:

- both live aggregate model labels are included in scoring
- scoring remains limited to unscored prediction rows
- scoring still matches predictions to their target hour
- the issue-time and target-completion guards remain present

Run the full suite after changing `src/timing.py`, aggregate prediction/scoring logic, or related live feature construction.

---

# Script Map

| Script | Purpose |
|---|---|
| `src/timing.py` | Completed-hour timing, hourly preparation, and v2 guards |
| `src/predict_next_hour.py` | Live aggregate Random Forest + XGBoost prediction |
| `src/score_predictions.py` | Score eligible aggregate predictions |
| `src/compare_v2_xgboost.py` | Leakage-safe aggregate RF vs XGBoost comparison |
| `src/compare_species_models.py` | Generic species walk-forward comparison |
| `src/species_candidates.py` | Rank species by live-prediction history/signal |
| `src/optimize_species_xgboost.py` | Chronological randomized XGBoost/threshold optimization |
| `src/bootstrap_species_ensemble.py` | Class-balanced bootstrap XGBoost probability ensemble experiment |
| `src/predict_species_live.py` | Live reference RF + XGBoost species prediction |
| `src/predict_species_challengers.py` | Live per-species challenger prediction runner |
| `src/score_species_predictions.py` | Score eligible species predictions |
| `live_species.txt` | Species receiving reference RF + XGBoost predictions |
| `species_challengers.json` | Per-species challenger strategy, model label, threshold, and parameters |

Earlier scripts such as `features.py`, `evaluate.py`, `train.py`, `compare_models.py`, `rolling_validation.py`, `feature_importance.py`, and `ablation.py` are retained as historical methodology. Several use the older row-based target convention and should not be presented as directly comparable with current T → T+2 results.

`ml/reports/experiments.md` is explicitly historical. Current curated findings belong in `docs/experiments/`.

---

# Validation Rules

Current v2 experiments use chronological evaluation rather than random train/test shuffling.

A training target is included only when that target would already have been observable at the simulated issue time.

For live aggregate comparison, compare Random Forest and XGBoost only across target hours where both have scored forecasts. Do not mix duplicate model rows into a single forecast count or aggregate metric.

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

- accumulate matched live Random Forest and XGBoost forward-validation history
- compare the two aggregate models only after enough shared scored target hours exist
- evaluate species probability thresholds
- add stronger ingestion/uptime completeness checks
- repeat model comparisons as the dataset grows
- add sunrise/daylight and later weather features where justified

Keep every prediction path understandable, leakage-safe, and reproducible.
