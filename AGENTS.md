# Agent guidance

## Before changing anything

Read [Executive summary](docs/executive-summary.md), [Architecture](docs/architecture.md), [Decisions](docs/decisions.md), then the relevant subsystem runbook. For cross-cutting changes, newer decisions supersede older ones; inspect code and runtime evidence before claiming deployment state.

Infrastructure is frozen by default. Reopen it only for a concrete data-protection need, security exposure, observed failure, recovery problem, or real feature requirement. Do not add hardening, verification frameworks, prerequisite auto-installation, timestamp/view redesign, or directory reorganization for completeness.

## Ownership and data invariants

- BirdNET owns audio analysis and native `~/BirdNET-Pi/scripts/birds.db`. Monitoring reads that database; do not alter it to simplify this project. BirdNET must keep detecting when downstream services fail.
- PostgreSQL on `ubuntu-infra` is the only active BirdNET PostgreSQL server and stores durable structured history. Loki stores operational logs. Alloy sends logs only to local Loki.
- This repository owns collectors, station-health provenance, ML, database objects, and BirdNET dashboards. Shared Grafana deployment belongs to `homelab-grafana`.
- AI Nexus / Birdynator is a downstream read-only consumer. Do not move collection, health, or ML ownership there, write back into BirdNET source data, or copy raw rows into agent memory. Agent analysis history belongs to AI Nexus. The richer ML/health interface remains deferred until its evidence contract is stable.
- Missing telemetry is `unknown`, never a fabricated outage or biological zero. Preserve the live health gate and its distinction between positive observations and health-supported zeroes.
- Protect historical source data and stored forecasts. Before destructive database work: create a dump, validate it with `pg_restore -l`, record row counts, make the change, then verify objects, counts, and ingestion. Never delete populated volumes to rerun initialization; `CREATE TABLE IF NOT EXISTS` is not a migration.
- Preserve reproducible narrow reader grants and HBA rules in `database/access.sql` and `deploy/ubuntu-infra/postgres/configure_access.sh`. Keep real client CIDRs and passwords in ignored configuration.
- Preserve the off-VM recovery chain: a fresh validated logical dump precedes the Proxmox backup to external storage. Do not mount broad writable backup storage into the guest. Archive listing is not a restore test.

## ML and time invariants

- Preserve temporal order, prevent target leakage, and compare with simple baselines; do not randomly shuffle time-series train/test data.
- Live timing is completed hour T -> target T+2. Issue forecasts before outcomes and keep retrospective results separate from forward validation.
- Keep aggregate and species work in the coordinated hourly cycle; check existing work before adding timers. Reference species live in `ml/live_species.txt`; challengers in `ml/species_challengers.json` use distinct model labels and must not overwrite reference forecasts.
- Do not change methodology under an existing model label or promote complexity for trivial metric gains. Preserve historical experiments/results unless deliberately superseded and documented.
- Local wall-clock timestamps use `America/Los_Angeles`, with known autumn DST ambiguity. Do not reinterpret them as UTC; Grafana prediction targets use `predicted_hour AT TIME ZONE 'America/Los_Angeles'`.
- Weather collectors request Fahrenheit, mph, and inches. Historical precipitation before the explicit inches fix has uncertain provenance; do not silently convert it.

## Changes and validation

Use canonical entry points on the appropriate host:

```bash
make repo-check       # public-repository hygiene
make pi-bootstrap     # deploy Pi integration
make pi-verify        # verify Pi integration
make infra-bootstrap  # deploy centralized services
make infra-verify     # verify centralized services
make backup           # create and validate logical PostgreSQL dump
make restore-test     # restore latest dump into a temporary database
make test             # ML regression suite
```

- Run `make repo-check` after configuration, networking, deployment-documentation, or example changes.
- Run `make test` (equivalent to `.venv/bin/python -m unittest discover -s ml/tests -v`) after timing, live-feature, health-gate, or scoring changes.
- Change checked-in systemd units and deployment scripts, not only installed copies. When deployment behavior changes, update bootstrap, verification, runbook, and decision log together.
- Validate Alloy before restart and verify fresh end-to-end Loki delivery afterward; a running service alone is insufficient.
- Check Grafana datasource UIDs/names, plugins, and query compatibility on import; valid JSON alone is insufficient.
- Prefer small reversible changes, explicit configuration, pinned tested container versions, persistent storage, and health checks. Distinguish repository checks from live-host verification.

## Public-repository hygiene

Never commit credentials, tokens, keys, runtime `.env`/`db.env` files, database dumps, exact live private addresses/subnets, station coordinates, WAN/DDNS details, topology-revealing hostnames, or sensitive screenshots. Use symbolic values such as `BIRDNET_HOST`, `INFRA_HOST`, `LOKI_URL`, and `POSTGRES_HOST`; examples contain placeholders only.

Use [config/runtime.example.env](config/runtime.example.env); keep real settings in ignored local files. Keep volumes, logs, Alloy state, synchronization checkpoints, caches, virtual environments, and generated experiment output outside Git.

## Documentation and provenance

Keep the root README an overview and navigation page; put operational detail in the existing runbooks. Update relevant documentation with behavior changes. Do not describe completed work as future work or planned work as deployed. Keep historical decision logs and experiment context.

- [Database contract](database/README.md)
- [ML methodology](docs/ml.md), [operations](ml/README.md), [curated experiments](docs/experiments/)
- [Station health](health/README.md)
- [Dashboards](grafana/README.md)
- [Pi deployment](deploy/birdnet-pi/README.md), [infra deployment](deploy/ubuntu-infra/README.md)
- [Backup and recovery](docs/backup-recovery.md)

Prefix commits written directly by ChatGPT through the GitHub connector with `Sol:`. User-created local commits keep normal messages; this prefix is informational, not a different trust level.
