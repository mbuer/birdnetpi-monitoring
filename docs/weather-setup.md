# Weather collection setup

The BirdNET Pi collects both current weather observations and forecast snapshots from Open-Meteo and stores them in PostgreSQL.

## Files

- `weather/weather.py` — long-running current-weather collector
- `weather/forecast.py` — one-shot 48-hour forecast collector
- `weather/requirements.txt` — Python dependencies for manual/virtual-environment use
- `systemd/weather.service` — current-weather service
- `systemd/birdnet-forecast.service` and `.timer` — forecast schedule

## Runtime paths

Weather JSONL is written to:

```text
/var/log/weather/weather.log
```

The bootstrap derives the runtime user, home directory, and repository checkout path rather than requiring one exact username or home path. Installed systemd units are rendered from the committed templates.

## Runtime configuration

Create the local configuration before installing or updating the Pi-side services:

```bash
sudo install -d -m 0755 /etc/birdnet-monitoring
sudo install -m 0600 config/runtime.example.env /etc/birdnet-monitoring/runtime.env
sudoedit /etc/birdnet-monitoring/runtime.env
```

Replace all example values with the real local environment. In particular, do not run the weather collectors with the example latitude/longitude.

The same runtime file is shared by detection sync, current-weather collection, and forecast collection.

## Python dependencies

The committed systemd units use `/usr/bin/python3`, so the production Pi needs the required modules available to the system Python environment.

On Ubuntu/Debian, install:

```bash
sudo apt update
sudo apt install -y python3-requests python3-psycopg
```

`weather/requirements.txt` contains equivalent pip-installable dependencies for development or a virtual environment. A venv is optional unless the systemd units are deliberately changed to use it.

## Installation

The canonical installation path is the BirdNET Pi bootstrap:

```bash
make pi-bootstrap
```

It installs the weather collector, forecast service/timer, dependencies, log directory, and rendered systemd units together so the deployed runtime matches Git.

The Pi-side collectors load environment-specific configuration from:

```text
/etc/birdnet-monitoring/runtime.env
```

Start from `config/runtime.example.env`, then set the real station coordinates, timezone, PostgreSQL host, and credentials locally. The runtime file must never be committed.

## Verify

Use the acceptance test first:

```bash
make pi-verify
```

For targeted troubleshooting:

```bash
systemctl status weather.service --no-pager
journalctl -u weather.service -n 50 --no-pager
systemctl status birdnet-forecast.timer --no-pager
journalctl -u birdnet-forecast.service -n 50 --no-pager
tail -n 5 /var/log/weather/weather.log
```

The Pi weather/forecast path was runtime-verified against the committed deployment workflow on 2026-09-26.

## PostgreSQL data

Current observations are stored in `weather_observations`.

Forecast snapshots are stored in `weather_forecasts`.

The weather pipeline distinguishes between the Open-Meteo observation/forecast timestamp and the local retrieval time. For current observations:

- `time` is the timestamp supplied by Open-Meteo.
- `logged_at` is when the BirdNET Pi retrieved and logged the response.
- PostgreSQL stores the Open-Meteo `time` as `weather_observations.observed_at`.
- JSONL retains both values.

The collectors request the timezone configured through `BIRDNET_TIMEZONE`, Fahrenheit, mph, and precipitation in **inches** explicitly. Station latitude/longitude and timezone are runtime configuration rather than repository constants.

### Historical precipitation warning

Earlier versions of both collectors did not set Open-Meteo's `precipitation_unit` parameter. Open-Meteo defaults precipitation to millimeters, while the PostgreSQL columns were already named `precipitation_in`.

Therefore, precipitation values collected before the 2026-09-14 unit fix may be millimeters stored in columns labeled as inches. Those historical precipitation fields should not be used quantitatively until they are audited and, if appropriate, converted. Do not bulk-convert them blindly without identifying the exact affected time range first.

No automatic historical rewrite is performed by this repository change.
