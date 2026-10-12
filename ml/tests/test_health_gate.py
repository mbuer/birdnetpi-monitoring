import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "ml" / "src"
sys.path.insert(0, str(SRC))

from health_gate import mask_unreliable_zero  # noqa: E402


class HealthGateTests(unittest.TestCase):
    def test_explicit_unreliable_zero_is_masked(self):
        frame = pd.DataFrame(
            {
                "activity_index": [0.0, 0.0],
                "health_state": ["incomplete", "unknown"],
            }
        )

        result = mask_unreliable_zero(
            frame,
            value_column="activity_index",
        )

        self.assertTrue(result["activity_index"].isna().all())

    def test_positive_observation_is_preserved(self):
        frame = pd.DataFrame(
            {
                "activity_index": [4.0],
                "health_state": ["incomplete"],
            }
        )

        result = mask_unreliable_zero(
            frame,
            value_column="activity_index",
        )

        self.assertEqual(result["activity_index"].iloc[0], 4.0)

    def test_legacy_hour_without_health_evidence_is_preserved(self):
        frame = pd.DataFrame(
            {
                "activity_index": [0.0],
                "health_state": [None],
            }
        )

        result = mask_unreliable_zero(
            frame,
            value_column="activity_index",
        )

        self.assertEqual(result["activity_index"].iloc[0], 0.0)

    def test_species_zero_masks_presence_and_detection_count(self):
        frame = pd.DataFrame(
            {
                "present": [0],
                "detection_count": [0],
                "health_state": ["unknown"],
            }
        )

        result = mask_unreliable_zero(
            frame,
            value_column="present",
            columns_to_mask=["present", "detection_count"],
        )

        self.assertTrue(pd.isna(result["present"].iloc[0]))
        self.assertTrue(pd.isna(result["detection_count"].iloc[0]))


if __name__ == "__main__":
    unittest.main()
