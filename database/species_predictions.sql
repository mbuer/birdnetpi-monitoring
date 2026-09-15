CREATE TABLE IF NOT EXISTS bird_species_predictions (
    id BIGSERIAL PRIMARY KEY,

    prediction_created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    station_id TEXT NOT NULL,
    species TEXT NOT NULL,

    predicted_hour TIMESTAMP NOT NULL,
    model TEXT NOT NULL,

    probability DOUBLE PRECISION NOT NULL,
    threshold DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    predicted_present INTEGER NOT NULL,

    current_present INTEGER NOT NULL,
    training_rows INTEGER NOT NULL,

    actual_present INTEGER,
    correct BOOLEAN,
    scored_at TIMESTAMPTZ,

    UNIQUE (
        station_id,
        species,
        predicted_hour,
        model
    )
);
