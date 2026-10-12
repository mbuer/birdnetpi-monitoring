# Residual-model retrospective method

## Question

Can activity history predict deviations from expected solar/time activity?
Does observed weather at completed hour T improve that correction?

## Status

COMPLETED RETROSPECTIVE METHOD. See the
[dated result](2026-10-11-residual-model.md) for the completed 859-forecast run.

This method follows the uncommitted weather and feature-family ablations.
The reviewed repository base is `7f35823b9e617cc2f3da5fa0e55c7162f6881049`.
The runner records the actual code state and script hashes for each run.

## Dataset

Source: `bird_activity_hourly`, through the existing aggregate loader and
station-health gate. The runner uses a read-only PostgreSQL transaction default.

Prediction horizon: completed hour T -> target T+2.

The hourly timeline is reindexed before lag and target shifts. Missing hours
remain unknown. Candidate rows require all live aggregate features, the five
candidate weather features at T, and an observed target outcome. Every model
uses the same eligible training rows and forecast hours. At least 192 training
rows are required, with target hours <= T. Prediction inputs additionally
require 25 consecutive usable activity hours through T, matching the live
recent-history guard. This can remove forecast hours retained by B/C.

The outcome cutoff is bounded by the latest completed hour. Target hours,
matched windows, counts, runtime versions, and skipped rows are reported.

## Baseline and residuals

Retain Package C's baseline: mean target activity in the same input-hour
sunrise-relative bin, `floor(hours_from_sunrise)`. Require three observations.
Fall back to the same input clock hour, then the global training mean.
This estimates expected T+2 activity conditional on the solar position at T;
it does not read target-hour observed weather or solar metadata as features.

For each forecast, construct the baseline from labels available at that
simulated issue time. Do not use a global climatology over the evaluation
period.

Training residual = target activity minus leave-one-out baseline. Remove the
row's own target from each candidate group before checking minimum counts and
calculating means, including the global fallback. Recompute these residuals
within each outer training fold. Other training outcomes are permitted because
they were already available at the outer issue time. These are fold-local
training transformations, not residual predictions issued at each historical
training row's original issue time.

Final prediction = fold-local expected target activity + predicted residual,
clipped at zero. Preserve raw corrections for residual diagnostics.

## Comparisons

| Model | Inputs / label |
|---|---|
| Persistence | Activity at T |
| Solar climatology | Fold-local solar / clock-hour means |
| RF full | Existing live feature list; absolute target activity |
| Residual RF | Current activity and 1h / 2h / 3h / 24h lags; residual label |
| Residual RF + weather | Activity family plus observed weather at T; residual label |

Weather: `temperature_f`, `humidity_pct`, `wind_mph`, `cloud_pct`,
`precipitation_in`. No time features are added to the residual RF in this first
experiment. No feature tuning or model selection is performed on the results.

RF parameters: 300 trees, `min_samples_leaf=3`, `random_state=42`.
One worker is the default to limit contention with existing host jobs.

## Metrics

Report MAE, RMSE, median absolute error, and P90 absolute error overall, by
target-hour day/night, and by actual activity bands 0 / 1-5 / 6-15 / 16+.
Input-hour day/night is also reported for comparison with B/C's convention.

Report matched head-to-head wins, actual residual distribution, raw and
clipping-adjusted residual MAE, and final-fold RF feature importance.
Fixed residual thresholds of +5 and -5 activity-index units describe unusually
active and quiet hours. They are diagnostics, not validated alert thresholds.

## Limitations

Retrospective chronology limits training labels and inputs. It does not
reconstruct historical ingestion, weather arrival, or health-row snapshots.
Late-arriving data may therefore differ from what was originally available.
Pre-health history retains the existing legacy provenance rule. Historical
precipitation units retain their documented uncertainty; no conversion is made.
The short dataset does not establish seasonal performance or causality.

Target-day metadata and actual residuals are outcome diagnostics only. They
are excluded from model fitting and baseline construction. Raw residual MAE
can differ from final activity MAE because the final prediction is clipped.

## Reproducibility

Script: `ml/src/residual_model.py`.
Tests: `ml/tests/test_residual_model.py`.

```bash
PGOPTIONS='-c default_transaction_read_only=on' \
BIRDNET_DB_PASSWORD="$(docker exec birdnet-postgres printenv POSTGRES_PASSWORD)" \
  .venv/bin/python -u ml/src/residual_model.py \
  --cutoff '2026-10-11 17:00' --output /tmp/residual-model-unique.csv
```

Use a new output path for each run. CSV output inside the checkout is refused.
Each completed forecast is flushed to disk. An interrupted CSV is partial
evidence; only a completed report establishes a completed experiment.
`--max-forecasts`, `--trees`, and `--min-training-rows` overrides are explicitly
reported as nonstandard runs. The upload runner uses a small smoke run before
the default full experiment.

The completed result is recorded in `2026-10-11-residual-model.md`.
Keep generated run output outside Git. Later reruns require a new dated record
when the dataset or methodology changes.

## Decision

NO PRODUCTION CHANGE.

Production impact: None. Live models, labels, features, health gating, timers,
database objects, dashboards, and deployment remain unchanged. No commit or
push is performed.
