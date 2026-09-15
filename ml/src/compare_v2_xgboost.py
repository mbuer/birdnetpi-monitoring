import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

from data import load_hourly_data
from timing import FEATURES, prepare_hourly_frame


MIN_TRAINING_ROWS = 192


def build_v2_dataset(raw: pd.DataFrame) -> pd.DataFrame:
    data = prepare_hourly_frame(raw)

    data["activity_lag_1h"] = data["activity_index"].shift(1)
    data["activity_lag_2h"] = data["activity_index"].shift(2)
    data["activity_lag_3h"] = data["activity_index"].shift(3)
    data["activity_lag_24h"] = data["activity_index"].shift(24)

    # Match the corrected live v2 horizon:
    # completed hour T -> target T+2.
    data["target_activity"] = data["activity_index"].shift(-2)
    data["target_hour"] = data.index + pd.Timedelta(hours=2)

    numeric_columns = FEATURES + ["target_activity"]

    for column in numeric_columns:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    data = data.dropna(
        subset=FEATURES + ["target_activity"]
    ).copy()

    return data


def make_models():
    return {
        "Random Forest": RandomForestRegressor(
            n_estimators=300,
            random_state=42,
            min_samples_leaf=3,
            n_jobs=-1,
        ),
        "XGBoost": XGBRegressor(
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


def metrics(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    return mae, rmse


raw = load_hourly_data()
df = build_v2_dataset(raw)

results = {
    "Persistence": [],
    "Random Forest": [],
    "XGBoost": [],
}

prediction_rows = []

for test_pos in range(MIN_TRAINING_ROWS, len(df)):
    test = df.iloc[[test_pos]]
    test_hour = test.index[0]

    # At issue time for feature hour T, only historical labels
    # whose target hour is <= T can genuinely be known.
    train = df.iloc[:test_pos].copy()
    train = train.loc[train["target_hour"] <= test_hour]

    if len(train) < MIN_TRAINING_ROWS:
        continue

    X_train = train[FEATURES].copy()
    X_test = test[FEATURES].copy()

    X_train["is_day"] = X_train["is_day"].astype(int)
    X_test["is_day"] = X_test["is_day"].astype(int)

    y_train = train["target_activity"]
    actual = float(test["target_activity"].iloc[0])

    persistence = float(test["activity_index"].iloc[0])

    results["Persistence"].append((actual, persistence))

    row = {
        "feature_hour": test_hour,
        "target_hour": test["target_hour"].iloc[0],
        "actual": actual,
        "Persistence": persistence,
    }

    for name, model in make_models().items():
        model.fit(X_train, y_train)

        prediction = float(model.predict(X_test)[0])
        prediction = max(0.0, prediction)

        results[name].append((actual, prediction))
        row[name] = prediction

    prediction_rows.append(row)


print()
print("BirdNET v2 model comparison")
print("===========================")
print()
print(f"Raw hourly rows:       {len(raw)}")
print(f"Valid v2 rows:         {len(df)}")
print(f"Walk-forward forecasts:{len(prediction_rows)}")
print(f"Dataset start:         {df.index.min()}")
print(f"Dataset cutoff:        {df.index.max()}")
print()
print("Prediction horizon:")
print("  completed hour T -> target T+2")
print()
print(f"{'Model':<20} {'MAE':>10} {'RMSE':>10}")
print("-" * 42)

summary = {}

for name, rows in results.items():
    if not rows:
        continue

    actual = np.array([r[0] for r in rows])
    predicted = np.array([r[1] for r in rows])

    mae, rmse = metrics(actual, predicted)
    summary[name] = (mae, rmse)

    print(f"{name:<20} {mae:>10.3f} {rmse:>10.3f}")

print()

if "Random Forest" in summary and "XGBoost" in summary:
    rf_mae = summary["Random Forest"][0]
    xgb_mae = summary["XGBoost"][0]

    if xgb_mae < rf_mae:
        improvement = (rf_mae - xgb_mae) / rf_mae * 100
        print(
            f"XGBoost beats Random Forest MAE by "
            f"{improvement:.2f}%."
        )
    elif rf_mae < xgb_mae:
        improvement = (xgb_mae - rf_mae) / xgb_mae * 100
        print(
            f"Random Forest beats XGBoost MAE by "
            f"{improvement:.2f}%."
        )
    else:
        print("Random Forest and XGBoost have identical MAE.")

print()

predictions = pd.DataFrame(prediction_rows)

if not predictions.empty:
    rf_wins = (
        abs(predictions["Random Forest"] - predictions["actual"])
        <
        abs(predictions["XGBoost"] - predictions["actual"])
    ).sum()

    xgb_wins = (
        abs(predictions["XGBoost"] - predictions["actual"])
        <
        abs(predictions["Random Forest"] - predictions["actual"])
    ).sum()

    ties = len(predictions) - rf_wins - xgb_wins

    print("Head-to-head")
    print("------------")
    print(f"Random Forest wins: {rf_wins}")
    print(f"XGBoost wins:       {xgb_wins}")
    print(f"Ties:               {ties}")
