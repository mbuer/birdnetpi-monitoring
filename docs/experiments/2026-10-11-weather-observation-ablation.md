# 2026-10-11 — Observed-weather ablation

## Question

Does weather observed at completed hour T improve aggregate activity forecasts
for target hour T+2?

## Status and code state

COMPLETED RETROSPECTIVE EXPERIMENT.

Base commit: `7f35823b9e617cc2f3da5fa0e55c7162f6881049`, with uncommitted
experiment-readiness documentation and `ml/src/weather_ablation.py`.
Reviewed script SHA256, normalized text:
`d9abff16cdd590ce08c1c90cd7e61ae7c0075881cba56482203e83868f7d8fab`.

Results below are transcribed from the operator's completed console output,
retained in the project conversation. No row-level forecast export was supplied
for this run. Exact run-time dependency versions were not recorded in that
output; repository requirements are pinned but do not prove the run environment.

## Dataset and validation

| Item | Value |
|---|---|
| Source | `bird_activity_hourly`, existing loader and health gate |
| Raw hourly rows | 1078 |
| Matched usable rows | 1051 |
| Walk-forward forecasts | 858 |
| Usable input start | 2026-08-28 22:00 |
| Usable input cutoff | 2026-10-11 16:00 |
| Implied latest target | 2026-10-11 18:00 |
| Timing | Completed hour T -> target T+2 |
| Minimum training rows | 192 |

Reindex the hourly timeline before constructing 1h / 2h / 3h / 24h lags and the
two-hour target. Fit separately at each chronological test hour. Include only
training rows with target hour <= T. Baseline and weather variants use identical
training and evaluation rows; missing weather excludes rows from both variants.
Preserve the existing station-health zero rule and legacy pre-health history.

## Features and models

Baseline: `hour_of_day`, `hours_from_sunrise`, `is_day`, `activity_index`,
`activity_lag_1h`, `activity_lag_2h`, `activity_lag_3h`, `activity_lag_24h`.

Weather additions at T: `temperature_f`, `humidity_pct`, `wind_mph`,
`cloud_pct`, `precipitation_in`. Future observed target-hour weather is excluded.
Historical forecast-weather snapshots are not tested.

RF: 300 trees, leaf minimum 3, seed 42, all available workers.
XGB: 300 trees, depth 3, learning rate 0.03, row/column sampling 0.8,
`reg:squarederror`, histogram method, seed 42, all available workers.
HGB: scikit-learn defaults, seed 42. Predictions are clipped at zero.
Persistence uses activity at T.

## Results

All overall metrics use the same 858 target hours.

| Model | MAE | RMSE | Median AE | P90 AE |
|---|---:|---:|---:|---:|
| Persistence | 8.466 | 13.691 | 4.000 | 24.000 |
| RF baseline | 4.460 | 7.433 | 2.001 | 12.700 |
| RF + weather | 4.493 | 7.360 | 2.067 | 12.501 |
| XGB baseline | 4.633 | 7.621 | 2.323 | 12.385 |
| XGB + weather | 4.731 | 7.558 | 2.400 | 12.536 |
| HGB baseline | 4.694 | 7.764 | 2.262 | 12.998 |
| HGB + weather | 4.869 | 7.784 | 2.502 | 13.294 |

The console reported MAE deterioration of 0.73% for RF, 2.11% for XGB,
and 3.74% for HGB. Percentage changes used unrounded metrics.

| Model | Weather wins | Baseline wins | Ties |
|---|---:|---:|---:|
| RF | 379 | 428 | 51 |
| XGB | 360 | 456 | 42 |
| HGB | 341 | 425 | 92 |

### Input-hour day / night MAE

These historical groups use `is_day` at T, not the target-hour day state.
The residual experiment separately reports target-hour groups.

| Period | Hours | RF base | RF weather | XGB base | XGB weather | HGB base | HGB weather |
|---|---:|---:|---:|---:|---:|---:|---:|
| Input day | 460 | 6.579 | 6.530 | 6.702 | 6.551 | 6.960 | 6.787 |
| Input night | 398 | 2.012 | 2.139 | 2.242 | 2.628 | 2.074 | 2.652 |

### Actual target activity bands: MAE

| Activity | Hours | RF base | RF weather | XGB base | XGB weather | HGB base | HGB weather |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 408 | 1.457 | 1.607 | 1.694 | 1.943 | 1.520 | 1.906 |
| 1-5 | 117 | 4.803 | 4.463 | 4.549 | 4.078 | 4.989 | 4.463 |
| 6-15 | 143 | 5.058 | 4.857 | 4.657 | 4.747 | 5.341 | 5.399 |
| 16+ | 190 | 10.249 | 10.436 | 10.980 | 11.108 | 10.839 | 11.082 |

## Diagnostics and interpretation

The final RF weather fit assigned importance 0.6090 to sunrise-relative time,
0.1333 to clock hour, 0.0474 to wind, 0.0421 to temperature, and 0.0338 to
humidity. Weather is used, but feature importance is not proof of causality
or improved predictive performance.

Weather modestly improves input-day MAE while degrading input-night MAE.
RF/XGB RMSE decreases slightly, but MAE worsens for every weather variant.
These results do not justify adding observed weather to the live feature list.
They do not establish that weather is biologically irrelevant or that historical
target-hour forecast weather would fail.

## Limitations and decision

The short, weather-backed dataset limits generalization. Chronological filters
do not reconstruct historical ingestion or health-row availability. Historical
precipitation units retain their documented uncertainty; no conversion is made.
Subgroups are diagnostics from an inspected dataset, not independent holdouts.

NO PRODUCTION CHANGE. Production impact: None.

The next completed investigation is the
[feature-family ablation](2026-10-11-feature-family-ablation.md).
Any forecast-weather follow-up requires snapshots that genuinely existed at
issue time; future observations are not a substitute.

## Reproducibility

```bash
PGOPTIONS='-c default_transaction_read_only=on' \
BIRDNET_DB_PASSWORD="$(docker exec birdnet-postgres printenv POSTGRES_PASSWORD)" \
  .venv/bin/python ml/src/weather_ablation.py
```

This historical script loads the current dataset. A later rerun will include
later observations and need not reproduce the recorded window or scores.
