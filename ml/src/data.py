import os

import pandas as pd
import psycopg


QUERY = """
SELECT
    a.hour_local,
    a.raw_detections,
    a.species_count,
    a.capped_detections,
    a.activity_index,
    a.is_day,
    a.hour_of_day,
    a.hours_from_sunrise,
    a.temperature_f,
    a.humidity_pct,
    a.wind_mph,
    a.cloud_pct,
    a.precipitation_in,
    h.health_state
FROM bird_activity_hourly AS a
LEFT JOIN station_health_hourly AS h
    ON h.station_id = 'birdnet'
   AND (h.hour_utc AT TIME ZONE 'America/Los_Angeles') = a.hour_local
ORDER BY a.hour_local;
"""


def load_hourly_data() -> pd.DataFrame:
    conn = psycopg.connect(
        host=os.environ.get("BIRDNET_DB_HOST", "127.0.0.1"),
        dbname=os.environ.get("BIRDNET_DB_NAME", "birdnet"),
        user=os.environ.get("BIRDNET_DB_USER", "birdnet"),
        password=os.environ["BIRDNET_DB_PASSWORD"],
    )

    try:
        with conn.cursor() as cur:
            cur.execute(QUERY)

            rows = cur.fetchall()
            columns = [description.name for description in cur.description]

        return pd.DataFrame(rows, columns=columns)

    finally:
        conn.close()


if __name__ == "__main__":
    df = load_hourly_data()

    print(df.head())
    print()
    print(df.tail())
    print()
    print(f"Rows: {len(df)}")
    print(f"First hour: {df['hour_local'].min()}")
    print(f"Last hour: {df['hour_local'].max()}")
