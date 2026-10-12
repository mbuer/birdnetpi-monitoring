import argparse
import os
from pathlib import Path

import psycopg


STATION_ID = "birdnet"
ROOT = Path(__file__).resolve().parents[2]
LIVE_SPECIES_FILE = ROOT / "ml" / "live_species.txt"


def connect():
    return psycopg.connect(
        host=os.environ.get("BIRDNET_DB_HOST", "127.0.0.1"),
        dbname=os.environ.get("BIRDNET_DB_NAME", "birdnet"),
        user=os.environ.get("BIRDNET_DB_USER", "birdnet"),
        password=os.environ["BIRDNET_DB_PASSWORD"],
    )


def load_live_species():
    if not LIVE_SPECIES_FILE.exists():
        return set()

    species = set()

    for raw_line in LIVE_SPECIES_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        species.add(line)

    return species


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Rank detected species by the amount of hourly presence history "
            "available for live-model evaluation."
        )
    )
    parser.add_argument(
        "--min-positive-hours",
        type=int,
        default=10,
        help="Only show species detected in at least this many hourly buckets.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of species to display.",
    )

    args = parser.parse_args()
    live_species = load_live_species()

    query = """
    SELECT
        species,
        COUNT(*) AS total_hours,
        SUM(present)::integer AS positive_hours,
        ROUND(100.0 * AVG(present::numeric), 2) AS prevalence_pct,
        SUM(detection_count)::integer AS detections,
        MIN(hour_local) FILTER (WHERE present = 1) AS first_positive_hour,
        MAX(hour_local) FILTER (WHERE present = 1) AS last_positive_hour
    FROM bird_species_hourly
    WHERE station_id = %s
    GROUP BY species
    HAVING SUM(present) >= %s
    ORDER BY positive_hours DESC, detections DESC, species
    LIMIT %s;
    """

    conn = connect()

    try:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    STATION_ID,
                    args.min_positive_hours,
                    args.limit,
                ),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("No species matched the requested minimum.")
        return

    headers = (
        "LIVE",
        "SPECIES",
        "POS HRS",
        "TOTAL HRS",
        "PREV %",
        "DETECTIONS",
        "FIRST POSITIVE",
        "LAST POSITIVE",
    )

    print(
        f"{headers[0]:<5} "
        f"{headers[1]:<28} "
        f"{headers[2]:>7} "
        f"{headers[3]:>9} "
        f"{headers[4]:>7} "
        f"{headers[5]:>10} "
        f"{headers[6]:<16} "
        f"{headers[7]:<16}"
    )
    print("-" * 116)

    for (
        species,
        total_hours,
        positive_hours,
        prevalence_pct,
        detections,
        first_positive_hour,
        last_positive_hour,
    ) in rows:
        live_marker = "yes" if species in live_species else ""

        print(
            f"{live_marker:<5} "
            f"{species:<28.28} "
            f"{positive_hours:>7} "
            f"{total_hours:>9} "
            f"{float(prevalence_pct):>7.2f} "
            f"{detections:>10} "
            f"{first_positive_hour:%Y-%m-%d %H:%M} "
            f"{last_positive_hour:%Y-%m-%d %H:%M}"
        )


if __name__ == "__main__":
    main()
