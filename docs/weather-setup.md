# Weather collection setup

The BirdNET Pi collects both current weather observations and forecast snapshots from Open-Meteo and stores them in PostgreSQL.

## Files

- `weather/weather.py` — long-running current-weather collector
- `weather/forecast.py` — one-shot 48-hour forecast collector
- `weather/requirements.txt` — Python dependencies for manual/virtual-environment use
- `systemd/weather.service` — current-weather service
- `systemd/birdnet-forecast.service` and `.timer` — forecast schedule

## Runtime paths

The current-weather service runs the installed copy at:

```text
/home/birduser/weather/weather.py
```

Weather JSONL is written to:

```text
/var/log/weather/weather.log
```

The forecast service runs from the checked-out repository path configured in its systemd unit.

## Python dependencies

The committed systemd units use `/usr/bin/python3`, so the production Pi needs the required modules available to the system Python environment.

On Ubuntu/Debian, install:

```bash
sudo apt update
sudo apt install -y python3-requests python3-psycopg
```

`weather/requirements.txt` contains equivalent pip-installable dependencies for development or a virtual environment. A venv is optional unless the systemd units are deliberately changed to use it.

## Current-weather installation

From the repository checkout:

```bash
mkdir -p ~/weather
cp weather/weather.py ~/weather/weather.py

sudo mkdir -p /var/log/weather
sudo chown birduser:birduser /var/log/weather

sudo cp systemd/weather.service /etc/systemd/system/weather.service
sudo systemctl daemon-reload
sudo systemctl enable --now weather.service
```

The service loads PostgreSQL credentials from:

```text
/home/birduser/.config/birdnet-monitoring/db.env
```

Never commit that file or its password.

## Forecast installation

Install the committed forecast service and timer only after confirming that their repository path matches the Pi checkout location:

```bash
sudo cp systemd/birdnet-forecast.service /etc/systemd/system/
sudo cp systemd/birdnet-forecast.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now birdnet-forecast.timer
```

## Verify

```bash
systemctl status weather.service --no-pager
journalctl -u weather.service -n 50 --no-pager
systemctl status birdnet-forecast.timer --no-pager
journalctl -u birdnet-forecast.service -n 50 --no-pager
tail -n 5 /var/log/weather/weather.log
```

## PostgreSQL data

Current observations are stored in `weather_observations`.

Forecast snapshots are stored in `weather_forecasts`.

The weather pipeline distinguishes between the Open-Meteo observation/forecast timestamp and the local retrieval time. For current observations:

- `time` is the timestamp supplied by Open-Meteo.
- `logged_at` is when the BirdNET Pi retrieved and logged the response.
- PostgreSQL stores the Open-Meteo `time` as `weather_observations.observed_at`.
- JSONL retains both values.

The collectors request `America/Los_Angeles`, Fahrenheit, mph, and precipitation in **inches** explicitly.

### Historical precipitation warning

Earlier versions of both collectors did not set Open-Meteo's `precipitation_unit` parameter. Open-Meteo defaults precipitation to millimeters, while the PostgreSQL columns were already named `precipitation_in`.

Therefore, precipitation values collected before the 2026-09-14 unit fix may be millimeters stored in columns labeled as inches. Those historical precipitation fields should not be used quantitatively until they are audited and, if appropriate, converted. Do not bulk-convert them blindly without identifying the exact affected time range first.

No automatic historical rewrite is performed by this repository change.
