import time

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from data import load_hourly_data
from timing import prepare_hourly_frame


MIN_TRAINING_ROWS = 192

TIME_FEATURES = [
    "hour_of_day",
    "hours_from_sunrise",
    "is_day",
]

ACTIVITY_FEATURES = [
    "activity_index",
    "activity_lag_1h",
    "activity_lag_2h",
    "activity_lag_3h",
    "activity_lag_24h",
]

FULL_FEATURES = TIME_FEATURES + ACTIVITY_FEATURES


def make_rf():
    return RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        min_samples_leaf=3,
        n_jobs=-1,
    )


def build_dataset(raw: pd.DataFrame) -> pd.DataFrame:
    data = prepare_hourly_frame(raw)

    data["activity_lag_1h"] = data["activity_index"].shift(1)
    data["activity_lag_2h"] = data["activity_index"].shift(2)
    data["activity_lag_3h"] = data["activity_index"].shift(3)
    data["activity_lag_24h"] = data["activity_index"].shift(24)

    # Same prediction contract as the live aggregate models:
    # completed hour T -> target hour T+2.
    data["target_activity"] = data["activity_index"].shift(-2)
    data["target_hour"] = data.index + pd.Timedelta(hours=2)

    numeric = FULL_FEATURES + ["target_activity"]

    for column in numeric:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    data = data.dropna(
        subset=FULL_FEATURES + ["target_activity"]
    ).copy()

    # A simple sunrise-relative climatology bin.  This uses only the
    # issue-time astronomical feature, not future observed activity.
    data["solar_bin"] = np.floor(
        data["hours_from_sunrise"]
    ).astype(int)

    return data


def regression_metrics(actual, predicted):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    errors = np.abs(predicted - actual)

    return {
        "mae": mean_absolute_error(actual, predicted),
        "rmse": np.sqrt(mean_squared_error(actual, predicted)),
        "median_ae": float(np.median(errors)),
        "p90_ae": float(np.percentile(errors, 90)),
    }


def climatology_prediction(train, test):
    solar_bin = int(test["solar_bin"].iloc[0])

    same_bin = train.loc[
        train["solar_bin"] == solar_bin,
        "target_activity",
    ]

    if len(same_bin) >= 3:
        return float(same_bin.mean())

    # Conservative fallback if a sunrise-relative bin has little history.
    hour = int(test["hour_of_day"].iloc[0])
    same_hour = train.loc[
        train["hour_of_day"] == hour,
        "target_activity",
    ]

    if len(same_hour) >= 3:
        return float(same_hour.mean())

    return float(train["target_activity"].mean())


def fit_predict(train, test, features):
    X_train = train[features].copy()
    X_test = test[features].copy()

    if "is_day" in features:
        X_train["is_day"] = X_train["is_day"].astype(int)
        X_test["is_day"] = X_test["is_day"].astype(int)

    model = make_rf()
    model.fit(X_train, train["target_activity"])

    prediction = float(model.predict(X_test)[0])

    return max(0.0, prediction), model


def activity_band(value):
    if value == 0:
        return "0"
    if value <= 5:
        return "1-5"
    if value <= 15:
        return "6-15"
    return "16+"


def print_overall(predictions):
    columns = [
        "Persistence",
        "Solar climatology",
        "RF time-only",
        "RF activity-only",
        "RF full",
    ]

    print("Overall")
    print("-------")
    print(
        f"{'Model':<22} {'Hours':>7} {'MAE':>9} "
        f"{'RMSE':>9} {'Median':>9} {'P90':>9}"
    )
    print("-" * 70)

    summary = {}

    for column in columns:
        m = regression_metrics(
            predictions["actual"],
            predictions[column],
        )
        summary[column] = m
        print(
            f"{column:<22} {len(predictions):>7} "
            f"{m['mae']:>9.3f} "
            f"{m['rmse']:>9.3f} "
            f"{m['median_ae']:>9.3f} "
            f"{m['p90_ae']:>9.3f}"
        )

    print()

    time_mae = summary["RF time-only"]["mae"]
    activity_mae = summary["RF activity-only"]["mae"]
    full_mae = summary["RF full"]["mae"]
    solar_mae = summary["Solar climatology"]["mae"]

    print("What does the full model add?")
    print("-----------------------------")
    print(
        "Full RF improvement vs time-only RF: "
        f"{(time_mae - full_mae) / time_mae * 100:+.2f}%"
    )
    print(
        "Full RF improvement vs activity-only RF: "
        f"{(activity_mae - full_mae) / activity_mae * 100:+.2f}%"
    )
    print(
        "Full RF improvement vs solar climatology: "
        f"{(solar_mae - full_mae) / solar_mae * 100:+.2f}%"
    )
    print()


def print_head_to_head(predictions):
    comparisons = [
        ("Full vs time-only", "RF full", "RF time-only"),
        ("Full vs activity-only", "RF full", "RF activity-only"),
        ("Full vs solar climatology", "RF full", "Solar climatology"),
    ]

    print("Head-to-head absolute-error wins")
    print("--------------------------------")

    for label, left, right in comparisons:
        left_error = np.abs(
            predictions[left] - predictions["actual"]
        )
        right_error = np.abs(
            predictions[right] - predictions["actual"]
        )

        left_wins = int((left_error < right_error).sum())
        right_wins = int((right_error < left_error).sum())
        ties = len(predictions) - left_wins - right_wins

        print(
            f"{label:<27} "
            f"{left_wins:>4} / {right_wins:>4} / {ties:>4}"
        )

    print("  format: first model wins / second model wins / ties")
    print()


def print_day_night(predictions):
    columns = [
        "Solar climatology",
        "RF time-only",
        "RF activity-only",
        "RF full",
    ]

    print("Day / night MAE")
    print("---------------")
    print(
        f"{'Period':<8} {'Hours':>7} "
        + " ".join(f"{c:>18}" for c in columns)
    )
    print("-" * 92)

    for is_day, label in [(1, "Day"), (0, "Night")]:
        subset = predictions.loc[
            predictions["is_day"] == is_day
        ]

        if subset.empty:
            continue

        maes = [
            mean_absolute_error(
                subset["actual"],
                subset[column],
            )
            for column in columns
        ]

        print(
            f"{label:<8} {len(subset):>7} "
            + " ".join(f"{m:>18.3f}" for m in maes)
        )

    print()


def print_activity_bands(predictions):
    work = predictions.copy()
    work["activity_band"] = work["actual"].map(activity_band)

    columns = [
        "Solar climatology",
        "RF time-only",
        "RF activity-only",
        "RF full",
    ]

    print("Activity-band MAE")
    print("-----------------")
    print(
        f"{'Band':<6} {'Hours':>7} "
        + " ".join(f"{c:>18}" for c in columns)
    )
    print("-" * 90)

    for band in ["0", "1-5", "6-15", "16+"]:
        subset = work.loc[
            work["activity_band"] == band
        ]

        if subset.empty:
            continue

        maes = [
            mean_absolute_error(
                subset["actual"],
                subset[column],
            )
            for column in columns
        ]

        print(
            f"{band:<6} {len(subset):>7} "
            + " ".join(f"{m:>18.3f}" for m in maes)
        )

    print()


def print_full_importance(model):
    importance = pd.Series(
        model.feature_importances_,
        index=FULL_FEATURES,
    ).sort_values(ascending=False)

    print("Final full-RF feature importance")
    print("--------------------------------")
    print("Diagnostic only; importance is not causality.")
    print()

    for feature, value in importance.items():
        family = (
            "time"
            if feature in TIME_FEATURES
            else "activity"
        )
        print(
            f"  {feature:<24} {value:>8.4f} [{family}]"
        )

    print()


def main():
    raw = load_hourly_data()
    df = build_dataset(raw)

    rows = []
    last_full_model = None
    started = time.monotonic()

    candidate_positions = list(
        range(MIN_TRAINING_ROWS, len(df))
    )

    print()
    print("BirdNET feature-family ablation")
    print("===============================")
    print()
    print(f"Raw hourly rows:        {len(raw)}")
    print(f"Usable rows:            {len(df)}")
    print(f"Candidate test rows:    {len(candidate_positions)}")
    print(f"Dataset start:          {df.index.min()}")
    print(f"Dataset cutoff:         {df.index.max()}")
    print()
    print("Prediction horizon:")
    print("  completed hour T -> target T+2")
    print()
    print("Question:")
    print(
        "  Does the full model predict meaningfully more than "
        "the expected daily rhythm?"
    )
    print()
    print("Feature families:")
    print(f"  time-only:     {TIME_FEATURES}")
    print(f"  activity-only: {ACTIVITY_FEATURES}")
    print(f"  full:          {FULL_FEATURES}")
    print()
    print("Progress:")
    print("  one dot ~= 25 completed walk-forward forecasts")
    print()

    completed = 0

    for test_pos in candidate_positions:
        test = df.iloc[[test_pos]]
        test_hour = test.index[0]

        # Leakage-safe rule: only historical targets whose target
        # hour is already complete at feature hour T can be trained on.
        train = df.iloc[:test_pos].copy()
        train = train.loc[
            train["target_hour"] <= test_hour
        ]

        if len(train) < MIN_TRAINING_ROWS:
            continue

        actual = float(
            test["target_activity"].iloc[0]
        )

        row = {
            "feature_hour": test_hour,
            "target_hour": test["target_hour"].iloc[0],
            "actual": actual,
            "is_day": int(test["is_day"].iloc[0]),
            "Persistence": float(
                test["activity_index"].iloc[0]
            ),
            "Solar climatology": climatology_prediction(
                train,
                test,
            ),
        }

        row["RF time-only"], _ = fit_predict(
            train,
            test,
            TIME_FEATURES,
        )

        row["RF activity-only"], _ = fit_predict(
            train,
            test,
            ACTIVITY_FEATURES,
        )

        row["RF full"], last_full_model = fit_predict(
            train,
            test,
            FULL_FEATURES,
        )

        rows.append(row)
        completed += 1

        if completed % 25 == 0:
            elapsed = time.monotonic() - started
            print(
                f"  {completed:>4} forecasts "
                f"({elapsed / 60:.1f} min)",
                flush=True,
            )

    predictions = pd.DataFrame(rows)

    if predictions.empty:
        raise RuntimeError(
            "No walk-forward forecasts were produced."
        )

    elapsed = time.monotonic() - started

    print()
    print(
        f"Completed {len(predictions)} forecasts "
        f"in {elapsed / 60:.1f} minutes."
    )
    print()

    print_overall(predictions)
    print_head_to_head(predictions)
    print_day_night(predictions)
    print_activity_bands(predictions)

    if last_full_model is not None:
        print_full_importance(last_full_model)

    print("Interpretation guard")
    print("--------------------")
    print(
        "This is a retrospective chronological ablation. "
        "It does not change live production features."
    )
    print(
        "If full RF barely beats time-only RF or solar climatology, "
        "the current model is mostly a diurnal-pattern estimator."
    )
    print(
        "If full RF materially beats both, activity history is adding "
        "dynamic information beyond sunrise/time structure."
    )
    print()


if __name__ == "__main__":
    main()
