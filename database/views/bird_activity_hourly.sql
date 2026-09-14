CREATE OR REPLACE VIEW public.bird_activity_hourly AS
WITH hourly_species AS (
    SELECT
        date_trunc(
            'hour',
            detections.detected_at AT TIME ZONE 'America/Los_Angeles'
        ) AS hour_local,
        detections.species,
        count(*) AS detections
    FROM public.detections
    GROUP BY
        date_trunc(
            'hour',
            detections.detected_at AT TIME ZONE 'America/Los_Angeles'
        ),
        detections.species
),
bird_hourly AS (
    SELECT
        hourly_species.hour_local,
        sum(hourly_species.detections) AS raw_detections,
        count(*) AS species_count,
        sum(LEAST(hourly_species.detections, 10::bigint)) AS capped_detections,
        count(*)::numeric
            + sum(LEAST(hourly_species.detections, 10::bigint)) AS activity_index
    FROM hourly_species
    GROUP BY hourly_species.hour_local
),
weather_hourly AS (
    SELECT
        date_trunc(
            'hour',
            weather_observations.observed_at AT TIME ZONE 'America/Los_Angeles'
        ) AS hour_local,
        bool_or(weather_observations.is_day) AS is_day,
        avg(weather_observations.temperature_f) AS temperature_f,
        avg(weather_observations.relative_humidity_pct) AS humidity_pct,
        avg(weather_observations.wind_speed_mph) AS wind_mph,
        avg(weather_observations.cloud_cover_pct) AS cloud_pct,
        avg(weather_observations.precipitation_in) AS precipitation_in,
        min(
            weather_observations.sunrise
            AT TIME ZONE 'America/Los_Angeles'
        ) AS sunrise_local
    FROM public.weather_observations
    GROUP BY
        date_trunc(
            'hour',
            weather_observations.observed_at AT TIME ZONE 'America/Los_Angeles'
        )
)
SELECT
    w.hour_local,
    COALESCE(b.raw_detections, 0::numeric) AS raw_detections,
    COALESCE(b.species_count, 0::bigint) AS species_count,
    COALESCE(b.capped_detections, 0::numeric) AS capped_detections,
    COALESCE(b.activity_index, 0::numeric) AS activity_index,
    w.is_day,
    EXTRACT(hour FROM w.hour_local)::integer AS hour_of_day,
    EXTRACT(epoch FROM (w.hour_local - w.sunrise_local)) / 3600.0
        AS hours_from_sunrise,
    w.temperature_f,
    w.humidity_pct,
    w.wind_mph,
    w.cloud_pct,
    w.precipitation_in
FROM weather_hourly w
LEFT JOIN bird_hourly b USING (hour_local);

GRANT SELECT ON public.bird_activity_hourly TO grafana_reader;

