import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "ml" / "src"
sys.path.insert(0, str(SRC))

from timing import (  # noqa: E402
    LOCAL_TZ,
    build_live_training_data,
    build_prediction_row,
    latest_completed_hour,
    prepare_hourly_frame,
)


class TimingTests(unittest.TestCase):
    def test_latest_completed_hour_after_grace_period(self):
        now = datetime(
            2026,
            9,
            14,
            14,
            10,
            tzinfo=LOCAL_TZ,
        )

        self.assertEqual(
            latest_completed_hour(now),
            pd.Timestamp("2026-09-14 13:00:00"),
        )

    def test_latest_completed_hour_before_grace_period(self):
        now = datetime(
            2026,
            9,
            14,
            14,
            9,
            tzinfo=LOCAL_TZ,
        )

        self.assertEqual(
            latest_completed_hour(now),
            pd.Timestamp("2026-09-14 12:00:00"),
        )

    def test_timezone_conversion_uses_los_angeles_time(self):
        now_utc = datetime(
            2026,
            9,
            14,
            21,
            10,
            tzinfo=ZoneInfo("UTC"),
        )

        self.assertEqual(
            latest_completed_hour(now_utc),
            pd.Timestamp("2026-09-14 13:00:00"),
        )


class FrameValidationTests(unittest.TestCase):
    def test_duplicate_local_hours_are_rejected(self):
        raw = pd.DataFrame(
            {
                "hour_local": [
                    pd.Timestamp("2026-11-01 01:00:00"),
                    pd.Timestamp("2026-11-01 01:00:00"),
                ],
                "activity_index": [1.0, 2.0],
            }
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "Duplicate local hours detected",
        ):
            prepare_hourly_frame(raw)

    def test_missing_recent_hour_is_rejected(self):
        end = pd.Timestamp("2026-09-14 13:00:00")
        hours = pd.date_range(
            end=end,
            periods=25,
            freq="h",
        )

        raw = _activity_frame(hours)
        raw = raw.loc[
            raw["hour_local"] != pd.Timestamp("2026-09-14 05:00:00")
        ].copy()

        with self.assertRaisesRegex(
            RuntimeError,
            "Recent hourly activity contains gaps",
        ):
            build_prediction_row(raw, end)


class LeakageTests(unittest.TestCase):
    def test_training_target_uses_two_hour_horizon(self):
        hours = pd.date_range(
            start="2026-09-01 00:00:00",
            periods=40,
            freq="h",
        )
        raw = _activity_frame(hours)
        completed = hours[-1]

        training = build_live_training_data(raw, completed)

        # T -> T+2 means the last trainable feature row is two hours
        # before the latest completed input hour. The completed hour itself
        # must never have a historical target available at issue time.
        self.assertEqual(
            training.index.max(),
            completed - pd.Timedelta(hours=2),
        )

        last_row = training.loc[training.index.max()]
        expected_target = raw.loc[
            raw["hour_local"] == completed,
            "activity_index",
        ].iloc[0]

        self.assertEqual(
            last_row["target_activity"],
            expected_target,
        )

    def test_prediction_row_uses_completed_hour_and_true_hourly_lags(self):
        hours = pd.date_range(
            start="2026-09-01 00:00:00",
            periods=30,
            freq="h",
        )
        raw = _activity_frame(hours)
        completed = hours[-1]

        prediction = build_prediction_row(raw, completed)
        row = prediction.iloc[0]

        self.assertEqual(prediction.index[0], completed)
        self.assertEqual(row["activity_lag_1h"], raw.iloc[-2]["activity_index"])
        self.assertEqual(row["activity_lag_2h"], raw.iloc[-3]["activity_index"])
        self.assertEqual(row["activity_lag_3h"], raw.iloc[-4]["activity_index"])
        self.assertEqual(row["activity_lag_24h"], raw.iloc[-25]["activity_index"])


def _activity_frame(hours):
    values = list(range(1, len(hours) + 1))

    return pd.DataFrame(
        {
            "hour_local": hours,
            "hour_of_day": hours.hour,
            "hours_from_sunrise": [float(i) for i in range(len(hours))],
            "is_day": [1] * len(hours),
            "activity_index": [float(v) for v in values],
        }
    )


if __name__ == "__main__":
    unittest.main()
