from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fraud_detection.scoring import predict_label, score_transaction, standardize


class ScoringTests(unittest.TestCase):
    def test_standardize_handles_zero_scale(self) -> None:
        result = standardize([10.0, 20.0], [5.0, 20.0], [5.0, 0.0])
        self.assertEqual(result, [1.0, 0.0])

    def test_score_transaction_returns_probability_and_label(self) -> None:
        artifact = {
            "feature_names": ["V1", "Time", "Amount", "AmountLog", "HourOfDay", "DayIndex", "IsNight", "IsHighAmount"],
            "means": [0.0] * 8,
            "scales": [1.0] * 8,
            "coefficients": [2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "intercept": 0.0,
            "threshold": 0.5,
            "high_amount_threshold": 200.0,
        }
        probability, label = score_transaction(
            transaction={"V1": 1.0, "Time": 3_600, "Amount": 250.0},
            artifact=artifact,
        )
        self.assertGreater(probability, 0.5)
        self.assertEqual(label, 1)
        self.assertEqual(predict_label(probability, 0.99), 0)


if __name__ == "__main__":
    unittest.main()
