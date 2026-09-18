import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from predict_species_live import (
    FEATURES,
    MIN_TRAINING_ROWS,
    STATION_ID,
    connect,
    load_species_data,
    prepare_dataset,
)
from timing import latest_completed_hour


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "ml" / "species_challengers.json"
RANDOM_SEED = 42


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def xgb_model(params, y_train, seed):
    positives = int(y_train.sum())
    negatives = int(len(y_train) - positives)

    if positives == 0:
        raise RuntimeError("Training data contains no positive samples.")

    factor = float(params.get("class_weight_factor", 0.0))

    if factor == 0:
        scale_pos_weight = 1.0
    else:
        scale_pos_weight = (negatives / positives) * factor

    return XGBClassifier(
        n_estimators=int(params["n_estimators"]),
        max_depth=int(params["max_depth"]),
        learning_rate=float(params["learning_rate"]),
        min_child_weight=float(params["min_child_weight"]),
        subsample=float(params["subsample"]),
        colsample_bytree=float(params["colsample_bytree"]),
        gamma=float(params["gamma"]),
        reg_alpha=float(params["reg_alpha"]),
        reg_lambda=float(params["reg_lambda"]),
        scale_pos_weight=scale_pos_weight,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        random_state=seed,
        n_jobs=-1,
    )


def balanced_bootstrap(training, seed):
    rng = np.random.default_rng(seed)

    positives = training.loc[
        training["target_present"].astype(int) == 1
    ]
    negatives = training.loc[
        training["target_present"].astype(int) == 0
    ]

    if positives.empty or negatives.empty:
        raise RuntimeError(
            "Training data must contain both target classes."
        )

    per_class = max(len(positives), len(negatives))

    pos_idx = rng.choice(
        positives.index.to_numpy(),
        size=per_class,
        replace=True,
    )
    neg_idx = rng.choice(
        negatives.index.to_numpy(),
        size=per_class,
        replace=True,
    )

    sampled = training.loc[
        np.concatenate([pos_idx, neg_idx])
    ].copy()

    order = rng.permutation(len(sampled))
    return sampled.iloc[order]


def save_prediction(
    conn,
    species,
    predicted_hour,
    model_name,
    probability,
    threshold,
    current_present,
    training_rows,
):
    predicted_present = int(probability >= threshold)

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
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                threshold,
                predicted_present,
                current_present,
                training_rows,
            ),
        )

    conn.commit()


def build_live_frame(conn, species):
    completed_hour = pd.Timestamp(latest_completed_hour())

    if completed_hour.tzinfo is not None:
        completed_hour = completed_hour.tz_localize(None)

    raw = load_species_data(conn, species)

    if raw.empty:
        raise RuntimeError(f"No data found for species: {species}")

    data = prepare_dataset(raw, completed_hour)

    prediction_row = data.loc[
        [completed_hour]
    ].dropna(subset=FEATURES)

    if prediction_row.empty:
        raise RuntimeError(
            "Latest completed hour does not have enough history "
            "to build prediction features."
        )

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

    return completed_hour, training, prediction_row


def predict_tuned(training, prediction_row, params):
    y_train = training["target_present"].astype(int)

    model = xgb_model(
        params,
        y_train,
        RANDOM_SEED,
    )
    model.fit(training[FEATURES], y_train)

    return float(
        model.predict_proba(
            prediction_row[FEATURES]
        )[0, 1]
    )


def predict_bootstrap(
    training,
    prediction_row,
    params,
    members,
):
    probabilities = []

    for member in range(members):
        seed = RANDOM_SEED + member * 1009
        sampled = balanced_bootstrap(training, seed)
        y_train = sampled["target_present"].astype(int)

        member_params = dict(params)
        member_params["class_weight_factor"] = 0.0

        model = xgb_model(
            member_params,
            y_train,
            seed,
        )
        model.fit(sampled[FEATURES], y_train)

        probabilities.append(
            float(
                model.predict_proba(
                    prediction_row[FEATURES]
                )[0, 1]
            )
        )

    return float(np.mean(probabilities))


def main():
    config = load_config()
    conn = connect()

    try:
        print()
        print("BirdNET species challenger predictions")
        print("======================================")
        print()

        for species, settings in config.items():
            if not settings.get("enabled", False):
                continue

            (
                completed_hour,
                training,
                prediction_row,
            ) = build_live_frame(conn, species)

            strategy = settings["strategy"]
            params = settings["params"]

            if strategy == "tuned_xgboost":
                probability = predict_tuned(
                    training,
                    prediction_row,
                    params,
                )
            elif strategy == "balanced_bootstrap_ensemble":
                probability = predict_bootstrap(
                    training,
                    prediction_row,
                    params,
                    int(settings.get("members", 15)),
                )
            else:
                raise RuntimeError(
                    f"Unsupported challenger strategy: {strategy}"
                )

            threshold = float(settings.get("threshold", 0.5))
            model_name = settings["model"]
            predicted_hour = (
                completed_hour + pd.Timedelta(hours=2)
            )
            current_present = int(
                prediction_row["present"].iloc[0]
            )

            save_prediction(
                conn=conn,
                species=species,
                predicted_hour=predicted_hour,
                model_name=model_name,
                probability=probability,
                threshold=threshold,
                current_present=current_present,
                training_rows=len(training),
            )

            decision = (
                "present"
                if probability >= threshold
                else "absent"
            )

            print(
                f"{species:<24} "
                f"{model_name:<32} "
                f"{probability * 100:6.1f}% "
                f"threshold={threshold:.3f} "
                f"-> {decision}"
            )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
