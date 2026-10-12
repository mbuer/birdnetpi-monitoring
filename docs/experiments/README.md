# ML Experiment Records

This directory contains curated, dated machine-learning experiment records for
the BirdNET monitoring project.

Stable methodology belongs in `docs/ml.md`.
Operational instructions belong in `ml/README.md`.
Historical or raw experiment output may remain under `ml/reports/`.

## Experiment contract

Every meaningful experiment should record:

1. question being tested
2. experiment date
3. repository commit or code state
4. dataset source
5. dataset start and cutoff
6. usable or matched row count
7. prediction horizon
8. feature sets
9. model labels and parameters
10. validation method
11. leakage controls
12. metrics
13. subgroup results where useful
14. interpretation
15. decision
16. production impact

Use `TEMPLATE.md` when starting a new experiment record.

## Evidence levels

### Retrospective experiment

A historical simulation using chronological data. Useful for developing
hypotheses, but weaker than genuinely issued forecasts.

### Forward validation

Predictions stored before the target outcome occurred and scored later. This is
the preferred evidence for deciding whether a live challenger has earned
promotion.

### Production reference

A model or methodology explicitly selected as the current reference. A
retrospective win alone does not make a model the production reference.

## Feature investigations

New features should normally be evaluated as challengers before changing live
production features.

For weather work, distinguish carefully between:

- observed weather available at issue time
- forecast weather for the future target hour

Historical target-hour observed weather must never be used as though it had
been available when the forecast was issued.

## Production changes

An experiment result should explicitly state one of:

- NO PRODUCTION CHANGE
- CONTINUE FORWARD VALIDATION
- PROMOTE TO LIVE CHALLENGER
- CHANGE REFERENCE MODEL
- CHANGE LIVE FEATURE SET

Any production methodology change must also update the relevant code, tests,
`docs/ml.md`, `ml/README.md`, and decision history.

## Current direction

The current aggregate reference remains Random Forest.

Live aggregate challengers currently include XGBoost and
HistGradientBoosting.

The 2026-10-11 investigation is complete:

| Package | Scope | Record / outcome |
|---|---|---|
| A | Experiment readiness | This contract and `TEMPLATE.md` |
| B | Observed weather at T | [Weather ablation](2026-10-11-weather-observation-ablation.md); no aggregate MAE improvement |
| C | Time/activity families | [Feature-family ablation](2026-10-11-feature-family-ablation.md); solar/time pattern dominates |
| D | Residual activity models | [Residual experiment](2026-10-11-residual-model.md); no improvement over full RF |

Package letters identify implementation packages. They are separate from the
earlier decision log's A/B/C weather-variant labels; the target-hour forecast
weather variant has not been tested.

NO PRODUCTION CHANGE. The current RF and live features remain the reference.
Refresh matched stored forward-validation evidence before another modeling
change. Any further experiment must state a new hypothesis and preserve an
honest future validation window. Historical forecast-weather work requires
actual snapshots available at issue time.
