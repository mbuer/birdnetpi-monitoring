# BirdNET Station Health

This component persists compact hourly health evidence from local Loki into PostgreSQL.

It exists to distinguish:

```text
healthy station + zero detections
    -> observed biological zero

incomplete / unknown station evidence + zero detections
    -> do not automatically treat as biological absence
```

The BirdNET Pi itself is not modified.

## Source signal

The collector queries local Loki for recurring BirdNET analysis messages:

```text
[birdnet_analysis][INFO] Analyzing ...StreamData/...wav
```

The current BirdNET recording length is 15 seconds, so a fully covered hour normally produces about 240 analyzed segments.

The collector stores both raw evidence and a derived state in PostgreSQL table:

```text
station_health_hourly
```

Fields include:

- station ID
- UTC hour
- analyzed segment count
- expected segment count
- coverage percentage
- health state
- evidence source
- collection timestamp

## Health states

Default classification:

- `healthy`: coverage is at least 95%
- `incomplete`: Loki contains analysis evidence, but coverage is below 95%
- `unknown`: no matching Loki evidence exists for that hour

`unknown` does not mean the BirdNET station was down. It can also mean Loki/Alloy/network telemetry was unavailable.

The raw counts are preserved so the threshold can be changed later without losing evidence.

## Normal hourly run

`health/collect_station_health.sh` defaults to the local PostgreSQL and Loki services on `ubuntu-infra`.

The systemd service runs a six-hour lookback each hour. Re-reading recent completed hours is intentional: delayed Loki delivery can be corrected through PostgreSQL upsert.

## Manual validation

From the repository root:

```bash
bash health/collect_station_health.sh --lookback-hours 6
```

Inspect:

```bash
docker exec birdnet-postgres psql -U birdnet -d birdnet -c "
SELECT
    hour_utc,
    analysis_segments,
    expected_segments,
    ROUND(coverage_pct::numeric, 1) AS coverage_pct,
    health_state,
    evidence_source
FROM station_health_hourly
ORDER BY hour_utc DESC
LIMIT 12;
"
```

## Historical backfill

Backfill only periods for which Loki actually retains BirdNET analysis evidence.

Example for the first locally verified retained period:

```bash
bash health/collect_station_health.sh \
  --start 2026-09-13T11:00:00-07:00 \
  --end   2026-09-26T11:00:00-07:00
```

The end timestamp is exclusive.

Do not fabricate earlier health rows. Historical hours without retained evidence should remain absent/unknown until a deliberate data migration defines otherwise.

## ML boundary

The ML pipeline now consumes `station_health_hourly` through provenance-aware zero gating.

Current behavior:

- positive activity/presence remains usable even when health is incomplete or unknown
- during the explicit health-evidence era, zero activity/presence is only treated as a biological zero when health is `healthy`
- missing health rows in that era are treated as `unknown`
- affected zeroes propagate through lag/target construction so unreliable training rows are naturally excluded
- zero-valued outcomes are not scored until healthy station evidence exists
- pre-health historical rows remain usable under the legacy methodology

This is intentionally narrower than strict healthy-only filtering or coverage weighting. More aggressive weighting/filtering would be a separate ML-methodology change and should be justified with evidence.


## Deployment status

Verified on 2026-09-26:

- 312 consecutive historical hours backfilled from retained Loki evidence
- all 312 classified healthy
- observed coverage range: 239–240 analyzed segments out of 240 expected per hour
- manual systemd service execution succeeded
- automatic timer execution succeeded at 19:20 UTC
- six-hour lookback/upsert behavior confirmed in PostgreSQL
