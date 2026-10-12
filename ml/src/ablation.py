import numpy as np

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from data import load_hourly_data
from features import build_features


FEATURE_SETS = {
    "Current activity only": [
        "activity_index",
    ],
    "Current + sunrise": [
        "activity_index",
        "hours_from_sunrise",
    ],
    "Recent lags only": [
        "activity_lag_1h",
        "activity_lag_2h",
        "activity_lag_3h",
        "activity_lag_24h",
    ],
    "Time only": [
        "hour_of_day",
        "hours_from_sunrise",
        "is_day",
    ],
    "Full feature set": [
        "hour_of_day",
        "hours_from_sunrise",
        "is_day",
        "activity_index",
        "activity_lag_1h",
        "activity_lag_2h",
        "activity_lag_3h",
        "activity_lag_24h",
    ],
}


def score(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    return mae, rmse


raw = load_hourly_data()
df = build_features(raw)

test_size = 24
initial_train_size = 192

results = []

for feature_name, features in FEATURE_SETS.items():
    fold_scores = []

    train_end = initial_train_size

    while train_end + test_size <= len(df):
        train = df.iloc[:train_end]
        test = df.iloc[train_end:train_end + test_size]

        X_train = train[features].copy()
        X_test = test[features].copy()

        if "is_day" in features:
            X_train["is_day"] = X_train["is_day"].astype(int)
            X_test["is_day"] = X_test["is_day"].astype(int)

        y_train = train["target_activity_next_hour"]
        y_test = test["target_activity_next_hour"]

        model = RandomForestRegressor(
            n_estimators=300,
            random_state=42,
            min_samples_leaf=3,
        )

        model.fit(X_train, y_train)

        predictions = model.predict(X_test)
        predictions = np.clip(predictions, 0, None)

        fold_scores.append(
            score(y_test, predictions)
        )

        train_end += test_size

    avg_mae = np.mean([x[0] for x in fold_scores])
    avg_rmse = np.mean([x[1] for x in fold_scores])

    results.append(
        (
            feature_name,
            avg_mae,
            avg_rmse,
        )
    )


print()
print("Random Forest feature ablation")
print()
print(f"{'Feature set':<25} {'MAE':>8} {'RMSE':>8}")
print("-" * 45)

for name, mae, rmse in sorted(results, key=lambda x: x[1]):
    print(f"{name:<25} {mae:>8.3f} {rmse:>8.3f}")
