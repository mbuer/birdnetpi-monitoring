import sys
from pathlib import Path
import contextlib
import io
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from residual_model import available_training, baseline_values, build_dataset, fit_fold
import residual_model


def hourly_data(hours=300):
    index = pd.date_range("2026-09-01", periods=hours, freq="h")
    activity = (index.hour.to_numpy() * 2 + np.arange(hours) % 7).astype(float)
    return pd.DataFrame({
        "hour_local": index, "activity_index": activity,
        "hour_of_day": index.hour, "hours_from_sunrise": index.hour - 6.5,
        "is_day": ((index.hour >= 7) & (index.hour < 19)).astype(int),
        "temperature_f": 65.0, "humidity_pct": 50.0,
        "wind_mph": 2.0, "cloud_pct": 10.0, "precipitation_in": 0.0,
        "health_state": "healthy",
    })


class ResidualModelTests(unittest.TestCase):
    def test_cli_smoke_writes_matched_forecasts_and_complete_report(self):
        raw = hourly_data()
        loader = types.ModuleType("data")
        loader.load_hourly_data = lambda: raw
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "forecasts.csv"
            command = ["residual_model.py", "--cutoff", str(raw["hour_local"].max()),
                       "--trees", "8", "--max-forecasts", "3", "--output", str(output)]
            report = io.StringIO()
            with patch.dict(sys.modules, {"data": loader}), patch.object(sys, "argv", command), \
                    patch.object(residual_model, "version", return_value="synthetic-test"), \
                    contextlib.redirect_stdout(report):
                residual_model.main()
            rows = pd.read_csv(output)
            self.assertEqual(len(rows), 3)
            self.assertTrue(np.isfinite(rows[residual_model.MODELS].to_numpy()).all())
            self.assertTrue((pd.to_datetime(rows["latest_training_target"]) <=
                             pd.to_datetime(rows["feature_hour"])).all())
            self.assertIn("NO PRODUCTION CHANGE", report.getvalue())
            self.assertIn("NONSTANDARD / SMOKE RUN", report.getvalue())

    def test_unavailable_labels_and_future_features_cannot_change_forecast(self):
        raw = hourly_data()
        cutoff = raw["hour_local"].max()
        frame = build_dataset(raw, cutoff)
        hour = raw["hour_local"].iloc[250]
        train = available_training(frame, hour)
        before, _, _ = fit_fold(train, frame.loc[[hour]], trees=8)
        changed = raw.copy()
        # Change all activity and weather after the latest completed input.
        changed.loc[changed["hour_local"] > hour, [
            "activity_index", "temperature_f", "humidity_pct",
            "wind_mph", "cloud_pct", "precipitation_in",
        ]] = 10000.0
        later = build_dataset(changed, cutoff)
        later_train = available_training(later, hour)
        pd.testing.assert_frame_equal(train, later_train)
        after, _, _ = fit_fold(later_train, later.loc[[hour]], trees=8)
        self.assertEqual(before, after)
        self.assertLessEqual(train["target_hour"].max(), hour)

    def test_each_training_baseline_excludes_its_own_outcome(self):
        frame = pd.DataFrame({
            "target_activity": [1., 3., 5., 7., 9.],
            "hour_of_day": [8] * 5, "solar_bin": [1] * 5,
        })
        before = baseline_values(frame, frame, leave_one_out=True)
        changed = frame.copy()
        changed.loc[0, "target_activity"] = 10001.0
        after = baseline_values(changed, changed, leave_one_out=True)
        self.assertEqual(before[0], after[0])
        self.assertEqual(before[0], 6.0)

    def test_leave_one_out_fallback_counts_and_global_mean(self):
        frame = pd.DataFrame({
            "target_activity": [2., 4., 6., 8., 20.],
            "hour_of_day": [8, 8, 8, 8, 9],
            "solar_bin": [0, 0, 1, 1, 2],
        })
        result = baseline_values(frame, frame, leave_one_out=True)
        # Small solar bins fall back to clock-hour; lone hour uses global LOO.
        self.assertEqual(result[0], 6.0)
        self.assertEqual(result[4], 5.0)
        query = pd.DataFrame({"hour_of_day": [8, 10], "solar_bin": [99, 99]})
        np.testing.assert_allclose(baseline_values(frame, query), [5., 8.])

    def test_missing_hour_does_not_compress_lags_or_targets(self):
        raw = hourly_data(100)
        missing = raw["hour_local"].iloc[50]
        frame = build_dataset(raw.drop(index=50), raw["hour_local"].max())
        self.assertNotIn(missing - pd.Timedelta(hours=2), frame.index)
        self.assertNotIn(missing + pd.Timedelta(hours=1), frame.index)
        self.assertFalse(frame.loc[missing + pd.Timedelta(hours=4), "recent_complete"])
        self.assertTrue(frame.loc[missing + pd.Timedelta(hours=25), "recent_complete"])

    def test_health_gate_preserves_positive_and_masks_unreliable_zero(self):
        raw = hourly_data(100)
        bad = raw["hour_local"].iloc[50]
        raw.loc[50, ["activity_index", "health_state"]] = [0.0, "unknown"]
        raw.loc[60, ["activity_index", "health_state"]] = [5.0, "incomplete"]
        frame = build_dataset(raw, raw["hour_local"].max())
        self.assertNotIn(bad, frame.index)
        self.assertNotIn(bad - pd.Timedelta(hours=2), frame.index)
        self.assertIn(raw["hour_local"].iloc[60], frame.index)

    def test_cutoff_and_target_day_alignment(self):
        raw = hourly_data(100)
        cutoff = raw["hour_local"].iloc[80]
        frame = build_dataset(raw, cutoff)
        self.assertLessEqual(frame["target_hour"].max(), cutoff)
        feature_hour = raw["hour_local"].iloc[42]  # 18:00 -> 20:00
        self.assertEqual(frame.loc[feature_hour, "is_day"], 1)
        self.assertEqual(frame.loc[feature_hour, "target_is_day"], 0)

    def test_duplicate_hour_rejected_and_weather_matching(self):
        raw = hourly_data(100)
        with self.assertRaises(RuntimeError):
            build_dataset(pd.concat([raw, raw.iloc[[50]]]), raw["hour_local"].max())
        raw.loc[50, "temperature_f"] = np.nan
        frame = build_dataset(raw, raw["hour_local"].max())
        self.assertNotIn(raw["hour_local"].iloc[50], frame.index)


if __name__ == "__main__":
    unittest.main()
