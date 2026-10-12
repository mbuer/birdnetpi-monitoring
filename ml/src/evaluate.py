import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error

from data import load_hourly_data
from features import build_features


def evaluate_persistence(df):
    split_index = int(len(df) * 0.8)

    train = df.iloc[:split_index]
    test = df.iloc[split_index:]

    # Baseline:
    # predict that next hour's activity will equal current activity.
    y_true = test["target_activity_next_hour"]
    y_pred = test["activity_index"]

    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

    return train, test, mae, rmse


if __name__ == "__main__":
    raw = load_hourly_data()
    features = build_features(raw)

    train, test, mae, rmse = evaluate_persistence(features)

    print(f"Training rows: {len(train)}")
    print(f"Test rows:     {len(test)}")
    print()
    print(f"Training period: {train['hour_local'].min()} -> {train['hour_local'].max()}")
    print(f"Test period:     {test['hour_local'].min()} -> {test['hour_local'].max()}")
    print()
    print("Persistence baseline")
    print(f"MAE:  {mae:.3f}")
    print(f"RMSE: {rmse:.3f}")
