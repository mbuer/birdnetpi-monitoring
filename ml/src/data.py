import os

import pandas as pd
import psycopg


QUERY = """
SELECT
    hour_local,
    raw_detections,
    species_count,
    capped_detections,
    activity_index,
    is_day,
    hour_of_day,
    hours_from_sunrise,
    temperature_f,
    humidity_pct,
    wind_mph,
    cloud_pct,
    precipitation_in
FROM bird_activity_hourly
ORDER BY hour_local;
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
