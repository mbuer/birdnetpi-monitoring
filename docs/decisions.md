# Decision Log

## 2026-09-26 — ML development sequence

The current ML stack already has live aggregate and species forecasting, stored forward predictions, scoring, and challenger models.

Decision:

- inspect and compare the accumulated live forward-validation history before changing model architecture
- treat data-quality and ingestion-completeness problems as higher priority than adding model complexity
- distinguish a genuinely quiet hour from missing or unhealthy station data before relying more heavily on zero-detection hours
- avoid another round of tuning against diagnostic holdout windows that have already influenced model choices
- add new features such as sunrise/daylight or weather only after the current live baseline has been evaluated cleanly
- defer the ML-to-Birdynator integration boundary until the ML outputs that are genuinely useful have become clearer

The intended sequence is:

```text
inspect live forward validation
    -> strengthen data completeness where needed
    -> establish a clean baseline
    -> add features one at a time
    -> compare against the baseline
    -> later expose stable analytical evidence to Birdynator
```

This keeps the ML work independently evolvable and avoids premature coupling to AI Nexus.

## 2026-09-26 — Start a third aggregate challenger now

The first matched live forward-validation comparison between the existing aggregate models used 233 scored target hours.

Observed matched results at this checkpoint:

- Random Forest MAE: 3.850
- XGBoost MAE: 4.069
- persistence MAE: 7.622
- Random Forest wins: 143
- XGBoost wins: 89
- ties: 1

The model differences are not uniform. Random Forest currently has a clearer advantage during quiet/night periods, while the models are closer during daytime and moderate activity.

Decision:

- add `HistGradientBoostingRegressor` as a third aggregate challenger
- keep Random Forest as the established reference model
- keep XGBoost as an existing challenger
- give the new challenger its own versioned model label
- begin issuing the new model live as soon as practical so forward-validation history starts accumulating
- do not backfill historical rows and present them as forward-issued forecasts
- do not tune or promote the challenger based on the current forward dataset before it has accumulated its own matched live evidence

The purpose is not to increase model count for its own sake. HistGradientBoosting provides a lightweight, meaningfully different comparison while preserving the same T -> T+2 timing and scoring contract.

