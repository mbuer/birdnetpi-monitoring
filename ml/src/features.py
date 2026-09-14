import pandas as pd


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    # Recent BirdNET activity available at prediction time.
    data["activity_lag_1h"] = data["activity_index"].shift(1)
    data["activity_lag_2h"] = data["activity_index"].shift(2)
    data["activity_lag_3h"] = data["activity_index"].shift(3)
    data["activity_lag_24h"] = data["activity_index"].shift(24)

    # Prediction target:
    # activity during the following hour.
    data["target_activity_next_hour"] = data["activity_index"].shift(-1)

    # Rows at the beginning have incomplete lag history.
    # The final row has no known next-hour target.
    data = data.dropna(
        subset=[
            "activity_lag_1h",
            "activity_lag_2h",
            "activity_lag_3h",
            "activity_lag_24h",
            "target_activity_next_hour",
        ]
    ).copy()

    return data


if __name__ == "__main__":
    from data import load_hourly_data

    raw = load_hourly_data()
    features = build_features(raw)

    columns = [
        "hour_local",
        "activity_index",
        "activity_lag_1h",
        "activity_lag_2h",
        "activity_lag_3h",
        "activity_lag_24h",
        "target_activity_next_hour",
    ]

    print(features[columns].head(10).to_string(index=False))
    print()
    print(f"Raw rows:      {len(raw)}")
    print(f"Training rows: {len(features)}")
