import os

import pandas as pd
import psycopg
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

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
    model_name,
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
                    model_name,
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

    for column in FEATURES:
        X_train[column] = pd.to_numeric(
            X_train[column],
            errors="coerce",
        )

    X_train["is_day"] = X_train["is_day"].astype(int)

    models = {
        MODEL_NAME: RandomForestRegressor(
            n_estimators=300,
            random_state=42,
            min_samples_leaf=3,
        ),
        "xgboost_v2_completed": XGBRegressor(
            n_estimators=300,
            max_depth=3,
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            tree_method="hist",
            random_state=42,
            n_jobs=-1,
        ),
    }

    latest = build_prediction_row(
        raw,
        completed_hour,
    )

    X_latest = latest[FEATURES].copy()

    for column in FEATURES:
        X_latest[column] = pd.to_numeric(
            X_latest[column],
            errors="coerce",
        )

    X_latest["is_day"] = X_latest["is_day"].astype(int)

    # Skip the hour already underway.
    predicted_hour = completed_hour + pd.Timedelta(hours=2)

    current_activity = float(
        latest["activity_index"].iloc[0]
    )

    print()
    print("BirdNET next-hour prediction")
    print("============================")
    print()
    print(f"Latest completed hour: {completed_hour}")
    print(f"Current activity:      {current_activity:.1f}")
    print(f"Predicted hour:        {predicted_hour}")
    print(f"Persistence prediction: {current_activity:.1f}")
    print(f"Training rows:          {len(training)}")
    print()

    for model_name, model in models.items():
        model.fit(X_train, y_train)

        prediction = float(model.predict(X_latest)[0])
        prediction = max(0.0, prediction)

        inserted = save_prediction(
            predicted_hour=predicted_hour,
            model_name=model_name,
            predicted_activity=prediction,
            current_activity=current_activity,
            training_rows=len(training),
        )

        print(f"{model_name}: {prediction:.1f}")

        if inserted:
            print("  Prediction stored in PostgreSQL.")
        else:
            print("  Prediction already exists; original preserved.")



if __name__ == "__main__":
    main()
