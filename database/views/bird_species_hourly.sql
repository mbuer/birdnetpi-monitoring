CREATE OR REPLACE VIEW bird_species_hourly AS

WITH detection_hours AS (
    SELECT
        station_id,
        MIN(
            date_trunc(
                'hour',
                detected_at AT TIME ZONE 'America/Los_Angeles'
            )
        ) AS first_hour,
        MAX(
            date_trunc(
                'hour',
                detected_at AT TIME ZONE 'America/Los_Angeles'
            )
        ) AS last_hour
    FROM detections
    GROUP BY station_id
),

hourly_timeline AS (
    SELECT
        d.station_id,
        generate_series(
            d.first_hour,
            d.last_hour,
            interval '1 hour'
        ) AS hour_local
    FROM detection_hours d
),

species_list AS (
    SELECT
        station_id,
        species,
        MIN(species_latin) AS species_latin
    FROM detections
    GROUP BY
        station_id,
        species
),

species_detections AS (
    SELECT
        station_id,
        date_trunc(
            'hour',
            detected_at AT TIME ZONE 'America/Los_Angeles'
        ) AS hour_local,
        species,
        COUNT(*) AS detection_count,
        AVG(confidence) AS avg_confidence,
        MAX(confidence) AS max_confidence
    FROM detections
    GROUP BY
        station_id,
        hour_local,
        species
)

SELECT
    t.station_id,
    t.hour_local,
    s.species,
    s.species_latin,

    COALESCE(d.detection_count, 0)::integer
        AS detection_count,

    CASE
        WHEN COALESCE(d.detection_count, 0) > 0 THEN 1
        ELSE 0
    END AS present,

    d.avg_confidence,
    d.max_confidence

FROM hourly_timeline t

JOIN species_list s
    ON s.station_id = t.station_id

LEFT JOIN species_detections d
    ON d.station_id = t.station_id
   AND d.hour_local = t.hour_local
   AND d.species = s.species;
