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

## 2026-09-26 — Expand live species reference set conservatively

A refreshed species-candidate review used 747 hourly observations.

The strongest additional candidates included:

- Black-crowned Night-Heron: 82 positive hours, 10.98% prevalence
- Cedar Waxwing: 47 positive hours, 6.29% prevalence
- Lesser Goldfinch: 45 positive hours, 6.02% prevalence
- Anna's Hummingbird: 43 positive hours, 5.76% prevalence

Decision:

- add Black-crowned Night-Heron and Lesser Goldfinch to the live species reference set
- initially issue only the existing Random Forest and XGBoost reference forecasts for these species
- do not add tuned or bootstrap challengers for the new species yet
- preserve the same completed-hour T -> T+2 timing and scoring contract
- use the newly accumulated forward-validation history, rather than retrospective tuning alone, to decide whether either species later deserves a challenger

Black-crowned Night-Heron was selected because it now has substantial positive-hour coverage across the observation period and adds a useful nocturnal case. Lesser Goldfinch was selected as a second, lower-prevalence species with enough distributed positive hours to begin collecting forward evidence without expanding the live set too aggressively.

This is a roadmap decision only until `ml/live_species.txt` is deliberately changed and deployed.

## 2026-09-26 — Persist hourly BirdNET health evidence in PostgreSQL

A data-completeness audit compared PostgreSQL detection history with the authoritative BirdNET SQLite database and found matching daytime zero-detection hours.

For the local Loki-retained period from 2026-09-13 12:00 through 2026-09-26 11:00, BirdNET analysis telemetry showed:

- 312 of 312 expected hourly samples
- minimum 239 analyzed 15-second segments per hour
- maximum 240 analyzed segments per hour
- healthy zero-detection hours can therefore be distinguished from missing station evidence during that retained period

Decision:

- persist hourly BirdNET analysis-coverage evidence in PostgreSQL on `ubuntu-infra`
- keep the BirdNET Pi itself unchanged
- store raw evidence (`analysis_segments`, `expected_segments`, and `coverage_pct`) as well as a derived health state
- use `healthy`, `incomplete`, and `unknown` states
- treat missing Loki evidence as `unknown`, not as proof that BirdNET was down
- collect recent completed hours repeatedly so delayed telemetry can self-heal through upsert
- backfill only periods for which Loki actually retains evidence; do not manufacture historical health for older hours
- keep ML behavior unchanged until the persisted health dataset has been deployed and validated

The purpose is to prevent future BirdNET/Pi outages from silently becoming biological zero-activity training examples while preserving BirdNET's independence from the monitoring stack.

