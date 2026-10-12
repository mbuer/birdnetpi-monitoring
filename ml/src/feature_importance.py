import pandas as pd

from sklearn.ensemble import RandomForestRegressor

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


raw = load_hourly_data()
df = build_features(raw)

split_index = int(len(df) * 0.8)

train = df.iloc[:split_index]

X_train = train[FEATURES].copy()
X_train["is_day"] = X_train["is_day"].astype(int)

y_train = train["target_activity_next_hour"]

model = RandomForestRegressor(
    n_estimators=300,
    random_state=42,
    min_samples_leaf=3,
)

model.fit(X_train, y_train)

importance = pd.DataFrame(
    {
        "feature": FEATURES,
        "importance": model.feature_importances_,
    }
).sort_values(
    "importance",
    ascending=False,
)

print()
print("Random Forest feature importance")
print()
print(importance.to_string(index=False))
