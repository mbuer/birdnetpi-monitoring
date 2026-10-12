# 2026-10-11 — Residual-model retrospective experiment

## Question

Can activity history predict deviations from expected solar/time activity?
Does weather observed at completed hour T improve the correction?

## Status and code state

COMPLETED RETROSPECTIVE EXPERIMENT. This is Package D, following the
[weather](2026-10-11-weather-observation-ablation.md) and
[feature-family](2026-10-11-feature-family-ablation.md) experiments.

Base commit: `7f35823b9e617cc2f3da5fa0e55c7162f6881049`, with uncommitted
Packages A/B/C/D. Script: `ml/src/residual_model.py`.
Reviewed script SHA256, normalized text:
`afb5782663536486d8268c596425f568353d9447f2292658361226c205814cc6`.

Provenance: completed runner report, 859-row forecast CSV, and code-state
manifest retained outside Git. The three-row, eight-tree smoke run is excluded
from all metrics below. The report confirmed preserved A/B/C and production
inputs. CSV chronology, unique input hours, two-hour horizon, target availability,
minimum training counts, and overall MAE were independently checked after export.

## Dataset

| Item | Value |
|---|---|
| Source | `bird_activity_hourly`, existing loader and health gate |
| Raw hourly rows | 1079 |
| Matched usable rows | 1052 |
| Completed forecasts | 859 |
| Usable input window | 2026-08-28 22:00 through 2026-10-11 17:00 |
| Completed-outcome cutoff | 2026-10-11 19:00 |
| Scored target window | 2026-09-06 01:00 through 2026-10-11 19:00 |
| Timing | Completed hour T -> target T+2 |
| Minimum training rows | 192 |
| Skipped: insufficient training | 193 |
| Skipped: recent activity gaps | 0 |
| Runtime | 19.5 minutes |

All timestamps are Los Angeles local wall-clock hours. Package C and D have
the same forecast count and reproduce the same aggregate persistence,
climatology, and full-RF metrics to reported precision. C did not export its
row-level predictions, so row-by-row identity is not independently established.

Runtime versions: Python 3.12.3 from the prerequisite review; the run itself
printed NumPy 2.5.3, pandas 3.0.5, scikit-learn 1.9.1, and psycopg 3.3.5.

## Features, models, and leakage controls

See [residual method](residual-model.md) for the complete baseline construction
and operational contract. Each fold uses only training target hours <= T.
Hourly reindexing precedes lag/target shifts. The existing health gate remains
in force; every scored input passes the live 25-hour recent-activity guard.

The solar-bin baseline estimates T+2 activity from the solar position at T,
with clock-hour/global fallbacks. It is rebuilt from available training history
for every test hour. Training residuals exclude their own outcome from each
baseline mean and minimum-count calculation. Other training labels are allowed
only because they are known at the outer issue time. This is a fold-local
training transformation, not a prequential residual-label archive.

RF full uses the existing eight live aggregate features and absolute activity
labels. Residual RF uses current activity and 1h / 2h / 3h / 24h lags. The
weather variant adds `temperature_f`, `humidity_pct`, `wind_mph`, `cloud_pct`,
and `precipitation_in` at T. No target-hour observed weather is used.

All RF fits use 300 trees, leaf minimum 3, seed 42, and one worker. Final
predictions are clipped at zero. All models share the same training and test
rows. Outcome day/night and residual groups are diagnostics, excluded from
feature selection, baseline construction, and fitting.

## Results

### Overall

| Model | Hours | MAE | RMSE | Median AE | P90 AE |
|---|---:|---:|---:|---:|---:|
| Persistence | 859 | 8.505 | 13.758 | 4.000 | 24.000 |
| Solar climatology | 859 | 4.598 | 7.680 | 2.000 | 13.113 |
| RF full | 859 | 4.456 | 7.428 | 2.000 | 12.699 |
| Residual RF | 859 | 4.696 | 7.823 | 2.096 | 12.965 |
| Residual RF + weather | 859 | 4.798 | 7.680 | 2.215 | 13.741 |

Residual RF worsens MAE by 5.39% relative to RF full; adding observed weather
worsens it by 7.67%. The weather residual variant worsens MAE by 2.16% relative
to the activity-only residual variant, while reducing its RMSE.

### Target-hour day / night MAE

| Group | Hours | Persistence | Solar climatology | RF full | Residual RF | Residual RF + weather |
|---|---:|---:|---:|---:|---:|---:|
| Target day | 462 | 12.898 | 7.878 | 7.473 | 7.947 | 7.899 |
| Target night | 397 | 3.393 | 0.782 | 0.946 | 0.914 | 1.189 |

Target-day metadata is available for every forecast. Solar climatology has
the lowest target-night MAE; RF full has the lowest target-day MAE.

### Input-hour day / night MAE

These groups retain B/C's convention for historical comparison.

| Group | Hours | Persistence | Solar climatology | RF full | Residual RF | Residual RF + weather |
|---|---:|---:|---:|---:|---:|---:|
| Input day | 461 | 11.302 | 6.557 | 6.566 | 6.687 | 6.618 |
| Input night | 398 | 5.266 | 2.329 | 2.012 | 2.391 | 2.690 |

### Actual target activity bands: MAE

| Group | Hours | Persistence | Solar climatology | RF full | Residual RF | Residual RF + weather |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 409 | 3.367 | 1.376 | 1.456 | 1.495 | 1.780 |
| 1-5 | 117 | 8.248 | 4.868 | 4.803 | 4.932 | 4.758 |
| 6-15 | 143 | 9.881 | 4.738 | 5.058 | 5.388 | 5.615 |
| 16+ | 190 | 18.689 | 11.264 | 10.249 | 10.923 | 10.704 |

### Head-to-head absolute-error wins

| First model | Second model | First wins | Second wins | Ties |
|---|---|---:|---:|---:|
| Residual RF | Solar climatology | 420 | 295 | 144 |
| Residual RF | RF full | 409 | 337 | 113 |
| Residual RF + weather | Residual RF | 324 | 414 | 121 |
| Residual RF + weather | RF full | 368 | 437 | 54 |

Ties use an absolute tolerance of 1e-9. Activity-only residual RF wins more
hours against full RF, but its aggregate error is larger. Wins alone do not
justify promotion.

## Residual diagnostics

Actual residual = outcome minus fold-local solar baseline.

| Statistic | Value |
|---|---:|
| Mean | 1.142 |
| Standard deviation | 7.599 |
| Minimum | -22.909 |
| P10 | -6.076 |
| Median | 0.000 |
| P90 | 11.229 |
| Maximum | 41.176 |

| Correction | Raw residual MAE | Effective MAE after clipping |
|---|---:|---:|
| Zero correction / solar baseline | 4.598 | 4.598 |
| Residual RF | 4.915 | 4.696 |
| Residual RF + weather | 4.998 | 4.798 |

Clipping negative activity predictions reduces error. Effective residual MAE
equals final activity MAE because both subtract the same baseline.

### Unusual target hours: MAE

Fixed residual thresholds were set before the run. They are outcome diagnostics,
not validated issue-time alert thresholds.

| Group | Hours | Persistence | Solar climatology | RF full | Residual RF | Residual RF + weather |
|---|---:|---:|---:|---:|---:|---:|
| Residual >= +5 | 160 | 17.481 | 13.657 | 11.496 | 13.231 | 13.005 |
| Residual <= -5 | 120 | 9.608 | 9.000 | 7.985 | 8.952 | 9.009 |

Neither residual variant beats RF full on unusually active or unusually quiet
hours. Both slightly improve on climatology for unusually active hours, but
the absolute full RF achieves a larger improvement.

### Final-fold feature importance

| Feature | Residual RF | Residual RF + weather |
|---|---:|---:|
| `activity_index` | 0.2305 | 0.0921 |
| `activity_lag_1h` | 0.2109 | 0.0635 |
| `activity_lag_2h` | 0.1576 | 0.0601 |
| `activity_lag_3h` | 0.1445 | 0.0475 |
| `activity_lag_24h` | 0.2564 | 0.1098 |
| `wind_mph` | — | 0.2095 |
| `temperature_f` | — | 0.1929 |
| `humidity_pct` | — | 0.1202 |
| `cloud_pct` | — | 0.0894 |
| `precipitation_in` | — | 0.0150 |

Importance shows model usage, not causality or predictive improvement. The
full RF's largest importances remain sunrise-relative time 0.6581 and clock
hour 0.1550, reproducing C's reported values.

## Interpretation and limitations

This simple residual formulation does not provide a better aggregate forecast
than RF full. It does not refute every possible dynamic-signal model. The
result is specific to raw activity-history features, the solar-bin baseline,
fold-local leave-one-out residual labels, and the inspected short dataset.

Chronological simulation does not reconstruct historical ingestion, weather
arrival, or health snapshots. Legacy pre-health provenance and uncertain
historical precipitation units remain unchanged. Repeated investigation of this
window makes it development evidence, not an untouched final holdout. These
859 forecasts are distinct from genuine stored live forward forecasts.

## Decision and production impact

NO PRODUCTION CHANGE. REFERENCE RETAINED.

Production impact: None. No model labels, production features, timers, database
objects, dashboards, or deployment behavior changed. Retrospective predictions
were written only to a CSV outside Git, never to the live prediction tables.

## Validation and follow-up

Python compilation, whitespace checks, all 23 ML tests, and repository hygiene
passed before execution. The full run completed, and the reviewed input hashes
still matched afterward.

Next: refresh matched genuine forward-validation evidence for the existing
aggregate models. Any further residual formulation needs a stated hypothesis
and future validation; do not tune repeatedly against these inspected hours.
Historical forecast weather remains a separate investigation requiring actual
issue-time snapshots.

## Reproducibility

```bash
PGOPTIONS='-c default_transaction_read_only=on' \
BIRDNET_DB_PASSWORD="$(docker exec birdnet-postgres printenv POSTGRES_PASSWORD)" \
  .venv/bin/python -u ml/src/residual_model.py \
  --cutoff '2026-10-11 19:00' --output /tmp/residual-model-new-run.csv
```

The cutoff prevents later outcome hours from entering this rerun. It does not
freeze later corrections to historical source or health rows. Raw artifacts
remain outside Git. SHA256 of retained evidence:

- `report.txt`: `ea5d09068f392bbf0c1daa828e8633c5b0c1845fa3f7cee8b44e6f0ef37d718c`
- `forecasts.csv`: `042ef87a6dbb9f38823ebf5a1c0919bf7cc6af1d7d06b61bbbc5671bd23c1e53`
- `code-state.json`: `9c7b103b64d0c37a286970c46f3467017b28a2c60259fe160a115549de33dfef`
