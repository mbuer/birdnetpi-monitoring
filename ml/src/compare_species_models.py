import argparse
import os

import numpy as np
import pandas as pd
import psycopg

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
)
from xgboost import XGBClassifier


MIN_TRAINING_ROWS = 192


def load_species_data(species):
    conn = psycopg.connect(
        host=os.environ.get("BIRDNET_DB_HOST", "127.0.0.1"),
        dbname=os.environ.get("BIRDNET_DB_NAME", "birdnet"),
        user=os.environ.get("BIRDNET_DB_USER", "birdnet"),
        password=os.environ["BIRDNET_DB_PASSWORD"],
    )

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
    WHERE s.station_id = 'birdnet'
      AND s.species = %s
    ORDER BY s.hour_local;
    """

    try:
        return pd.read_sql(query, conn, params=(species,))
    finally:
        conn.close()


def build_features(df):
    df = df.copy()

    df["hour_local"] = pd.to_datetime(df["hour_local"])
    df = df.set_index("hour_local").sort_index()

    df = df.asfreq("h")

    numeric = [
        "present",
        "detection_count",
        "total_detections",
        "species_count",
    ]

    for column in numeric:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["hour_of_day"] = df.index.hour

    df["present_lag_1h"] = df["present"].shift(1)
    df["present_lag_2h"] = df["present"].shift(2)
    df["present_lag_3h"] = df["present"].shift(3)
    df["present_lag_24h"] = df["present"].shift(24)

    df["target_present"] = df["present"].shift(-2)
    df["target_hour"] = df.index + pd.Timedelta(hours=2)

    features = [
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

    df = df.dropna(
        subset=features + ["target_present"]
    ).copy()

    return df, features


def calculate_metrics(actual, predicted, probability):
    return {
        "accuracy": accuracy_score(actual, predicted),
        "precision": precision_score(
            actual,
            predicted,
            zero_division=0,
        ),
        "recall": recall_score(
            actual,
            predicted,
            zero_division=0,
        ),
        "f1": f1_score(
            actual,
            predicted,
            zero_division=0,
        ),
        "roc_auc": roc_auc_score(actual, probability),
        "pr_auc": average_precision_score(
            actual,
            probability,
        ),
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--species",
        required=True,
    )

    args = parser.parse_args()

    raw = load_species_data(args.species)
    data, features = build_features(raw)

    predictions = []

    for test_pos in range(MIN_TRAINING_ROWS, len(data)):
        test = data.iloc[[test_pos]]
        issue_hour = test.index[0]

        train = data.iloc[:test_pos].copy()

        train = train.loc[
            train["target_hour"] <= issue_hour
        ]

        if len(train) < MIN_TRAINING_ROWS:
            continue

        if train["target_present"].nunique() < 2:
            continue

        X_train = train[features]
        y_train = train["target_present"].astype(int)

        X_test = test[features]
        actual = int(test["target_present"].iloc[0])

        prevalence = float(y_train.mean())

        persistence_probability = float(
            test["present"].iloc[0]
        )

        rf = RandomForestClassifier(
            n_estimators=300,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1,
        )

        xgb = XGBClassifier(
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
        )

        rf.fit(X_train, y_train)
        xgb.fit(X_train, y_train)

        rf_probability = float(
            rf.predict_proba(X_test)[0, 1]
        )

        xgb_probability = float(
            xgb.predict_proba(X_test)[0, 1]
        )

        predictions.append(
            {
                "actual": actual,
                "prevalence_probability": prevalence,
                "persistence_probability":
                    persistence_probability,
                "rf_probability": rf_probability,
                "xgb_probability": xgb_probability,
            }
        )

    results = pd.DataFrame(predictions)

    if results.empty:
        raise RuntimeError(
            "No valid walk-forward predictions."
        )

    actual = results["actual"].astype(int)

    models = {
        "Prevalence": results[
            "prevalence_probability"
        ],
        "Persistence": results[
            "persistence_probability"
        ],
        "Random Forest": results[
            "rf_probability"
        ],
        "XGBoost": results[
            "xgb_probability"
        ],
    }

    print()
    print("BirdNET species prediction")
    print("==========================")
    print()
    print(f"Species:             {args.species}")
    print(f"Raw hours:           {len(raw)}")
    print(f"Valid feature rows:  {len(data)}")
    print(f"Forecasts:           {len(results)}")
    print(
        f"Positive targets:    "
        f"{int(actual.sum())} "
        f"({actual.mean() * 100:.1f}%)"
    )
    print()
    print("Prediction horizon:")
    print("  completed hour T -> presence at T+2")
    print()

    header = (
        f"{'Model':<16}"
        f"{'Accuracy':>10}"
        f"{'Precision':>11}"
        f"{'Recall':>9}"
        f"{'F1':>9}"
        f"{'ROC-AUC':>10}"
        f"{'PR-AUC':>10}"
    )

    print(header)
    print("-" * len(header))

    for name, probability in models.items():
        predicted = (probability >= 0.5).astype(int)

        metrics = calculate_metrics(
            actual,
            predicted,
            probability,
        )

        print(
            f"{name:<16}"
            f"{metrics['accuracy']:>10.3f}"
            f"{metrics['precision']:>11.3f}"
            f"{metrics['recall']:>9.3f}"
            f"{metrics['f1']:>9.3f}"
            f"{metrics['roc_auc']:>10.3f}"
            f"{metrics['pr_auc']:>10.3f}"
        )


if __name__ == "__main__":
    main()
