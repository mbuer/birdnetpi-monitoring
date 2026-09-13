#!/usr/bin/env python3

import os

import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


API_URL = "https://api.open-meteo.com/v1/forecast"

LATITUDE = 34.18
LONGITUDE = -118.31

STATION_ID = "birdnet"
STATION_TIMEZONE_NAME = "America/Los_Angeles"
STATION_TIMEZONE = ZoneInfo(STATION_TIMEZONE_NAME)

LOGFILE = "/var/log/weather/weather.log"
INTERVAL_SECONDS = 900

DB_CONNECT = {
    "host": os.getenv("BIRDNET_DB_HOST", "localhost"),
    "dbname": os.getenv("BIRDNET_DB_NAME", "birdnet"),
    "user": os.getenv("BIRDNET_DB_USER", "birdnet"),
    "password": os.getenv("BIRDNET_DB_PASSWORD", ""),
    "connect_timeout": 5,
    "application_name": "birdnet-weather",
}

CURRENT_FIELDS = [
    "temperature_2m",
    "dew_point_2m",
    "relative_humidity_2m",
    "pressure_msl",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
    "weather_code",
    "is_day",
]

API_PARAMS = {
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "current": ",".join(CURRENT_FIELDS),
    "daily": "sunrise,sunset",
    "timezone": STATION_TIMEZONE_NAME,
    "temperature_unit": "fahrenheit",
    "wind_speed_unit": "mph",
}

REQUIRED_CURRENT_FIELDS = {
    "time",
    *CURRENT_FIELDS,
}


def station_now():
    return datetime.now(STATION_TIMEZONE)


def parse_station_time(value):
    return datetime.fromisoformat(value).replace(
        tzinfo=STATION_TIMEZONE
    )


def create_http_session():
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )

    adapter = HTTPAdapter(max_retries=retry)

    session = requests.Session()
    session.mount("https://", adapter)

    return session


HTTP = create_http_session()


def collect_weather():
    response = HTTP.get(
        API_URL,
        params=API_PARAMS,
        timeout=10,
    )
    response.raise_for_status()

    weather = response.json()

    if "current" not in weather:
        raise ValueError("Open-Meteo response is missing 'current'")

    if "daily" not in weather:
        raise ValueError("Open-Meteo response is missing 'daily'")

    current = dict(weather["current"])
    daily = weather["daily"]

    missing = REQUIRED_CURRENT_FIELDS - current.keys()
    if missing:
        raise ValueError(
            "Open-Meteo response missing current fields: "
            + ", ".join(sorted(missing))
        )

    sunrise_values = daily.get("sunrise")
    sunset_values = daily.get("sunset")

    if not sunrise_values or not sunset_values:
        raise ValueError(
            "Open-Meteo response is missing sunrise or sunset"
        )

    sunrise = sunrise_values[0]
    sunset = sunset_values[0]

    sunrise_dt = parse_station_time(sunrise)
    sunset_dt = parse_station_time(sunset)

    current["sunrise"] = sunrise
    current["sunset"] = sunset
    current["sunrise_unix"] = int(sunrise_dt.timestamp())
    current["sunset_unix"] = int(sunset_dt.timestamp())
    current["logged_at"] = station_now().isoformat()

    return current


def write_json_log(current):
    with open(LOGFILE, "a", encoding="utf-8") as logfile:
        logfile.write(json.dumps(current) + "\n")


def write_database(current):
    observed_at = parse_station_time(current["time"])
    sunrise = parse_station_time(current["sunrise"])
    sunset = parse_station_time(current["sunset"])

    with psycopg.connect(**DB_CONNECT) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO weather_observations (
                    observed_at,
                    station_id,
                    temperature_f,
                    dew_point_f,
                    relative_humidity_pct,
                    pressure_msl_hpa,
                    precipitation_in,
                    cloud_cover_pct,
                    wind_speed_mph,
                    wind_gusts_mph,
                    wind_direction_deg,
                    weather_code,
                    is_day,
                    sunrise,
                    sunset
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (station_id, observed_at)
                DO NOTHING
                RETURNING id
                """,
                (
                    observed_at,
                    STATION_ID,
                    current["temperature_2m"],
                    current["dew_point_2m"],
                    current["relative_humidity_2m"],
                    current["pressure_msl"],
                    current["precipitation"],
                    current["cloud_cover"],
                    current["wind_speed_10m"],
                    current["wind_gusts_10m"],
                    current["wind_direction_10m"],
                    current["weather_code"],
                    current["is_day"] == 1,
                    sunrise,
                    sunset,
                ),
            )

            return cur.fetchone() is not None


def main():
    while True:
        try:
            current = collect_weather()
        except Exception as exc:
            print(
                f"{station_now().isoformat()} WEATHER ERROR: {exc}",
                flush=True,
            )
            time.sleep(INTERVAL_SECONDS)
            continue

        database_ok = True
        new_observation = True
        log_written = False

        try:
            new_observation = write_database(current)
        except Exception as exc:
            database_ok = False
            print(
                f"{station_now().isoformat()} DATABASE ERROR: {exc}",
                flush=True,
            )

        if new_observation or not database_ok:
            try:
                write_json_log(current)
                log_written = True
            except Exception as exc:
                print(
                    f"{station_now().isoformat()} LOG ERROR: {exc}",
                    flush=True,
                )

        print(
            f"{station_now().isoformat()} Weather collected "
            f"(new={new_observation}, "
            f"log_written={log_written}, "
            f"database={database_ok})",
            flush=True,
        )

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
