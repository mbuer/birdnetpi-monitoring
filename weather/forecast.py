#!/usr/bin/env python3

import os

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

FORECAST_HOURS = 48

DB_CONNECT = {
    "host": os.getenv("BIRDNET_DB_HOST", "localhost"),
    "dbname": os.getenv("BIRDNET_DB_NAME", "birdnet"),
    "user": os.getenv("BIRDNET_DB_USER", "birdnet"),
    "password": os.getenv("BIRDNET_DB_PASSWORD", ""),
    "connect_timeout": 5,
    "application_name": "birdnet-forecast",
}

HOURLY_FIELDS = [
    "temperature_2m",
    "dew_point_2m",
    "relative_humidity_2m",
    "precipitation_probability",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
    "pressure_msl",
    "uv_index",
    "weather_code",
]

API_PARAMS = {
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "hourly": ",".join(HOURLY_FIELDS),
    "forecast_hours": FORECAST_HOURS,
    "timezone": STATION_TIMEZONE_NAME,
    "temperature_unit": "fahrenheit",
    "wind_speed_unit": "mph",
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


def collect_forecast():
    response = HTTP.get(
        API_URL,
        params=API_PARAMS,
        timeout=15,
    )
    response.raise_for_status()

    data = response.json()

    if "hourly" not in data:
        raise ValueError(
            "Open-Meteo response is missing 'hourly'"
        )

    hourly = data["hourly"]

    required_fields = {"time", *HOURLY_FIELDS}
    missing = required_fields - hourly.keys()

    if missing:
        raise ValueError(
            "Open-Meteo response missing hourly fields: "
            + ", ".join(sorted(missing))
        )

    row_count = len(hourly["time"])

    for field in required_fields:
        if len(hourly[field]) != row_count:
            raise ValueError(
                f"Open-Meteo hourly field '{field}' "
                f"has unexpected length"
            )

    return hourly


def write_database(hourly):
    # One forecast snapshot per station per hour.
    # Rounding to the hour makes retries during the same hour idempotent.
    forecast_created_at = station_now().replace(
        minute=0,
        second=0,
        microsecond=0,
    )

    inserted = 0

    with psycopg.connect(**DB_CONNECT) as conn:
        with conn.cursor() as cur:
            for index, timestamp in enumerate(hourly["time"]):
                forecast_for = parse_station_time(timestamp)

                cur.execute(
                    """
                    INSERT INTO weather_forecasts (
                        forecast_created_at,
                        forecast_for,
                        station_id,
                        temperature_f,
                        dew_point_f,
                        relative_humidity_pct,
                        precipitation_probability_pct,
                        precipitation_in,
                        cloud_cover_pct,
                        wind_speed_mph,
                        wind_gusts_mph,
                        wind_direction_deg,
                        pressure_msl_hpa,
                        uv_index,
                        weather_code
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (
                        station_id,
                        forecast_created_at,
                        forecast_for
                    )
                    DO NOTHING
                    RETURNING id
                    """,
                    (
                        forecast_created_at,
                        forecast_for,
                        STATION_ID,
                        hourly["temperature_2m"][index],
                        hourly["dew_point_2m"][index],
                        hourly["relative_humidity_2m"][index],
                        hourly["precipitation_probability"][index],
                        hourly["precipitation"][index],
                        hourly["cloud_cover"][index],
                        hourly["wind_speed_10m"][index],
                        hourly["wind_gusts_10m"][index],
                        hourly["wind_direction_10m"][index],
                        hourly["pressure_msl"][index],
                        hourly["uv_index"][index],
                        hourly["weather_code"][index],
                    ),
                )

                if cur.fetchone() is not None:
                    inserted += 1

    return forecast_created_at, inserted


def main():
    try:
        hourly = collect_forecast()
        forecast_created_at, inserted = write_database(hourly)

        print(
            f"{station_now().isoformat()} Forecast collected "
            f"(snapshot={forecast_created_at.isoformat()}, "
            f"hours={len(hourly['time'])}, "
            f"inserted={inserted})",
            flush=True,
        )

    except Exception as exc:
        print(
            f"{station_now().isoformat()} FORECAST ERROR: {exc}",
            flush=True,
        )
        raise


if __name__ == "__main__":
    main()
