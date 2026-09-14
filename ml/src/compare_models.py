import numpy as np

from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

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


def evaluate_model(name, model, X_train, X_test, y_train, y_test):
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    predictions = np.clip(predictions, 0, None)

    mae = mean_absolute_error(y_test, predictions)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))

    return name, mae, rmse


raw = load_hourly_data()
df = build_features(raw)

split_index = int(len(df) * 0.8)

train = df.iloc[:split_index]
test = df.iloc[split_index:]

X_train = train[FEATURES].copy()
X_test = test[FEATURES].copy()

X_train["is_day"] = X_train["is_day"].astype(int)
X_test["is_day"] = X_test["is_day"].astype(int)

y_train = train["target_activity_next_hour"]
y_test = test["target_activity_next_hour"]

models = [
    (
        "Poisson Regression",
        make_pipeline(
            StandardScaler(),
            PoissonRegressor(alpha=1.0, max_iter=1000),
        ),
    ),
    (
        "Random Forest",
        RandomForestRegressor(
            n_estimators=300,
            random_state=42,
            min_samples_leaf=3,
        ),
    ),
    (
        "HistGradientBoosting",
        HistGradientBoostingRegressor(
            random_state=42,
        ),
    ),
]

results = []

for name, model in models:
    results.append(
        evaluate_model(
            name,
            model,
            X_train,
            X_test,
            y_train,
            y_test,
        )
    )

print()
print("Model comparison")
print()
print(f"{'Model':<24} {'MAE':>8} {'RMSE':>8}")
print("-" * 42)

for name, mae, rmse in sorted(results, key=lambda x: x[1]):
    print(f"{name:<24} {mae:>8.3f} {rmse:>8.3f}")

print()
print("Persistence baseline")
print("MAE:  4.234")
print("RMSE: 7.272")
