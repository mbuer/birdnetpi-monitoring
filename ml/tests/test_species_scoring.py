import unittest
from unittest.mock import patch

from ml.src import score_species_predictions


class FakeCursor:
    def __init__(self):
        self.query = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params):
        self.query = query
        self.params = params

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class SpeciesScoringTests(unittest.TestCase):
    def test_challenger_suffix_and_forward_scoring_guards(self):
        conn = FakeConnection()

        with patch.object(
            score_species_predictions,
            "connect",
            return_value=conn,
        ):
            rows = (
                score_species_predictions
                .score_species_predictions()
            )

        self.assertEqual(rows, [])
        self.assertEqual(
            conn.cursor_obj.params,
            (
                score_species_predictions.MODEL_SUFFIX,
                score_species_predictions.MODEL_SUFFIX,
            ),
        )

        query = conn.cursor_obj.query
        self.assertIn(
            "RIGHT(p.model, LENGTH(%s)) = %s",
            query,
        )
        self.assertIn(
            "p.actual_present IS NULL",
            query,
        )
        self.assertIn(
            "s.hour_local = p.predicted_hour",
            query,
        )
        self.assertIn(
            "p.prediction_created_at <",
            query,
        )
        self.assertIn(
            "interval '1 hour 10 minutes'",
            query,
        )
        self.assertTrue(conn.committed)
        self.assertTrue(conn.closed)

    def test_suffix_covers_baselines_and_challengers(self):
        labels = (
            "random_forest_species_v1",
            "xgboost_species_v1",
            "xgboost_tuned_species_v1",
            "xgboost_bootstrap_species_v1",
        )

        for label in labels:
            with self.subTest(label=label):
                self.assertTrue(
                    label.endswith(
                        score_species_predictions.MODEL_SUFFIX
                    )
                )


if __name__ == "__main__":
    unittest.main()
