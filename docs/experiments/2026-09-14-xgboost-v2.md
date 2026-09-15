# Experiment: XGBoost vs Random Forest

**Date:** 2026-09-14  
**Status:** Completed  
**Prediction horizon:** T → T+2  
**Validation:** Chronological walk-forward

## Objective

Compare XGBoost with the current Random Forest model using the corrected v2 prediction timing.

The live v2 pipeline uses the latest completed hour as input and predicts the next full future hour.

Example:

- input: 22:00–23:00
- 23:00–00:00 is already underway
- prediction target: 00:00–01:00

This corresponds to a historical relationship of **T → T+2**.

## Dataset

| Item | Value |
|---|---:|
| Source | `bird_activity_hourly` |
| Raw hourly rows | 430 |
| Valid rows | 404 |
| Walk-forward forecasts | 211 |
| Dataset start | 2026-08-28 22:00 |
| Dataset cutoff | 2026-09-14 17:00 |

The dataset covers only a short period, so conclusions should be considered preliminary.

## Features

- `hour_of_day`
- `hours_from_sunrise`
- `is_day`
- `activity_index`
- `activity_lag_1h`
- `activity_lag_2h`
- `activity_lag_3h`
- `activity_lag_24h`

Weather features were excluded.

## Models

### Persistence

Uses the latest completed activity value as the prediction.

### Random Forest

- 300 trees
- `min_samples_leaf = 3`
- `random_state = 42`

### XGBoost

Version: **3.4.1**

- 300 estimators
- `max_depth = 3`
- `learning_rate = 0.03`
- `subsample = 0.8`
- `colsample_bytree = 0.8`
- `tree_method = hist`
- `objective = reg:squarederror`

No hyperparameter tuning was performed.

## Results

| Model | MAE | RMSE |
|---|---:|---:|
| Persistence | 6.123 | 10.463 |
| Random Forest | 4.498 | 7.146 |
| **XGBoost** | **4.460** | **7.127** |

XGBoost reduced MAE by **0.85%** compared with Random Forest.

### Head-to-head

| Result | Forecasts |
|---|---:|
| Random Forest wins | 126 |
| XGBoost wins | 84 |
| Ties | 1 |

Random Forest was closer more often, while XGBoost achieved slightly better aggregate error.

## Conclusion

XGBoost is competitive, but its advantage is currently too small to justify replacing Random Forest.

**Decision:** Keep Random Forest as the live champion and retain XGBoost as a challenger.

Both models substantially outperform persistence.

## Next Steps

Evaluate the models separately during:

- daytime hours
- active bird hours
- high-activity periods
- zero-activity periods

Repeat the comparison as more historical data becomes available.

## Reproducibility

Experiment script:

`ml/src/compare_v2_xgboost.py`

Raw experiment output:

`ml/reports/runs/`

Dependency:

`xgboost==3.4.1`
