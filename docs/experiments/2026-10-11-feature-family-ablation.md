# 2026-10-11 — Aggregate feature-family ablation

## Question

Does the full aggregate RF add useful dynamic information beyond the daily
solar/time activity pattern?

## Status and code state

COMPLETED RETROSPECTIVE EXPERIMENT.

Base commit: `7f35823b9e617cc2f3da5fa0e55c7162f6881049`, with uncommitted
Packages A/B/C. Script: `ml/src/feature_family_ablation.py`.
Reviewed script SHA256, normalized text:
`999dc00847152bdfe67af52f229f4fe11157e72979db6f665d44d7625f5818c0`.

Results are transcribed from the operator's completed console output retained
in the project conversation. No row-level forecast export was supplied for C.
Run-time versions were not printed; pinned repository requirements alone do
not establish the environment used for that run.

## Dataset and validation

| Item | Value |
|---|---|
| Source | `bird_activity_hourly`, existing loader and health gate |
| Raw hourly rows | 1079 |
| Usable rows | 1052 |
| Walk-forward forecasts | 859 |
| Usable input start | 2026-08-28 22:00 |
| Usable input cutoff | 2026-10-11 17:00 |
| Implied latest target | 2026-10-11 19:00 |
| Timing | Completed hour T -> target T+2 |
| Minimum training rows | 192 |
| Runtime | 14.8 minutes |

Reindex before constructing lags and targets. Fit on an expanding chronological
window, admitting only training targets <= T. All comparisons use identical
training and test rows. Missing required features or targets exclude a row;
the existing health gate masks unreliable zeroes and preserves legacy history.

## Features and models

Time family: `hour_of_day`, `hours_from_sunrise`, `is_day`.

Activity family: `activity_index`, `activity_lag_1h`, `activity_lag_2h`,
`activity_lag_3h`, `activity_lag_24h`. Full RF uses both families.

Each RF uses 300 trees, leaf minimum 3, seed 42, and all available workers.
Predictions are clipped at zero. Persistence uses activity at T.

Solar climatology averages known target labels in the same input-hour
`floor(hours_from_sunrise)` bin, requiring at least three observations.
Fallback: same input clock hour with three observations, then global training
mean. The baseline is rebuilt from available history at every simulated issue.
No global future-informed climatology or weather feature is used.

## Results

All overall metrics use the same 859 target hours.

| Model | MAE | RMSE | Median AE | P90 AE |
|---|---:|---:|---:|---:|
| Persistence | 8.505 | 13.758 | 4.000 | 24.000 |
| Solar climatology | 4.598 | 7.680 | 2.000 | 13.113 |
| RF time-only | 4.466 | 7.520 | 1.952 | 12.867 |
| RF activity-only | 7.407 | 10.572 | 5.592 | 16.929 |
| RF full | 4.456 | 7.428 | 2.000 | 12.699 |

The console reported full-model MAE improvements of 0.21% over time-only,
39.84% over activity-only, and 3.09% over solar climatology. These percentages
used unrounded metrics.

| Comparison | Full wins | Other wins | Ties |
|---|---:|---:|---:|
| Full vs time-only | 328 | 353 | 178 |
| Full vs activity-only | 620 | 238 | 1 |
| Full vs solar climatology | 383 | 394 | 82 |

### Input-hour day / night MAE

The historical script groups by input hour T, not target-hour day state.

| Period | Hours | Solar climatology | RF time-only | RF activity-only | RF full |
|---|---:|---:|---:|---:|---:|
| Input day | 461 | 6.557 | 6.597 | 7.533 | 6.566 |
| Input night | 398 | 2.329 | 1.997 | 7.261 | 2.012 |

### Actual target activity bands: MAE

| Activity | Hours | Solar climatology | RF time-only | RF activity-only | RF full |
|---|---:|---:|---:|---:|---:|
| 0 | 409 | 1.376 | 1.224 | 5.268 | 1.456 |
| 1-5 | 117 | 4.868 | 5.101 | 4.286 | 4.803 |
| 6-15 | 143 | 4.738 | 6.121 | 4.418 | 5.058 |
| 16+ | 190 | 11.264 | 9.805 | 16.183 | 10.249 |

## Diagnostics and interpretation

| Final full-RF feature | Importance |
|---|---:|
| `hours_from_sunrise` | 0.6581 |
| `hour_of_day` | 0.1550 |
| `activity_index` | 0.0513 |
| `activity_lag_24h` | 0.0397 |
| `activity_lag_1h` | 0.0375 |
| `activity_lag_3h` | 0.0314 |
| `activity_lag_2h` | 0.0262 |
| `is_day` | 0.0007 |

Time/solar features account for approximately 81% of final impurity importance.
Together with the 0.21% time-only MAE difference, this supports describing the
full RF as primarily a diurnal-pattern estimator on this dataset. Importance
is not causality. Aggregate MAE and per-hour wins measure different properties.

Activity-only RF is poor overall but competitive in the 1-5 and 6-15 bands.
This motivated testing a separate residual objective; it did not establish that
residualization would improve performance. Those bands depend on actual future
activity and cannot be used as an issue-time model selector.

## Limitations and decision

The short dataset, weather-backed coverage, historical arrival uncertainty,
and legacy pre-health provenance remain limitations. These are retrospective
forecasts, not stored live forward-validation evidence.

NO PRODUCTION CHANGE. Production impact: None.

REFERENCE RETAINED. The time-only improvement is too small to justify changing
the live feature list. The subsequent
[residual experiment](2026-10-11-residual-model.md) tests the dynamic-signal
hypothesis directly.

## Reproducibility

```bash
PGOPTIONS='-c default_transaction_read_only=on' \
BIRDNET_DB_PASSWORD="$(docker exec birdnet-postgres printenv POSTGRES_PASSWORD)" \
  .venv/bin/python ml/src/feature_family_ablation.py
```

The script loads the current dataset; later reruns need not reproduce the
recorded cutoff or scores. Keep generated output outside Git.
