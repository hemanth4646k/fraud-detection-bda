from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .schema import ANON_FEATURES


def _to_float(value: Any, default: float = 0.0) -> float:
    if value in {None, ""}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_model_features(
    transaction: Mapping[str, Any],
    high_amount_threshold: float,
) -> dict[str, float]:
    time_value = max(_to_float(transaction.get("Time")), 0.0)
    amount = max(_to_float(transaction.get("Amount")), 0.0)
    hour_of_day = float(int(time_value // 3600) % 24)
    day_index = float(int(time_value // 86400))

    features = {feature: _to_float(transaction.get(feature)) for feature in ANON_FEATURES}
    features.update(
        {
            "Time": time_value,
            "Amount": amount,
            "AmountLog": math.log1p(amount),
            "HourOfDay": hour_of_day,
            "DayIndex": day_index,
            "IsNight": 1.0 if hour_of_day <= 5 else 0.0,
            "IsHighAmount": 1.0 if amount >= high_amount_threshold else 0.0,
        }
    )
    return features


def build_feature_vector(
    transaction: Mapping[str, Any],
    feature_names: Sequence[str],
    high_amount_threshold: float,
) -> list[float]:
    feature_map = build_model_features(transaction=transaction, high_amount_threshold=high_amount_threshold)
    return [float(feature_map[name]) for name in feature_names]
