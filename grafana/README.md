# BirdNET Grafana Dashboards

This directory owns the BirdNET dashboard exports. Grafana deployment, plugin installation, and shared datasource provisioning belong to the separate `homelab-grafana` repository.

Keep the operational and analytical views complementary:

```text
Loki + Infinity/Open-Meteo -> Bird Home - Burbank
PostgreSQL                -> Bird Home — Prediction Lab
```

## Dashboard Files

| File | Purpose | Export format |
|---|---|---|
| `Bird Home - Burbank Cloud.json` | Original Cloud reference | `dashboard.grafana.app/v2` resource |
| `Bird Home - Burbank Local.json` | Adapted local operational dashboard | `dashboard.grafana.app/v2` resource |
| `bird-home-prediction-lab.json` | Experimental activity forecasts and scores | Classic dashboard JSON |

The two operational exports retain the same internal title, resource name, UID, and Cloud metadata. Their filenames do not create separate dashboard identities. Check the import preview and destination identity before loading both into one instance.

Use an import mechanism compatible with each export format. JSON validity alone does not prove Grafana import compatibility.

## Operational Dashboard

The Local export references `Loki` and `Infinity`; the Cloud export references `grafanacloud-logs` and `bfu1g66742jnkd`. Check datasource references in variables as well as panels.

Infinity supplies direct Open-Meteo weather requests. Relative `/forecast?...` URLs need the base URL `https://api.open-meteo.com/v1`. Preserve the required Infinity plugin and datasource configuration through the Grafana deployment repository.

Loki uses `http://192.168.1.137:3100` in this Home Lab. The reported live Pi configuration dual-writes logs to local and Cloud Loki, while the committed Alloy sample is still Cloud-only. Do not replace the installed config with that sample without reconciling it.

Useful Explore checks:

```logql
{unit="birdnet_analysis.service"}
```

```logql
{job="weather"} | json
```

Operational dashboard confidence/species filters do not define the SQL activity index. Raw log events and accepted SQLite detections are different datasets, so their counts need not match.

## Prediction Lab Prerequisites

- PostgreSQL database `birdnet`.
- View `public.bird_activity_hourly`.
- Table `public.bird_activity_predictions`.
- SELECT permission on both for `grafana_reader`.
- PostgreSQL datasource `BirdNET PostgreSQL`, currently UID `afy5j1yt18b9cb`.

See [database setup](../database/README.md#initializing-a-new-database) for application order and grants. The prediction-table SQL does not include its grant.

The datasource UID is hard-coded in panels and targets. Map every occurrence when moving to another Grafana instance. Queries already use raw SQL / Code mode; verify they remain present after changing a datasource.

From the repository root:

```bash
python3 -m json.tool grafana/bird-home-prediction-lab.json > /dev/null
```

Import the full JSON through Grafana and verify the datasource, queries, and recent prediction records. This checks configuration; it does not validate the model's temporal correctness.

## Reading the Dashboard

Blue represents ML, green observed activity, and orange persistence.

| Panel/group | Current query scope |
|---|---|
| Next Hour Forecast | Latest stored v2 target; still inspect its timestamp for freshness |
| Latest Completed Activity | Latest hour ended at least ten minutes ago |
| Live MAE, Model Edge, Scored Forecasts | All scored v2 rows across all time |
| Forecast vs Reality, Prediction Error, Daily MAE | Selected time range |
| Model Win Rate, ML MAE, Persistence MAE, Best Forecast | All scored v2 rows |
| Recent Predictions | Latest 50 v2 rows, regardless of selected range |

“Daily MAE” groups by local calendar day; it is not a sliding rolling average. Live MAE and ML MAE currently duplicate the same calculation.

Model Edge is percentage MAE improvement over persistence. It is null when no scored rows exist or persistence MAE is zero. Win Rate counts strict ML wins; ties stay in the denominator but are not wins.

An empty accuracy metric can be expected before scoring. Zero activity is a valid stored value, but may also conceal missing detection ingestion. A stale last forecast is still shown as “Next Hour Forecast” today.

## Time Handling

SQL target hours represent Los Angeles wall time without timezone. Time-series queries use:

```sql
predicted_hour AT TIME ZONE 'America/Los_Angeles'
```

The dashboard timezone is `browser`, so charts display in the viewer's timezone. Recent Predictions formats the stored local timestamp as text and therefore always shows Los Angeles wall time. Label that column explicitly if viewers use other timezones.

The conversion fixes ordinary display offsets. It does not recover two distinct autumn DST hours after the database has merged them.

## Current Validation Limitation

This README describes the accompanying v2 dashboard JSON and completed-hour code fix. Import the full JSON after installation. All prediction queries select `random_forest_v2_completed`; legacy scores remain stored but excluded. V2 waits until the target ends plus ten minutes to score. Treat accuracy as experimental: late ingestion and missing station-health evidence remain [limitations](../ml/README.md#known-validation-limitations).

Recommended follow-up changes are selectable model comparisons, freshness/issue-time display, consistent or explicitly labeled metric scopes, and a timezone label for the table. The current full replacement filters to v2 deliberately.
