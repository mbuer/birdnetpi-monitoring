import argparse
import math
import os

import numpy as np
import pandas as pd
import psycopg

from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

from compare_species_models import build_features


MIN_TRAINING_ROWS = 192
DEFAULT_TRIALS = 12
DEFAULT_FOLDS = 4
DEFAULT_HOLDOUT_FRACTION = 0.20
THRESHOLDS = np.arange(0.05, 0.51, 0.025)


BASELINE_PARAMS = {
    "n_estimators": 300,
    "max_depth": 3,
    "learning_rate": 0.03,
    "min_child_weight": 1.0,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "gamma": 0.0,
    "reg_alpha": 0.0,
    "reg_lambda": 1.0,
    "class_weight_factor": 0.0,
}


def connect():
    return psycopg.connect(
        host=os.environ.get("BIRDNET_DB_HOST", "127.0.0.1"),
        dbname=os.environ.get("BIRDNET_DB_NAME", "birdnet"),
        user=os.environ.get("BIRDNET_DB_USER", "birdnet"),
        password=os.environ["BIRDNET_DB_PASSWORD"],
    )


def load_species_data(species):
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
        WHERE station_id = 'birdnet'
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

    conn = connect()

    try:
        with conn.cursor() as cur:
            cur.execute(query, (species,))
            rows = cur.fetchall()
            columns = [d.name for d in cur.description]
    finally:
        conn.close()

    return pd.DataFrame(rows, columns=columns)


def sample_params(rng):
    return {
        "n_estimators": int(rng.choice([150, 250, 350, 500])),
        "max_depth": int(rng.choice([2, 3, 4, 5])),
        "learning_rate": float(rng.choice([0.01, 0.02, 0.03, 0.05, 0.08])),
        "min_child_weight": float(rng.choice([1, 2, 4, 8])),
        "subsample": float(rng.choice([0.6, 0.75, 0.9, 1.0])),
        "colsample_bytree": float(rng.choice([0.6, 0.75, 0.9, 1.0])),
        "gamma": float(rng.choice([0.0, 0.1, 0.3, 0.7])),
        "reg_alpha": float(rng.choice([0.0, 0.05, 0.2, 0.7])),
        "reg_lambda": float(rng.choice([0.5, 1.0, 2.0, 5.0])),
        # 0 = no class weighting.
        # Otherwise multiply the fold's natural neg/pos ratio.
        "class_weight_factor": float(rng.choice([0.0, 0.5, 1.0, 1.5, 2.0])),
    }


def make_model(params, y_train, seed):
    positives = int(y_train.sum())
    negatives = int(len(y_train) - positives)

    if positives == 0:
        raise RuntimeError("Training split contains no positive samples.")

    factor = params["class_weight_factor"]

    if factor == 0:
        scale_pos_weight = 1.0
    else:
        scale_pos_weight = (negatives / positives) * factor

    return XGBClassifier(
        n_estimators=params["n_estimators"],
        max_depth=params["max_depth"],
        learning_rate=params["learning_rate"],
        min_child_weight=params["min_child_weight"],
        subsample=params["subsample"],
        colsample_bytree=params["colsample_bytree"],
        gamma=params["gamma"],
        reg_alpha=params["reg_alpha"],
        reg_lambda=params["reg_lambda"],
        scale_pos_weight=scale_pos_weight,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        random_state=seed,
        n_jobs=-1,
    )


def chronological_folds(data, folds):
    remaining = len(data) - MIN_TRAINING_ROWS

    if remaining < folds:
        raise RuntimeError(
            f"Not enough rows for {folds} chronological folds."
        )

    block = max(1, remaining // folds)
    splits = []

    for fold in range(folds):
        val_start = MIN_TRAINING_ROWS + fold * block

        if fold == folds - 1:
            val_end = len(data)
        else:
            val_end = min(len(data), val_start + block)

        if val_start >= val_end:
            continue

        validation = data.iloc[val_start:val_end]
        issue_hour = validation.index[0]

        training = data.iloc[:val_start].copy()
        training = training.loc[
            training["target_hour"] <= issue_hour
        ]

        if len(training) < MIN_TRAINING_ROWS:
            continue

        if training["target_present"].nunique() < 2:
            continue

        if validation["target_present"].nunique() < 2:
            # PR-AUC is still defined with one class in some cases, but
            # these folds are too weak to be useful for model selection.
            continue

        splits.append((training, validation))

    if len(splits) < 2:
        raise RuntimeError(
            "Fewer than two usable chronological validation folds."
        )

    return splits


def evaluate_params(params, splits, features, seed):
    fold_scores = []
    oof_actual = []
    oof_probability = []

    for fold_index, (training, validation) in enumerate(splits):
        X_train = training[features]
        y_train = training["target_present"].astype(int)

        X_val = validation[features]
        y_val = validation["target_present"].astype(int)

        model = make_model(
            params,
            y_train,
            seed + fold_index,
        )
        model.fit(X_train, y_train)

        probability = model.predict_proba(X_val)[:, 1]

        fold_scores.append(
            average_precision_score(y_val, probability)
        )
        oof_actual.extend(y_val.tolist())
        oof_probability.extend(probability.tolist())

    return (
        float(np.mean(fold_scores)),
        np.asarray(oof_actual, dtype=int),
        np.asarray(oof_probability, dtype=float),
    )


def choose_threshold(actual, probability):
    best = None

    for threshold in THRESHOLDS:
        predicted = (probability >= threshold).astype(int)

        metrics = {
            "threshold": float(threshold),
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
        }

        if best is None:
            best = metrics
            continue

        # Primary decision metric is F1. Prefer higher recall on an exact
        # F1 tie because missing a true occurrence is costly for this use.
        candidate_key = (
            metrics["f1"],
            metrics["recall"],
            metrics["precision"],
        )
        best_key = (
            best["f1"],
            best["recall"],
            best["precision"],
        )

        if candidate_key > best_key:
            best = metrics

    return best


def metric_summary(actual, probability, threshold):
    predicted = (probability >= threshold).astype(int)

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


def walk_forward_holdout(
    data,
    holdout_start,
    features,
    params,
    seed,
):
    actual = []
    probability = []

    for test_pos in range(holdout_start, len(data)):
        test = data.iloc[[test_pos]]
        issue_hour = test.index[0]

        training = data.iloc[:test_pos].copy()
        training = training.loc[
            training["target_hour"] <= issue_hour
        ]

        if len(training) < MIN_TRAINING_ROWS:
            continue

        if training["target_present"].nunique() < 2:
            continue

        X_train = training[features]
        y_train = training["target_present"].astype(int)
        X_test = test[features]

        model = make_model(
            params,
            y_train,
            seed + test_pos,
        )
        model.fit(X_train, y_train)

        actual.append(int(test["target_present"].iloc[0]))
        probability.append(
            float(model.predict_proba(X_test)[0, 1])
        )

    return (
        np.asarray(actual, dtype=int),
        np.asarray(probability, dtype=float),
    )


def print_metrics(name, metrics):
    print(
        f"{name:<24}"
        f"{metrics['accuracy']:>10.3f}"
        f"{metrics['precision']:>11.3f}"
        f"{metrics['recall']:>9.3f}"
        f"{metrics['f1']:>9.3f}"
        f"{metrics['roc_auc']:>10.3f}"
        f"{metrics['pr_auc']:>10.3f}"
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Leakage-safe randomized XGBoost search for one BirdNET species."
        )
    )
    parser.add_argument("--species", required=True)
    parser.add_argument(
        "--trials",
        type=int,
        default=DEFAULT_TRIALS,
    )
    parser.add_argument(
        "--folds",
        type=int,
        default=DEFAULT_FOLDS,
    )
    parser.add_argument(
        "--holdout-fraction",
        type=float,
        default=DEFAULT_HOLDOUT_FRACTION,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    args = parser.parse_args()

    if not 0.10 <= args.holdout_fraction <= 0.40:
        raise ValueError(
            "--holdout-fraction must be between 0.10 and 0.40"
        )

    raw = load_species_data(args.species)
    data, features = build_features(raw)

    holdout_rows = max(
        1,
        int(math.ceil(len(data) * args.holdout_fraction)),
    )
    holdout_start = len(data) - holdout_rows

    development = data.iloc[:holdout_start].copy()

    if len(development) <= MIN_TRAINING_ROWS:
        raise RuntimeError(
            "Not enough development rows after reserving holdout data."
        )

    splits = chronological_folds(
        development,
        args.folds,
    )

    rng = np.random.default_rng(args.seed)

    best = None

    print()
    print("BirdNET species XGBoost optimization")
    print("====================================")
    print()
    print(f"Species:             {args.species}")
    print(f"Raw hours:           {len(raw)}")
    print(f"Valid feature rows:  {len(data)}")
    print(f"Development rows:    {len(development)}")
    print(f"Final holdout rows:  {len(data) - holdout_start}")
    print(f"CV folds:            {len(splits)}")
    print(f"Random trials:       {args.trials}")
    print()
    print("Search objective: mean chronological validation PR-AUC")
    print()

    candidates = [BASELINE_PARAMS.copy()]

    for _ in range(args.trials):
        candidates.append(sample_params(rng))

    for index, params in enumerate(candidates):
        score, actual, probability = evaluate_params(
            params,
            splits,
            features,
            args.seed + index * 100,
        )

        label = "baseline" if index == 0 else f"trial {index:02d}"
        print(f"{label:<12} PR-AUC {score:.4f}")

        if best is None or score > best["score"]:
            best = {
                "score": score,
                "params": params,
                "actual": actual,
                "probability": probability,
            }

    threshold = choose_threshold(
        best["actual"],
        best["probability"],
    )

    print()
    print("Best development result")
    print("-----------------------")
    print(f"Mean PR-AUC: {best['score']:.4f}")
    print(
        "Threshold:   "
        f"{threshold['threshold']:.3f} "
        f"(F1 {threshold['f1']:.3f}, "
        f"precision {threshold['precision']:.3f}, "
        f"recall {threshold['recall']:.3f})"
    )
    print()
    print("Best parameters:")
    for key, value in best["params"].items():
        print(f"  {key}: {value}")

    print()
    print("Running untouched chronological holdout...")
    print()

    baseline_actual, baseline_probability = walk_forward_holdout(
        data,
        holdout_start,
        features,
        BASELINE_PARAMS,
        args.seed,
    )

    tuned_actual, tuned_probability = walk_forward_holdout(
        data,
        holdout_start,
        features,
        best["params"],
        args.seed + 10000,
    )

    if not np.array_equal(baseline_actual, tuned_actual):
        raise RuntimeError(
            "Baseline and tuned holdout targets do not match."
        )

    if len(tuned_actual) == 0:
        raise RuntimeError("No valid holdout predictions.")

    baseline_metrics = metric_summary(
        baseline_actual,
        baseline_probability,
        0.5,
    )
    tuned_default_metrics = metric_summary(
        tuned_actual,
        tuned_probability,
        0.5,
    )
    tuned_threshold_metrics = metric_summary(
        tuned_actual,
        tuned_probability,
        threshold["threshold"],
    )

    print(
        f"Holdout positives:    {int(tuned_actual.sum())} "
        f"of {len(tuned_actual)} "
        f"({tuned_actual.mean() * 100:.1f}%)"
    )
    print()

    header = (
        f"{'Model':<24}"
        f"{'Accuracy':>10}"
        f"{'Precision':>11}"
        f"{'Recall':>9}"
        f"{'F1':>9}"
        f"{'ROC-AUC':>10}"
        f"{'PR-AUC':>10}"
    )
    print(header)
    print("-" * len(header))

    print_metrics(
        "Current XGB @ 0.50",
        baseline_metrics,
    )
    print_metrics(
        "Tuned XGB @ 0.50",
        tuned_default_metrics,
    )
    print_metrics(
        f"Tuned XGB @ {threshold['threshold']:.3f}",
        tuned_threshold_metrics,
    )

    print()
    print(
        "The final holdout was not used for hyperparameter or threshold "
        "selection."
    )
    print(
        "Treat the tuned model as a challenger until it also accumulates "
        "live forward-validation history."
    )


if __name__ == "__main__":
    main()
