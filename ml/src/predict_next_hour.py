import os

import pandas as pd
import psycopg
from sklearn.ensemble import RandomForestRegressor

from data import load_hourly_data
from timing import (
    FEATURES,
    MODEL_NAME,
    build_live_training_data,
    build_prediction_row,
    latest_completed_hour,
)


MIN_TRAINING_ROWS = 192


def save_prediction(
    predicted_hour,
    predicted_activity,
    current_activity,
    training_rows,
):
    conn = psycopg.connect(
        host=os.environ.get("BIRDNET_DB_HOST", "127.0.0.1"),
        dbname=os.environ.get("BIRDNET_DB_NAME", "birdnet"),
        user=os.environ.get("BIRDNET_DB_USER", "birdnet"),
        password=os.environ["BIRDNET_DB_PASSWORD"],
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bird_activity_predictions (
                    predicted_hour,
                    model,
                    predicted_activity,
                    current_activity,
                    training_rows
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (predicted_hour, model)
                DO NOTHING
                RETURNING id;
                """,
                (
                    predicted_hour,
                    MODEL_NAME,
                    predicted_activity,
                    current_activity,
                    training_rows,
                ),
            )

            inserted = cur.fetchone()

        conn.commit()

        return inserted is not None

    finally:
        conn.close()


def main():
    raw = load_hourly_data()

    completed_hour = latest_completed_hour()

    training = build_live_training_data(
        raw,
        completed_hour,
    )

    if len(training) < MIN_TRAINING_ROWS:
        raise RuntimeError(
            f"Only {len(training)} valid training rows; "
            f"need at least {MIN_TRAINING_ROWS}."
        )

    X_train = training[FEATURES].copy()
    y_train = training["target_activity"]

    X_train["is_day"] = X_train["is_day"].astype(int)

    model = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        min_samples_leaf=3,
    )

    model.fit(X_train, y_train)

    latest = build_prediction_row(
        raw,
        completed_hour,
    )

    X_latest = latest[FEATURES].copy()
    X_latest["is_day"] = X_latest["is_day"].astype(int)

    prediction = float(model.predict(X_latest)[0])
    prediction = max(0.0, prediction)

    # Skip the hour already underway.
    predicted_hour = completed_hour + pd.Timedelta(hours=2)

    current_activity = float(
        latest["activity_index"].iloc[0]
    )

    inserted = save_prediction(
        predicted_hour=predicted_hour,
        predicted_activity=prediction,
        current_activity=current_activity,
        training_rows=len(training),
    )

    print()
    print("BirdNET next-hour prediction")
    print("============================")
    print()
    print(f"Model:                 {MODEL_NAME}")
    print(f"Latest completed hour: {completed_hour}")
    print(f"Current activity:      {current_activity:.1f}")
    print()
    print(f"Predicted hour:        {predicted_hour}")
    print(f"Predicted activity:    {prediction:.1f}")
    print()
    print(f"Persistence prediction: {current_activity:.1f}")
    print(f"Training rows:          {len(training)}")
    print()

    if inserted:
        print("Prediction stored in PostgreSQL.")
    else:
        print(
            "Prediction already exists; "
            "original prediction preserved."
        )


if __name__ == "__main__":
    main()
