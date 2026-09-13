#!/usr/bin/env python3

import os

import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg


SQLITE_DB = Path.home() / "BirdNET-Pi" / "scripts" / "birds.db"

STATE_DIR = Path.home() / ".local" / "state" / "birdnet-db-sync"
STATE_FILE = STATE_DIR / "last_rowid"

DB_CONNECT = {
    "host": os.getenv("BIRDNET_DB_HOST", "localhost"),
    "dbname": os.getenv("BIRDNET_DB_NAME", "birdnet"),
    "user": os.getenv("BIRDNET_DB_USER", "birdnet"),
    "password": os.getenv("BIRDNET_DB_PASSWORD", ""),
    "connect_timeout": 5,
    "application_name": "birdnet-db-sync",
}

STATION_ID = "birdnet"
STATION_TIMEZONE = ZoneInfo("America/Los_Angeles")


SELECT_MAX_ROWID_SQL = """
SELECT COALESCE(MAX(rowid), 0)
FROM detections
"""

SELECT_SQL = """
SELECT
    rowid,
    Date,
    Time,
    Sci_Name,
    Com_Name,
    Confidence,
    Lat,
    Lon,
    Cutoff,
    Week,
    Sens,
    Overlap,
    File_Name
FROM detections
WHERE rowid > ?
ORDER BY rowid
"""

INSERT_SQL = """
INSERT INTO detections (
    detected_at,
    station_id,
    species,
    species_latin,
    confidence,
    latitude,
    longitude,
    cutoff,
    week,
    sensitivity,
    overlap,
    file_name,
    source_rowid
)
VALUES (
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s
)
ON CONFLICT (
    station_id,
    detected_at,
    species_latin,
    file_name
)
DO NOTHING
"""


def read_last_rowid():
    try:
        value = int(STATE_FILE.read_text().strip())
    except FileNotFoundError:
        return 0
    except (ValueError, OSError) as exc:
        print(
            f"Warning: could not read state file {STATE_FILE}: {exc}. "
            "Starting from rowid 0."
        )
        return 0

    if value < 0:
        print(
            f"Warning: invalid last_rowid={value}. "
            "Starting from rowid 0."
        )
        return 0

    return value


def write_last_rowid(rowid):
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    temporary_file = STATE_FILE.with_suffix(".tmp")
    temporary_file.write_text(f"{rowid}\n")
    temporary_file.replace(STATE_FILE)


def main():
    if not SQLITE_DB.is_file():
        raise FileNotFoundError(
            f"BirdNET SQLite database not found: {SQLITE_DB}"
        )

    last_rowid = read_last_rowid()

    sqlite_conn = sqlite3.connect(
        f"file:{SQLITE_DB}?mode=ro",
        uri=True,
    )

    inserted = 0
    processed = 0
    newest_rowid = last_rowid

    try:
        source_max_rowid = sqlite_conn.execute(
            SELECT_MAX_ROWID_SQL
        ).fetchone()[0]

        if source_max_rowid < last_rowid:
            print(
                "BirdNET SQLite rowid appears to have reset "
                f"(source={source_max_rowid}, state={last_rowid}). "
                "Restarting synchronization from rowid 0."
            )
            last_rowid = 0
            newest_rowid = 0

        rows = sqlite_conn.execute(SELECT_SQL, (last_rowid,))

        with psycopg.connect(**DB_CONNECT) as pg_conn:
            with pg_conn.cursor() as cur:
                for row in rows:
                    (
                        rowid,
                        date,
                        time,
                        sci_name,
                        com_name,
                        confidence,
                        lat,
                        lon,
                        cutoff,
                        week,
                        sens,
                        overlap,
                        file_name,
                    ) = row

                    detected_at = datetime.fromisoformat(
                        f"{date}T{time}"
                    ).replace(tzinfo=STATION_TIMEZONE)

                    cur.execute(
                        INSERT_SQL,
                        (
                            detected_at,
                            STATION_ID,
                            com_name,
                            sci_name,
                            confidence,
                            lat,
                            lon,
                            cutoff,
                            week,
                            sens,
                            overlap,
                            file_name,
                            rowid,
                        ),
                    )

                    inserted += cur.rowcount
                    processed += 1
                    newest_rowid = rowid

        if newest_rowid > last_rowid:
            write_last_rowid(newest_rowid)

    finally:
        sqlite_conn.close()

    print(
        f"Processed {processed} detections, "
        f"imported {inserted} new detections, "
        f"last_rowid={newest_rowid}"
    )


if __name__ == "__main__":
    main()
