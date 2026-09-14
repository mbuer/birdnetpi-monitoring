CREATE TABLE IF NOT EXISTS bird_activity_predictions (
    id BIGSERIAL PRIMARY KEY,
    prediction_created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    predicted_hour TIMESTAMP NOT NULL,
    model TEXT NOT NULL,
    predicted_activity DOUBLE PRECISION NOT NULL,
    current_activity DOUBLE PRECISION NOT NULL,
    training_rows INTEGER NOT NULL,
    actual_activity DOUBLE PRECISION,
    absolute_error DOUBLE PRECISION,
    scored_at TIMESTAMPTZ,

    UNIQUE (predicted_hour, model)
);
