import numpy as np
import pandas as pd

from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

from data import load_hourly_data
from timing import FEATURES, prepare_hourly_frame


MIN_TRAINING_ROWS = 192

WEATHER_FEATURES = [
    "temperature_f",
    "humidity_pct",
    "wind_mph",
    "cloud_pct",
    "precipitation_in",
]

BASELINE_FEATURES = list(FEATURES)
WEATHER_AUGMENTED_FEATURES = BASELINE_FEATURES + WEATHER_FEATURES


def build_dataset(raw: pd.DataFrame) -> pd.DataFrame:
    data = prepare_hourly_frame(raw)

    data["activity_lag_1h"] = data["activity_index"].shift(1)
    data["activity_lag_2h"] = data["activity_index"].shift(2)
    data["activity_lag_3h"] = data["activity_index"].shift(3)
    data["activity_lag_24h"] = data["activity_index"].shift(24)

    # Match the live v2 prediction contract:
    # completed hour T -> target hour T+2.
    data["target_activity"] = data["activity_index"].shift(-2)
    data["target_hour"] = data.index + pd.Timedelta(hours=2)

    numeric_columns = (
        WEATHER_AUGMENTED_FEATURES
        + ["target_activity"]
    )

    for column in numeric_columns:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    # The ablation must compare baseline and weather models on exactly
    # the same rows. Therefore rows missing candidate weather features
    # are removed from both sides of the comparison.
    data = data.dropna(
        subset=WEATHER_AUGMENTED_FEATURES + ["target_activity"]
    ).copy()

    return data


def make_models():
    return {
        "Random Forest": lambda: RandomForestRegressor(
            n_estimators=300,
            random_state=42,
            min_samples_leaf=3,
            n_jobs=-1,
        ),
        "XGBoost": lambda: XGBRegressor(
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
        "HistGradientBoosting": lambda: HistGradientBoostingRegressor(
            random_state=42,
        ),
    }


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


def print_metric_table(predictions):
    rows = []

    for column in [
        "Persistence",
        "RF baseline",
        "RF + weather",
        "XGB baseline",
        "XGB + weather",
        "HGB baseline",
        "HGB + weather",
    ]:
        m = regression_metrics(
            predictions["actual"],
            predictions[column],
        )
        rows.append((column, len(predictions), m))

    print("Overall")
    print("-------")
    print(
        f"{'Model':<22} {'Hours':>7} {'MAE':>9} "
        f"{'RMSE':>9} {'Median':>9} {'P90':>9}"
    )
    print("-" * 70)

    for name, hours, m in rows:
        print(
            f"{name:<22} {hours:>7} "
            f"{m['mae']:>9.3f} "
            f"{m['rmse']:>9.3f} "
            f"{m['median_ae']:>9.3f} "
            f"{m['p90_ae']:>9.3f}"
        )

    print()


def print_ablation_head_to_head(predictions):
    pairs = [
        ("Random Forest", "RF baseline", "RF + weather"),
        ("XGBoost", "XGB baseline", "XGB + weather"),
        ("HistGradientBoosting", "HGB baseline", "HGB + weather"),
    ]

    print("Baseline vs weather head-to-head")
    print("--------------------------------")

    for label, baseline, weather in pairs:
        baseline_error = np.abs(
            predictions[baseline] - predictions["actual"]
        )
        weather_error = np.abs(
            predictions[weather] - predictions["actual"]
        )

        weather_wins = int((weather_error < baseline_error).sum())
        baseline_wins = int((baseline_error < weather_error).sum())
        ties = len(predictions) - weather_wins - baseline_wins

        baseline_mae = float(baseline_error.mean())
        weather_mae = float(weather_error.mean())

        delta_pct = (
            (baseline_mae - weather_mae) / baseline_mae * 100
            if baseline_mae
            else 0.0
        )

        print(label)
        print(f"  baseline MAE: {baseline_mae:.3f}")
        print(f"  weather MAE:  {weather_mae:.3f}")
        print(f"  MAE change:   {delta_pct:+.2f}%")
        print(
            f"  weather wins / baseline wins / ties: "
            f"{weather_wins} / {baseline_wins} / {ties}"
        )

    print()


def print_day_night(predictions):
    print("Day / night")
    print("-----------")
    print(
        f"{'Period':<8} {'Hours':>7} "
        f"{'RF base':>9} {'RF wx':>9} "
        f"{'XGB base':>9} {'XGB wx':>9} "
        f"{'HGB base':>9} {'HGB wx':>9}"
    )
    print("-" * 82)

    for is_day, label in [(1, "Day"), (0, "Night")]:
        subset = predictions.loc[predictions["is_day"] == is_day]

        if subset.empty:
            continue

        values = []
        for column in [
            "RF baseline",
            "RF + weather",
            "XGB baseline",
            "XGB + weather",
            "HGB baseline",
            "HGB + weather",
        ]:
            values.append(
                mean_absolute_error(
                    subset["actual"],
                    subset[column],
                )
            )

        print(
            f"{label:<8} {len(subset):>7} "
            + " ".join(f"{value:>9.3f}" for value in values)
        )

    print()


def activity_band(value):
    if value == 0:
        return "0"
    if value <= 5:
        return "1-5"
    if value <= 15:
        return "6-15"
    return "16+"


def print_activity_bands(predictions):
    work = predictions.copy()
    work["activity_band"] = work["actual"].map(activity_band)

    print("Activity bands")
    print("--------------")
    print(
        f"{'Band':<6} {'Hours':>7} "
        f"{'RF base':>9} {'RF wx':>9} "
        f"{'XGB base':>9} {'XGB wx':>9} "
        f"{'HGB base':>9} {'HGB wx':>9}"
    )
    print("-" * 80)

    for band in ["0", "1-5", "6-15", "16+"]:
        subset = work.loc[work["activity_band"] == band]

        if subset.empty:
            continue

        values = []
        for column in [
            "RF baseline",
            "RF + weather",
            "XGB baseline",
            "XGB + weather",
            "HGB baseline",
            "HGB + weather",
        ]:
            values.append(
                mean_absolute_error(
                    subset["actual"],
                    subset[column],
                )
            )

        print(
            f"{band:<6} {len(subset):>7} "
            + " ".join(f"{value:>9.3f}" for value in values)
        )

    print()


def print_weather_importance(last_models):
    print("Weather-model feature importance")
    print("--------------------------------")
    print("Diagnostic only; importance is not causality.")
    print()

    for name in ["Random Forest", "XGBoost"]:
        model = last_models.get((name, "weather"))

        if model is None or not hasattr(model, "feature_importances_"):
            continue

        importance = pd.Series(
            model.feature_importances_,
            index=WEATHER_AUGMENTED_FEATURES,
        ).sort_values(ascending=False)

        print(name)

        for feature, value in importance.items():
            marker = " [weather]" if feature in WEATHER_FEATURES else ""
            print(f"  {feature:<24} {value:>8.4f}{marker}")

        print()


def main():
    raw = load_hourly_data()
    df = build_dataset(raw)

    prediction_rows = []
    last_models = {}

    model_factories = make_models()

    for test_pos in range(MIN_TRAINING_ROWS, len(df)):
        test = df.iloc[[test_pos]]
        test_hour = test.index[0]

        # At feature hour T, only labels whose target hour is <= T
        # would genuinely be known.
        train = df.iloc[:test_pos].copy()
        train = train.loc[train["target_hour"] <= test_hour]

        if len(train) < MIN_TRAINING_ROWS:
            continue

        y_train = train["target_activity"]
        actual = float(test["target_activity"].iloc[0])
        persistence = float(test["activity_index"].iloc[0])

        row = {
            "feature_hour": test_hour,
            "target_hour": test["target_hour"].iloc[0],
            "actual": actual,
            "is_day": int(test["is_day"].iloc[0]),
            "Persistence": persistence,
        }

        for model_name, factory in model_factories.items():
            for variant, features in [
                ("baseline", BASELINE_FEATURES),
                ("weather", WEATHER_AUGMENTED_FEATURES),
            ]:
                X_train = train[features].copy()
                X_test = test[features].copy()

                X_train["is_day"] = X_train["is_day"].astype(int)
                X_test["is_day"] = X_test["is_day"].astype(int)

                model = factory()
                model.fit(X_train, y_train)

                prediction = float(model.predict(X_test)[0])
                prediction = max(0.0, prediction)

                short = {
                    "Random Forest": "RF",
                    "XGBoost": "XGB",
                    "HistGradientBoosting": "HGB",
                }[model_name]

                row[
                    f"{short} + weather"
                    if variant == "weather"
                    else f"{short} baseline"
                ] = prediction

                last_models[(model_name, variant)] = model

        prediction_rows.append(row)

    predictions = pd.DataFrame(prediction_rows)

    print()
    print("BirdNET weather feature ablation")
    print("===============================")
    print()
    print(f"Raw hourly rows:          {len(raw)}")
    print(f"Matched usable rows:      {len(df)}")
    print(f"Walk-forward forecasts:   {len(predictions)}")
    print(f"Dataset start:            {df.index.min()}")
    print(f"Dataset cutoff:           {df.index.max()}")
    print()
    print("Prediction horizon:")
    print("  completed hour T -> target T+2")
    print()
    print("Weather candidate features:")
    for feature in WEATHER_FEATURES:
        print(f"  - {feature}")
    print()
    print("IMPORTANT:")
    print("  These are weather observations available at feature hour T.")
    print("  This experiment does NOT use future observed target-hour weather.")
    print("  It does NOT change the live production feature list.")
    print()

    if predictions.empty:
        raise RuntimeError("No walk-forward forecasts were produced.")

    print_metric_table(predictions)
    print_ablation_head_to_head(predictions)
    print_day_night(predictions)
    print_activity_bands(predictions)
    print_weather_importance(last_models)


if __name__ == "__main__":
    main()
