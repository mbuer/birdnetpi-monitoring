import argparse
import math

import numpy as np

from sklearn.metrics import average_precision_score

from optimize_species_xgboost import (
    BASELINE_PARAMS,
    MIN_TRAINING_ROWS,
    choose_threshold,
    chronological_folds,
    load_species_data,
    make_model,
    metric_summary,
    sample_params,
)
from compare_species_models import build_features


DEFAULT_TRIALS = 12
DEFAULT_MEMBERS = 15
DEFAULT_FOLDS = 4
DEFAULT_HOLDOUT_FRACTION = 0.20


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
            "Training split must contain both target classes."
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


def fit_single(training, validation, features, params, seed):
    y_train = training["target_present"].astype(int)

    model = make_model(
        params,
        y_train,
        seed,
    )
    model.fit(
        training[features],
        y_train,
    )

    return model.predict_proba(
        validation[features]
    )[:, 1]


def fit_ensemble(
    training,
    validation,
    features,
    params,
    members,
    seed,
):
    probabilities = []

    for member in range(members):
        sampled = balanced_bootstrap(
            training,
            seed + member * 1009,
        )

        y_train = sampled["target_present"].astype(int)

        member_params = dict(params)

        # The bootstrap is explicitly class-balanced, so do not apply
        # a second class imbalance correction on top of it.
        member_params["class_weight_factor"] = 0.0

        model = make_model(
            member_params,
            y_train,
            seed + member * 1009,
        )

        model.fit(
            sampled[features],
            y_train,
        )

        probabilities.append(
            model.predict_proba(
                validation[features]
            )[:, 1]
        )

    return np.mean(
        np.vstack(probabilities),
        axis=0,
    )


def search_best_params(
    development,
    features,
    folds,
    trials,
    seed,
):
    splits = chronological_folds(
        development,
        folds,
    )

    rng = np.random.default_rng(seed)
    candidates = [BASELINE_PARAMS.copy()]

    for _ in range(trials):
        candidates.append(sample_params(rng))

    best = None

    print("Hyperparameter search")
    print("---------------------")

    for index, params in enumerate(candidates):
        scores = []

        for fold_index, (training, validation) in enumerate(splits):
            probability = fit_single(
                training,
                validation,
                features,
                params,
                seed + index * 100 + fold_index,
            )

            actual = validation[
                "target_present"
            ].astype(int)

            scores.append(
                average_precision_score(
                    actual,
                    probability,
                )
            )

        score = float(np.mean(scores))
        label = (
            "baseline"
            if index == 0
            else f"trial {index:02d}"
        )

        print(f"{label:<12} PR-AUC {score:.4f}")

        if best is None or score > best["score"]:
            best = {
                "score": score,
                "params": params,
            }

    return best, splits


def collect_development_predictions(
    splits,
    features,
    params,
    members,
    seed,
):
    actual_all = []
    single_all = []
    ensemble_all = []

    for fold_index, (training, validation) in enumerate(splits):
        actual = validation[
            "target_present"
        ].astype(int).to_numpy()

        single_probability = fit_single(
            training,
            validation,
            features,
            params,
            seed + fold_index * 100,
        )

        ensemble_probability = fit_ensemble(
            training,
            validation,
            features,
            params,
            members,
            seed + 10000 + fold_index * 1000,
        )

        actual_all.extend(actual.tolist())
        single_all.extend(single_probability.tolist())
        ensemble_all.extend(
            ensemble_probability.tolist()
        )

    return (
        np.asarray(actual_all, dtype=int),
        np.asarray(single_all, dtype=float),
        np.asarray(ensemble_all, dtype=float),
    )


def print_metrics(name, metrics):
    print(
        f"{name:<30}"
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
            "Experimental class-balanced bootstrap XGBoost ensemble "
            "for BirdNET species prediction."
        )
    )
    parser.add_argument("--species", required=True)
    parser.add_argument(
        "--trials",
        type=int,
        default=DEFAULT_TRIALS,
    )
    parser.add_argument(
        "--members",
        type=int,
        default=DEFAULT_MEMBERS,
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

    if args.members < 3:
        raise ValueError("--members must be at least 3")

    if not 0.10 <= args.holdout_fraction <= 0.40:
        raise ValueError(
            "--holdout-fraction must be between 0.10 and 0.40"
        )

    raw = load_species_data(args.species)
    data, features = build_features(raw)

    holdout_rows = max(
        1,
        int(
            math.ceil(
                len(data) * args.holdout_fraction
            )
        ),
    )
    holdout_start = len(data) - holdout_rows

    development = data.iloc[:holdout_start].copy()
    holdout = data.iloc[holdout_start:].copy()

    if len(development) <= MIN_TRAINING_ROWS:
        raise RuntimeError(
            "Not enough development rows after reserving holdout."
        )

    print()
    print("BirdNET species bootstrap ensemble")
    print("==================================")
    print()
    print(f"Species:             {args.species}")
    print(f"Raw hours:           {len(raw)}")
    print(f"Valid feature rows:  {len(data)}")
    print(f"Development rows:    {len(development)}")
    print(f"Diagnostic holdout:  {len(holdout)}")
    print(f"Ensemble members:    {args.members}")
    print()

    best, splits = search_best_params(
        development,
        features,
        args.folds,
        args.trials,
        args.seed,
    )

    print()
    print("Best hyperparameters")
    print("--------------------")
    print(f"Mean CV PR-AUC: {best['score']:.4f}")
    for key, value in best["params"].items():
        print(f"  {key}: {value}")

    (
        dev_actual,
        dev_single_probability,
        dev_ensemble_probability,
    ) = collect_development_predictions(
        splits,
        features,
        best["params"],
        args.members,
        args.seed,
    )

    single_threshold = choose_threshold(
        dev_actual,
        dev_single_probability,
    )
    ensemble_threshold = choose_threshold(
        dev_actual,
        dev_ensemble_probability,
    )

    print()
    print("Development thresholds")
    print("----------------------")
    print(
        f"Single XGB: {single_threshold['threshold']:.3f} "
        f"(F1 {single_threshold['f1']:.3f}, "
        f"precision {single_threshold['precision']:.3f}, "
        f"recall {single_threshold['recall']:.3f})"
    )
    print(
        f"Ensemble:   {ensemble_threshold['threshold']:.3f} "
        f"(F1 {ensemble_threshold['f1']:.3f}, "
        f"precision {ensemble_threshold['precision']:.3f}, "
        f"recall {ensemble_threshold['recall']:.3f})"
    )

    if holdout["target_present"].nunique() < 2:
        raise RuntimeError(
            "Diagnostic holdout contains only one target class."
        )

    holdout_actual = holdout[
        "target_present"
    ].astype(int).to_numpy()

    single_probability = fit_single(
        development,
        holdout,
        features,
        best["params"],
        args.seed + 50000,
    )

    ensemble_probability = fit_ensemble(
        development,
        holdout,
        features,
        best["params"],
        args.members,
        args.seed + 60000,
    )

    baseline_probability = fit_single(
        development,
        holdout,
        features,
        BASELINE_PARAMS,
        args.seed + 70000,
    )

    baseline_metrics = metric_summary(
        holdout_actual,
        baseline_probability,
        0.5,
    )
    single_metrics = metric_summary(
        holdout_actual,
        single_probability,
        single_threshold["threshold"],
    )
    ensemble_metrics = metric_summary(
        holdout_actual,
        ensemble_probability,
        ensemble_threshold["threshold"],
    )

    print()
    print("Diagnostic chronological holdout")
    print("--------------------------------")
    print(
        f"Positive targets: {int(holdout_actual.sum())} "
        f"of {len(holdout_actual)} "
        f"({holdout_actual.mean() * 100:.1f}%)"
    )
    print()

    header = (
        f"{'Model':<30}"
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
        f"Tuned XGB @ {single_threshold['threshold']:.3f}",
        single_metrics,
    )
    print_metrics(
        f"Bootstrap avg @ {ensemble_threshold['threshold']:.3f}",
        ensemble_metrics,
    )

    print()
    print(
        "The ensemble uses class-balanced bootstrap samples with "
        "replacement and averages probabilities across members."
    )
    print(
        "This script is experimental only; it does not change the "
        "live predictor or scheduled species."
    )
    print(
        "If this species was already evaluated on the same final time "
        "window, treat the holdout as diagnostic rather than untouched."
    )
    print(
        "Future live forward-validation remains the strongest evidence "
        "for promotion."
    )


if __name__ == "__main__":
    main()
