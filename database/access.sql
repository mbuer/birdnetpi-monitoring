\set ON_ERROR_STOP on

SELECT format(
  'CREATE ROLE grafana_reader WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L',
  :'grafana_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_reader')
\gexec

SELECT format(
  'CREATE ROLE birdynator_reader WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L',
  :'birdynator_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'birdynator_reader')
\gexec

ALTER ROLE grafana_reader
  WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;

ALTER ROLE birdynator_reader
  WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;

REVOKE ALL PRIVILEGES ON SCHEMA public
  FROM grafana_reader, birdynator_reader;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
  FROM grafana_reader, birdynator_reader;

REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
  FROM grafana_reader, birdynator_reader;

GRANT USAGE ON SCHEMA public TO grafana_reader, birdynator_reader;

GRANT SELECT ON
  public.bird_activity_hourly,
  public.bird_activity_predictions,
  public.bird_species_hourly,
  public.bird_species_predictions,
  public.detections,
  public.station_health_hourly,
  public.weather_forecasts,
  public.weather_observations
TO grafana_reader;

GRANT SELECT ON
  public.bird_activity_hourly,
  public.bird_species_hourly,
  public.detections,
  public.weather_observations
TO birdynator_reader;
