import numpy as np

from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from data import load_hourly_data
from features import build_features


FEATURES = [
    "hour_of_day",
    "hours_from_sunrise",
    "is_day",
    "activity_index",
    "activity_lag_1h",
    "activity_lag_2h",
    "activity_lag_3h",
    "activity_lag_24h",
]


def score(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    return mae, rmse


raw = load_hourly_data()
df = build_features(raw)

# Expanding-window validation.
# Each test window is 48 hours.
test_size = 24

# Leave enough data for a meaningful initial training set.
initial_train_size = 192

models = {
    "Random Forest": RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        min_samples_leaf=3,
    ),
    "HistGradientBoosting": HistGradientBoostingRegressor(
        random_state=42,
    ),
}

results = []

fold = 1
train_end = initial_train_size

while train_end + test_size <= len(df):
    train = df.iloc[:train_end]
    test = df.iloc[train_end:train_end + test_size]

    X_train = train[FEATURES].copy()
    X_test = test[FEATURES].copy()

    X_train["is_day"] = X_train["is_day"].astype(int)
    X_test["is_day"] = X_test["is_day"].astype(int)

    y_train = train["target_activity_next_hour"]
    y_test = test["target_activity_next_hour"]

    # Persistence baseline
    persistence_pred = test["activity_index"]
    persistence_mae, persistence_rmse = score(
        y_test,
        persistence_pred,
    )

    results.append(
        (
            fold,
            "Persistence",
            persistence_mae,
            persistence_rmse,
        )
    )

    for name, model in models.items():
        model.fit(X_train, y_train)

        predictions = model.predict(X_test)
        predictions = np.clip(predictions, 0, None)

        mae, rmse = score(y_test, predictions)

        results.append(
            (
                fold,
                name,
                mae,
                rmse,
            )
        )

    print(
        f"Fold {fold}: "
        f"{test['hour_local'].min()} -> "
        f"{test['hour_local'].max()}"
    )

    fold += 1
    train_end += test_size


print()
print("Per-fold results")
print()
print(f"{'Fold':<6} {'Model':<22} {'MAE':>8} {'RMSE':>8}")
print("-" * 48)

for fold, name, mae, rmse in results:
    print(f"{fold:<6} {name:<22} {mae:>8.3f} {rmse:>8.3f}")


print()
print("Average across folds")
print()
print(f"{'Model':<22} {'MAE':>8} {'RMSE':>8}")
print("-" * 40)

names = sorted(set(row[1] for row in results))

for name in names:
    model_rows = [row for row in results if row[1] == name]

    avg_mae = np.mean([row[2] for row in model_rows])
    avg_rmse = np.mean([row[3] for row in model_rows])

    print(f"{name:<22} {avg_mae:>8.3f} {avg_rmse:>8.3f}")

