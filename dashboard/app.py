from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fraud_detection.config import get_settings
from fraud_detection.dashboard_data import load_dashboard_frames


st.set_page_config(
    page_title="Fraud Detection Command Center",
    layout="wide",
)


def format_ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.00%"
    return f"{(numerator / denominator) * 100:.2f}%"


def precision_recall_from_stream(predictions: pd.DataFrame) -> tuple[float | None, float | None]:
    if predictions.empty or {"actual_label", "predicted_label"} - set(predictions.columns):
        return None, None

    actual_positive = predictions["actual_label"].astype(int) == 1
    predicted_positive = predictions["predicted_label"].astype(int) == 1
    true_positive = int((actual_positive & predicted_positive).sum())
    predicted_positive_count = int(predicted_positive.sum())
    actual_positive_count = int(actual_positive.sum())

    precision = true_positive / predicted_positive_count if predicted_positive_count else None
    recall = true_positive / actual_positive_count if actual_positive_count else None
    return precision, recall


settings = get_settings()
predictions, alerts = load_dashboard_frames(settings)

st.title("Real-Time Fraud Detection Command Center")
st.caption("Kafka -> Spark Structured Streaming -> parquet + MinIO + optional Snowflake")

threshold = st.sidebar.slider(
    "Visible alert threshold",
    min_value=0.0,
    max_value=1.0,
    value=float(settings.min_alert_probability),
    step=0.05,
)
st.sidebar.caption("Use the browser refresh button after new micro-batches arrive.")

if predictions.empty:
    st.warning("No scored transactions found yet. Start the streaming job and the Kafka producer, then refresh.")
    st.stop()

predictions = predictions.sort_values("processed_at") if "processed_at" in predictions.columns else predictions
alerts_view = alerts.copy()
if not alerts_view.empty and "risk_score" in alerts_view.columns:
    alerts_view = alerts_view[alerts_view["risk_score"] >= threshold]

total_transactions = int(len(predictions))
predicted_fraud = int(predictions["predicted_label"].sum()) if "predicted_label" in predictions.columns else 0
actual_fraud = int(predictions["actual_label"].sum()) if "actual_label" in predictions.columns else 0
average_risk = float(predictions["risk_score"].mean()) if "risk_score" in predictions.columns else 0.0
precision, recall = precision_recall_from_stream(predictions)

metric_columns = st.columns(5)
metric_columns[0].metric("Transactions scored", f"{total_transactions:,}")
metric_columns[1].metric("Predicted fraud", f"{predicted_fraud:,}", format_ratio(predicted_fraud, total_transactions))
metric_columns[2].metric("Actual fraud in replay", f"{actual_fraud:,}", format_ratio(actual_fraud, total_transactions))
metric_columns[3].metric("Average risk score", f"{average_risk:.3f}")
metric_columns[4].metric(
    "Stream precision / recall",
    (
        f"{precision:.2%} / {recall:.2%}"
        if precision is not None and recall is not None
        else "Unavailable"
    ),
)

left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Risk Trend")
    if "processed_at" in predictions.columns and "risk_score" in predictions.columns:
        risk_timeline = (
            predictions.dropna(subset=["processed_at"])
            .set_index("processed_at")["risk_score"]
            .resample("1min")
            .mean()
            .dropna()
        )
        if not risk_timeline.empty:
            st.line_chart(risk_timeline)
        else:
            st.info("Not enough timestamped batches yet to draw a trend.")
    else:
        st.info("Timestamp columns are missing from the prediction sink.")

with right_col:
    st.subheader("Alerts by Merchant Category")
    if not alerts_view.empty and "merchant_category" in alerts_view.columns:
        category_counts = (
            alerts_view.groupby("merchant_category")
            .size()
            .sort_values(ascending=False)
            .head(10)
            .rename("alert_count")
        )
        st.bar_chart(category_counts)
    else:
        st.info("No alert rows match the current threshold yet.")

st.subheader("Recent High-Risk Transactions")
if alerts_view.empty:
    st.info("No alerts match the selected threshold yet.")
else:
    display_columns = [
        column
        for column in [
            "processed_at",
            "transaction_id",
            "merchant_category",
            "Amount",
            "risk_score",
            "alert_level",
            "predicted_label",
            "actual_label",
            "channel",
            "city",
            "country_code",
        ]
        if column in alerts_view.columns
    ]
    st.dataframe(
        alerts_view.sort_values("risk_score", ascending=False)[display_columns].head(25),
        use_container_width=True,
    )

