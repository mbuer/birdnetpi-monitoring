import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from data import load_hourly_data
from features import build_features


FEATURES = [
    "hour_of_day",
    "hours_from_sunrise",
    "is_day",
    "temperature_f",
    "humidity_pct",
    "wind_mph",
    "cloud_pct",
    "precipitation_in",
    "activity_index",
    "activity_lag_1h",
    "activity_lag_2h",
    "activity_lag_3h",
    "activity_lag_24h",
]

def train_time_model(df):
    split_index = int(len(df) * 0.8)

    train = df.iloc[:split_index]
    test = df.iloc[split_index:]

    X_train = train[FEATURES].copy()
    X_test = test[FEATURES].copy()

    X_train["is_day"] = X_train["is_day"].astype(int)
    X_test["is_day"] = X_test["is_day"].astype(int)

    y_train = train["target_activity_next_hour"]
    y_test = test["target_activity_next_hour"]

    model = HistGradientBoostingRegressor(
        random_state=42
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    predictions = np.clip(predictions, 0, None)

    mae = mean_absolute_error(y_test, predictions)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))

    return train, test, mae, rmse


if __name__ == "__main__":
    raw = load_hourly_data()
    features = build_features(raw)

    train, test, mae, rmse = train_time_model(features)

    print("Time + weather + recent activity HistGradientBoosting")
    print()
    print(f"Training rows: {len(train)}")
    print(f"Test rows:     {len(test)}")
    print()
    print(f"MAE:  {mae:.3f}")
    print(f"RMSE: {rmse:.3f}")
    print()
    print("Persistence baseline")
    print("MAE:  4.234")
    print("RMSE: 7.272")
