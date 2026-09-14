from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd


LOCAL_TZ = ZoneInfo("America/Los_Angeles")
GRACE_MINUTES = 10
MODEL_NAME = "random_forest_v2_completed"

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


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def latest_completed_hour(now: datetime | None = None) -> pd.Timestamp:
    if now is None:
        now = now_local()

    local_now = pd.Timestamp(now).tz_convert(LOCAL_TZ)

    eligible_time = local_now - pd.Timedelta(minutes=GRACE_MINUTES)

    current_hour = eligible_time.floor("h")

    completed_start = current_hour - pd.Timedelta(hours=1)

    return completed_start.tz_localize(None)


def prepare_hourly_frame(raw: pd.DataFrame) -> pd.DataFrame:
    data = raw.copy()

    data["hour_local"] = pd.to_datetime(data["hour_local"])

    if data["hour_local"].duplicated().any():
        duplicates = data.loc[
            data["hour_local"].duplicated(keep=False),
            "hour_local",
        ]
        raise RuntimeError(
            "Duplicate local hours detected; refusing prediction. "
            f"Duplicates: {duplicates.tolist()}"
        )

    data = data.set_index("hour_local").sort_index()

    full_index = pd.date_range(
        start=data.index.min(),
        end=data.index.max(),
        freq="h",
    )

    data = data.reindex(full_index)
    data.index.name = "hour_local"

    return data


def build_live_training_data(
    raw: pd.DataFrame,
    completed_hour: pd.Timestamp,
) -> pd.DataFrame:
    data = prepare_hourly_frame(raw)

    data = data.loc[data.index <= completed_hour].copy()

    data["activity_lag_1h"] = data["activity_index"].shift(1)
    data["activity_lag_2h"] = data["activity_index"].shift(2)
    data["activity_lag_3h"] = data["activity_index"].shift(3)
    data["activity_lag_24h"] = data["activity_index"].shift(24)

    # Live timing:
    #
    # At 14:10:
    #   latest completed bucket = 13:00-14:00
    #   14:00-15:00 is already underway
    #   forecast target         = 15:00-16:00
    #
    # Therefore historical training uses T -> T+2 hours.
    data["target_activity"] = data["activity_index"].shift(-2)

    training = data.dropna(
        subset=FEATURES + ["target_activity"]
    ).copy()

    return training


def build_prediction_row(
    raw: pd.DataFrame,
    completed_hour: pd.Timestamp,
) -> pd.DataFrame:
    data = prepare_hourly_frame(raw)

    if completed_hour not in data.index:
        raise RuntimeError(
            f"Latest completed hour {completed_hour} is missing."
        )

    recent_start = completed_hour - pd.Timedelta(hours=24)
    recent = data.loc[recent_start:completed_hour]

    expected_rows = 25

    if len(recent) != expected_rows:
        raise RuntimeError(
            "Recent hourly history is incomplete; refusing prediction."
        )

    if recent["activity_index"].isna().any():
        missing = recent.index[
            recent["activity_index"].isna()
        ].tolist()

        raise RuntimeError(
            "Recent hourly activity contains gaps; "
            f"refusing prediction. Missing: {missing}"
        )

    data["activity_lag_1h"] = data["activity_index"].shift(1)
    data["activity_lag_2h"] = data["activity_index"].shift(2)
    data["activity_lag_3h"] = data["activity_index"].shift(3)
    data["activity_lag_24h"] = data["activity_index"].shift(24)

    latest = data.loc[[completed_hour]].copy()

    if latest[FEATURES].isna().any().any():
        raise RuntimeError(
            "Latest completed hour does not contain all required features."
        )

    return latest
