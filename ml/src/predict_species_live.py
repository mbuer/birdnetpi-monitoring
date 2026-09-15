import argparse
import os

import pandas as pd
import psycopg

from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

from timing import latest_completed_hour


MIN_TRAINING_ROWS = 192
THRESHOLD = 0.5
STATION_ID = "birdnet"


FEATURES = [
    "hour_of_day",
    "present",
    "present_lag_1h",
    "present_lag_2h",
    "present_lag_3h",
    "present_lag_24h",
    "detection_count",
    "total_detections",
    "species_count",
]


def connect():
    return psycopg.connect(
        host=os.environ.get("BIRDNET_DB_HOST", "127.0.0.1"),
        dbname=os.environ.get("BIRDNET_DB_NAME", "birdnet"),
        user=os.environ.get("BIRDNET_DB_USER", "birdnet"),
        password=os.environ["BIRDNET_DB_PASSWORD"],
    )


def load_species_data(conn, species):
    query = """
    WITH overall AS (
        SELECT
            date_trunc(
                'hour',
                detected_at AT TIME ZONE 'America/Los_Angeles'
            ) AS hour_local,
            COUNT(*) AS total_detections,
            COUNT(DISTINCT species) AS species_count
        FROM detections
        WHERE station_id = %s
        GROUP BY 1
    )
    SELECT
        s.hour_local,
        s.present,
        s.detection_count,
        COALESCE(o.total_detections, 0) AS total_detections,
        COALESCE(o.species_count, 0) AS species_count
    FROM bird_species_hourly s
    LEFT JOIN overall o
        ON o.hour_local = s.hour_local
    WHERE s.station_id = %s
      AND s.species = %s
    ORDER BY s.hour_local;
    """

    with conn.cursor() as cur:
        cur.execute(
            query,
            (STATION_ID, STATION_ID, species),
        )
        rows = cur.fetchall()
        columns = [d.name for d in cur.description]

    return pd.DataFrame(rows, columns=columns)


def prepare_dataset(raw, completed_hour):
    df = raw.copy()

    df["hour_local"] = pd.to_datetime(df["hour_local"])
    df = df.set_index("hour_local").sort_index()

    # Never use a partially completed future/current bucket.
    df = df.loc[df.index <= completed_hour]

    if df.empty:
        raise RuntimeError("No historical species data available.")

    # Extend through the latest completed hour.
    # Missing detection hours represent zero detected activity.
    full_index = pd.date_range(
        start=df.index.min(),
        end=completed_hour,
        freq="h",
    )

    df = df.reindex(full_index)
    df.index.name = "hour_local"

    zero_columns = [
        "present",
        "detection_count",
        "total_detections",
        "species_count",
    ]

    for column in zero_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0)

    df["hour_of_day"] = df.index.hour

    df["present_lag_1h"] = df["present"].shift(1)
    df["present_lag_2h"] = df["present"].shift(2)
    df["present_lag_3h"] = df["present"].shift(3)
    df["present_lag_24h"] = df["present"].shift(24)

    # Same corrected v2 horizon as aggregate activity:
    # completed feature hour T -> target hour T+2.
    df["target_present"] = df["present"].shift(-2)
    df["target_hour"] = df.index + pd.Timedelta(hours=2)

    return df


def save_prediction(
    conn,
    species,
    predicted_hour,
    model_name,
    probability,
    current_present,
    training_rows,
):
    predicted_present = int(probability >= THRESHOLD)

    query = """
    INSERT INTO bird_species_predictions (
        station_id,
        species,
        predicted_hour,
        model,
        probability,
        threshold,
        predicted_present,
        current_present,
        training_rows
    )
    VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    ON CONFLICT (
        station_id,
        species,
        predicted_hour,
        model
    )
    DO NOTHING;
    """

    with conn.cursor() as cur:
        cur.execute(
            query,
            (
                STATION_ID,
                species,
                predicted_hour,
                model_name,
                probability,
                THRESHOLD,
                predicted_present,
                current_present,
                training_rows,
            ),
        )

    conn.commit()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--species",
        required=True,
        help="Common species name, for example 'House Finch'",
    )

    args = parser.parse_args()

    completed_hour = pd.Timestamp(latest_completed_hour())

    if completed_hour.tzinfo is not None:
        completed_hour = completed_hour.tz_localize(None)

    conn = connect()

    try:
        raw = load_species_data(
            conn,
            args.species,
        )

        if raw.empty:
            raise RuntimeError(
                f"No data found for species: {args.species}"
            )

        data = prepare_dataset(
            raw,
            completed_hour,
        )

        prediction_row = data.loc[
            [completed_hour]
        ].dropna(
            subset=FEATURES
        )

        if prediction_row.empty:
            raise RuntimeError(
                "Latest completed hour does not have enough "
                "history to build prediction features."
            )

        # Leakage-safe:
        # only train on labels whose target hour has already
        # occurred by the prediction issue hour.
        training = data.loc[
            data["target_hour"] <= completed_hour
        ].dropna(
            subset=FEATURES + ["target_present"]
        ).copy()

        if len(training) < MIN_TRAINING_ROWS:
            raise RuntimeError(
                f"Only {len(training)} usable training rows; "
                f"need at least {MIN_TRAINING_ROWS}."
            )

        if training["target_present"].nunique() < 2:
            raise RuntimeError(
                "Training data contains only one target class."
            )

        X_train = training[FEATURES]
        y_train = training["target_present"].astype(int)

        X_test = prediction_row[FEATURES]

        current_present = int(
            prediction_row["present"].iloc[0]
        )

        predicted_hour = (
            completed_hour
            + pd.Timedelta(hours=2)
        )

        models = {
            "random_forest_species_v1":
                RandomForestClassifier(
                    n_estimators=300,
                    min_samples_leaf=3,
                    random_state=42,
                    n_jobs=-1,
                ),

            "xgboost_species_v1":
                XGBClassifier(
                    n_estimators=300,
                    max_depth=3,
                    learning_rate=0.03,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    objective="binary:logistic",
                    eval_metric="logloss",
                    tree_method="hist",
                    random_state=42,
                    n_jobs=-1,
                ),
        }

        print()
        print("BirdNET live species prediction")
        print("===============================")
        print()
        print(f"Species:               {args.species}")
        print(f"Latest completed hour: {completed_hour}")
        print(f"Predicted hour:        {predicted_hour}")
        print(f"Current presence:      {current_present}")
        print(f"Training rows:         {len(training)}")
        print()

        for model_name, model in models.items():
            model.fit(
                X_train,
                y_train,
            )

            probability = float(
                model.predict_proba(X_test)[0, 1]
            )

            save_prediction(
                conn=conn,
                species=args.species,
                predicted_hour=predicted_hour,
                model_name=model_name,
                probability=probability,
                current_present=current_present,
                training_rows=len(training),
            )

            prediction_text = (
                "present"
                if probability >= THRESHOLD
                else "absent"
            )

            print(
                f"{model_name:<28} "
                f"{probability * 100:6.1f}% "
                f"-> {prediction_text}"
            )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
