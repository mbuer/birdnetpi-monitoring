-- BirdNET Monitoring Database Schema
-- Long-term storage for bird detections, weather observations,
-- and weather forecasts.

CREATE TABLE IF NOT EXISTS detections (
    id BIGSERIAL PRIMARY KEY,
    detected_at TIMESTAMPTZ NOT NULL,
    station_id TEXT NOT NULL DEFAULT 'birdnet',
    species TEXT NOT NULL,
    species_latin TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    cutoff DOUBLE PRECISION,
    week INTEGER,
    sensitivity DOUBLE PRECISION,
    overlap DOUBLE PRECISION,
    file_name TEXT NOT NULL,
    source_rowid BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_detections_detected_at
    ON detections (detected_at);

CREATE INDEX IF NOT EXISTS idx_detections_species
    ON detections (species);

CREATE UNIQUE INDEX IF NOT EXISTS idx_detections_unique
    ON detections (
        station_id,
        detected_at,
        species_latin,
        file_name
    );

CREATE INDEX IF NOT EXISTS idx_detections_source_rowid
    ON detections (source_rowid);


CREATE TABLE IF NOT EXISTS weather_observations (
    id BIGSERIAL PRIMARY KEY,
    observed_at TIMESTAMPTZ NOT NULL,
    station_id TEXT NOT NULL DEFAULT 'birdnet',

    temperature_f DOUBLE PRECISION,
    dew_point_f DOUBLE PRECISION,
    relative_humidity_pct DOUBLE PRECISION,
    pressure_msl_hpa DOUBLE PRECISION,
    precipitation_in DOUBLE PRECISION,
    cloud_cover_pct DOUBLE PRECISION,
    wind_speed_mph DOUBLE PRECISION,
    wind_gusts_mph DOUBLE PRECISION,
    wind_direction_deg DOUBLE PRECISION,
    weather_code INTEGER,
    is_day BOOLEAN,

    sunrise TIMESTAMPTZ,
    sunset TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_weather_observations_observed_at
    ON weather_observations (observed_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_weather_observations_unique
    ON weather_observations (
        station_id,
        observed_at
    );


CREATE TABLE IF NOT EXISTS weather_forecasts (
    id BIGSERIAL PRIMARY KEY,
    forecast_created_at TIMESTAMPTZ NOT NULL,
    forecast_for TIMESTAMPTZ NOT NULL,
    station_id TEXT NOT NULL DEFAULT 'birdnet',

    temperature_f DOUBLE PRECISION,
    dew_point_f DOUBLE PRECISION,
    relative_humidity_pct DOUBLE PRECISION,
    precipitation_probability_pct DOUBLE PRECISION,
    precipitation_in DOUBLE PRECISION,
    cloud_cover_pct DOUBLE PRECISION,
    wind_speed_mph DOUBLE PRECISION,
    wind_gusts_mph DOUBLE PRECISION,
    wind_direction_deg DOUBLE PRECISION,
    pressure_msl_hpa DOUBLE PRECISION,
    uv_index DOUBLE PRECISION,
    weather_code INTEGER
);

CREATE INDEX IF NOT EXISTS idx_weather_forecasts_for
    ON weather_forecasts (forecast_for);

CREATE INDEX IF NOT EXISTS idx_weather_forecasts_created
    ON weather_forecasts (forecast_created_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_weather_forecasts_unique
    ON weather_forecasts (
        station_id,
        forecast_created_at,
        forecast_for
    );


-- Durable hourly evidence that the BirdNET analysis pipeline was operating.
-- Missing Loki telemetry is represented as health_state='unknown', not as
-- proof that the station was down.
CREATE TABLE IF NOT EXISTS station_health_hourly (
    station_id TEXT NOT NULL DEFAULT 'birdnet',
    hour_utc TIMESTAMPTZ NOT NULL,
    analysis_segments INTEGER,
    expected_segments INTEGER NOT NULL,
    coverage_pct DOUBLE PRECISION,
    health_state TEXT NOT NULL,
    evidence_source TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (station_id, hour_utc),

    CHECK (analysis_segments IS NULL OR analysis_segments >= 0),
    CHECK (expected_segments > 0),
    CHECK (coverage_pct IS NULL OR coverage_pct >= 0),
    CHECK (health_state IN ('healthy', 'incomplete', 'unknown'))
);

CREATE INDEX IF NOT EXISTS idx_station_health_hourly_hour
    ON station_health_hourly (hour_utc);
