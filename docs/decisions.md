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

This decision is implemented in `ml/live_species.txt` and runtime-verified in the coordinated hourly cycle.

## 2026-09-26 — Persist hourly BirdNET health evidence in PostgreSQL

A data-completeness audit compared PostgreSQL detection history with the authoritative BirdNET SQLite database and found matching daytime zero-detection hours.

For 312 consecutive completed hours from 2026-09-13 11:00 through 2026-09-26 11:00 America/Los_Angeles (end exclusive), BirdNET analysis telemetry showed:

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

## 2026-09-26 — Station-health persistence deployed and verified

The hourly station-health pipeline is now deployed on `ubuntu-infra`.

Verified runtime state:

- the PostgreSQL `station_health_hourly` table is active
- the initial retained Loki period was backfilled with 312 consecutive healthy hourly records
- observed analysis coverage in that backfill was 239–240 of 240 expected 15-second segments per hour
- the systemd service completed successfully when run manually
- the systemd timer fired automatically at 2026-09-26 19:20 UTC
- that scheduled run rechecked the latest six completed hours and upserted fresh `collected_at` timestamps
- the timer advanced correctly to the next hourly trigger
- the BirdNET Pi itself was not modified

Decision:

- treat the station-health collector as deployed and operational
- preserve the six-hour lookback/upsert behavior so delayed telemetry can self-heal
- continue to interpret missing Loki evidence as `unknown`, not as proof of an outage
- do not retroactively assign health states to older periods without retained evidence
- any future ML use of `station_health_hourly` is a separate methodology change and must be evaluated explicitly

## 2026-09-26 — Use provenance-aware health gating instead of strict filtering

Station-health persistence is now operational, but the verified health-history window is much shorter than the full ML history.

Considered approaches:

- strict filtering to healthy hours only
- provenance-aware gating of unreliable zero observations
- coverage-weighted training

Decision:

- preserve legacy pre-health history rather than discarding it
- when explicit health evidence exists, keep positive detections/activity even if health is incomplete or unknown
- when explicit health evidence exists, do not use a zero activity/presence observation as a biological zero unless health is `healthy`
- propagate masked zeroes through lag/target construction so affected training rows are naturally excluded
- do not score zero-valued aggregate or species outcomes in the health-evidence era until a healthy station-health row exists
- continue scoring positive outcomes without requiring perfect station coverage
- do not introduce coverage weighting yet

This is intentionally conservative: it fixes the known false-zero failure mode without shrinking the historical training set to only the recent station-health window or adding model-weighting complexity before it is justified.

## 2026-09-26 — Run ML after hourly station-health collection

The provenance-aware gating rule depends on station-health evidence for the latest completed hour.

Decision:

- keep station-health collection at minute 20
- move the hourly ML cycle from minute 10 to minute 30
- preserve the existing T -> T+2 prediction horizon
- preserve the internal ten-minute completed-hour grace
- treat a missing station-health row as `unknown` for hours after health collection began
- keep pre-health historical hours usable under the legacy methodology

This ordering gives the health collector time to persist evidence before the latest completed hour is used for training, prediction inputs, or zero-valued scoring.

## 2026-09-26 — Retire Grafana Cloud Loki dual-write

Local Loki and Grafana OSS have been validated as the active operational observability path.

Runtime verification on the BirdNET Pi confirmed:

- Alloy restarted successfully with a local-only configuration
- the new Alloy process contained no Grafana Cloud writer
- fresh BirdNET journal data was queryable from local Loki
- fresh weather log data was queryable from local Loki

Decision:

- retire the Grafana Cloud Loki output from the active Alloy configuration
- keep local Loki on `ubuntu-infra` as the sole operational log destination
- remove Cloud credential placeholders and dual-write instructions from the active repository configuration
- treat reintroduction of an external log destination as a deliberate architectural change
- preserve historical Cloud dashboard exports only as references where useful; they are not part of the active log-delivery path

## 2026-09-26 — Environment-specific values stay outside Git

The repository is intended to remain safe to share and portable across future Home Lab network changes.

Decision:

- do not commit exact private IP addresses or live private subnets
- do not commit exact station latitude/longitude
- keep real PostgreSQL, Loki, station-location, and credential values in ignored local runtime configuration
- provide safe committed examples in `config/runtime.example.env`
- use symbolic host roles such as `BIRDNET_HOST` and `INFRA_HOST` in documentation
- keep runtime code configurable through environment variables rather than embedding the current Home Lab topology
- preserve stable data semantics such as station identity and timezone through explicit runtime configuration
- treat reintroduction of live addressing into Git as a repository-hygiene regression

This follows the same source-of-truth principle used by AI Nexus: Git records architecture and reproducible configuration shape, while the live environment supplies environment-specific values.

