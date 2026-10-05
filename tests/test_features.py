from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fraud_detection.features import build_feature_vector, build_model_features
from fraud_detection.schema import MODEL_FEATURES


class FeatureEngineeringTests(unittest.TestCase):
    def test_build_model_features_derives_realtime_fields(self) -> None:
        features = build_model_features(
            {"Time": 90_000, "Amount": 250.0, "V1": -1.25, "V2": 2.5},
            high_amount_threshold=200.0,
        )
        self.assertEqual(features["DayIndex"], 1.0)
        self.assertEqual(features["HourOfDay"], 1.0)
        self.assertEqual(features["IsNight"], 1.0)
        self.assertEqual(features["IsHighAmount"], 1.0)
        self.assertAlmostEqual(features["AmountLog"], 5.5254529391, places=6)
        self.assertEqual(features["V1"], -1.25)
        self.assertEqual(features["V28"], 0.0)

    def test_build_feature_vector_respects_feature_order(self) -> None:
        record = {"Time": 3_600, "Amount": 50.0, "V1": 1.0}
        vector = build_feature_vector(record, MODEL_FEATURES[:6], high_amount_threshold=200.0)
        self.assertEqual(vector[0], 1.0)
        self.assertEqual(len(vector), 6)


if __name__ == "__main__":
    unittest.main()
