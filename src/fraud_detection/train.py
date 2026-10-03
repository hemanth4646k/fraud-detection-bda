from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

from .config import get_settings
from .dataset import download_dataset, load_raw_dataset, save_streaming_seed, split_dataframe
from .schema import MODEL_FEATURES
from .scoring import save_model_artifact


def build_feature_frame(frame: pd.DataFrame, high_amount_threshold: float) -> pd.DataFrame:
    features = frame.copy()
    features["AmountLog"] = np.log1p(features["Amount"].clip(lower=0))
    features["HourOfDay"] = ((features["Time"] // 3600) % 24).astype(float)
    features["DayIndex"] = (features["Time"] // 86400).astype(float)
    features["IsNight"] = (features["HourOfDay"] <= 5).astype(float)
    features["IsHighAmount"] = (features["Amount"] >= high_amount_threshold).astype(float)
    return features[MODEL_FEATURES].astype(float)


def choose_threshold(labels: np.ndarray, probabilities: np.ndarray, beta: float) -> tuple[float, dict[str, float]]:
    precision, recall, thresholds = precision_recall_curve(labels, probabilities)
    if len(thresholds) == 0:
        return 0.5, {"precision": 0.0, "recall": 0.0, "fbeta": 0.0}
    aligned_precision = precision[:-1]
    aligned_recall = recall[:-1]
    beta_sq = beta * beta
    denominator = (beta_sq * aligned_precision) + aligned_recall
    fbeta_scores = np.where(
        denominator == 0.0, 0.0,
        (1 + beta_sq) * aligned_precision * aligned_recall / denominator,
    )
    best_index = int(np.nanargmax(fbeta_scores))
    return float(thresholds[best_index]), {
        "precision": float(aligned_precision[best_index]),
        "recall": float(aligned_recall[best_index]),
        "fbeta": float(fbeta_scores[best_index]),
    }


def evaluate_binary_classifier(labels: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict[str, float]:
    predictions = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    return {
        "threshold": float(threshold),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, probabilities)),
        "average_precision": float(average_precision_score(labels, probabilities)),
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
    }


def top_coefficients(model: LogisticRegression, feature_names: list[str], limit: int = 8) -> dict[str, list[dict[str, float]]]:
    coefficients = model.coef_[0]
    ordered = sorted(zip(feature_names, coefficients, strict=True), key=lambda item: abs(float(item[1])), reverse=True)
    positives = sorted(
        [{"feature": n, "coefficient": float(v)} for n, v in ordered if v > 0],
        key=lambda item: item["coefficient"], reverse=True,
    )[:limit]
    negatives = sorted(
        [{"feature": n, "coefficient": float(v)} for n, v in ordered if v < 0],
        key=lambda item: item["coefficient"],
    )[:limit]
    return {"positive": positives, "negative": negatives}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the fraud detection model.")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--beta", type=float, default=2.0)
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    settings.ensure_local_dirs()

    download_dataset(dataset_url=settings.dataset_url, output_path=settings.raw_data_path, force=args.force_download)
    raw_frame = load_raw_dataset(settings.raw_data_path)
    train_frame, validation_frame, test_frame = split_dataframe(raw_frame, random_state=args.random_state)

    high_amount_threshold = float(train_frame["Amount"].quantile(0.95))
    x_train = build_feature_frame(train_frame, high_amount_threshold)
    x_validation = build_feature_frame(validation_frame, high_amount_threshold)
    x_test = build_feature_frame(test_frame, high_amount_threshold)

    y_train = train_frame["Class"].to_numpy(dtype=int)
    y_validation = validation_frame["Class"].to_numpy(dtype=int)
    y_test = test_frame["Class"].to_numpy(dtype=int)

    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train)
    x_validation_scaled = scaler.transform(x_validation)
    x_test_scaled = scaler.transform(x_test)

    model = LogisticRegression(class_weight="balanced", max_iter=2_000, random_state=args.random_state)
    model.fit(x_train_scaled, y_train)

    validation_probabilities = model.predict_proba(x_validation_scaled)[:, 1]
    threshold, threshold_metrics = choose_threshold(labels=y_validation, probabilities=validation_probabilities, beta=args.beta)
    test_probabilities = model.predict_proba(x_test_scaled)[:, 1]

    validation_metrics = evaluate_binary_classifier(y_validation, validation_probabilities, threshold)
    test_metrics = evaluate_binary_classifier(y_test, test_probabilities, threshold)

    artifact = {
        "model_type": "weighted_logistic_regression",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_url": settings.dataset_url,
        "feature_names": MODEL_FEATURES,
        "means": scaler.mean_.tolist(),
        "scales": scaler.scale_.tolist(),
        "coefficients": model.coef_[0].tolist(),
        "intercept": float(model.intercept_[0]),
        "threshold": threshold,
        "high_amount_threshold": high_amount_threshold,
        "training_rows": int(len(train_frame)),
        "validation_rows": int(len(validation_frame)),
        "test_rows": int(len(test_frame)),
    }

    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_url": settings.dataset_url,
        "row_counts": {"train": int(len(train_frame)), "validation": int(len(validation_frame)), "test": int(len(test_frame))},
        "class_balance": {
            "train_fraud_rate": float(train_frame["Class"].mean()),
            "validation_fraud_rate": float(validation_frame["Class"].mean()),
            "test_fraud_rate": float(test_frame["Class"].mean()),
        },
        "threshold_selection": {"beta": args.beta, "selected_threshold": threshold, **threshold_metrics},
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "top_coefficients": top_coefficients(model, MODEL_FEATURES),
    }

    save_model_artifact(artifact, settings.model_artifact_path)
    with settings.metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2, sort_keys=True)
    save_streaming_seed(test_frame, settings.streaming_seed_path)

    print(f"Model artifact saved to: {settings.model_artifact_path}")
    print(f"Metrics saved to:        {settings.metrics_path}")
    print(f"Streaming seed saved to: {settings.streaming_seed_path}")
    print(f"Selected threshold: {threshold:.4f} | Validation recall={validation_metrics['recall']:.4f} | precision={validation_metrics['precision']:.4f}")
    print(f"Test metrics: recall={test_metrics['recall']:.4f}, precision={test_metrics['precision']:.4f}, roc_auc={test_metrics['roc_auc']:.4f}")


if __name__ == "__main__":
    main()
