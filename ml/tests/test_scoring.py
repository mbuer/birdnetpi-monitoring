import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "ml" / "src"
sys.path.insert(0, str(SRC))

import score_predictions  # noqa: E402


class FakeCursor:
    def __init__(self):
        self.sql = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class AggregateScoringTests(unittest.TestCase):
    def test_live_model_labels_include_rf_and_xgboost(self):
        self.assertEqual(
            score_predictions.MODEL_NAMES,
            (
                "random_forest_v2_completed",
                "xgboost_v2_completed",
            ),
        )

    def test_scorer_targets_both_live_models_and_only_unscored_rows(self):
        conn = FakeConnection()

        with patch.object(
            score_predictions,
            "get_connection",
            return_value=conn,
        ):
            rows = score_predictions.score_predictions()

        self.assertEqual(rows, [])
        self.assertEqual(
            conn.cursor_instance.params,
            score_predictions.MODEL_NAMES,
        )

        sql = " ".join(conn.cursor_instance.sql.split())

        self.assertIn("p.model IN (%s, %s)", sql)
        self.assertIn("p.actual_activity IS NULL", sql)
        self.assertIn("p.predicted_hour = h.hour_local", sql)
        self.assertIn("p.prediction_created_at <", sql)
        self.assertIn("INTERVAL '1 hour 10 minutes'", sql)

        self.assertTrue(conn.committed)
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
