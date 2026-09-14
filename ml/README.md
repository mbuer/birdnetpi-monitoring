# BirdNET ML

Machine-learning experiments for predicting BirdNET activity from historical detections, time, weather, and eventually weather forecasts.

This lives inside the larger `birdnetpi-monitoring` project.

The first goal remains simple:

> Predict the BirdNET activity index for the next hour.

The important part is building honest baselines, avoiding data leakage, and comparing sensible models on unseen data. The repository now includes experiments, stored predictions, scoring, an hourly systemd cycle, and a PostgreSQL dashboard.

**Current status:** this README describes the accompanying completed-hour fix, which must be installed first. The pipeline is experimental. V2 enforces completed inputs, a ten-minute grace period, fresh recent history, and scoring after target completion. It cannot prove ingestion completeness or repair legacy scores.

---

## Current Dataset

Data comes from `bird_activity_hourly`, defined in [the hourly view SQL](../database/views/bird_activity_hourly.sql). It combines BirdNET activity with weather observations.

The initial September 13 snapshot reported 405 hourly rows spanning August 27–September 13, 195 active hours, average activity 6.15, and maximum 49. These are historical observations, not current totals or quality guarantees. The initial dataset covered about 17 days; it cannot establish seasonal behavior.

Weather hours define the view. Bird hours without weather are omitted; weather hours without detections have zero activity. The view includes incomplete current hours and combines stations. See [database documentation](../database/README.md) for the exact data contract.

## Activity Index

Raw detection count can be misleading because one persistent bird can generate many detections.

```text
capped detections = sum(min(species detections, 10))
activity index = species count + capped detections
```

This makes repeated calls from one species less dominant. It is a practical project metric, not an established ecological measure. It measures recorded detections, which also depend on station uptime and detection settings.

## Prediction Features

The live model and main comparison scripts use the same feature names:

- hour of day
- hours from sunrise
- day/night
- current activity
- activity lags of 1, 2, 3, and 24 hours in v2 (row shifts in the older experiments)

V2 reindexes hourly history and rejects input windows containing gaps or ambiguous DST hours. The older experiment scripts still rely on row continuity and retain their original target horizon.

Temperature, humidity, wind, cloud cover, and precipitation remain in the loaded dataset. They are used by the older `train.py` experiment, but **not** by the current live Random Forest or main comparison/rolling scripts.

Historical weather experiments did not improve the early one-hour results. That is a dataset-specific observation, not evidence that weather is generally irrelevant.

## Current Model and Baseline

The corrected live model label is `random_forest_v2_completed`:

```text
RandomForestRegressor
n_estimators = 300
min_samples_leaf = 3
random_state = 42
```

Each invocation fits a new model on valid completed feature/target rows, requiring at least 192 training examples. At 14:10, the feature bucket is 13:00–14:00 and the forecast target is 15:00–16:00. V2 training uses the same two-hour offset between bucket starts. It does not load a persisted model artifact or implement a champion/challenger promotion system.

Persistence predicts that the target activity equals the latest input activity. That value is stored as `current_activity`, so later comparisons use the baseline available with the original forecast.

## Experiments and Evaluation

No random train/test shuffling is used.

| Script | Purpose |
|---|---|
| `src/data.py` | Load completed hours with a ten-minute ingestion grace period |
| `src/timing.py` | V2 time-based horizon, hourly gap checks, freshness and DST guards |
| `src/features.py` | Row shifts for lags and next-row target |
| `src/evaluate.py` | Persistence, chronological 80/20 split |
| `src/train.py` | Older time/weather/activity HistGradientBoosting experiment |
| `src/compare_models.py` | Poisson, Random Forest, HistGradientBoosting and persistence; 80/20 split |
| `src/rolling_validation.py` | Expanding training window: initially 192 rows, 24-row test windows |
| `src/feature_importance.py` | Random Forest impurity-based feature importance |
| `src/ablation.py` | Five feature sets, expanding 192/24-row evaluation |
| `run_experiments.sh` | Run comparison, rolling validation, importance and ablation; save a report |

The rolling script's comment still says 48 hours; its active value is 24 rows. Each test row uses its own historical activity inputs. These are repeated one-step evaluations with a model fixed within each fold, not a 24-hour forecast issued all at once.

MAE measures average absolute error. RMSE gives more weight to large errors. The rolling summary averages fold RMSEs; it is not a pooled RMSE calculation. Compare models and persistence on the same valid rows.

The old experiment scripts still use a one-row target horizon. Their results are not directly comparable with v2; matched retrospective evaluation remains follow-up work.

The historical [experiment log](reports/experiments.md) records the early results, including Random Forest average MAE 3.874 versus persistence 4.274 in seven 24-row windows. These results have not been reproduced against a frozen dataset in this review.

`train.py` still prints hard-coded persistence scores. Use `evaluate.py` or `compare_models.py` for a baseline calculated from the current data.

## Running Experiments

Run on `ubuntu-infra` from `/opt/birdnetpi-monitoring`. The scripts expect a root-level `.venv`.

```bash
cd /opt/birdnetpi-monitoring
python3 -m venv .venv
.venv/bin/python -m pip install -r ml/requirements.txt
./ml/run_experiments.sh
```

The checked-in requirements pin pandas, scikit-learn, and psycopg. They import NumPy transitively; recording it explicitly would improve reproducibility.

The shell wrappers use `BIRDNET_DB_HOST`, `BIRDNET_DB_NAME`, `BIRDNET_DB_USER`, and `BIRDNET_DB_PASSWORD`. Defaults are `127.0.0.1`, `birdnet`, and `birdnet`. When no password is supplied, the wrappers read `POSTGRES_PASSWORD` from the local `birdnet-postgres` container. This requires Docker access and couples the job to that container. Never paste the resulting secret into Git or a report.

Reports go to `ml/reports/runs/run_YYYY-MM-DD_HH-MM-SS.txt`. This directory and `.venv/` are already ignored. Keep curated conclusions in `reports/experiments.md`.

## Live Prediction and Scoring

```text
birdnet-ml-prediction.timer
    -> birdnet-ml-prediction.service
    -> ml/hourly_prediction_cycle.sh
        -> score_predictions.sh -> src/score_predictions.py
        -> predict_next_hour.sh -> src/predict_next_hour.py
    -> PostgreSQL bird_activity_predictions
    -> Grafana Prediction Lab
```

The cycle scores first, then predicts. Shell failure handling stops the cycle if scoring fails.

The prediction requires the previous completed local hour and targets the next full local hour: at 14:10, use 13:00 inputs for 15:00. It validates freshness again after fitting and checks the issue hour at insertion. It stores model output, persistence, training-row count, and insertion time. Duplicate target-hour/model pairs preserve the first forecast.

The corrected scorer updates only unscored `random_forest_v2_completed` rows, after the target ends plus ten minutes and only if the prediction was created before the target began. It stores actual activity, absolute error, and scoring time. A missing target view row remains pending. An already scored row is not revised when late detections arrive.

The [deployment runbook](../deploy/ubuntu-infra/README.md) describes the `infra` service account, paths, timer, installation, and checks. The timer runs at minute 10 each hour in the host timezone and is persistent; it does not generate every missed forecast after downtime.

## Known Validation Limitations

The accompanying fix addresses unfinished inputs, premature v2 scoring, stale prediction inputs, and compressed live lags. Ten offline regression checks cover issue timing, training horizon, gaps, stale data and DST intervals.

- Ten minutes after hour end is an ingestion grace period, not proof that all detections arrived. Station heartbeat/completeness checks and late-data reconciliation remain open.
- Existing v1 predictions and scores are preserved and no longer scored by the corrected job. Audit them before any repair; do not compare their scores directly with v2.
- The SQL view still combines stations and uses local timestamp keys. V2 skips ambiguous recent DST windows; a UTC/station-key migration remains later work.
- The original retrospective scripts retain their one-row horizon and row-based lag handling. They need a matched v2 evaluation before their results support conclusions about the corrected model.
- Input snapshots, exact cutoff and dependency/code provenance are not yet stored per prediction. The model label separates the timing change but is not a full reproducibility record.
- Missing weather can exclude hours and zero detections can conceal outages. New scoring leaves already scored actuals unchanged if data later arrives.

## Checking the Fix

Run `ml/tests/test_timing.py` with the repository virtual environment. The Python entry points support `--check`: prediction fits/validates without inserting, and scoring counts eligible records without updating. Supply the normal database environment when invoking Python directly. The provided installer performs these checks before resuming the timer.

## Grafana

[Prediction Lab](../grafana/README.md) reads the prediction table and hourly view through `grafana_reader`. Pending forecasts are expected before a valid actual is ready. The accompanying updated dashboard filters all prediction queries to v2; its summary statistics cover all scored v2 rows, while chart panels use the selected time range. Import that JSON to activate the filtering; copying it to the repository is insufficient.

Legacy records remain stored and are excluded from the updated dashboard. The first v2 accuracy metrics appear only after a target has ended and been scored.

## Weather Observations vs Forecasts

Future weather-aware models must use forecasts available at issue time, not future observed weather. Existing `forecast_created_at` values are rounded to the collection hour; exact retrieval timestamps are not stored in the forecast table. Add provenance before claiming exact as-of availability.

Both weather collectors currently write precipitation to an `_in` column without explicitly requesting precipitation units. Audit units and historical values before adding those fields to model comparisons.

## Next Work

- Run matched retrospective v2 evaluation and add stronger ingestion-completeness checks.
- Record dataset cutoffs, code/dependency versions, and comparable baseline results.
- Accumulate a larger history and inspect daytime, zero-activity, and burst errors separately.
- Revisit weather and species-specific targets when data supports them.
- Consider uncertainty estimates and champion/challenger experiments later.

## Guiding Principle

The goal is to build the simplest model that reliably predicts future activity better than straightforward baselines.

If the data eventually justifies more complexity, we can add it then.
