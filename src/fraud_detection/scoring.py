from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .features import build_feature_vector


def load_model_artifact(path: str | Path) -> dict[str, Any]:
    artifact_path = Path(path)
    with artifact_path.open("r", encoding="utf-8") as handle:
        artifact = json.load(handle)
    artifact["feature_names"] = list(artifact["feature_names"])
    artifact["means"] = [float(v) for v in artifact["means"]]
    artifact["scales"] = [float(v) for v in artifact["scales"]]
    artifact["coefficients"] = [float(v) for v in artifact["coefficients"]]
    artifact["intercept"] = float(artifact["intercept"])
    artifact["threshold"] = float(artifact.get("threshold", 0.5))
    artifact["high_amount_threshold"] = float(artifact.get("high_amount_threshold", 200.0))
    return artifact


def save_model_artifact(artifact: Mapping[str, Any], path: str | Path) -> Path:
    artifact_path = Path(path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with artifact_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
    return artifact_path


def sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def standardize(values: Sequence[float], means: Sequence[float], scales: Sequence[float]) -> list[float]:
    result: list[float] = []
    for value, mean, scale in zip(values, means, scales):
        denom = scale if scale not in {0.0, -0.0} else 1.0
        result.append((float(value) - float(mean)) / float(denom))
    return result


def score_feature_vector(feature_vector: Sequence[float], artifact: Mapping[str, Any]) -> float:
    standardized = standardize(feature_vector, artifact["means"], artifact["scales"])
    linear = float(artifact["intercept"])
    for coef, val in zip(artifact["coefficients"], standardized):
        linear += float(coef) * float(val)
    return sigmoid(linear)


def predict_label(probability: float, threshold: float) -> int:
    return int(float(probability) >= float(threshold))


def score_transaction(transaction: Mapping[str, Any], artifact: Mapping[str, Any]) -> tuple[float, int]:
    feature_vector = build_feature_vector(
        transaction=transaction,
        feature_names=artifact["feature_names"],
        high_amount_threshold=float(artifact["high_amount_threshold"]),
    )
    probability = score_feature_vector(feature_vector, artifact)
    label = predict_label(probability, float(artifact["threshold"]))
    return probability, label
