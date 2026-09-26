#!/usr/bin/env python3
"""Persist hourly BirdNET analysis coverage from Loki into PostgreSQL.

The collector deliberately stores raw coverage evidence rather than treating
absence of Loki data as proof that BirdNET was down. Missing telemetry is
recorded as health_state='unknown'.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import urlopen

import psycopg


DEFAULT_STATION_ID = "birdnet"
DEFAULT_LOKI_URL = "http://localhost:3100"
DEFAULT_EXPECTED_SEGMENTS = 240
DEFAULT_HEALTHY_MIN_PCT = 95.0
LOKI_QUERY = (
    'sum(count_over_time({unit="birdnet_analysis.service"} '
    '|= "Analyzing /home/birduser/BirdSongs/StreamData/" [1h]))'
)


def floor_hour(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamps must include a UTC offset")
    return floor_hour(parsed)


def completed_hour_window(lookback_hours: int) -> tuple[datetime, datetime]:
    end = floor_hour(datetime.now(timezone.utc))
    start = end - timedelta(hours=lookback_hours)
    return start, end


def iter_hours(start: datetime, end: datetime):
    current = start
    while current < end:
        yield current
        current += timedelta(hours=1)


def query_analysis_segments(loki_url: str, hour_start: datetime) -> int | None:
    # count_over_time([1h]) evaluated at the end of the target hour covers
    # exactly [hour_start, hour_start + 1h].
    query_time = hour_start + timedelta(hours=1)
    params = urlencode(
        {
            "query": LOKI_QUERY,
            "time": query_time.timestamp(),
        }
    )
    url = f"{loki_url.rstrip('/')}/loki/api/v1/query?{params}"

    with urlopen(url, timeout=15) as response:
        payload = json.load(response)

    if payload.get("status") != "success":
        raise RuntimeError(f"Loki query failed: {payload}")

    result = payload.get("data", {}).get("result", [])
    if not result:
        return None

    value = result[0].get("value")
    if not value or len(value) < 2:
        raise RuntimeError(f"Unexpected Loki result: {payload}")

    return int(float(value[1]))


def classify(
    analysis_segments: int | None,
    expected_segments: int,
    healthy_min_pct: float,
) -> tuple[float | None, str]:
    if analysis_segments is None:
        return None, "unknown"

    coverage_pct = 100.0 * analysis_segments / expected_segments
    if coverage_pct >= healthy_min_pct:
        return coverage_pct, "healthy"
    return coverage_pct, "incomplete"


def connect():
    return psycopg.connect(
        host=os.environ.get("BIRDNET_DB_HOST", "127.0.0.1"),
        dbname=os.environ.get("BIRDNET_DB_NAME", "birdnet"),
        user=os.environ.get("BIRDNET_DB_USER", "birdnet"),
        password=os.environ["BIRDNET_DB_PASSWORD"],
    )


def upsert_health(
    conn,
    *,
    station_id: str,
    hour_utc: datetime,
    analysis_segments: int | None,
    expected_segments: int,
    coverage_pct: float | None,
    health_state: str,
) -> None:
    conn.execute(
        """
        INSERT INTO station_health_hourly (
            station_id,
            hour_utc,
            analysis_segments,
            expected_segments,
            coverage_pct,
            health_state,
            evidence_source,
            collected_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (station_id, hour_utc)
        DO UPDATE SET
            analysis_segments = EXCLUDED.analysis_segments,
            expected_segments = EXCLUDED.expected_segments,
            coverage_pct = EXCLUDED.coverage_pct,
            health_state = EXCLUDED.health_state,
            evidence_source = EXCLUDED.evidence_source,
            collected_at = now()
        """,
        (
            station_id,
            hour_utc,
            analysis_segments,
            expected_segments,
            coverage_pct,
            health_state,
            "loki:birdnet_analysis.service",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--station-id", default=DEFAULT_STATION_ID)
    parser.add_argument("--loki-url", default=os.environ.get("BIRDNET_LOKI_URL", DEFAULT_LOKI_URL))
    parser.add_argument("--expected-segments", type=int, default=DEFAULT_EXPECTED_SEGMENTS)
    parser.add_argument("--healthy-min-pct", type=float, default=DEFAULT_HEALTHY_MIN_PCT)
    parser.add_argument("--lookback-hours", type=int, default=6)
    parser.add_argument("--start", type=parse_timestamp)
    parser.add_argument("--end", type=parse_timestamp)
    args = parser.parse_args()

    if args.expected_segments <= 0:
        parser.error("--expected-segments must be greater than zero")
    if not 0 < args.healthy_min_pct <= 100:
        parser.error("--healthy-min-pct must be in (0, 100]")
    if args.lookback_hours <= 0:
        parser.error("--lookback-hours must be greater than zero")
    if bool(args.start) != bool(args.end):
        parser.error("--start and --end must be supplied together")

    if args.start and args.end:
        start, end = args.start, args.end
        if start >= end:
            parser.error("--start must be earlier than --end")
    else:
        start, end = completed_hour_window(args.lookback_hours)

    rows = []
    with connect() as conn:
        for hour_utc in iter_hours(start, end):
            segments = query_analysis_segments(args.loki_url, hour_utc)
            coverage_pct, health_state = classify(
                segments,
                args.expected_segments,
                args.healthy_min_pct,
            )
            upsert_health(
                conn,
                station_id=args.station_id,
                hour_utc=hour_utc,
                analysis_segments=segments,
                expected_segments=args.expected_segments,
                coverage_pct=coverage_pct,
                health_state=health_state,
            )
            rows.append((hour_utc, segments, coverage_pct, health_state))
        conn.commit()

    for hour_utc, segments, coverage_pct, health_state in rows:
        coverage_text = "n/a" if coverage_pct is None else f"{coverage_pct:.1f}%"
        segments_text = "none" if segments is None else str(segments)
        print(
            f"{hour_utc.isoformat()} "
            f"segments={segments_text}/{args.expected_segments} "
            f"coverage={coverage_text} state={health_state}"
        )


if __name__ == "__main__":
    main()
