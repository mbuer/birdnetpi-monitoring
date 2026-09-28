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

## 2026-09-26 — Git plus local configuration is the rebuild contract

The repository had enough individual components to explain the deployment, but a new session still had to reconstruct installation order and host integration manually.

Decision:

- provide explicit BirdNET-Pi and ubuntu-infra bootstrap workflows
- provide matching verification workflows rather than treating service startup as proof of end-to-end health
- use `Makefile` targets as stable human and agent entry points
- derive checkout paths and service users during bootstrap where practical instead of requiring one developer-specific home path
- keep live addresses, coordinates, and credentials outside Git
- make database bootstrap apply the complete analytical object set rather than only the base schema
- keep Grafana provisioning in the separate `homelab-grafana` repository
- add a repository hygiene check to prevent private network addressing and retired Cloud configuration from silently returning

The target recovery model is:

```text
Git
+ local runtime configuration / secrets
+ PostgreSQL backup when restoring historical state
= reproducible BirdNET monitoring environment
```

BirdNET itself remains independently installed and is not absorbed into this repository.

## 2026-09-26 — Rebuild verification passed on both live hosts

The new repository rebuild contract was exercised against the actual BirdNET Pi and `ubuntu-infra` runtime.

Verified on the BirdNET Pi:

- repository hygiene check passed
- BirdNET SQLite was readable
- PostgreSQL was reachable
- Loki was ready
- weather and Alloy services were active
- detection-sync and forecast timers were active and enabled
- installed Alloy configuration matched Git
- recent BirdNET and weather records were queryable from local Loki

Verified on `ubuntu-infra`:

- PostgreSQL and Loki containers were running and ready
- all core PostgreSQL tables and analytical views were present
- station-health, ML-prediction, and PostgreSQL-backup timers were active and enabled
- the ML virtual environment existed
- ML regression tests passed

The validation also exposed two bootstrap-quality issues:

- a fresh infra host may not have `make`, even though the documented operator entry points use it
- verification should fail immediately when core prerequisites are unavailable instead of cascading into misleading service failures

Decision:

- install `make` as part of the infra bootstrap
- explicitly require Docker, Docker Compose v2, `curl`, and `systemctl` before infra verification continues
- treat the BirdNET Pi and infra verification scripts as the canonical post-deployment acceptance tests

## 2026-09-26 — Keep AI Nexus downstream of the BirdNET data plane

The wider Home Lab now includes AI Nexus / Birdynator as a consumer of BirdNET evidence.

Decision:

- BirdNET and `ubuntu-infra` remain authoritative for detections, weather, station-health evidence, analytical views, and ML prediction/scoring
- AI Nexus remains a separate security and execution boundary
- Birdynator may consume BirdNET evidence through a constrained read-only datasource boundary
- Birdynator does not collect station health and must not duplicate the upstream health collector
- Birdynator does not write into BirdNET source data
- Birdynator analysis runs belong to AI Nexus rather than the BirdNET historical datastore
- raw BirdNET rows should not be copied into persistent agent memory merely to simplify analysis
- a richer ML/health evidence interface is deferred until its schema, provenance, and usefulness are stable
- future downstream evidence should preserve states such as `healthy`, `incomplete`, and `unknown` where they materially affect interpretation

This keeps collection and provenance close to the source, prevents the agent platform from becoming an accidental second data plane, and allows AI workflows to evolve without destabilizing BirdNET monitoring.

## 2026-09-26 — Freeze infrastructure after three remaining essentials

The monitoring stack is now reliable enough that continued hardening risks adding more complexity than practical value.

Decision:

- keep infrastructure work limited to three remaining essentials: off-host PostgreSQL backup plus one restore drill, reproducible narrow PostgreSQL access policy, and cleanup of clearly obsolete migration artifacts
- after those are complete, treat the BirdNET infrastructure as frozen by default
- do not add hardening, automation, abstraction, or verification depth merely because it is technically possible
- reopen infrastructure work only for a concrete data-protection need, identified security exposure, observed operational failure, recovery problem, or real feature requirement
- keep Docker/Alloy auto-installation, broad verification expansion, timestamp redesign, aggregate-view redesign, and additional Loki/network hardening out of active scope unless a concrete need emerges
- prioritize Birdynator analysis, useful reporting, anomaly detection, and accumulation/evaluation of genuine forward ML evidence after the infrastructure essentials are finished

This deliberately trades theoretical completeness for a smaller, easier-to-understand, easier-to-operate Home Lab system.


## 2026-09-26 — Retire the Pi-local PostgreSQL instance

The BirdNET Pi still had an older local PostgreSQL 17 instance and daily backup timer from the pre-centralization architecture.

Runtime inspection confirmed:

- active collectors target PostgreSQL on `ubuntu-infra`
- the Pi-local database had no meaningful client connections
- the local schema only contained the older detection/weather tables
- the active Pi verification suite passed after local PostgreSQL was stopped and removed

Decision:

- remove the Pi-local PostgreSQL cluster and packages
- remove the legacy `birdnet-db-backup` timer/service and local SQL dump directory
- remove the obsolete Pi-local backup script and units from Git
- remove the stale Grafana Cloud environment file and temporary weather rollback copy
- keep centralized PostgreSQL on `ubuntu-infra` as the only active BirdNET PostgreSQL service

This reduces duplicate state and removes a misleading recovery path without changing the active BirdNET pipeline.


## 2026-09-27 — Reproduce narrow PostgreSQL access policy from local configuration

The live PostgreSQL deployment already used source-restricted SCRAM rules, but the exact roles, grants, and HBA policy were partly runtime state rather than a complete rebuild contract.

Inspection established the active boundaries:

- BirdNET Pi uses the `birdnet` database and `birdnet` role from one exact client address
- Grafana uses `grafana_reader` from its Docker client network
- local ML/health jobs use `birdnet` through the PostgreSQL Docker bridge gateway
- Birdynator uses `birdynator_reader` from one exact AI Nexus client address
- `grafana_reader` is read-only on the eight existing Grafana/source objects
- `birdynator_reader` is read-only on detections, weather observations, and the two analytical views
- the `birdnet` account is the PostgreSQL bootstrap superuser and cannot be demoted in place

Decision:

- keep `birdnet` as the bootstrap/application account for recovery simplicity
- narrow its remote HBA access by database, role, and exact source instead of introducing another runtime writer role
- define `grafana_reader` and `birdynator_reader` plus their exact grants in `database/access.sql`
- render `pg_hba.conf` from environment-specific CIDRs stored only in the ignored PostgreSQL `.env`
- derive the PostgreSQL Docker gateway automatically for local ML/health access
- preserve existing reader passwords during an access refresh; require reader passwords only when creating those roles on a fresh cluster
- have `infra-bootstrap` apply the access policy and `infra-verify` check the roles, grants, HBA syntax, expected source rules, and absence of broad remote access

This keeps recovery simple while making the database-level access boundary reproducible and explicit without committing live addresses or secrets.


## 2026-09-27 — Freeze BirdNET infrastructure after final acceptance

The final planned infrastructure homework item, reproducible narrow PostgreSQL access control, was applied and tested against the live system.

Verified after the generated HBA policy replaced the earlier manual runtime edit:

- `make repo-check` passed
- `make infra-verify` passed, including reader-role constraints, Grafana grants, Birdynator grants, schema usage, HBA parsing, expected source rules, and absence of a broad remote HBA rule
- `make pi-verify` passed from the BirdNET Pi
- Grafana's real PostgreSQL datasource health check returned `Database Connection OK`
- Birdynator authenticated as `birdynator_reader`
- Birdynator could SELECT from `detections` and `bird_activity_hourly`
- Birdynator could not SELECT from `bird_activity_predictions`
- Birdynator could not INSERT into `detections`

The other two infrastructure essentials were already complete: off-host recovery with a tested logical restore, and removal of obsolete Cloud-era/Pi-local migration artifacts.

Decision:

- consider the three planned infrastructure essentials complete
- treat BirdNET monitoring infrastructure as frozen by default
- reopen infrastructure work only for a concrete data-protection need, identified security exposure, observed operational failure, recovery problem, or real feature requirement
- prioritize Birdynator analysis, useful reporting, anomaly detection, and evidence-driven ML evaluation

This closes the infrastructure-hardening phase deliberately rather than continuing to add complexity for completeness.
